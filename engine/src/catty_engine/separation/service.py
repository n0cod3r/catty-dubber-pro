from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from catty_engine.logging import logged_process
from catty_engine.media.audio import AudioAsset, AudioAssetKind
from catty_engine.media.fingerprint import source_fingerprint
from catty_engine.models.manager import (
    SEPARATION_MODEL_ID,
    ModelManager,
)

from .errors import SeparationModelMissing
from .mdx import BACKGROUND_FILE_NAME, CHANNELS, SAMPLE_RATE, MdxBackgroundExtractor

BACKGROUND_METADATA_FILE_NAME = "background.json"


class BackgroundExtractor(Protocol):
    def extract_background(self, source: Path, destination: Path) -> None: ...


class AudioSeparationService:
    def __init__(self, runner: BackgroundExtractor | None = None) -> None:
        self._runner = runner
        self._runners: dict[str, BackgroundExtractor] = {}

    @logged_process
    def prepare_background_audio(
        self,
        *,
        project_directory: Path,
        episode_id: UUID,
        source: str | Path,
        model_id: str = SEPARATION_MODEL_ID,
        existing_asset: AudioAsset | None = None,
    ) -> AudioAsset:
        # Like prepared speech audio, background stems are content-addressed and
        # shared across episode IDs; keep the argument for a uniform contract.
        del episode_id

        source_path = Path(source).expanduser().resolve()
        fingerprint = source_fingerprint(source_path)

        destination = (
            project_directory
            / "assets"
            / "media"
            / fingerprint
            / "separation"
            / model_id
            / BACKGROUND_FILE_NAME
        ).resolve()

        if self._cache_valid(
            existing_asset=existing_asset,
            destination=destination,
            fingerprint=fingerprint,
        ):
            assert existing_asset is not None
            return existing_asset

        # The frontend may not have restored its AudioAsset after a restart, so
        # the sidecar manifest keeps the exact persisted asset (including
        # created_at) for an already separated file.
        cached_asset = self._load_cached_asset(destination, fingerprint)
        if cached_asset is not None:
            return cached_asset

        # Cache entries written before the sidecar existed are reconstructed
        # once and then get a manifest for the next run.
        if self._prepared_file_valid(destination):
            asset = self._asset(destination, fingerprint)
            self._save_cached_asset(asset)
            return asset

        self._extractor(model_id).extract_background(source_path, destination)

        asset = self._asset(destination, fingerprint)
        self._save_cached_asset(asset)
        return asset

    def _extractor(self, model_id: str) -> BackgroundExtractor:
        if self._runner is not None:
            return self._runner
        if model_id not in self._runners:
            manager = ModelManager()
            spec = manager.spec(model_id)
            if not manager.installed(model_id) or not spec.file_name:
                raise SeparationModelMissing(
                    "The separation model is not installed. Install it in Settings first."
                )
            self._runners[model_id] = MdxBackgroundExtractor(
                manager.path_for(model_id) / spec.file_name
            )
        return self._runners[model_id]

    @staticmethod
    def _asset(destination: Path, fingerprint: str) -> AudioAsset:
        return AudioAsset(
            path=str(destination),
            kind=AudioAssetKind.BACKGROUND,
            sample_rate=SAMPLE_RATE,
            channels=CHANNELS,
            source_fingerprint=fingerprint,
        )

    @staticmethod
    def _metadata_path(destination: Path) -> Path:
        return destination.with_name(BACKGROUND_METADATA_FILE_NAME)

    @classmethod
    def _save_cached_asset(cls, asset: AudioAsset) -> None:
        destination = Path(asset.path).expanduser().resolve()
        metadata = cls._metadata_path(destination)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        temporary = metadata.with_suffix(metadata.suffix + ".tmp")
        temporary.write_text(
            json.dumps(asset.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(metadata)

    @classmethod
    def _load_cached_asset(
        cls,
        destination: Path,
        fingerprint: str,
    ) -> AudioAsset | None:
        if not cls._prepared_file_valid(destination):
            return None

        metadata = cls._metadata_path(destination)
        if not metadata.is_file():
            return None

        try:
            asset = AudioAsset.model_validate_json(metadata.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError):
            return None

        if cls._cache_valid(
            existing_asset=asset,
            destination=destination,
            fingerprint=fingerprint,
        ):
            return asset
        return None

    @staticmethod
    def _prepared_file_valid(destination: Path) -> bool:
        return destination.is_file() and destination.stat().st_size > 0

    @classmethod
    def _cache_valid(
        cls,
        *,
        existing_asset: AudioAsset | None,
        destination: Path,
        fingerprint: str,
    ) -> bool:
        if existing_asset is None:
            return False

        if existing_asset.kind != AudioAssetKind.BACKGROUND:
            return False

        if existing_asset.source_fingerprint != fingerprint:
            return False

        if existing_asset.sample_rate != SAMPLE_RATE:
            return False

        if existing_asset.channels != CHANNELS:
            return False

        asset_path = Path(existing_asset.path).expanduser().resolve()
        if asset_path != destination:
            return False

        return cls._prepared_file_valid(destination)
