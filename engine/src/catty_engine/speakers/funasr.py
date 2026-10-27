"""Local FunASR pipeline, pinned to the models used in Catty's review benchmark.

No gender inference: cluster labels describe acoustic groups, not voice profiles.
Imports and diagnostics are redirected because stdout belongs to the JSON IPC.
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
    from huggingface_hub import snapshot_download

    override = os.environ.get("CATTY_FUNASR_MODEL_DIR")
    cache = ModelManager().root / "funasr"
    resolved = {}
    for name, revision in MODEL_REVISIONS.items():
        weight = "campplus_cn_common.bin" if name == "campplus" else "model.pt"
        required = [weight, "configuration.json", "config.yaml"]
        if name in {"paraformer-zh", "ct-punc"}:
            required.append("tokens.json")
        if name in {"paraformer-zh", "fsmn-vad"}:
            required.append("am.mvn")
        def complete(directory: Path) -> bool:
            return all((directory / file).is_file() and (directory / file).stat().st_size > 0 for file in required)
        if override:
            directory = Path(override).expanduser().resolve() / name
        else:
            from huggingface_hub.errors import LocalEntryNotFoundError
            options = dict(repo_id=f"funasr/{name}", revision=revision, cache_dir=str(cache))
            try:
                directory = Path(snapshot_download(**options, local_files_only=True))
            except LocalEntryNotFoundError:
                directory = cache / ".missing"
            if not complete(directory):
                directory = Path(snapshot_download(
                    **options,
                    allow_patterns=["*.json", "*.yaml", "*.mvn", "*.pt", "*.bin", "*.txt"],
                ))
        if not complete(directory):
            raise ValueError(f"Incomplete FunASR model {name}; check model downloads or CATTY_FUNASR_MODEL_DIR")
        resolved[name] = str(directory)
    return resolved


@lru_cache(maxsize=1)
def _load_pipeline(model_paths: tuple[tuple[str, str], ...]) -> Any:
    # CPU is the portable baseline tested on Apple Silicon. Avoid MPS-only ops.
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    from funasr import AutoModel

    torch.set_num_threads(2)
    models = dict(model_paths)
    return AutoModel(
        model=models["paraformer-zh"], vad_model=models["fsmn-vad"],
        punc_model=models["ct-punc"], spk_model=models["campplus"],
        device="cpu", ncpu=2, disable_update=True, disable_pbar=True,
        trust_remote_code=False, log_level="ERROR", spk_mode="punc_segment",
        vad_kwargs={"max_single_segment_time": 30000},
        spk_kwargs={"cb_kwargs": {"merge_thr": 0.78}},
    )


def parse_sentences(result: list[dict[str, Any]], *, start: float, duration: float) -> list[TranscriptSegment]:
    """FunASR milliseconds are relative to the requested audio range."""
    segments = []
    labels: dict[int, str] = {}
    for sentence in result[0].get("sentence_info", []) if result else []:
        left, right = float(sentence["start"]) / 1000, float(sentence["end"]) / 1000
        if not math.isfinite(left) or not math.isfinite(right):
            raise ValueError("FunASR returned invalid sentence timestamps")
        left, right = max(0, left), min(duration, right)
        text = str(sentence.get("text", "")).strip()
        if right <= left or not text:
            continue
        cluster = sentence.get("spk")
        if cluster is None:
            raise ValueError("FunASR did not return speaker labels; saved dialogue was not changed")
        label = labels.setdefault(int(cluster), f"S{len(labels) + 1}")
        segments.append(TranscriptSegment(start=start + left, end=start + right, text=text, speaker=label))
    if result and str(result[0].get("text", "")).strip() and not segments:
        raise ValueError("FunASR returned text without timed speaker sentences")
    return sorted(segments, key=lambda segment: (segment.start, segment.end))


def match_speakers(segments: list[TranscriptSegment], turns: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Sum overlap per cluster; gaps remain unassigned rather than guessed."""
    matched = []
    for segment in segments:
        overlaps: dict[str, float] = {}
        for turn in turns:
            overlap = max(0.0, min(segment.end, turn.end) - max(segment.start, turn.start))
            if overlap > 0 and turn.speaker is not None:
                overlaps[turn.speaker] = overlaps.get(turn.speaker, 0) + overlap
        label = max(overlaps, key=lambda key: overlaps[key]) if overlaps else None
        matched.append(segment.model_copy(update={"speaker": label}))
    return matched


class FunASRSpeakerPipeline:
    def transcribe(self, audio: Path, *, start: float, duration: float, language: str) -> TranscriptionResult:
        if language not in {"zh", "zh-CN", "zh-cn"}:
            raise ValueError("The approved FunASR Paraformer pipeline supports Chinese dialogue")
        rate, samples = read_mono_pcm16(audio, start=start, duration=duration)
        if rate != 16000:
            raise ValueError("FunASR requires prepared 16 kHz analysis audio")
        if samples.size == 0:
            return TranscriptionResult(backend="paraformer", model="funasr-paraformer-campplus", language=language, segments=[])
        with contextlib.redirect_stdout(sys.stderr):
            models = resolve_models()
            pipeline = _load_pipeline(tuple(models.items()))
            result = pipeline.generate(input=samples, fs=rate, batch_size_s=30, disable_pbar=True, return_spk_res=True)
        segments = parse_sentences(result, start=start, duration=min(duration, len(samples) / rate))
        return TranscriptionResult(backend="paraformer", model="funasr-paraformer-campplus", language=language, segments=segments)
