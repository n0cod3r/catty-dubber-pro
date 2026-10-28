from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
import soundfile

from catty_engine.media import AudioAssetKind
from catty_engine.separation import AudioSeparationService, BACKGROUND_FILE_NAME
from catty_engine.separation.errors import SeparationModelMissing


class FakeBackgroundExtractor:
    def __init__(self) -> None:
        self.calls = 0
        self.sources: list[Path] = []

    def extract_background(self, source: Path, destination: Path) -> None:
        self.calls += 1
        self.sources.append(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        soundfile.write(
            destination,
            np.zeros((441, 2), dtype=np.float32),
            44_100,
            subtype="PCM_16",
        )


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "EP01.mp4"
    source.write_bytes(b"video")
    return source


def test_prepares_background_stem(tmp_path: Path) -> None:
    source = _source(tmp_path)
    runner = FakeBackgroundExtractor()
    service = AudioSeparationService(runner=runner)

    asset = service.prepare_background_audio(
        project_directory=tmp_path / "project",
        episode_id=uuid4(),
        source=source,
    )

    assert runner.calls == 1
    assert asset.kind == AudioAssetKind.BACKGROUND
    assert asset.sample_rate == 44_100
    assert asset.channels == 2

    output = Path(asset.path)
    assert output.is_file()
    assert output.name == BACKGROUND_FILE_NAME
    assert output.parent.name == "uvr-mdx-inst-hq3"
    assert output.parent.parent.name == "separation"
    assert output.parent.parent.parent.name == asset.source_fingerprint
    assert output.with_name("background.json").is_file()


def test_reuses_valid_cached_stem(tmp_path: Path) -> None:
    source = _source(tmp_path)
    runner = FakeBackgroundExtractor()
    service = AudioSeparationService(runner=runner)
    directory = tmp_path / "project"

    first = service.prepare_background_audio(
        project_directory=directory, episode_id=uuid4(), source=source
    )
    second = service.prepare_background_audio(
        project_directory=directory,
        episode_id=uuid4(),
        source=source,
        existing_asset=first,
    )

    assert runner.calls == 1
    assert second == first


def test_reuses_stem_after_restart_without_existing_asset(tmp_path: Path) -> None:
    source = _source(tmp_path)
    directory = tmp_path / "project"
    first_runner = FakeBackgroundExtractor()
    first = AudioSeparationService(runner=first_runner).prepare_background_audio(
        project_directory=directory, episode_id=uuid4(), source=source
    )

    second_runner = FakeBackgroundExtractor()
    second = AudioSeparationService(runner=second_runner).prepare_background_audio(
        project_directory=directory, episode_id=uuid4(), source=source
    )

    assert first_runner.calls == 1
    assert second_runner.calls == 0
    assert second == first


def test_replaces_stem_when_source_changes(tmp_path: Path) -> None:
    source = _source(tmp_path)
    runner = FakeBackgroundExtractor()
    service = AudioSeparationService(runner=runner)
    directory = tmp_path / "project"

    first = service.prepare_background_audio(
        project_directory=directory, episode_id=uuid4(), source=source
    )
    source.write_bytes(b"replaced video with new audio")
    second = service.prepare_background_audio(
        project_directory=directory,
        episode_id=uuid4(),
        source=source,
        existing_asset=first,
    )

    assert runner.calls == 2
    assert second.source_fingerprint != first.source_fingerprint
    assert second.path != first.path


def test_cache_is_scoped_to_the_separation_model(tmp_path: Path) -> None:
    source = _source(tmp_path)
    runner = FakeBackgroundExtractor()
    service = AudioSeparationService(runner=runner)
    directory = tmp_path / "project"

    first = service.prepare_background_audio(
        project_directory=directory, episode_id=uuid4(), source=source
    )
    second = service.prepare_background_audio(
        project_directory=directory,
        episode_id=uuid4(),
        source=source,
        model_id="other-mdx",
        existing_asset=first,
    )

    assert runner.calls == 2
    assert Path(second.path).parent.name == "other-mdx"
    assert Path(second.path) != Path(first.path)


def test_corrupt_metadata_is_repaired_without_reseparating(tmp_path: Path) -> None:
    source = _source(tmp_path)
    runner = FakeBackgroundExtractor()
    service = AudioSeparationService(runner=runner)
    directory = tmp_path / "project"

    first = service.prepare_background_audio(
        project_directory=directory, episode_id=uuid4(), source=source
    )
    Path(first.path).with_name("background.json").write_text("{}", encoding="utf-8")

    second = service.prepare_background_audio(
        project_directory=directory, episode_id=uuid4(), source=source
    )

    assert runner.calls == 1
    metadata = json.loads(
        Path(second.path).with_name("background.json").read_text(encoding="utf-8")
    )
    assert metadata["kind"] == "background"
    assert metadata["source_fingerprint"] == first.source_fingerprint


def test_missing_model_is_reported_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CATTY_APP_DATA", str(tmp_path / "app-data"))
    source = _source(tmp_path)
    directory = tmp_path / "project"

    with pytest.raises(SeparationModelMissing):
        AudioSeparationService().prepare_background_audio(
            project_directory=directory, episode_id=uuid4(), source=source
        )

    assert not directory.exists()
