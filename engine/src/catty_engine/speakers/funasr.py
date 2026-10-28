"""FunASR smart Chinese transcription for Catty.

One integrated FunASR pass owns VAD, Paraformer ASR, CT-Punc sentence timing and
CAM++ speaker clustering. The transcript is canonical; speaker labels are
optional metadata and are never allowed to delete recognized dialogue.
"""

from __future__ import annotations

import contextlib
import logging
import math
import os
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from catty_engine.logging import logged_process
from catty_engine.progress import (
    report_transcription_phase,
    transcription_progress,
)
from catty_engine.speech.canonical_alignment import align_observed_paraformer
from catty_engine.speech.diagnostics import current_trace, snapshot
from catty_engine.speech.model_manager import ModelManager
from catty_engine.speech.models import SpeechRegion, TranscriptSegment, TranscriptionResult
from catty_engine.speech.wav import read_mono_pcm16

MODEL_REVISIONS = {
    "paraformer-zh": "d7811ee3ac581fbcfdeb37c98c6ba674028433dc",
    "fsmn-vad": "df20e6b30c653645fa4ff125cacfcabd1020a669",
    "ct-punc": "d0e55e2b8722a78b63705ff443d09c4f86e5d750",
    "campplus": "e4b6ede7ce16997aff4ae69fbca1f0175e2afede",
}
MAX_VAD_SEGMENT_MS = 30_000
MIN_SPEAKER_OVERLAP_SECONDS = 0.30
MIN_SPEAKER_COVERAGE = 0.50


@logged_process
def resolve_models() -> dict[str, str]:
    """Resolve pinned FunASR models, preferring a complete local cache."""
    from huggingface_hub import snapshot_download

    override = os.environ.get("CATTY_FUNASR_MODEL_DIR")
    cache = ModelManager().root / "funasr"
    cache.mkdir(parents=True, exist_ok=True)
    resolved: dict[str, str] = {}
    for name, revision in MODEL_REVISIONS.items():
        weight = "campplus_cn_common.bin" if name == "campplus" else "model.pt"
        required = [weight, "configuration.json", "config.yaml"]
        if name in {"paraformer-zh", "ct-punc"}:
            required.append("tokens.json")
        if name in {"paraformer-zh", "fsmn-vad"}:
            required.append("am.mvn")

        def complete(directory: Path) -> bool:
            return all(
                (directory / file).is_file() and (directory / file).stat().st_size > 0
                for file in required
            )

        if override:
            directory = Path(override).expanduser().resolve() / name
            if not complete(directory):
                raise ValueError(
                    f"Incomplete FunASR model {name} in CATTY_FUNASR_MODEL_DIR"
                )
        else:
            from huggingface_hub.errors import LocalEntryNotFoundError

            repo_id = f"funasr/{name}"
            try:
                directory = Path(
                    snapshot_download(
                        repo_id=repo_id,
                        revision=revision,
                        cache_dir=cache,
                        local_files_only=True,
                    )
                )
            except LocalEntryNotFoundError:
                directory = cache / ".missing"
            if not complete(directory):
                try:
                    directory = Path(
                        snapshot_download(
                            repo_id=repo_id,
                            revision=revision,
                            cache_dir=cache,
                            allow_patterns=[
                                "*.json",
                                "*.yaml",
                                "*.mvn",
                                "*.pt",
                                "*.bin",
                                "*.txt",
                            ],
                        )
                    )
                except Exception as exc:
                    raise RuntimeError(
                        f"Could not download FunASR model {name}. Check the internet connection and retry."
                    ) from exc
        if not complete(directory):
            raise ValueError(f"Incomplete FunASR model {name}; retry the model download")
        resolved[name] = str(directory)
    return resolved


def _cpu_threads() -> int:
    override = os.environ.get("CATTY_FUNASR_CPU_THREADS")
    if override:
        try:
            value = int(override)
        except ValueError as exc:
            raise ValueError("CATTY_FUNASR_CPU_THREADS must be an integer") from exc
        if value < 1 or value > 32:
            raise ValueError("CATTY_FUNASR_CPU_THREADS must be between 1 and 32")
        return value
    count = os.cpu_count() or 4
    return max(2, min(8, count // 2 or 1))


def resolve_device(torch: Any) -> str:
    requested = os.environ.get("CATTY_FUNASR_DEVICE", "auto").strip().lower()
    allowed = {"auto", "cpu", "cuda", "mps"}
    if requested not in allowed:
        raise ValueError("CATTY_FUNASR_DEVICE must be auto, cpu, cuda, or mps")
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested for FunASR but is not available")
    if requested == "mps":
        mps = getattr(torch.backends, "mps", None)
        if mps is None or not mps.is_available():
            raise RuntimeError("MPS was requested for FunASR but is not available")
    return requested


@lru_cache(maxsize=2)
@logged_process
def _load_pipeline(
    model_paths: tuple[tuple[str, str], ...], device: str, ncpu: int
) -> Any:
    """Load the single production Smart Transcribe pipeline."""
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    from funasr import AutoModel

    torch.set_num_threads(ncpu)
    models = dict(model_paths)
    return AutoModel(
        model=models["paraformer-zh"],
        vad_model=models["fsmn-vad"],
        punc_model=models["ct-punc"],
        spk_model=models["campplus"],
        device=device,
        ncpu=ncpu,
        disable_update=True,
        disable_pbar=True,
        trust_remote_code=False,
        log_level="ERROR",
        spk_mode="punc_segment",
        vad_kwargs={"max_single_segment_time": MAX_VAD_SEGMENT_MS},
        spk_kwargs={"cb_kwargs": {"merge_thr": 0.78}},
    )


def _has_spoken_text(text: str) -> bool:
    return any(
        not unicodedata.category(character).startswith(("P", "S", "Z", "C"))
        for character in text
    )


def _sentence_text(sentence: dict[str, Any]) -> str:
    value = sentence.get("sentence") or sentence.get("text", "")
    if isinstance(value, list):
        value = "".join(str(item) for item in value)
    return str(value).strip()


def parse_sentences(
    result: list[dict[str, Any]],
    *,
    start: float,
    duration: float,
) -> list[TranscriptSegment]:
    """Convert punctuated FunASR sentence_info into fallback dialogue."""
    segments: list[TranscriptSegment] = []
    labels: dict[int, str] = {}
    for sentence in result[0].get("sentence_info", []) if result else []:
        left = float(sentence["start"]) / 1000
        right = float(sentence["end"]) / 1000
        if not math.isfinite(left) or not math.isfinite(right):
            raise ValueError("FunASR returned invalid sentence timestamps")
        left, right = max(0, left), min(duration, right)
        text = _sentence_text(sentence)
        if right <= left or not text or not _has_spoken_text(text):
            trace = current_trace()
            if trace is not None and trace.attempt is not None:
                reason = (
                    "invalid_or_clipped_timing"
                    if right <= left
                    else "empty_text"
                    if not text
                    else "punctuation_only"
                )
                trace.safe(
                    trace.attempt["dropped_regions"].append,
                    {
                        "stage": "sentence_parser",
                        "reason": reason,
                        "start": start + left,
                        "end": start + right,
                        "text": text,
                        "native": snapshot(sentence),
                    },
                )
            continue
        cluster = sentence.get("spk")
        label = None
        if cluster is not None:
            label = labels.setdefault(int(cluster), f"S{len(labels) + 1}")
        segments.append(
            TranscriptSegment(
                start=start + left,
                end=start + right,
                text=text,
                speaker=label,
            )
        )
    top_text = str(result[0].get("text", "")).strip() if result else ""
    if top_text and not segments:
        raise ValueError("FunASR returned text without timed dialogue")
    return sorted(segments, key=lambda segment: (segment.start, segment.end))


def match_speakers(
    segments: list[TranscriptSegment], turns: list[TranscriptSegment]
) -> list[TranscriptSegment]:
    """Assign speakers only when overlap provides meaningful coverage."""
    matched: list[TranscriptSegment] = []
    for segment in segments:
        overlaps: dict[str, float] = {}
        for turn in turns:
            overlap = max(0.0, min(segment.end, turn.end) - max(segment.start, turn.start))
            if overlap > 0 and turn.speaker is not None:
                overlaps[turn.speaker] = overlaps.get(turn.speaker, 0.0) + overlap
        label = None
        if overlaps:
            candidate = max(overlaps, key=lambda key: overlaps[key])
            best = overlaps[candidate]
            duration = max(0.001, segment.end - segment.start)
            required = min(
                duration,
                max(MIN_SPEAKER_OVERLAP_SECONDS, MIN_SPEAKER_COVERAGE * duration),
            )
            if best >= required:
                label = candidate
        matched.append(segment.model_copy(update={"speaker": label}))
    return matched


class _ProductionCapture:
    """Capture the exact VAD→ASR mapping needed for canonical timestamps.

    This is production data, not diagnostic data. FunASR batches VAD chunks in
    duration order before Paraformer inference, so Catty records that same order
    while the integrated pass runs and restores absolute source timestamps.
    """

    def __init__(self, *, source_start: float, return_spk_res: bool) -> None:
        self.source_start = source_start
        self.return_spk_res = return_spk_res
        self.queue: list[dict[str, float]] = []
        self.cursor = 0
        self.raw_asr: list[dict[str, Any]] = []

    def warn(self, message: str) -> None:
        trace = current_trace()
        if trace is not None and trace.attempt is not None:
            trace.safe(trace.attempt["capture_warnings"].append, message)

    def capture_result(self, result: list[dict[str, Any]]) -> None:
        """Recover absolute word timing from FunASR's final merged result.

        ``inference_with_vad`` adds each VAD chunk offset to word timestamps
        before punctuation, so ``timestamp`` is already in source time. This
        keeps canonical raw-word alignment available when the internal
        ``inference`` hook cannot be observed.
        """
        if not isinstance(result, list) or not result:
            return
        if self.raw_asr and all(
            row.get("absolute_word_timestamps") for row in self.raw_asr
        ):
            return
        row = result[0]
        timestamps = row.get("timestamp")
        if not isinstance(timestamps, list) or not timestamps:
            return
        absolute: list[list[float]] = []
        for pair in timestamps:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                return
            absolute.append(
                [
                    self.source_start + float(pair[0]) / 1000,
                    self.source_start + float(pair[1]) / 1000,
                ]
            )
        self.raw_asr = []
        self.raw_asr.append(
            {
                "vad_region": None,
                "mapping": "funasr_result_word_timestamps",
                "native": {
                    "text": str(row.get("text") or row.get("raw_text") or ""),
                    "timestamp": timestamps,
                },
                "absolute_word_timestamps": absolute,
            }
        )

    def observe(self, stage: str, value: Any, input_count: int | None) -> None:
        rows = snapshot(value)
        if not isinstance(rows, list):
            return
        if stage == "vad":
            regions: list[dict[str, float]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for pair in row.get("value", []):
                    if not isinstance(pair, list) or len(pair) < 2:
                        continue
                    left, right = float(pair[0]), float(pair[1])
                    regions.append(
                        {
                            "start": self.source_start + left / 1000,
                            "end": self.source_start + right / 1000,
                            "native_start_ms": left,
                            "native_end_ms": right,
                        }
                    )
            self.queue = sorted(
                regions,
                key=lambda region: region["native_end_ms"] - region["native_start_ms"],
            )
            self.cursor = 0
            return
        if stage != "asr":
            return

        count = input_count or 0
        known = count == len(rows) and self.cursor + count <= len(self.queue)
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            region = self.queue[self.cursor + index] if known else None
            absolute: list[list[float]] = []
            if region is not None:
                for pair in row.get("timestamp", []):
                    if isinstance(pair, list) and len(pair) >= 2:
                        absolute.append(
                            [
                                region["start"] + float(pair[0]) / 1000,
                                region["start"] + float(pair[1]) / 1000,
                            ]
                        )
                for pair in row.get("timestamps", []):
                    if (
                        isinstance(pair, dict)
                        and "start_time" in pair
                        and "end_time" in pair
                    ):
                        absolute.append(
                            [
                                region["start"] + float(pair["start_time"]),
                                region["start"] + float(pair["end_time"]),
                            ]
                        )
            self.raw_asr.append(
                {
                    "vad_region": region,
                    "mapping": (
                        "duration_sorted_vad_order"
                        if known
                        else "unavailable_result_count_mismatch"
                    ),
                    "native": row,
                    "absolute_word_timestamps": absolute,
                }
            )
        self.cursor += count


def _begin_diagnostic_attempt(return_spk_res: bool) -> None:
    """Let diagnostics observe production capture without owning correctness."""
    trace = current_trace()
    if trace is None:
        return
    attempt = {
        "return_spk_res": return_spk_res,
        "vad_regions": [],
        "raw_asr": [],
        "punctuated": [],
        "dropped_regions": [],
        "capture_warnings": [],
    }
    trace.data["attempts"].append(attempt)
    trace.attempt = attempt
    trace.queue = []
    trace.cursor = 0


@contextlib.contextmanager
def _capture_production_pipeline(
    pipeline: Any, *, source_start: float, return_spk_res: bool
):
    capture = _ProductionCapture(
        source_start=source_start, return_spk_res=return_spk_res
    )
    try:
        _begin_diagnostic_attempt(return_spk_res)
    except Exception:
        logging.getLogger(__name__).warning(
            "Could not start the transcription trace attempt", exc_info=True
        )
    original = getattr(pipeline, "inference", None)
    if original is None:
        capture.warn(
            "Pipeline exposes no inference hook; using final result word timestamps"
        )
        yield capture
        return
    own = "inference" in getattr(pipeline, "__dict__", {})

    def observed(*args: Any, **kwargs: Any):
        model = kwargs.get(
            "model", args[2] if len(args) > 2 else getattr(pipeline, "model", None)
        )
        stage = next(
            (
                name
                for name, attribute in [
                    ("vad", "vad_model"),
                    ("punctuation", "punc_model"),
                    ("asr", "model"),
                ]
                if model is not None and model is getattr(pipeline, attribute, None)
            ),
            None,
        )
        if stage == "vad":
            report_transcription_phase("vad")
        elif stage == "punctuation":
            report_transcription_phase("punctuation")
        output = original(*args, **kwargs)
        if stage:
            input_data = kwargs.get("input", args[0] if args else None)
            count = (
                len(input_data)
                if stage == "asr" and isinstance(input_data, (list, tuple))
                else None
            )
            try:
                capture.observe(stage, output, count)
            except Exception:
                capture.warn(
                    f"{stage} capture failed; ASR inference left unchanged"
                )
                logging.getLogger(__name__).warning(
                    "FunASR %s capture failed; inference unchanged",
                    stage,
                    exc_info=True,
                )
            trace = current_trace()
            if trace is not None:
                trace.safe(trace.observe, stage, output, count)
                reporter = transcription_progress()
                if reporter is not None and trace.attempt is not None:
                    trace.safe(reporter.observe, stage, trace.attempt)
                if (
                    stage == "punctuation"
                    and trace.attempt is not None
                    and isinstance(input_data, str)
                ):
                    trace.attempt["punctuation_input_text"] = input_data
        return output

    try:
        pipeline.inference = observed
    except Exception:
        capture.warn(
            "Could not install the inference hook; using final result word timestamps"
        )
        yield capture
        return
    try:
        yield capture
    finally:
        try:
            if own:
                pipeline.inference = original
            else:
                del pipeline.inference
        except Exception:
            logging.getLogger(__name__).warning(
                "Could not restore the FunASR inference hook", exc_info=True
            )


@logged_process
def _run_generate(
    pipeline: Any,
    samples: Any,
    rate: int,
    *,
    source_start: float,
    return_spk_res: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run one production pass and return result plus absolute raw word timing."""
    with _capture_production_pipeline(
        pipeline,
        source_start=source_start,
        return_spk_res=return_spk_res,
    ) as capture:
        result = pipeline.generate(
            input=samples,
            fs=rate,
            batch_size_s=30,
            disable_pbar=True,
            sentence_timestamp=True,
            return_spk_res=return_spk_res,
        )
        try:
            capture.capture_result(result)
        except Exception:
            capture.warn("Result timing capture failed; inference unchanged")
            logging.getLogger(__name__).warning(
                "Could not capture FunASR result word timing", exc_info=True
            )
        trace = current_trace()
        if trace is not None and trace.attempt is not None:
            trace.safe(lambda: trace.attempt.update(funasr_result=snapshot(result)))
        return result, capture.raw_asr


def _canonical_segments(
    result: list[dict[str, Any]],
    raw_asr: list[dict[str, Any]],
    *,
    start: float,
    duration: float,
) -> list[TranscriptSegment]:
    """Prefer proven raw-word alignment; use sentence_info only as safe fallback."""
    aligned = align_observed_paraformer(
        result,
        raw_asr,
        start=start,
        duration=duration,
    )
    trace = current_trace()
    if aligned is not None:
        if trace is not None:
            trace.data["canonical_alignment"] = "raw_word_timestamps"
        return aligned
    if trace is not None:
        trace.data["canonical_alignment"] = "sentence_info_fallback"
    return parse_sentences(result, start=start, duration=duration)


class FunASRParaformerBackend:
    """Canonical Chinese Smart Transcribe backend using one large FunASR pass."""

    id = "paraformer"
    model = "funasr-paraformer-ct-punc-campplus"
    integrated_speakers = True
    integrated_vad = True

    def __init__(self) -> None:
        self.speaker_error: str | None = None

    @logged_process
    def transcribe(
        self,
        audio: Path,
        regions: list[SpeechRegion],
        *,
        language: str,
    ) -> list[TranscriptSegment]:
        self.speaker_error = None
        if language not in {"zh", "zh-CN", "zh-cn"}:
            raise ValueError("The FunASR Paraformer backend supports Chinese dialogue")
        if not regions:
            return []
        start = min(region.start for region in regions)
        end = max(region.end for region in regions)
        duration = end - start
        rate, samples = read_mono_pcm16(audio, start=start, duration=duration)
        if rate != 16000:
            raise ValueError("FunASR requires prepared 16 kHz analysis audio")
        if samples.size == 0:
            return []

        with contextlib.redirect_stdout(sys.stderr):
            report_transcription_phase("loading")
            models = resolve_models()
            import torch

            device = resolve_device(torch)
            ncpu = _cpu_threads()
            trace = current_trace()
            if trace is not None:
                trace.data["model_revisions"] = dict(MODEL_REVISIONS)
                trace.data["runtime"] = {
                    "device": device,
                    "cpu_threads": ncpu,
                    "max_vad_segment_ms": MAX_VAD_SEGMENT_MS,
                    "batch_size_s": 30,
                    "sentence_timestamp": True,
                }
            model_paths = tuple(models.items())
            pipeline = _load_pipeline(model_paths, device, ncpu)
            audio_duration = min(duration, len(samples) / rate)
            try:
                result, raw_asr = _run_generate(
                    pipeline,
                    samples,
                    rate,
                    source_start=start,
                    return_spk_res=True,
                )
                return _canonical_segments(
                    result,
                    raw_asr,
                    start=start,
                    duration=audio_duration,
                )
            except Exception as speaker_exc:
                try:
                    result, raw_asr = _run_generate(
                        pipeline,
                        samples,
                        rate,
                        source_start=start,
                        return_spk_res=False,
                    )
                    segments = _canonical_segments(
                        result,
                        raw_asr,
                        start=start,
                        duration=audio_duration,
                    )
                except Exception as transcription_exc:
                    raise transcription_exc from speaker_exc
                logging.getLogger(__name__).warning(
                    "Speaker detection failed; retaining transcript without speaker labels: %s",
                    speaker_exc,
                )
                self.speaker_error = str(speaker_exc)
                return segments


class FunASRSpeakerPipeline:
    """Speaker helper retained for non-Paraformer backends such as SenseVoice."""

    @logged_process
    def transcribe(
        self,
        audio: Path,
        *,
        start: float,
        duration: float,
        language: str,
    ) -> TranscriptionResult:
        backend = FunASRParaformerBackend()
        regions = [SpeechRegion(start=start, end=start + duration)]
        segments = backend.transcribe(audio, regions, language=language)
        return TranscriptionResult(
            backend="paraformer",
            model=backend.model,
            language=language,
            segments=segments,
            speaker_error=backend.speaker_error,
        )
