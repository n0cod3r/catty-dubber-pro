from pathlib import Path
from uuid import uuid4

import pytest

from catty_engine.project import ProjectService
from catty_engine.project.models import (
    DialogueSegment,
    EpisodeSpeaker,
    Translation,
    TranslationStatus,
    VoiceEngine,
    VoiceProfile,
)
from catty_engine.tts.service import TTSGenerationCancelled, TTSService


class FakeEdge:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def synthesize(self, text, output, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("generation failed")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(f"audio-{self.calls}".encode())
        self.text = text
        self.kwargs = kwargs
        return output


def fixture_project(tmp_path: Path):
    projects = ProjectService()
    project = projects.create_project(tmp_path, "TTS")
    episode = project.add_episode("episode.mp4")
    for index, text in enumerate(("សួស្តី", "អរគុណ")):
        episode.dialogue_segments.append(
            DialogueSegment(
                start=2 + index * 3,
                end=4.5 + index * 3,
                source_language="zh",
                source_text="你好",
                translation=Translation(text=text, status=TranslationStatus.TRANSLATED),
            )
        )
    voice = VoiceProfile(name="Sreymom", engine=VoiceEngine.EDGE, engine_voice_id="km-KH-SreymomNeural")
    project.voice_profiles.append(voice)
    projects.save_project(tmp_path, project)
    return projects, episode, voice


def test_generate_segment_persists_audio_and_controls(tmp_path: Path):
    projects, episode, voice = fixture_project(tmp_path)
    dialogue = episode.dialogue_segments[0]
    fake = FakeEdge()
    dub = TTSService(edge=fake).generate_segment(
        tmp_path, episode.id, dialogue.id, voice.id, speed=1.15, pitch=4, volume=-5
    )
    assert fake.text == "សួស្តី"
    assert fake.kwargs == {"voice": "km-KH-SreymomNeural", "speed": 1.15, "pitch": 4, "volume": -5}
    assert dub.status.value == "ready"
    assert dub.target_duration == 2.5
    assert (tmp_path / dub.audio_path).read_bytes() == b"audio-1"
    persisted = projects.open_project(tmp_path).episode(episode.id).dub_segments[0]
    assert persisted.id == dub.id


def test_generate_missing_skips_ready_segments_and_selected_scopes_work(tmp_path: Path):
    _, episode, voice = fixture_project(tmp_path)
    fake = FakeEdge()
    service = TTSService(edge=fake)
    first, second = episode.dialogue_segments
    service.generate_segment(tmp_path, episode.id, first.id, voice.id)
    generated = service.generate_episode(tmp_path, episode.id, voice.id, mode="missing")
    assert [item.dialogue_segment_id for item in generated] == [second.id]
    selected = service.generate_episode(tmp_path, episode.id, voice.id, mode="selected", segment_ids={first.id})
    assert [item.dialogue_segment_id for item in selected] == [first.id]


def test_failed_regeneration_keeps_previous_audio_ready(tmp_path: Path):
    projects, episode, voice = fixture_project(tmp_path)
    dialogue = episode.dialogue_segments[0]
    fake = FakeEdge()
    service = TTSService(edge=fake)
    original = service.generate_segment(tmp_path, episode.id, dialogue.id, voice.id)
    original_bytes = (tmp_path / original.audio_path).read_bytes()
    fake.fail = True
    with pytest.raises(RuntimeError, match="generation failed"):
        service.generate_segment(tmp_path, episode.id, dialogue.id, voice.id, speed=1.2)
    reopened = projects.open_project(tmp_path)
    persisted = reopened.episode(episode.id).dub_segments[0]
    assert persisted.status.value == "ready"
    assert persisted.audio_path == original.audio_path
    assert (tmp_path / persisted.audio_path).read_bytes() == original_bytes


def test_preview_uses_unique_cache_files(tmp_path: Path):
    fake = FakeEdge()
    service = TTSService(edge=fake)
    first = service.preview(tmp_path, "សួស្តី", "km-KH-SreymomNeural")
    second = service.preview(tmp_path, "សួស្តី", "km-KH-SreymomNeural")
    assert first != second
    assert first.parent == tmp_path / "cache" / "tts-preview"


def test_dubbing_status_tracks_translated_coverage(tmp_path: Path):
    projects, episode, voice = fixture_project(tmp_path)
    first, second = episode.dialogue_segments
    service = TTSService(edge=FakeEdge())
    service.generate_episode(
        tmp_path, episode.id, voice.id, mode="selected", segment_ids={first.id}
    )
    partial = projects.open_project(tmp_path).episode(episode.id)
    assert partial.processing.dubbing.value == "idle"
    service.generate_episode(tmp_path, episode.id, voice.id, mode="missing")
    complete = projects.open_project(tmp_path).episode(episode.id)
    assert complete.processing.dubbing.value == "completed"
    assert [dub.dialogue_segment_id for dub in complete.dub_segments] == [
        first.id,
        second.id,
    ]


def test_generation_cancels_between_segments_without_synthesizing(tmp_path: Path):
    projects, episode, voice = fixture_project(tmp_path)
    cancel = tmp_path / "cancel"
    cancel.write_text("cancel")
    fake = FakeEdge()
    phases: list[str] = []
    with pytest.raises(TTSGenerationCancelled):
        TTSService(edge=fake).generate_episode(
            tmp_path,
            episode.id,
            voice.id,
            mode="all",
            cancel_file=cancel,
            on_progress=lambda phase, *_: phases.append(phase),
        )
    assert fake.calls == 0
    assert phases == ["started", "cancelled"]
    state = projects.open_project(tmp_path).episode(episode.id)
    assert state.dub_segments == []
    assert state.processing.dubbing.value == "idle"


def test_speaker_voice_assignment_persists_outdates_and_wins_over_default(tmp_path: Path):
    projects, episode, voice = fixture_project(tmp_path)
    first = episode.dialogue_segments[0]
    second_voice = VoiceProfile(
        name="Piseth", engine=VoiceEngine.EDGE, engine_voice_id="km-KH-PisethNeural"
    )
    project = projects.open_project(tmp_path)
    episode = project.episode(episode.id)
    project.voice_profiles.append(second_voice)
    speaker = EpisodeSpeaker(name="S1", segment_ids=[first.id])
    episode.speakers.append(speaker)
    episode.dialogue_segments[0].speaker_id = speaker.id
    projects.save_project(tmp_path, project)

    fake = FakeEdge()
    service = TTSService(edge=fake)
    original = service.generate_segment(tmp_path, episode.id, first.id, voice.id)
    service.assign_speaker_voice(tmp_path, episode.id, speaker.id, second_voice.id)

    reopened = projects.open_project(tmp_path).episode(episode.id)
    outdated = next(
        dub for dub in reopened.dub_segments if dub.id == original.id
    )
    assert outdated.status.value == "outdated"
    assert reopened.processing.dubbing.value == "idle"

    service.generate_episode(
        tmp_path, episode.id, voice.id, mode="selected", segment_ids={first.id}
    )
    persisted = projects.open_project(tmp_path).episode(episode.id)
    dub = next(dub for dub in persisted.dub_segments if dub.dialogue_segment_id == first.id)
    assert dub.voice_profile_id == second_voice.id
    assert fake.kwargs["voice"] == "km-KH-PisethNeural"


def test_speaker_voice_assignment_rejects_unknown_ids(tmp_path: Path):
    _, episode, voice = fixture_project(tmp_path)
    service = TTSService(edge=FakeEdge())
    project = ProjectService().open_project(tmp_path)
    speaker = EpisodeSpeaker(name="S1")
    project.episode(episode.id).speakers.append(speaker)
    ProjectService().save_project(tmp_path, project)
    with pytest.raises(ValueError, match="Speaker not found"):
        service.assign_speaker_voice(tmp_path, episode.id, uuid4(), voice.id)
    with pytest.raises(ValueError, match="Voice profile not found"):
        service.assign_speaker_voice(tmp_path, episode.id, speaker.id, uuid4())


def _speaker_project(tmp_path: Path, voice: VoiceProfile):
    projects = ProjectService()
    project = projects.open_project(tmp_path)
    episode = project.episode(project.episodes[0].id)
    speaker = EpisodeSpeaker(
        name="S1",
        segment_ids=[segment.id for segment in episode.dialogue_segments],
        voice_profile_id=voice.id,
    )
    episode.speakers.append(speaker)
    for segment in episode.dialogue_segments:
        segment.speaker_id = speaker.id
    projects.save_project(tmp_path, project)
    return projects, episode, speaker


def test_segment_voice_override_wins_over_speaker_voice(tmp_path: Path):
    projects, episode, voice = fixture_project(tmp_path)
    first, second = episode.dialogue_segments
    override_voice = VoiceProfile(
        name="Sokha", engine=VoiceEngine.EDGE, engine_voice_id="km-KH-SokhaNeural"
    )
    project = projects.open_project(tmp_path)
    project.voice_profiles.append(override_voice)
    projects.save_project(tmp_path, project)
    projects, episode, _ = _speaker_project(tmp_path, voice)

    fake = FakeEdge()
    service = TTSService(edge=fake)
    original = service.generate_segment(tmp_path, episode.id, first.id, voice.id)
    service.assign_segment_voice(tmp_path, episode.id, first.id, override_voice.id)

    reopened = projects.open_project(tmp_path).episode(episode.id)
    assert reopened.dialogue_segments[0].voice_profile_id == override_voice.id
    assert reopened.dub_segments[0].id == original.id
    assert reopened.dub_segments[0].status.value == "outdated"

    service.generate_episode(
        tmp_path, episode.id, voice.id, mode="selected", segment_ids={first.id, second.id}
    )
    persisted = projects.open_project(tmp_path).episode(episode.id)
    by_segment = {dub.dialogue_segment_id: dub for dub in persisted.dub_segments}
    assert by_segment[first.id].voice_profile_id == override_voice.id
    assert by_segment[second.id].voice_profile_id == voice.id
    assert fake.kwargs["voice"] == "km-KH-SreymomNeural"


def test_segment_voice_override_survives_translation_edits_and_can_be_cleared(tmp_path: Path):
    projects, episode, voice = fixture_project(tmp_path)
    first = episode.dialogue_segments[0]
    override_voice = VoiceProfile(
        name="Sokha", engine=VoiceEngine.EDGE, engine_voice_id="km-KH-SokhaNeural"
    )
    project = projects.open_project(tmp_path)
    project.voice_profiles.append(override_voice)
    projects.save_project(tmp_path, project)
    projects, episode, _ = _speaker_project(tmp_path, voice)
    service = TTSService(edge=FakeEdge())
    service.assign_segment_voice(tmp_path, episode.id, first.id, override_voice.id)

    project = projects.open_project(tmp_path)
    projects.update_dialogue_translation(
        tmp_path, project, episode.id, first.id, "សួស្តីថ្មី", "សួស្តី"
    )
    edited = projects.open_project(tmp_path).episode(episode.id)
    assert edited.dialogue_segments[0].voice_profile_id == override_voice.id
    assert edited.dub_segments == []

    service.assign_segment_voice(tmp_path, episode.id, first.id, None)
    cleared = projects.open_project(tmp_path).episode(episode.id)
    assert cleared.dialogue_segments[0].voice_profile_id is None
    service.generate_episode(
        tmp_path, episode.id, voice.id, mode="selected", segment_ids={first.id}
    )
    dub = projects.open_project(tmp_path).episode(episode.id).dub_segments[0]
    assert dub.voice_profile_id == voice.id


def test_speaker_voice_change_skips_segments_with_overrides(tmp_path: Path):
    projects, episode, voice = fixture_project(tmp_path)
    first, second = episode.dialogue_segments
    override_voice = VoiceProfile(
        name="Sokha", engine=VoiceEngine.EDGE, engine_voice_id="km-KH-SokhaNeural"
    )
    replacement = VoiceProfile(
        name="Piseth", engine=VoiceEngine.EDGE, engine_voice_id="km-KH-PisethNeural"
    )
    project = projects.open_project(tmp_path)
    project.voice_profiles.extend([override_voice, replacement])
    projects.save_project(tmp_path, project)
    projects, episode, speaker = _speaker_project(tmp_path, voice)
    service = TTSService(edge=FakeEdge())
    service.assign_segment_voice(tmp_path, episode.id, first.id, override_voice.id)
    service.generate_episode(tmp_path, episode.id, voice.id, mode="missing")
    ready = {dub.dialogue_segment_id: dub for dub in projects.open_project(tmp_path).episode(episode.id).dub_segments}
    assert ready[first.id].status.value == "ready"
    assert ready[second.id].status.value == "ready"

    service.assign_speaker_voice(tmp_path, episode.id, speaker.id, replacement.id)
    persisted = projects.open_project(tmp_path).episode(episode.id)
    by_segment = {dub.dialogue_segment_id: dub for dub in persisted.dub_segments}
    assert by_segment[first.id].status.value == "ready"
    assert by_segment[second.id].status.value == "outdated"
    assert persisted.processing.dubbing.value == "idle"


def test_segment_voice_assignment_rejects_unknown_ids(tmp_path: Path):
    _, episode, voice = fixture_project(tmp_path)
    service = TTSService(edge=FakeEdge())
    first = episode.dialogue_segments[0]
    with pytest.raises(ValueError, match="Dialogue segment not found"):
        service.assign_segment_voice(tmp_path, episode.id, uuid4(), voice.id)
    with pytest.raises(ValueError, match="Voice profile not found"):
        service.assign_segment_voice(tmp_path, episode.id, first.id, uuid4())
