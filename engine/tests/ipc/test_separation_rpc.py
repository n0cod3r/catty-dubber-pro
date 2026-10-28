from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile

from catty_engine.ipc import handle_request
from catty_engine.project import ProjectService
from catty_engine.project.models import ProcessingStatus
from catty_engine.separation import AudioSeparationService


class FakeBackgroundExtractor:
    def __init__(self) -> None:
        self.calls = 0

    def extract_background(self, source: Path, destination: Path) -> None:
        self.calls += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        soundfile.write(
            destination,
            np.zeros((441, 2), dtype=np.float32),
            44_100,
            subtype="PCM_16",
        )


def _project(tmp_path: Path):
    source = tmp_path / "EP01.mp4"
    source.write_bytes(b"video")
    service = ProjectService()
    project = service.create_project(tmp_path, "Separation")
    episode = project.add_episode(str(source))
    service.save_project(tmp_path, project)
    return service, project, episode, source


def _request(tmp_path: Path, episode_id: str) -> dict:
    return {
        "version": 1,
        "id": "separate",
        "method": "project.separate_audio",
        "params": {
            "project_directory": str(tmp_path),
            "episode_id": episode_id,
        },
    }


def test_separate_audio_reuses_cached_background(tmp_path: Path) -> None:
    _, _, episode, source = _project(tmp_path)
    runner = FakeBackgroundExtractor()
    seeded = AudioSeparationService(runner=runner).prepare_background_audio(
        project_directory=tmp_path, episode_id=episode.id, source=source
    )

    response = handle_request(_request(tmp_path, str(episode.id)))

    assert "error" not in response
    result = response["result"]
    assert result["processing"]["separation"] == "completed"
    backgrounds = [
        asset for asset in result["audio_assets"] if asset["kind"] == "background"
    ]
    assert len(backgrounds) == 1
    assert backgrounds[0]["path"] == seeded.path
    assert runner.calls == 1


def test_stale_processing_status_can_retry(tmp_path: Path) -> None:
    service, project, episode, source = _project(tmp_path)
    seeded = AudioSeparationService(runner=FakeBackgroundExtractor()).prepare_background_audio(
        project_directory=tmp_path, episode_id=episode.id, source=source
    )
    episode.processing.separation = ProcessingStatus.PROCESSING
    service.save_project(tmp_path, project)

    response = handle_request(_request(tmp_path, str(episode.id)))

    assert "error" not in response
    result = response["result"]
    assert result["processing"]["separation"] == "completed"
    backgrounds = [
        asset for asset in result["audio_assets"] if asset["kind"] == "background"
    ]
    assert backgrounds[0]["path"] == seeded.path


def test_separate_audio_reports_missing_model_and_marks_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CATTY_APP_DATA", str(tmp_path / "app-data"))
    _, _, episode, _ = _project(tmp_path)

    response = handle_request(_request(tmp_path, str(episode.id)))

    assert response["error"]["code"] == "SEPARATION_MODEL_MISSING"
    reopened = ProjectService().open_project(tmp_path)
    assert reopened.episodes[0].processing.separation.value == "failed"
