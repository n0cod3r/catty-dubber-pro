from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from .audio import AudioAsset, AudioAssetKind
from .ffmpeg import FFmpegRunner
from .fingerprint import source_fingerprint


SPEECH_SAMPLE_RATE = 16_000
SPEECH_CHANNELS = 1
SPEECH_FILE_NAME = "speech-16k-mono.wav"
SPEECH_METADATA_FILE_NAME = "speech-16k-mono.json"


class AudioExtractor(Protocol):
    def extract_speech_audio(
        self,
        source: Path,
        destination: Path,
        *,
        sample_rate: int = SPEECH_SAMPLE_RATE,
        channels: int = SPEECH_CHANNELS,
    ) -> None: ...


class AudioPreparationService:
    def __init__(
        self,
        runner: AudioExtractor | None = None,
    ) -> None:
        self._runner: AudioExtractor = runner or FFmpegRunner()

    def prepare_speech_audio(
        self,
        *,
        project_directory: Path,
        episode_id: UUID,
        source: str | Path,
        existing_asset: AudioAsset | None = None,
    ) -> AudioAsset:
        # episode_id intentionally remains part of the public contract even though
        # prepared source audio is content-addressed and shared across episode IDs.
        del episode_id

        source_path = Path(source).expanduser().resolve()
        fingerprint = source_fingerprint(source_path)

        destination = (
            project_directory
            / "assets"
            / "media"
            / fingerprint
            / "audio"
            / SPEECH_FILE_NAME
        ).resolve()

        if self._cache_valid(
            existing_asset=existing_asset,
            destination=destination,
            fingerprint=fingerprint,
        ):
            assert existing_asset is not None
            return existing_asset

        # On restart the frontend may not have restored its AudioAsset yet. Keep a
        # tiny sidecar manifest next to the WAV so we can reconstruct the exact
        # persisted asset (including created_at) instead of manufacturing a new
        # logical asset for an already prepared file.
        cached_asset = self._load_cached_asset(destination, fingerprint)
        if cached_asset is not None:
            return cached_asset

        # Backward compatibility for cache entries created before the metadata
        # sidecar existed. Reconstruct once and persist the manifest for next time.
        if self._prepared_file_valid(destination):
            asset = self._asset(destination, fingerprint)
            self._save_cached_asset(asset)
            return asset

        self._runner.extract_speech_audio(
            source_path,
            destination,
            sample_rate=SPEECH_SAMPLE_RATE,
            channels=SPEECH_CHANNELS,
        )

        asset = self._asset(destination, fingerprint)
        self._save_cached_asset(asset)
        return asset

    @staticmethod
    def _asset(destination: Path, fingerprint: str) -> AudioAsset:
        return AudioAsset(
            path=str(destination),
            kind=AudioAssetKind.SPEECH,
            sample_rate=SPEECH_SAMPLE_RATE,
            channels=SPEECH_CHANNELS,
            source_fingerprint=fingerprint,
        )

    @staticmethod
    def _metadata_path(destination: Path) -> Path:
        return destination.with_name(SPEECH_METADATA_FILE_NAME)

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

        if existing_asset.kind != AudioAssetKind.SPEECH:
            return False

        if existing_asset.source_fingerprint != fingerprint:
            return False

        if existing_asset.sample_rate != SPEECH_SAMPLE_RATE:
            return False

        if existing_asset.channels != SPEECH_CHANNELS:
            return False

        asset_path = Path(existing_asset.path).expanduser().resolve()
        if asset_path != destination:
            return False

        return cls._prepared_file_valid(destination)
