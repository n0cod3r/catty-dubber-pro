from pathlib import Path

from catty_engine.project import ProjectService
from catty_engine.project.models import DialogueSegment, Translation, TranslationStatus, VoiceEngine, VoiceProfile
from catty_engine.tts.service import TTSService


class FakeEdge:
    def synthesize(self, text, output, **kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"audio")
        self.text = text
        self.kwargs = kwargs
        return output


def test_generate_segment_persists_audio_and_controls(tmp_path: Path):
    projects = ProjectService()
    project = projects.create_project(tmp_path, "TTS")
    episode = project.add_episode("episode.mp4")
    dialogue = DialogueSegment(
        start=2,
        end=4.5,
        source_language="zh",
        source_text="你好",
        translation=Translation(
            text="សួស្តី",
            status=TranslationStatus.TRANSLATED,
        ),
    )
    episode.dialogue_segments.append(dialogue)
    voice = VoiceProfile(
        name="Sreymom",
        engine=VoiceEngine.EDGE,
        engine_voice_id="km-KH-SreymomNeural",
    )
    project.voice_profiles.append(voice)
    projects.save_project(tmp_path, project)

    fake = FakeEdge()
    dub = TTSService(edge=fake).generate_segment(
        tmp_path,
        episode.id,
        dialogue.id,
        voice.id,
        speed=1.15,
        pitch=4,
        volume=-5,
    )

    assert fake.text == "សួស្តី"
    assert fake.kwargs == {
        "voice": "km-KH-SreymomNeural",
        "speed": 1.15,
        "pitch": 4,
        "volume": -5,
    }
    assert dub.status.value == "ready"
    assert dub.target_duration == 2.5
    assert dub.speed == 1.15
    assert dub.pitch == 4
    assert dub.volume == -5
    assert dub.audio_path is not None
    assert (tmp_path / dub.audio_path).read_bytes() == b"audio"

    reopened = projects.open_project(tmp_path)
    persisted = reopened.episode(episode.id).dub_segments[0]
    assert persisted.id == dub.id
    assert persisted.audio_path == dub.audio_path
