from pathlib import Path
from types import SimpleNamespace
import sys
import wave

import pytest
from pydantic import ValidationError

from catty_engine.models.manager import ModelManager
from catty_engine.project import ProjectService
from catty_engine.tts.library import VoiceDraft, VoiceLibrary
from catty_engine.tts import library as library_module
from catty_engine.tts import voxcpm as vox_module


def wav(path: Path, seconds: int = 4):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * 16000 * seconds)
    return path


class FakeVox:
    calls = 0
    def synthesize(self, text, output, **kwargs):
        FakeVox.calls += 1
        return wav(output)


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("CATTY_APP_DATA", str(tmp_path / "app"))
    monkeypatch.setattr(library_module, "VoxCPM2Provider", FakeVox)
    FakeVox.calls = 0
    return VoiceLibrary()


def test_edge_presets_are_persistent_and_builtins_are_readonly(library):
    voice = library.create(VoiceDraft(name="My girl", engine="edge", engine_voice_id="km-KH-SreymomNeural", pitch=25))
    assert VoiceLibrary().get(voice.id).pitch == 25
    assert voice.speed == 1.25
    with pytest.raises(ValueError, match="Built-in"):
        library.remove("builtin-edge-man")
    library.remove(voice.id)
    with pytest.raises(ValueError, match="not found"):
        library.get(voice.id)


def test_imported_reference_is_managed_and_project_copy_survives_library_deletion(library, tmp_path):
    source = wav(tmp_path / "original.wav")
    voice = library.create(VoiceDraft(name="Clone", engine="voxcpm2", speed=1, reference_audio_path=str(source), reference_text="Exact reference words"))
    source.unlink()
    assert Path(voice.reference_audio_path).is_file()
    projects = ProjectService()
    root = tmp_path / "project"
    projects.create_project(root, "Voice project")
    profile = library.use_in_project(voice.id, root)
    assert not Path(profile.reference_audio_path).is_absolute()
    assert (root / profile.reference_audio_path).is_file()
    assert profile.reference_text == "Exact reference words"
    assert library.use_in_project(voice.id, root).id == profile.id
    library.remove(voice.id)
    restored = projects.open_project(root).voice_profiles[0]
    assert (root / restored.reference_audio_path).is_file()
    assert restored.library_voice_id == voice.id


def test_builtin_vox_samples_are_generated_once_and_copied_to_custom_voice(library):
    first = library.preview(voice_id="builtin-voxcpm2-woman")
    second = library.preview(voice_id="builtin-voxcpm2-woman")
    assert first == second
    assert FakeVox.calls == 1
    custom = library.create(VoiceDraft(name="Gentle Woman", engine="voxcpm2", speed=1, base_voice_id="builtin-voxcpm2-woman"))
    assert Path(custom.reference_audio_path).read_bytes() == first.read_bytes()
    assert FakeVox.calls == 1


def test_invalid_references_and_edge_controls_are_rejected(library, tmp_path):
    source = wav(tmp_path / "short.wav", seconds=1)
    with pytest.raises(ValueError, match="3 and 30"):
        library.create(VoiceDraft(name="Short", engine="voxcpm2", speed=1, reference_audio_path=str(source)))
    assert not list((library.root / "user").glob("*/profile.json"))
    with pytest.raises(ValidationError, match="not Edge"):
        VoiceDraft(name="Wrong controls", engine="voxcpm2", speed=1, pitch=20)
    with pytest.raises(ValidationError):
        VoiceDraft(name=" ", engine="edge", engine_voice_id="km-KH-SreymomNeural")


def test_voxcpm_is_downloadable_but_never_a_translation_candidate(library):
    manager = ModelManager()
    assert manager.spec("voxcpm2").repository == "openbmb/VoxCPM2"
    assert "voxcpm2" not in [item.id for item in manager.list_specs(kind="translation")]
    with pytest.raises(ValueError, match="Download VoxCPM2"):
        vox_module.VoxCPM2Provider().synthesize("ខ្មែរ", library.root / "out.wav")


def test_voxcpm_loads_only_local_weights_once_and_keeps_stdout_clean(tmp_path, monkeypatch, capsys):
    loaded = []
    generated = []
    class Model:
        tts_model = SimpleNamespace(sample_rate=48000)
        def generate(self, **kwargs):
            print("model diagnostic")
            generated.append(kwargs)
            return [0.0]
    class Loader:
        @staticmethod
        def from_pretrained(path, **kwargs):
            loaded.append((path, kwargs))
            return Model()
    monkeypatch.setattr(vox_module, "_model", None)
    monkeypatch.setattr(vox_module, "_model_key", None)
    monkeypatch.setattr(vox_module, "ModelManager", lambda: SimpleNamespace(installed=lambda _: True, path_for=lambda _: tmp_path))
    settings = SimpleNamespace(
        performance=SimpleNamespace(device="cpu"),
        voice_clone=SimpleNamespace(model="voxcpm2"),
    )
    monkeypatch.setattr(vox_module, "SettingsService", lambda: SimpleNamespace(get=lambda: settings))
    monkeypatch.setitem(sys.modules, "voxcpm", SimpleNamespace(VoxCPM=Loader))
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace(write=lambda path, *args, **kwargs: Path(path).write_bytes(b"audio")))
    reference = wav(tmp_path / "reference.wav")
    for _ in range(2):
        vox_module.VoxCPM2Provider().synthesize("ខ្មែរ", tmp_path / "out.wav", reference=reference, style="warm voice")
    assert len(loaded) == 1
    assert loaded[0][1]["local_files_only"] is True
    assert loaded[0][1]["load_denoiser"] is False
    assert generated[0]["reference_wav_path"] == str(reference)
    assert generated[0]["text"] == "(warm voice)ខ្មែរ"
    assert capsys.readouterr().out == ""


def test_project_vox_profile_generates_wav_using_existing_durable_pipeline(library, tmp_path, monkeypatch):
    from catty_engine.project.models import DialogueSegment, Translation
    from catty_engine.tts import service as service_module
    from catty_engine.tts.service import TTSService
    root = tmp_path / "project"
    projects = ProjectService()
    project = projects.create_project(root, "Clone generation")
    episode = project.add_episode("episode.mp4")
    row = DialogueSegment(start=2, end=6, source_text="你好", source_language="zh", translation=Translation(text="សួស្តី"))
    episode.dialogue_segments.append(row)
    projects.save_project(root, project)
    voice = library.create(VoiceDraft(name="Actor", engine="voxcpm2", speed=1, style_prompt="warm man"))
    profile = library.use_in_project(voice.id, root)
    monkeypatch.setattr(service_module, "VoxCPM2Provider", FakeVox)
    generated = TTSService().generate_segment(root, episode.id, row.id, profile.id, speed=1.25, pitch=20)
    assert generated.audio_path.endswith(".wav")
    assert generated.generated_duration == 4
    assert generated.speed == 1
    assert generated.pitch == 0
    assert generated.status.value == "ready"
    restored = projects.open_project(root).episode(episode.id).dub_segments[0]
    assert restored.id == generated.id
    assert (root / restored.audio_path).is_file()
