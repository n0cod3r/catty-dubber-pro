from __future__ import annotations

from catty_engine.logging import logged_process
from catty_engine.progress import report_transcription_phase, transcription_progress

from pathlib import Path
from typing import Protocol
from uuid import UUID

from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService

from .backends import AsrBackendRegistry
from .canonical_alignment import align_observed_paraformer
from .diagnostics import current_trace, trace_transcription
from .models import TranscriptionResult
from .segmentation import split_long_dialogue
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
        self._diagnostic_run_id: str | None = None
        self._speaker_pipeline = speaker_pipeline
        self._asr_backends = asr_backends
        self._vad = vad
        self._audio_preparation = audio_preparation or AudioPreparationService()

    @logged_process
    @trace_transcription
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
        trace = current_trace()
        if trace is not None:
            trace.data["audio"] = speech_asset.model_dump(mode="json")
            trace.data["backend"] = backend_id
        audio = Path(speech_asset.path)
        regions = self._vad.detect(audio, start=source_start, duration=duration)
        backend = self._asr_backends.get(backend_id)
        segments = backend.transcribe(audio, regions, language=language)

        report_transcription_phase("alignment")

        # FunASR concatenates VAD chunks before punctuation/speaker processing.
        # Its sentence_info timestamps can therefore lose the silent gaps between
        # chunks even though the raw Paraformer word timestamps are still correct.
        # Rebuild canonical dialogue from the already-observed raw timestamps and
        # final punctuated text. The aligner is intentionally strict and falls
        # back to sentence_info whenever one-to-one alignment cannot be proven.
        trace = current_trace()
        if backend_id == "paraformer" and trace is not None and trace.attempt is not None:
            observed_result = trace.attempt.get("funasr_result")
            raw_asr = trace.attempt.get("raw_asr", [])
            if isinstance(observed_result, list):
                aligned = align_observed_paraformer(
                    observed_result,
                    raw_asr,
                    start=source_start,
                    duration=duration,
                )
                if aligned is not None:
                    segments = aligned
                    trace.data["canonical_alignment"] = "raw_word_timestamps"
                else:
                    trace.data["canonical_alignment"] = "sentence_info_fallback"

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

        # ASR keeps full context. Shorten only after recognition and speaker
        # annotation, so every split inherits the recognized speaker.
        if trace is not None:
            trace.safe(
                trace.data.update,
                parsed_segments=[segment.model_dump(mode="json") for segment in segments],
            )
        segments = split_long_dialogue(segments)
        reporter = transcription_progress()
        if reporter is not None:
            reporter.aligned(segments)
        return TranscriptionResult(
            backend=backend.id,
            model=model,
            language=language,
            segments=segments,
            speaker_error=speaker_error,
        )
