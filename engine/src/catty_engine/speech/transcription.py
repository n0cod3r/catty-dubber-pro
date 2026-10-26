from __future__ import annotations

from pathlib import Path
from uuid import UUID

from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService

from .backends import AsrBackendRegistry
from .models import TranscriptionResult
from .vad import VadBackend


class TranscriptionService:
    def __init__(
        self,
        *,
        asr_backends: AsrBackendRegistry,
        vad: VadBackend,
        audio_preparation: AudioPreparationService | None = None,
    ) -> None:
        self._asr_backends = asr_backends
        self._vad = vad
        self._audio_preparation = audio_preparation or AudioPreparationService()

    def transcribe(
        self,
        *,
        project_directory: Path,
        episode_id: UUID,
        source: str | Path,
        backend_id: str,
        language: str,
        source_start: float,
        duration: float,
        existing_asset: AudioAsset | None = None,
    ) -> TranscriptionResult:
        if source_start < 0:
            raise ValueError("source_start must be >= 0")
        if duration <= 0:
            raise ValueError("duration must be > 0")

        # Preparation is deliberately internal. Editor actions ask to transcribe;
        # they never need to expose the 16 kHz mono working asset to the user.
        speech_asset = self._audio_preparation.prepare_speech_audio(
            project_directory=project_directory,
            episode_id=episode_id,
            source=source,
            existing_asset=existing_asset,
        )
        audio = Path(speech_asset.path)
        regions = self._vad.detect(
            audio,
            start=source_start,
            duration=duration,
        )
        backend = self._asr_backends.get(backend_id)
        segments = backend.transcribe(audio, regions, language=language)
        return TranscriptionResult(
            backend=backend.id,
            model=backend.model,
            language=language,
            segments=segments,
        )
