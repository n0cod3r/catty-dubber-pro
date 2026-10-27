from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService

from .backends import AsrBackendRegistry
from .models import TranscriptionResult
from .vad import VadBackend


class SpeakerPipeline(Protocol):
    def transcribe(
        self, audio: Path, *, start: float, duration: float, language: str
    ) -> TranscriptionResult: ...


class TranscriptionService:
    def __init__(
        self,
        *,
        asr_backends: AsrBackendRegistry,
        vad: VadBackend,
        audio_preparation: AudioPreparationService | None = None,
        speaker_pipeline: SpeakerPipeline | None = None,
    ) -> None:
        self._speaker_pipeline = speaker_pipeline
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

        speech_asset = self._audio_preparation.prepare_speech_audio(
            project_directory=project_directory,
            episode_id=episode_id,
            source=source,
            existing_asset=existing_asset,
        )
        audio = Path(speech_asset.path)
        regions = self._vad.detect(audio, start=source_start, duration=duration)
        backend = self._asr_backends.get(backend_id)
        segments = backend.transcribe(audio, regions, language=language)

        speaker_error = getattr(backend, "speaker_error", None)
        model = backend.model
        integrated_speakers = bool(getattr(backend, "integrated_speakers", False))

        # Alternative ASR backends may use the shared FunASR speaker helper. A
        # diarization failure is non-fatal: canonical ASR remains available and
        # the UI can surface speaker_error while keeping dialogue editable.
        if self._speaker_pipeline is not None and not integrated_speakers:
            try:
                speaker_result = self._speaker_pipeline.transcribe(
                    audio, start=source_start, duration=duration, language=language
                )
                from catty_engine.speakers.funasr import match_speakers

                segments = match_speakers(segments, speaker_result.segments)
                model = f"{model}+{speaker_result.model}"
                speaker_error = speaker_result.speaker_error
            except Exception as exc:
                speaker_error = str(exc)

        return TranscriptionResult(
            backend=backend.id,
            model=model,
            language=language,
            segments=segments,
            speaker_error=speaker_error,
        )
