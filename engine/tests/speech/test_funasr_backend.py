import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from catty_engine.speakers import funasr
from catty_engine.speakers.funasr import FunASRParaformerBackend
from catty_engine.speech.models import SpeechRegion


class FakePipeline:
    """Mimics FunASR's integrated generate → inference(VAD/ASR/punc) contract."""

    def __init__(self, *, fail_speakers: bool, fail_asr: bool = False) -> None:
        self.fail_speakers = fail_speakers
        self.fail_asr = fail_asr
        self.calls: list[bool] = []
        self.model = SimpleNamespace(name="asr")
        self.vad_model = SimpleNamespace(name="vad")
        self.punc_model = SimpleNamespace(name="punc")

    def inference(self, input, input_len=None, model=None, kwargs=None, **cfg):
        if model is self.vad_model:
            return [{"value": [[0, 1000]]}]
        if model is self.model:
            return [{"text": "你好", "timestamp": [[0, 200], [200, 500]]} for _ in input]
        if model is self.punc_model:
            return [{"text": "你好。", "punc_array": [1]}]
        raise AssertionError("unexpected model")

    def generate(self, **kwargs):
        speaker = kwargs["return_spk_res"]
        self.calls.append(speaker)
        self.inference("audio", model=self.vad_model)
        if self.fail_asr and not speaker:
            raise RuntimeError("ASR failed")
        self.inference(["chunk"], model=self.model)
        if speaker and self.fail_speakers:
            raise RuntimeError("CAM++ failed")
        self.inference("你好", model=self.punc_model)
        sentence = {"start": 0, "end": 1000, "text": "你好。"}
        if speaker:
            sentence["spk"] = 0
        return [
            {
                "text": "你好。",
                # Word timing is absolute after FunASR adds each VAD offset.
                "timestamp": [[0, 200], [200, 500]],
                "sentence_info": [sentence],
            }
        ]


class ResultOnlyPipeline:
    """FunASR version that no longer exposes the internal inference hook."""

    def generate(self, **kwargs):
        return [
            {
                "text": "你好。",
                "timestamp": [[0, 200], [200, 500]],
                "sentence_info": [{"start": 0, "end": 1000, "text": "你好。"}],
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
    assert (segments[0].start, segments[0].end) == (0.0, 0.5)
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
    # Canonical raw-word timing wins over the wider native sentence_info span.
    assert (segments[0].start, segments[0].end) == (0.0, 0.5)
    assert "inference" not in vars(pipeline)


def test_missing_inference_hook_keeps_asr_and_uses_result_word_timestamps(
    monkeypatch,
):
    _patch(monkeypatch, ResultOnlyPipeline())
    backend = FunASRParaformerBackend()

    segments = _run(backend)

    assert [(segment.start, segment.end) for segment in segments] == [(0.0, 0.5)]
    assert [segment.text for segment in segments] == ["你好。"]
    assert backend.speaker_error is None


def test_capture_failure_does_not_break_inference(monkeypatch):
    class BrokenVadPipeline(FakePipeline):
        def inference(self, input, input_len=None, model=None, kwargs=None, **cfg):
            if model is self.vad_model:
                return [{"value": [["broken", 1000]]}]
            return super().inference(input, input_len, model, kwargs, **cfg)

    _patch(monkeypatch, BrokenVadPipeline(fail_speakers=False))
    backend = FunASRParaformerBackend()

    segments = _run(backend)

    assert [(segment.start, segment.end) for segment in segments] == [(0.0, 0.5)]
    assert [segment.text for segment in segments] == ["你好。"]
