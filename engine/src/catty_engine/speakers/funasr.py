"""FunASR smart Chinese transcription for Catty.

One integrated FunASR pass owns VAD, Paraformer ASR, CT-Punc sentence timing and
CAM++ speaker clustering. The transcript is canonical; speaker labels are
optional metadata and are never allowed to delete recognized dialogue.
"""

from __future__ import annotations

import contextlib
import math
import os
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

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
    """Convert punctuated FunASR sentence_info into canonical dialogue."""
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


def _run_generate(
    pipeline: Any,
    samples: Any,
    rate: int,
    *,
    return_spk_res: bool,
) -> list[dict[str, Any]]:
    """Run the one production pipeline, optionally skipping CAM++ annotation.

    FunASR does not expose a speaker-only entry point: speaker clustering is part
    of the same ``generate`` call that runs ASR. Reusing the loaded pipeline with
    ``return_spk_res=False`` is therefore the supported recovery path. It keeps
    canonical ASR, VAD and CT-Punc output without loading a second model stack.
    """
    return pipeline.generate(
        input=samples,
        fs=rate,
        batch_size_s=30,
        disable_pbar=True,
        sentence_timestamp=True,
        return_spk_res=return_spk_res,
    )


class FunASRParaformerBackend:
    """Canonical Chinese Smart Transcribe backend using one large FunASR pass."""

    id = "paraformer"
    model = "funasr-paraformer-ct-punc-campplus"
    integrated_speakers = True
    integrated_vad = True

    def __init__(self) -> None:
        self.speaker_error: str | None = None

    def transcribe(
        self,
        audio: Path,
        regions: list[SpeechRegion],
        *,
        language: str,
    ) -> list[TranscriptSegment]:
        # A reused backend instance must never leak a previous speaker warning.
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
            models = resolve_models()
            import torch

            device = resolve_device(torch)
            ncpu = _cpu_threads()
            model_paths = tuple(models.items())
            pipeline = _load_pipeline(model_paths, device, ncpu)
            audio_duration = min(duration, len(samples) / rate)
            try:
                result = _run_generate(
                    pipeline, samples, rate, return_spk_res=True
                )
                return parse_sentences(
                    result, start=start, duration=audio_duration
                )
            except Exception as speaker_exc:
                # No clean speaker-only exception boundary exists inside FunASR.
                # Retry the SAME pipeline without CAM++; if the transcript comes
                # back, the failure was speaker-related. If it also fails, the
                # original error is chained and the real ASR failure surfaces.
                try:
                    result = _run_generate(
                        pipeline, samples, rate, return_spk_res=False
                    )
                    segments = parse_sentences(
                        result, start=start, duration=audio_duration
                    )
                except Exception as transcription_exc:
                    raise transcription_exc from speaker_exc
                self.speaker_error = str(speaker_exc)
                return segments


class FunASRSpeakerPipeline:
    """Speaker helper retained for non-Paraformer backends such as SenseVoice."""

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
