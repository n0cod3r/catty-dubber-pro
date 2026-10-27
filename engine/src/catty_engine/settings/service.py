"""Atomic application-settings persistence, separate from project state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import AppSettings
from .paths import app_data_dir

CURRENT_SCHEMA_VERSION = 1


class SettingsError(RuntimeError):
    """Actionable application-settings failure."""


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


class SettingsService:
    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or app_data_dir()
        self._file = self._directory / "settings.json"

    @property
    def path(self) -> Path:
        return self._file

    def get(self) -> AppSettings:
        if not self._file.exists():
            settings = AppSettings()
            self._save(settings)
            return settings
        try:
            payload = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SettingsError(
                f"Application settings are unreadable: {self._file}"
            ) from exc
        if not isinstance(payload, dict):
            raise SettingsError("Application settings must be a JSON object")
        version = payload.get("schema_version", CURRENT_SCHEMA_VERSION)
        if version != CURRENT_SCHEMA_VERSION:
            raise SettingsError(
                f"Unsupported settings schema version: {version}"
            )
        try:
            return AppSettings.model_validate(payload)
        except ValidationError as exc:
            raise SettingsError(
                "Application settings contain invalid values. Fix or remove the file."
            ) from exc

    def update(self, patch: dict[str, Any]) -> AppSettings:
        if not isinstance(patch, dict):
            raise SettingsError("Settings update must be a JSON object")
        requested_version = patch.get("schema_version")
        if (
            requested_version is not None
            and requested_version != CURRENT_SCHEMA_VERSION
        ):
            raise SettingsError(
                f"Unsupported settings schema version: {requested_version}"
            )
        current = self.get().model_dump(mode="json")
        try:
            updated = AppSettings.model_validate(_deep_merge(current, patch))
        except ValidationError as exc:
            raise SettingsError("Invalid settings values") from exc
        self._save(updated)
        return updated

    def _save(self, settings: AppSettings) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        payload = settings.model_dump_json(indent=2)
        temporary = self._directory / ".settings.json.tmp"
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self._file)
        try:
            directory_fd = os.open(self._directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
