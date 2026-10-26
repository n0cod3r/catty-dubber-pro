from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from .audio import AudioAsset, AudioAssetKind
from .ffmpeg import FFmpegRunner
from .fingerprint import source_fingerprint


SPEECH_SAMPLE_RATE = 16_000
SPEECH_CHANNELS = 1
SPEECH_FILE_NAME = "speech-16k-mono.wav"


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
        source_path = Path(source).expanduser().resolve()
        fingerprint = source_fingerprint(source_path)

        # Prepared media is source-derived, not episode-derived. A UI session may
        # assign a fresh episode UUID after restart, but the same source should
        # still reuse the same expensive derived audio. Keeping the cache under
        # the source fingerprint also lets multiple episodes reference one asset
        # without duplicating it on disk.
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

        # The persisted UI/project state may not have restored its AudioAsset yet.
        # The content-addressed file is sufficient to reconstruct that state.
        if self._prepared_file_valid(destination):
            return self._asset(destination, fingerprint)

        self._runner.extract_speech_audio(
            source_path,
            destination,
            sample_rate=SPEECH_SAMPLE_RATE,
            channels=SPEECH_CHANNELS,
        )

        return self._asset(destination, fingerprint)

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
