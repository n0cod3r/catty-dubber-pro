import json
from pathlib import Path
from types import SimpleNamespace

from catty_engine.ipc import handle_request
from catty_engine.progress import (
    report_transcription_phase,
    transcription_progress,
    transcription_progress_scope,
)
from catty_engine.project import DialogueSegment, ProjectService
from catty_engine.speech.models import TranscriptSegment, TranscriptionResult


def progress_events(capsys):
    return [
        entry["payload"]
        for line in capsys.readouterr().err.splitlines()
        if (entry := json.loads(line)).get("catty_progress") == "transcription"
    ]


def test_chunk_previews_are_sorted_and_not_claimed_as_persisted(capsys):
    with transcription_progress_scope("job", Path("/project"), "ep") as reporter:
        reporter.observe("vad", {"vad_regions": [{}, {}]})
        rows = [
            {
                "vad_region": {"start": 107, "end": 110},
                "native": {"text": "我 叫 宋 之"},
                "absolute_word_timestamps": [
                    [107.1, 107.3],
                    [107.3, 107.5],
                    [107.5, 107.7],
                    [107.7, 108.0],
                ],
            },
            {
                "vad_region": {"start": 1, "end": 2},
                "native": {"text": "你 好"},
                "absolute_word_timestamps": [[1.1, 1.4], [1.4, 1.8]],
            },
        ]
        reporter.observe("asr", {"raw_asr": rows[:1]})
        reporter.observe("asr", {"raw_asr": rows})
        reporter.aligned([TranscriptSegment(start=107.1, end=108, text="我叫宋之，")])
    events = progress_events(capsys)
    asr = [e for e in events if e["phase"] == "asr"]
    assert [e["completed"] for e in asr] == [0, 1, 2]
    assert [s["text"] for s in asr[-1]["preview_segments"]] == ["你好", "我叫宋之"]
    assert [s["start"] for s in asr[-1]["preview_segments"]] == [1.1, 107.1]
    assert all(e["episode"] is None for e in events)
    assert events[-1]["phase"] == "alignment"
    assert transcription_progress() is None


def test_progress_completion_is_published_only_after_rpc_persistence(
    tmp_path, monkeypatch, capsys
):
    from catty_engine.speech import runtime

    projects = ProjectService()
    project = projects.create_project(tmp_path, "Progress")
    episode = project.add_episode("video.mp4")
    episode.dialogue_segments = [
        DialogueSegment(start=0, end=1, source_text="old", source_language="zh")
    ]
    projects.save_project(tmp_path, project)
    original = (tmp_path / "project.json").read_bytes()

    def transcribe(**kwargs):
        reporter = transcription_progress()
        reporter.observe("vad", {"vad_regions": [{}]})
        reporter.observe(
            "asr",
            {
                "raw_asr": [
                    {
                        "vad_region": {"start": 1, "end": 2},
                        "native": {"text": "你 好"},
                        "absolute_word_timestamps": [[1, 1.5], [1.5, 2]],
                    }
                ]
            },
        )
        assert (tmp_path / "project.json").read_bytes() == original
        segments = [TranscriptSegment(start=1, end=2, text="你好。")]
        reporter.aligned(segments)
        return TranscriptionResult(
            backend="paraformer", model="test", language="zh", segments=segments
        )

    monkeypatch.setattr(
        runtime,
        "create_transcription_service",
        lambda **kwargs: SimpleNamespace(transcribe=transcribe),
    )
    response = handle_request(
        {
            "version": 1,
            "id": "rpc",
            "method": "speech.transcribe",
            "params": {
                "operation_id": "job",
                "project_directory": str(tmp_path),
                "episode_id": str(episode.id),
                "source": "video.mp4",
                "source_start": 0,
                "duration": 3,
                "asr_config": {},
                "vad_config": {},
            },
        }
    )
    assert "error" not in response
    events = progress_events(capsys)
    assert events[-2]["phase"] == "saving"
    assert events[-1]["phase"] == "completed"
    assert all(e["episode"] is None for e in events[:-1])
    assert events[-1]["episode"] == projects.open_project(tmp_path).episodes[
        0
    ].model_dump(mode="json")
    assert events[-1]["episode"]["dialogue_segments"][0]["source_text"] == "你好。"


def test_failed_preview_does_not_overwrite_previous_dialogue(
    tmp_path, monkeypatch, capsys
):
    from catty_engine.speech import runtime

    projects = ProjectService()
    project = projects.create_project(tmp_path, "Failure")
    episode = project.add_episode("video.mp4")
    projects.save_project(tmp_path, project)
    original = (tmp_path / "project.json").read_bytes()

    def transcribe(**kwargs):
        transcription_progress().aligned(
            [TranscriptSegment(start=1, end=2, text="draft")]
        )
        raise ValueError("ASR failure")

    monkeypatch.setattr(
        runtime,
        "create_transcription_service",
        lambda **kwargs: SimpleNamespace(transcribe=transcribe),
    )
    response = handle_request(
        {
            "version": 1,
            "id": "rpc",
            "method": "speech.transcribe",
            "params": {
                "operation_id": "job",
                "project_directory": str(tmp_path),
                "episode_id": str(episode.id),
                "source": "video.mp4",
                "source_start": 0,
                "duration": 3,
                "asr_config": {},
                "vad_config": {},
            },
        }
    )
    assert "error" in response
    assert (tmp_path / "project.json").read_bytes() == original
    events = progress_events(capsys)
    assert events[-1]["phase"] == "failed"
    assert all(e["episode"] is None for e in events)


def test_requests_without_progress_id_keep_existing_protocol(capsys):
    with transcription_progress_scope(None, "/project", "ep") as reporter:
        assert reporter is None
        report_transcription_phase("alignment")
    assert capsys.readouterr().err == ""
