from pathlib import Path
from types import SimpleNamespace

import pytest

from catty_engine.speakers.funasr import (
    _cpu_threads,
    match_speakers,
    parse_sentences,
    resolve_device,
)
from catty_engine.speech.models import TranscriptSegment


def test_fun_asr_offsets_clamps_and_normalizes_cluster_labels():
    result = parse_sentences(
        [
            {
                "sentence_info": [
                    {"start": 100, "end": 1400, "spk": 7, "text": "你好"},
                    {"start": 1400, "end": 4000, "spk": 2, "text": "世界"},
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


def test_missing_speaker_output_fails_instead_of_saving_unassigned_dialogue():
    with pytest.raises(ValueError, match="speaker labels"):
        parse_sentences(
            [{"sentence_info": [{"start": 0, "end": 1000, "text": "你好"}]}],
            start=0,
            duration=1,
        )


def test_overlap_matching_sums_each_speaker_and_leaves_gaps_unassigned():
    segments = [
        TranscriptSegment(start=0, end=4, text="你好"),
        TranscriptSegment(start=8, end=9, text="世界"),
    ]
    turns = [
        TranscriptSegment(start=a, end=b, text="x", speaker=s)
        for a, b, s in [(0, 1, "S1"), (1, 2.5, "S2"), (2.5, 4, "S1")]
    ]
    result = match_speakers(segments, turns)
    assert [s.speaker for s in result] == ["S1", None]
    assert [s.text for s in result] == ["你好", "世界"]
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


def test_pipeline_keeps_asr_canonical_and_uses_fun_asr_only_for_speakers(
    tmp_path: Path,
):
    from test_transcription import FakeAsr, PreparedAudio
    from catty_engine.speech import (
        AsrBackendRegistry,
        TranscriptionService,
        WholeClipVad,
    )
    from catty_engine.speech.models import TranscriptionResult
    from uuid import uuid4

    class Speakers:
        def transcribe(self, audio, *, start, duration, language):
            assert audio.name == "speech.wav"
            # Deliberately cover only the first half. ASR dialogue outside this
            # range must survive and remain unassigned rather than disappearing.
            return TranscriptionResult(
                backend="paraformer",
                model="funasr-speakers",
                language=language,
                segments=[
                    TranscriptSegment(
                        start=start,
                        end=start + duration / 2,
                        text="speaker turn",
                        speaker="S1",
                    )
                ],
            )

    class Sense(FakeAsr):
        id = "sense-small"

    registry = AsrBackendRegistry()
    registry.register(FakeAsr())
    registry.register(Sense())
    service = TranscriptionService(
        asr_backends=registry,
        vad=WholeClipVad(),
        audio_preparation=PreparedAudio(),
        speaker_pipeline=Speakers(),
    )
    params = dict(
        project_directory=tmp_path,
        episode_id=uuid4(),
        source="video.mp4",
        language="zh",
        source_start=2,
        duration=8,
    )

    paraformer = service.transcribe(**params, backend_id="paraformer")
    assert paraformer.backend == "paraformer"
    assert [segment.text for segment in paraformer.segments] == ["你好", "你好"]
    assert [segment.speaker for segment in paraformer.segments] == ["S1", None]
    assert paraformer.segments[-1].end == 10

    sense = service.transcribe(**params, backend_id="sense-small")
    assert sense.backend == "sense-small"
    assert [segment.text for segment in sense.segments] == ["你好", "你好"]
    assert [segment.speaker for segment in sense.segments] == ["S1", None]
