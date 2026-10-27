"""Local FunASR smart-transcription pipeline used by Catty.

The pipeline owns Chinese VAD, ASR, punctuation and speaker diarization so one
Transcribe action returns speaker-aware dialogue. Speaker labels are acoustic
clusters, not character identities or gender labels.
"""
from __future__ import annotations

import contextlib
import math
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from catty_engine.speech.model_manager import ModelManager
from catty_engine.speech.models import TranscriptSegment, TranscriptionResult
from catty_engine.speech.wav import read_mono_pcm16

MODEL_REVISIONS = {
    "paraformer-zh": "d7811ee3ac581fbcfdeb37c98c6ba674028433dc",
    "fsmn-vad": "df20e6b30c653645fa4ff125cacfcabd1020a669",
    "ct-punc": "d0e55e2b8722a78b63705ff443d09c4f86e5d750",
    "campplus": "e4b6ede7ce16997aff4ae69fbca1f0175e2afede",
}


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

            options = {
                "repo_id": f"funasr/{name}",
                "revision": revision,
                "cache_dir": str(cache),
            }
            try:
                directory = Path(snapshot_download(**options, local_files_only=True))
            except LocalEntryNotFoundError:
                directory = cache / ".missing"
            if not complete(directory):
                try:
                    directory = Path(
                        snapshot_download(
                            **options,
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
    """Choose a production-safe FunASR device.

    Windows/NVIDIA automatically uses CUDA. CPU is the portable baseline and
    remains the automatic Apple Silicon path because the complete FunASR stack
    contains operations that are not consistently MPS-safe. Developers may
    explicitly test MPS with CATTY_FUNASR_DEVICE=mps.
    """
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
def _load_pipeline(model_paths: tuple[tuple[str, str], ...], device: str, ncpu: int) -> Any:
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
        vad_kwargs={"max_single_segment_time": 30000},
        spk_kwargs={"cb_kwargs": {"merge_thr": 0.78}},
    )


def parse_sentences(
    result: list[dict[str, Any]], *, start: float, duration: float
) -> list[TranscriptSegment]:
    """Convert FunASR range-relative milliseconds to source-relative seconds."""
    segments: list[TranscriptSegment] = []
    labels: dict[int, str] = {}
    for sentence in result[0].get("sentence_info", []) if result else []:
        left = float(sentence["start"]) / 1000
        right = float(sentence["end"]) / 1000
        if not math.isfinite(left) or not math.isfinite(right):
            raise ValueError("FunASR returned invalid sentence timestamps")
        left, right = max(0, left), min(duration, right)
        text = str(sentence.get("text", "")).strip()
        if right <= left or not text:
            continue
        cluster = sentence.get("spk")
        if cluster is None:
            raise ValueError(
                "FunASR did not return speaker labels; saved dialogue was not changed"
            )
        label = labels.setdefault(int(cluster), f"S{len(labels) + 1}")
        segments.append(
            TranscriptSegment(
                start=start + left,
                end=start + right,
                text=text,
                speaker=label,
            )
        )
    if result and str(result[0].get("text", "")).strip() and not segments:
        raise ValueError("FunASR returned text without timed speaker sentences")
    return sorted(segments, key=lambda segment: (segment.start, segment.end))


def match_speakers(
    segments: list[TranscriptSegment], turns: list[TranscriptSegment]
) -> list[TranscriptSegment]:
    """Assign the cluster with greatest overlap; gaps remain unassigned."""
    matched: list[TranscriptSegment] = []
    for segment in segments:
        overlaps: dict[str, float] = {}
        for turn in turns:
            overlap = max(
                0.0,
                min(segment.end, turn.end) - max(segment.start, turn.start),
            )
            if overlap > 0 and turn.speaker is not None:
                overlaps[turn.speaker] = overlaps.get(turn.speaker, 0) + overlap
        label = max(overlaps, key=lambda key: overlaps[key]) if overlaps else None
        matched.append(segment.model_copy(update={"speaker": label}))
    return matched


class FunASRSpeakerPipeline:
    def transcribe(
        self,
        audio: Path,
        *,
        start: float,
        duration: float,
        language: str,
    ) -> TranscriptionResult:
        if language not in {"zh", "zh-CN", "zh-cn"}:
            raise ValueError("The FunASR smart transcription pipeline supports Chinese dialogue")
        rate, samples = read_mono_pcm16(audio, start=start, duration=duration)
        if rate != 16000:
            raise ValueError("FunASR requires prepared 16 kHz analysis audio")
        if samples.size == 0:
            return TranscriptionResult(
                backend="paraformer",
                model="funasr-paraformer-campplus",
                language=language,
                segments=[],
            )

        with contextlib.redirect_stdout(sys.stderr):
            models = resolve_models()
            import torch

            device = resolve_device(torch)
            ncpu = _cpu_threads()
            pipeline = _load_pipeline(tuple(models.items()), device, ncpu)
            try:
                result = pipeline.generate(
                    input=samples,
                    fs=rate,
                    batch_size_s=30,
                    disable_pbar=True,
                    return_spk_res=True,
                )
            except RuntimeError as exc:
                if device == "cuda" and "out of memory" in str(exc).lower():
                    raise RuntimeError(
                        "FunASR ran out of GPU memory. Set CATTY_FUNASR_DEVICE=cpu and retry."
                    ) from exc
                raise

        segments = parse_sentences(
            result,
            start=start,
            duration=min(duration, len(samples) / rate),
        )
        return TranscriptionResult(
            backend="paraformer",
            model=f"funasr-paraformer-campplus:{device}",
            language=language,
            segments=segments,
        )
