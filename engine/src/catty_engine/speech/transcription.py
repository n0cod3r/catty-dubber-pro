from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService

from .backends import AsrBackendRegistry
from .models import SpeechRegion, TranscriptSegment, TranscriptionResult
from .vad import VadBackend

# Long uncovered ranges are only a recovery path. Normal dialogue boundaries come
# from detected speech/sentence timing, never from fixed six-second timeline bins.
MAX_RECOVERY_REGION_SECONDS = 6.0
MIN_RECOVERY_GAP_SECONDS = 0.35


def split_long_speech_regions(
    regions: list[SpeechRegion],
    *,
    max_duration: float = MAX_RECOVERY_REGION_SECONDS,
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


def _is_whole_clip_region(
    regions: list[SpeechRegion], *, start: float, duration: float
) -> bool:
    if len(regions) != 1:
        return False
    region = regions[0]
    return abs(region.start - start) <= 0.01 and abs(region.end - (start + duration)) <= 0.01


def _timing_regions_with_coverage(
    turns: list[TranscriptSegment], *, start: float, duration: float
) -> list[SpeechRegion]:
    """Use detected dialogue timing while retaining uncovered audio as recovery.

    FunASR/CAM++ timing is useful for subtitle boundaries, but it is not allowed
    to define transcript coverage. Any uncovered range remains an ASR recovery
    region, so a missed diarization turn cannot silently remove spoken dialogue.
    """
    clip_end = start + duration
    hints = sorted(
        (
            SpeechRegion(start=max(start, turn.start), end=min(clip_end, turn.end))
            for turn in turns
            if turn.end > start and turn.start < clip_end
        ),
        key=lambda region: (region.start, region.end),
    )
    hints = [region for region in hints if region.end - region.start > 0.001]
    if not hints:
        return split_long_speech_regions([SpeechRegion(start=start, end=clip_end)])

    regions: list[SpeechRegion] = []
    cursor = start
    for hint in hints:
        if hint.start - cursor >= MIN_RECOVERY_GAP_SECONDS:
            regions.extend(
                split_long_speech_regions(
                    [SpeechRegion(start=cursor, end=hint.start)]
                )
            )
        regions.append(hint)
        cursor = max(cursor, hint.end)
    if clip_end - cursor >= MIN_RECOVERY_GAP_SECONDS:
        regions.extend(
            split_long_speech_regions([SpeechRegion(start=cursor, end=clip_end)])
        )
    return regions


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

        regions = self._vad.detect(
            audio,
            start=source_start,
            duration=duration,
        )

        # Smart Transcribe currently uses WholeClipVad for canonical Paraformer
        # coverage while FunASR supplies high-quality speech/sentence timing. Use
        # those timings as boundary hints, but explicitly fill every uncovered
        # range so diarization can never make transcript audio disappear.
        speaker_result = None
        if self._speaker_pipeline is not None:
            speaker_result = self._speaker_pipeline.transcribe(
                audio, start=source_start, duration=duration, language=language
            )
            if _is_whole_clip_region(
                regions, start=source_start, duration=duration
            ):
                regions = _timing_regions_with_coverage(
                    speaker_result.segments,
                    start=source_start,
                    duration=duration,
                )

        backend = self._asr_backends.get(backend_id)
        segments = backend.transcribe(audio, regions, language=language)

        if speaker_result is not None:
            from catty_engine.speakers.funasr import match_speakers

            segments = match_speakers(segments, speaker_result.segments)

        model = backend.model
        if speaker_result is not None:
            model = f"{model}+{speaker_result.model}"
        return TranscriptionResult(
            backend=backend.id,
            model=model,
            language=language,
            segments=segments,
        )
