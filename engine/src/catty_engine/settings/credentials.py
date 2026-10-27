"""Provider credentials kept out of settings.json and project.json."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .paths import app_data_dir

SERVICE_NAME = "Catty Dubber Pro"


class CredentialStore:
    """Small OS-keychain-first store with a private-file fallback.

    The store never returns secrets to the renderer on its own. IPC code must only
    expose ``has()`` (``credential_configured``) and use ``get()`` server-side.
    """

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or app_data_dir()
        self._fallback = self._directory / "credentials.json"

    def get(self, provider: str) -> str | None:
        self._validate(provider)
        backend = self._keyring()
        if backend is not None:
            try:
                value = backend.get_password(SERVICE_NAME, provider)
                if value:
                    return value
            except Exception:
                pass
        return self._read_fallback().get(provider)

    def set(self, provider: str, secret: str) -> None:
        self._validate(provider)
        secret = secret.strip()
        if not secret:
            self.delete(provider)
            return
        backend = self._keyring()
        if backend is not None:
            try:
                backend.set_password(SERVICE_NAME, provider, secret)
                return
            except Exception:
                pass
        values = self._read_fallback()
        values[provider] = secret
        self._write_fallback(values)

    def delete(self, provider: str) -> None:
        self._validate(provider)
        backend = self._keyring()
        if backend is not None:
            try:
                backend.delete_password(SERVICE_NAME, provider)
            except Exception:
                pass
        values = self._read_fallback()
        if provider in values:
            values.pop(provider, None)
            self._write_fallback(values)

    def has(self, provider: str) -> bool:
        return bool(self.get(provider))

    @staticmethod
    def _validate(provider: str) -> None:
        if not provider or not provider.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Invalid credential provider id")

    @staticmethod
    def _keyring():
        try:
            import keyring

            backend = keyring.get_keyring()
            name = f"{type(backend).__module__}.{type(backend).__name__}".lower()
            if ".fail." in name or ".null." in name:
                return None
            return keyring
        except Exception:
            return None

    def _read_fallback(self) -> dict[str, str]:
        try:
            payload = json.loads(self._fallback.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            key: value
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def _write_fallback(self, values: dict[str, str]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        temporary = self._directory / ".credentials.json.tmp"
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(values, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self._fallback)
        os.chmod(self._fallback, 0o600)
