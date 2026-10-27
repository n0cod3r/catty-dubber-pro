from pathlib import Path

import pytest

from catty_engine.speakers.funasr import match_speakers, parse_sentences
from catty_engine.speech.models import TranscriptSegment


def test_fun_asr_offsets_clamps_and_normalizes_cluster_labels():
    result = parse_sentences([{"sentence_info": [
        {"start": 100, "end": 1400, "spk": 7, "text": "你好"},
        {"start": 1400, "end": 4000, "spk": 2, "text": "世界"},
    ]}], start=12, duration=3)
    assert [(s.start, s.end, s.speaker) for s in result] == [(12.1, 13.4, "S1"), (13.4, 15, "S2")]


def test_missing_speaker_output_fails_instead_of_saving_unassigned_dialogue():
    with pytest.raises(ValueError, match="speaker labels"):
        parse_sentences([{"sentence_info": [{"start": 0, "end": 1000, "text": "你好"}]}], start=0, duration=1)


def test_overlap_matching_sums_each_speaker_and_leaves_gaps_unassigned():
    segments = [TranscriptSegment(start=0, end=4, text="你好"), TranscriptSegment(start=8, end=9, text="世界")]
    turns = [TranscriptSegment(start=a, end=b, text="x", speaker=s) for a, b, s in [(0, 1, "S1"), (1, 2.5, "S2"), (2.5, 4, "S1")]]
    result = match_speakers(segments, turns)
    assert [s.speaker for s in result] == ["S1", None]
    assert segments[0].speaker is None


def test_pipeline_uses_prepared_audio_and_preserves_sense_backend(tmp_path: Path):
    from test_transcription import PreparedAudio, FakeAsr
    from catty_engine.speech import AsrBackendRegistry, TranscriptionService, WholeClipVad
    from catty_engine.speech.models import TranscriptionResult
    from uuid import uuid4

    class Speakers:
        def transcribe(self, audio, *, start, duration, language):
            assert audio.name == "speech.wav"
            return TranscriptionResult(backend="paraformer", model="funasr", language=language,
                segments=[TranscriptSegment(start=start, end=start+duration, text="FunASR", speaker="S1")])
    class Sense(FakeAsr):
        id = "sense-small"
    registry = AsrBackendRegistry()
    registry.register(Sense())
    service = TranscriptionService(asr_backends=registry, vad=WholeClipVad(), audio_preparation=PreparedAudio(), speaker_pipeline=Speakers())
    params = dict(project_directory=tmp_path, episode_id=uuid4(), source="video.mp4", language="zh", source_start=2, duration=2)
    assert service.transcribe(**params, backend_id="paraformer").segments[0].text == "FunASR"
    sense = service.transcribe(**params, backend_id="sense-small")
    assert sense.backend == "sense-small"
    assert sense.segments[0].text == "你好"
    assert sense.segments[0].speaker == "S1"
