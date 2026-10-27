from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from catty_engine.speakers.funasr import (
    _cpu_threads,
    match_speakers,
    parse_sentences,
    resolve_device,
)
from catty_engine.speech.models import TranscriptSegment, TranscriptionResult


def test_fun_asr_offsets_clamps_and_normalizes_cluster_labels():
    result = parse_sentences(
        [
            {
                "sentence_info": [
                    {"start": 100, "end": 1400, "spk": 7, "text": "你好。"},
                    {"start": 1400, "end": 4000, "spk": 2, "text": "世界！"},
                ]
            }
        ],
        start=12,
        duration=3,
    )
    assert [(s.start, s.end, s.speaker) for s in result] == [
        (12.1, 13.4, "S1"),
        (13.4, 15, "S2"),
    ]
    assert [s.text for s in result] == ["你好。", "世界！"]


def test_missing_speaker_output_keeps_canonical_dialogue_unassigned():
    result = parse_sentences(
        [{"sentence_info": [{"start": 0, "end": 1000, "text": "你好。"}]}],
        start=0,
        duration=1,
    )
    assert len(result) == 1
    assert result[0].text == "你好。"
    assert result[0].speaker is None


def test_punctuation_only_sentence_is_discarded():
    result = parse_sentences(
        [
            {
                "sentence_info": [
                    {"start": 0, "end": 100, "spk": 0, "text": "，"},
                    {"start": 100, "end": 900, "spk": 0, "text": "你好。"},
                ]
            }
        ],
        start=0,
        duration=1,
    )
    assert [(s.start, s.end, s.text) for s in result] == [(0.1, 0.9, "你好。")]


def test_sentence_text_list_is_normalized():
    result = parse_sentences(
        [{"sentence_info": [{"start": 0, "end": 1000, "spk": 0, "text": ["你", "好", "。"]}]}],
        start=0,
        duration=1,
    )
    assert result[0].text == "你好。"


def test_overlap_matching_requires_meaningful_coverage():
    segments = [
        TranscriptSegment(start=0, end=4, text="你好"),
        TranscriptSegment(start=8, end=9, text="世界"),
        TranscriptSegment(start=10, end=16, text="很长"),
    ]
    turns = [
        TranscriptSegment(start=0, end=2.2, text="x", speaker="S1"),
        TranscriptSegment(start=8.0, end=8.01, text="x", speaker="S2"),
        TranscriptSegment(start=10.0, end=12.0, text="x", speaker="S3"),
    ]
    result = match_speakers(segments, turns)
    assert [s.speaker for s in result] == ["S1", None, None]
    assert [s.text for s in result] == ["你好", "世界", "很长"]
    assert segments[0].speaker is None


def test_auto_device_prefers_cuda_and_uses_cpu_without_it(monkeypatch):
    monkeypatch.delenv("CATTY_FUNASR_DEVICE", raising=False)
    cuda = SimpleNamespace(is_available=lambda: True)
    backends = SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True))
    assert resolve_device(SimpleNamespace(cuda=cuda, backends=backends)) == "cuda"
    cuda.is_available = lambda: False
    assert resolve_device(SimpleNamespace(cuda=cuda, backends=backends)) == "cpu"


def test_explicit_device_is_validated(monkeypatch):
    cuda = SimpleNamespace(is_available=lambda: False)
    backends = SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False))
    torch = SimpleNamespace(cuda=cuda, backends=backends)
    monkeypatch.setenv("CATTY_FUNASR_DEVICE", "cuda")
    with pytest.raises(RuntimeError, match="CUDA"):
        resolve_device(torch)
    monkeypatch.setenv("CATTY_FUNASR_DEVICE", "mps")
    with pytest.raises(RuntimeError, match="MPS"):
        resolve_device(torch)
    monkeypatch.setenv("CATTY_FUNASR_DEVICE", "bad")
    with pytest.raises(ValueError, match="auto, cpu, cuda, or mps"):
        resolve_device(torch)


def test_cpu_thread_override(monkeypatch):
    monkeypatch.setenv("CATTY_FUNASR_CPU_THREADS", "6")
    assert _cpu_threads() == 6
    monkeypatch.setenv("CATTY_FUNASR_CPU_THREADS", "0")
    with pytest.raises(ValueError, match="between 1 and 32"):
        _cpu_threads()


def test_speaker_pipeline_exception_keeps_asr_dialogue(tmp_path: Path):
    from test_transcription import FakeAsr, PreparedAudio
    from catty_engine.speech import AsrBackendRegistry, TranscriptionService, WholeClipVad

    class RaisingSpeakers:
        def transcribe(self, audio, *, start, duration, language):
            raise RuntimeError("CAM++ failed")

    registry = AsrBackendRegistry()
    registry.register(FakeAsr())
    service = TranscriptionService(
        asr_backends=registry,
        vad=WholeClipVad(),
        audio_preparation=PreparedAudio(),
        speaker_pipeline=RaisingSpeakers(),
    )
    result = service.transcribe(
        project_directory=tmp_path,
        episode_id=uuid4(),
        source="video.mp4",
        backend_id="paraformer",
        language="zh",
        source_start=2,
        duration=8,
    )
    assert [segment.text for segment in result.segments] == ["你好"]
    assert result.segments[0].speaker is None
    assert result.speaker_error == "CAM++ failed"


def test_partial_speaker_coverage_never_deletes_asr_dialogue(tmp_path: Path):
    from test_transcription import FakeAsr, PreparedAudio
    from catty_engine.speech import AsrBackendRegistry, SpeechRegion, TranscriptionService

    class TwoRegionsVad:
        id = "test"

        def detect(self, audio, *, start=0, duration=None):
            return [
                SpeechRegion(start=start, end=start + 2),
                SpeechRegion(start=start + 6, end=start + 8),
            ]

    class Speakers:
        def transcribe(self, audio, *, start, duration, language):
            return TranscriptionResult(
                backend="speaker",
                model="campplus",
                language=language,
                segments=[
                    TranscriptSegment(
                        start=start,
                        end=start + 2,
                        text="turn",
                        speaker="S1",
                    )
                ],
            )

    registry = AsrBackendRegistry()
    registry.register(FakeAsr())
    service = TranscriptionService(
        asr_backends=registry,
        vad=TwoRegionsVad(),
        audio_preparation=PreparedAudio(),
        speaker_pipeline=Speakers(),
    )
    result = service.transcribe(
        project_directory=tmp_path,
        episode_id=uuid4(),
        source="video.mp4",
        backend_id="paraformer",
        language="zh",
        source_start=2,
        duration=8,
    )
    assert [segment.text for segment in result.segments] == ["你好", "你好"]
    assert [segment.speaker for segment in result.segments] == ["S1", None]
    assert result.segments[-1].end == 10
