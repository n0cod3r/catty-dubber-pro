from pathlib import Path

from catty_engine.media.models import MediaInfo
from catty_engine.project import DialogueSegment, ProjectService


class FakeProbe:
    def probe(self, source: str) -> MediaInfo:
        return MediaInfo(source_path=source)


def project_service_without_ffprobe() -> ProjectService:
    return ProjectService(media_probe=FakeProbe())  # type: ignore[arg-type]


def test_create_and_reload_project(tmp_path: Path) -> None:
    service = ProjectService()
    project_dir = tmp_path / "my-drama"
    created = service.create_project(directory=project_dir, name="My Drama")
    loaded = service.open_project(project_dir)
    assert loaded.id == created.id
    assert loaded.name == "My Drama"
    assert loaded.schema_version == 1
    assert loaded.episodes == []
    assert (project_dir / "project.json").is_file()
    for child in ("episodes", "assets", "voices", "cache", "exports"):
        assert (project_dir / child).is_dir()


def test_import_multiple_episodes(tmp_path: Path) -> None:
    service = project_service_without_ffprobe(); project_dir = tmp_path / "my-drama"
    project = service.create_project(directory=project_dir, name="My Drama")
    paths = [tmp_path / f"EP0{index}.mp4" for index in range(1, 4)]
    for path in paths: path.touch()
    imported = service.import_episodes(directory=project_dir, project=project, source_paths=[str(path) for path in paths])
    assert [episode.name for episode in imported] == ["EP01", "EP02", "EP03"]
    assert [episode.order for episode in imported] == [0, 1, 2]
    assert len(service.open_project(project_dir).episodes) == 3


def test_duplicate_episode_is_not_imported(tmp_path: Path) -> None:
    service = project_service_without_ffprobe(); project_dir = tmp_path / "my-drama"
    project = service.create_project(directory=project_dir, name="My Drama")
    episode = tmp_path / "EP01.mp4"; episode.touch()
    service.import_episodes(directory=project_dir, project=project, source_paths=[str(episode)])
    imported_again = service.import_episodes(directory=project_dir, project=project, source_paths=[str(episode)])
    assert imported_again == []
    assert len(project.episodes) == 1


def test_reimport_after_reload_reuses_episode_id(tmp_path: Path) -> None:
    class FakeAudioPreparation:
        def prepare_speech_audio(self, **kwargs):
            from catty_engine.media.audio import AudioAsset, AudioAssetKind
            return AudioAsset(path=str(tmp_path / "speech.wav"), kind=AudioAssetKind.SPEECH, sample_rate=16000, channels=1, source_fingerprint="stable")
    service = ProjectService(media_probe=FakeProbe(), audio_preparation=FakeAudioPreparation())  # type: ignore[arg-type]
    project_dir = tmp_path / "my-drama"; project = service.create_project(directory=project_dir, name="My Drama")
    source = tmp_path / "EP01.mp4"; source.write_bytes(b"video")
    first = service.import_episode(directory=project_dir, project=project, source_path=str(source))
    reloaded = service.open_project(project_dir)
    second = service.import_episode(directory=project_dir, project=reloaded, source_path=str(source))
    assert second.id == first.id
    assert len(reloaded.episodes) == 1


def test_split_dialogue_segment_persists_timing_and_text(tmp_path: Path) -> None:
    service = ProjectService(); project_dir = tmp_path / "my-drama"
    project = service.create_project(project_dir, "My Drama")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    segment = DialogueSegment(start=2.0, end=10.0, source_language="zh", source_text="你好世界")
    episode.dialogue_segments = [segment]
    service.save_project(project_dir, project)
    updated = service.split_dialogue_segment(project_dir, project, episode.id, segment.id, 6.0)
    assert [(item.start, item.end, item.source_text) for item in updated.dialogue_segments] == [(2.0, 6.0, "你好"), (6.0, 10.0, "世界")]
    assert len(service.open_project(project_dir).episodes[0].dialogue_segments) == 2


def test_merge_dialogue_segment_with_next_persists(tmp_path: Path) -> None:
    service = ProjectService(); project_dir = tmp_path / "my-drama"
    project = service.create_project(project_dir, "My Drama")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    first = DialogueSegment(start=1.0, end=3.0, source_language="zh", source_text="你好", confidence=0.8)
    second = DialogueSegment(start=3.2, end=5.0, source_language="zh", source_text="世界", confidence=1.0)
    episode.dialogue_segments = [first, second]
    service.save_project(project_dir, project)
    updated = service.merge_dialogue_segment_with_next(project_dir, project, episode.id, first.id)
    assert len(updated.dialogue_segments) == 1
    merged = updated.dialogue_segments[0]
    assert (merged.start, merged.end, merged.source_text) == (1.0, 5.0, "你好世界")
    assert merged.confidence == 0.9
    assert len(service.open_project(project_dir).episodes[0].dialogue_segments) == 1
