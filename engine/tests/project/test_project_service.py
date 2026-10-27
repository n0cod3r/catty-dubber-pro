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
    class FakeVideoProxy:
        def prepare_playback_proxy(self, **kwargs):
            return str(tmp_path / "proxy.mp4")
    service = ProjectService(media_probe=FakeProbe(), audio_preparation=FakeAudioPreparation(), video_proxy=FakeVideoProxy())  # type: ignore[arg-type]
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


def test_split_restores_speaker_references_after_reopen(tmp_path: Path) -> None:
    from catty_engine.project.models import EpisodeSpeaker

    service = ProjectService()
    project = service.create_project(tmp_path, "Speakers")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    speaker = EpisodeSpeaker(name="A")
    segment = DialogueSegment(start=0, end=4, source_language="zh", source_text="你好世界", speaker_id=speaker.id)
    untouched = DialogueSegment(start=5, end=6, source_language="zh", source_text="好", speaker_id=speaker.id)
    speaker.segment_ids = [segment.id, untouched.id]
    episode.speakers = [speaker]
    episode.dialogue_segments = [segment, untouched]
    service.save_project(tmp_path, project)
    service.split_dialogue_segment(tmp_path, project, episode.id, segment.id, 2)
    restored = service.open_project(tmp_path).episodes[0]
    assert set(restored.speakers[0].segment_ids) == {item.id for item in restored.dialogue_segments}
    assert segment.id not in restored.speakers[0].segment_ids
    assert [(item.start, item.end) for item in restored.dialogue_segments] == [(0, 2), (2, 4), (5, 6)]


def test_merge_restores_same_speaker_reference_after_reopen(tmp_path: Path) -> None:
    from catty_engine.project.models import EpisodeSpeaker

    service = ProjectService()
    project = service.create_project(tmp_path, "Speakers")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    speaker = EpisodeSpeaker(name="A")
    first = DialogueSegment(start=0, end=2, source_language="zh", source_text="你好", speaker_id=speaker.id)
    second = DialogueSegment(start=2, end=4, source_language="zh", source_text="世界", speaker_id=speaker.id)
    speaker.segment_ids = [first.id, second.id]
    episode.speakers = [speaker]
    episode.dialogue_segments = [first, second]
    service.save_project(tmp_path, project)
    service.merge_dialogue_segment_with_next(tmp_path, project, episode.id, first.id)
    restored = service.open_project(tmp_path).episodes[0]
    merged = restored.dialogue_segments[0]
    assert merged.speaker_id == speaker.id
    assert restored.speakers[0].segment_ids == [merged.id]
    assert merged.source_text == "你好世界"


def test_merge_different_speakers_clears_obsolete_references(tmp_path: Path) -> None:
    from catty_engine.project.models import EpisodeSpeaker

    service = ProjectService()
    project = service.create_project(tmp_path, "Speakers")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    speakers = [EpisodeSpeaker(name="A"), EpisodeSpeaker(name="B")]
    first = DialogueSegment(start=0, end=2, source_language="zh", source_text="你好", speaker_id=speakers[0].id)
    second = DialogueSegment(start=2, end=4, source_language="zh", source_text="世界", speaker_id=speakers[1].id)
    speakers[0].segment_ids = [first.id]
    speakers[1].segment_ids = [second.id]
    episode.speakers = speakers
    episode.dialogue_segments = [first, second]
    service.save_project(tmp_path, project)
    service.merge_dialogue_segment_with_next(tmp_path, project, episode.id, first.id)
    restored = service.open_project(tmp_path).episodes[0]
    assert restored.dialogue_segments[0].speaker_id is None
    assert all(not speaker.segment_ids for speaker in restored.speakers)


def test_merge_undo_redo_persist_original_ids_speakers_and_translation(tmp_path: Path) -> None:
    from catty_engine.project.models import EpisodeSpeaker, Translation

    service = ProjectService()
    project = service.create_project(tmp_path, "Undo")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    speaker = EpisodeSpeaker(name="A")
    first = DialogueSegment(start=0, end=2, source_language="zh", source_text="你好", speaker_id=speaker.id, translation=Translation(text="សួស្តី"))
    second = DialogueSegment(start=2, end=4, source_language="zh", source_text="世界", speaker_id=speaker.id)
    speaker.segment_ids = [first.id, second.id]
    episode.speakers = [speaker]
    episode.dialogue_segments = [first, second]
    service.save_project(tmp_path, project)
    before = episode.model_copy(deep=True)
    service.merge_dialogue_segment_with_next(tmp_path, project, episode.id, first.id)
    after = episode.model_copy(deep=True)
    service.restore_dialogue(tmp_path, project, episode.id, after.dialogue_segments, before.dialogue_segments, before.speakers, before.dub_segments)
    restored = service.open_project(tmp_path).episodes[0]
    assert restored.dialogue_segments == before.dialogue_segments
    assert restored.dialogue_segments[0].translation.text == "សួស្តី"
    assert restored.speakers == before.speakers
    service.restore_dialogue(tmp_path, project, episode.id, before.dialogue_segments, after.dialogue_segments, after.speakers, after.dub_segments)
    assert service.open_project(tmp_path).episodes[0].dialogue_segments == after.dialogue_segments


def test_dialogue_undo_rejects_stale_history_without_overwriting_project(tmp_path: Path) -> None:
    import pytest

    service = ProjectService()
    project = service.create_project(tmp_path, "Undo")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    segment = DialogueSegment(start=0, end=4, source_language="zh", source_text="你好世界")
    episode.dialogue_segments = [segment]
    service.save_project(tmp_path, project)
    before = episode.model_copy(deep=True)
    service.split_dialogue_segment(tmp_path, project, episode.id, segment.id, 2)
    with pytest.raises(ValueError, match="changed since"):
        service.restore_dialogue(tmp_path, project, episode.id, before.dialogue_segments, [], [], [])
    assert len(service.open_project(tmp_path).episodes[0].dialogue_segments) == 2


def test_dialogue_undo_accepts_json_float_rounding_but_rejects_real_edits(tmp_path: Path) -> None:
    import math
    from datetime import timedelta
    import pytest

    service = ProjectService()
    project = service.create_project(tmp_path, "JSON undo")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    segment = DialogueSegment(start=1.123456789123, end=4.987654321987, source_language="zh", source_text="你好世界", confidence=0.876543210987)
    episode.dialogue_segments = [segment]
    service.save_project(tmp_path, project)
    expected = segment.model_copy(deep=True)
    expected.start = math.nextafter(expected.start, math.inf)
    expected.confidence = math.nextafter(expected.confidence, math.inf)
    expected.updated_at += timedelta(microseconds=1)
    service.restore_dialogue(tmp_path, project, episode.id, [expected], [segment], [], [])
    changed = expected.model_copy(deep=True)
    changed.source_text = "Changed text"
    with pytest.raises(ValueError, match="changed since"):
        service.restore_dialogue(tmp_path, project, episode.id, [changed], [], [], [])
    changed = expected.model_copy(deep=True)
    changed.start += 0.001
    with pytest.raises(ValueError, match="changed since"):
        service.restore_dialogue(tmp_path, project, episode.id, [changed], [], [], [])
