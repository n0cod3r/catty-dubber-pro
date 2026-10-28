import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from catty_engine.speakers import funasr
from catty_engine.speakers.funasr import FunASRParaformerBackend
from catty_engine.speech.models import SpeechRegion


class FakePipeline:
    def __init__(self, *, fail_speakers: bool, fail_asr: bool = False) -> None:
        self.fail_speakers = fail_speakers
        self.fail_asr = fail_asr
        self.calls: list[bool] = []

    def generate(self, **kwargs):
        speaker = kwargs["return_spk_res"]
        self.calls.append(speaker)
        if speaker and self.fail_speakers:
            raise RuntimeError("CAM++ failed")
        if not speaker and self.fail_asr:
            raise RuntimeError("ASR failed")
        return [
            {
                "text": "你好。",
                "sentence_info": [
                    {
                        "start": 0,
                        "end": 1000,
                        "text": "你好。",
                        **({"spk": 0} if speaker else {}),
                    }
                ],
            }
        ]


def _patch(monkeypatch, pipeline):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace())
    monkeypatch.setattr(
        funasr,
        "resolve_models",
        lambda: {
            "paraformer-zh": "p",
            "fsmn-vad": "v",
            "ct-punc": "c",
            "campplus": "s",
        },
    )
    monkeypatch.setattr(funasr, "resolve_device", lambda torch: "cpu")
    monkeypatch.setattr(funasr, "_cpu_threads", lambda: 2)
    monkeypatch.setattr(
        funasr,
        "read_mono_pcm16",
        lambda audio, *, start, duration: (
            16000,
            np.zeros(int(duration * 16000), dtype=np.float32),
        ),
    )
    monkeypatch.setattr(
        funasr,
        "_capture_production_pipeline",
        lambda *args, **kwargs: contextlib.nullcontext(SimpleNamespace(raw_asr=[])),
    )
    loads: list[int] = []

    def load(*args, **kwargs):
        loads.append(1)
        return pipeline

    monkeypatch.setattr(funasr, "_load_pipeline", load)
    return loads


def _run(backend: FunASRParaformerBackend):
    return backend.transcribe(
        Path("speech.wav"),
        [SpeechRegion(start=0, end=1)],
        language="zh",
    )


def test_speaker_failure_keeps_transcript_and_uses_same_pipeline(monkeypatch):
    pipeline = FakePipeline(fail_speakers=True)
    loads = _patch(monkeypatch, pipeline)
    backend = FunASRParaformerBackend()

    segments = _run(backend)

    assert [segment.text for segment in segments] == ["你好。"]
    assert (segments[0].start, segments[0].end) == (0.0, 1.0)
    assert segments[0].speaker is None
    assert backend.speaker_error == "CAM++ failed"
    assert pipeline.calls == [True, False]
    assert len(loads) == 1
    assert not hasattr(funasr, "_load_asr_fallback")


def test_asr_failure_is_not_masked_by_speaker_warning(monkeypatch):
    pipeline = FakePipeline(fail_speakers=True, fail_asr=True)
    _patch(monkeypatch, pipeline)
    backend = FunASRParaformerBackend()

    with pytest.raises(RuntimeError, match="ASR failed") as error:
        _run(backend)

    assert isinstance(error.value.__cause__, RuntimeError)
    assert str(error.value.__cause__) == "CAM++ failed"
    assert backend.speaker_error is None


def test_successful_run_clears_stale_speaker_error(monkeypatch):
    pipeline = FakePipeline(fail_speakers=True)
    _patch(monkeypatch, pipeline)
    backend = FunASRParaformerBackend()
    _run(backend)
    assert backend.speaker_error == "CAM++ failed"

    pipeline.fail_speakers = False
    segments = _run(backend)

    assert backend.speaker_error is None
    assert segments[0].speaker == "S1"
