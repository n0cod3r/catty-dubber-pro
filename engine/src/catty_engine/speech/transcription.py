from __future__ import annotations

from pathlib import Path
from uuid import UUID
from typing import Protocol

from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService

from .backends import AsrBackendRegistry
from .models import SpeechRegion, TranscriptionResult
from .vad import VadBackend

# Dialogue is the editing unit for subtitles, translation, and dubbing. Keep long
# uninterrupted VAD regions bounded so one fast narrator does not become a
# single 15-30 second subtitle/TTS job. Natural VAD pauses remain the preferred
# boundary; this is only the hard safety limit.
MAX_DIALOGUE_REGION_SECONDS = 6.0


def split_long_speech_regions(
    regions: list[SpeechRegion],
    *,
    max_duration: float = MAX_DIALOGUE_REGION_SECONDS,
) -> list[SpeechRegion]:
    if max_duration <= 0:
        raise ValueError("max_duration must be > 0")

    result: list[SpeechRegion] = []
    for region in regions:
        start = region.start
        while region.end - start > max_duration + 0.001:
            end = start + max_duration
            result.append(
                SpeechRegion(start=start, end=end, confidence=region.confidence)
            )
            start = end
        if region.end - start > 0.001:
            result.append(
                SpeechRegion(start=start, end=region.end, confidence=region.confidence)
            )
    return result


class SpeakerPipeline(Protocol):
    def transcribe(self, audio: Path, *, start: float, duration: float, language: str) -> TranscriptionResult: ...


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

        # Preparation is deliberately internal. Editor actions ask to transcribe;
        # they never need to expose the 16 kHz mono working asset to the user.
        speech_asset = self._audio_preparation.prepare_speech_audio(
            project_directory=project_directory,
            episode_id=episode_id,
            source=source,
            existing_asset=existing_asset,
        )
        audio = Path(speech_asset.path)
        speaker_result = None
        if self._speaker_pipeline is not None:
            speaker_result = self._speaker_pipeline.transcribe(audio, start=source_start, duration=duration, language=language)
            if backend_id == "paraformer":
                return speaker_result
        regions = self._vad.detect(
            audio,
            start=source_start,
            duration=duration,
        )
        regions = split_long_speech_regions(regions)
        backend = self._asr_backends.get(backend_id)
        segments = backend.transcribe(audio, regions, language=language)
        if speaker_result is not None:
            from catty_engine.speakers.funasr import match_speakers
            segments = match_speakers(segments, speaker_result.segments)
        return TranscriptionResult(
            backend=backend.id,
            model=backend.model,
            language=language,
            segments=segments,
        )
