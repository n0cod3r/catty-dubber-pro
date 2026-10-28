"""Application voice library. Project copies remain self-contained."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from catty_engine.logging import logged_process
from catty_engine.media.ffmpeg import FFmpegRunner
from catty_engine.media.probe import MediaProbeService
from catty_engine.project import ProjectService
from catty_engine.project.models import VoiceEngine, VoiceProfile
from catty_engine.settings.paths import app_data_dir
from .edge import EdgeTTSProvider
from .voxcpm import VoxCPM2Provider

SAMPLE_TEXT = "សួស្តី! ថ្ងៃនេះខ្ញុំរីករាយណាស់ដែលបានជួបអ្នក។ តើយើងទៅផ្ទះជាមួយគ្នាបានទេ?"


class VoiceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    engine: Literal["edge", "voxcpm2"]
    gender: str = ""
    engine_voice_id: str | None = None
    speed: float = Field(default=1.25, ge=0.5, le=2)
    pitch: int = Field(default=0, ge=-100, le=100)
    volume: int = Field(default=0, ge=-100, le=100)
    reference_audio_path: str | None = None
    reference_text: str | None = Field(default=None, max_length=10000)
    style_prompt: str = Field(default="", max_length=2000)
    base_voice_id: str | None = None

    @model_validator(mode="after")
    def validate_voice(self) -> VoiceDraft:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Enter a voice name")
        if self.engine == "edge" and self.engine_voice_id not in {"km-KH-PisethNeural", "km-KH-SreymomNeural"}:
            raise ValueError("Select Piseth or Sreymom for an Edge voice")
        if self.engine == "voxcpm2" and (self.speed != 1 or self.pitch != 0 or self.volume != 0):
            raise ValueError("VoxCPM2 uses style instructions, not Edge pitch/speed/volume controls")
        return self


class LibraryVoice(VoiceDraft):
    id: str
    origin: Literal["builtin", "user"]


def builtins() -> list[LibraryVoice]:
    roles = [("man", "Man", "male", 0, "An adult man with a clear, warm voice"),
        ("woman", "Woman", "female", 0, "An adult woman with a clear, warm voice"),
        ("girl", "Girl", "female", 20, "A young woman with a bright, gentle voice"),
        ("small-girl", "Small Girl", "female", 30, "A little girl with a light, youthful voice"),
        ("old-man", "Old Man", "male", -20, "An elderly man with a low, mature voice"),
        ("old-woman", "Old Woman", "female", -20, "An elderly woman with a mature, slightly husky voice")]
    result = []
    for engine in ("edge", "voxcpm2"):
        for key, name, gender, pitch, style in roles:
            result.append(LibraryVoice(id=f"builtin-{engine}-{key}", origin="builtin", name=name,
                engine=engine, gender=gender, engine_voice_id=("km-KH-PisethNeural" if gender == "male" else "km-KH-SreymomNeural") if engine == "edge" else None,
                speed=1.25 if engine == "edge" else 1, pitch=pitch if engine == "edge" else 0,
                style_prompt=style if engine == "voxcpm2" else ""))
    return result


class VoiceLibrary:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_data_dir() / "voices"

    def list(self) -> list[LibraryVoice]:
        voices = builtins()
        for manifest in sorted((self.root / "user").glob("*/profile.json")):
            voices.append(LibraryVoice.model_validate_json(manifest.read_text(encoding="utf-8")))
        return voices

    def get(self, voice_id: str) -> LibraryVoice:
        for voice in self.list():
            if voice.id == voice_id:
                return voice
        raise ValueError("Voice profile was not found in the library")

    def _reference(self, draft: VoiceDraft, folder: Path) -> Path:
        target = folder / "reference.wav"
        if draft.reference_audio_path:
            source = Path(draft.reference_audio_path).expanduser().resolve()
            info = MediaProbeService().probe(source)
            if not info.audio_codec or not info.duration or not 3 <= info.duration <= 30:
                raise ValueError("Choose a clear reference recording between 3 and 30 seconds")
            FFmpegRunner().extract_speech_audio(source, target)
        elif draft.base_voice_id:
            base = self.get(draft.base_voice_id)
            if base.engine != "voxcpm2":
                raise ValueError("Choose a VoxCPM2 base voice")
            source = self._builtin_reference(base) if base.origin == "builtin" else Path(base.reference_audio_path or "")
            if not source.is_file():
                raise ValueError("Base voice reference is missing")
            shutil.copy2(source, target)
        elif draft.style_prompt.strip():
            VoxCPM2Provider().synthesize(SAMPLE_TEXT, target, style=draft.style_prompt)
        else:
            raise ValueError("Import reference audio, choose a base voice, or describe a voice")
        return target

    def _builtin_reference(self, voice: LibraryVoice) -> Path:
        folder = self.root / "builtin" / voice.id
        target = folder / "reference.wav"
        if not target.is_file():
            folder.mkdir(parents=True, exist_ok=True)
            temporary = folder / f".{uuid4()}.wav"
            try:
                VoxCPM2Provider().synthesize(SAMPLE_TEXT, temporary, style=voice.style_prompt)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        return target

    @logged_process
    def create(self, draft: VoiceDraft) -> LibraryVoice:
        voice_id = str(uuid4())
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / "user" / voice_id
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.root) as temporary:
            folder = Path(temporary)
            voice = LibraryVoice(**draft.model_dump(), id=voice_id, origin="user")
            if voice.engine == "voxcpm2":
                self._reference(draft, folder)
                voice.reference_audio_path = str(destination / "reference.wav")
                if draft.base_voice_id:
                    # A base reference has its own transcript, never a user's unrelated text.
                    voice.reference_text = None
            else:
                voice.reference_audio_path = None
                voice.reference_text = None
            voice.base_voice_id = None
            (folder / "profile.json").write_text(voice.model_dump_json(indent=2), encoding="utf-8")
            folder.replace(destination)
        return voice

    @logged_process
    def preview(self, *, voice_id: str | None = None, draft: VoiceDraft | None = None, text: str = SAMPLE_TEXT) -> Path:
        voice = self.get(voice_id) if voice_id else draft
        if voice is None:
            raise ValueError("Choose or create a voice")
        folder = self.root / "previews"
        folder.mkdir(parents=True, exist_ok=True)
        if isinstance(voice, LibraryVoice) and voice.origin == "builtin" and text == SAMPLE_TEXT:
            if voice.engine == "voxcpm2":
                return self._builtin_reference(voice)
            output = folder / f"{voice.id}.mp3"
            if output.is_file():
                return output
        else:
            output = folder / f"{uuid4()}.{'mp3' if voice.engine == 'edge' else 'wav'}"
        if voice.engine == "edge":
            return EdgeTTSProvider().synthesize(text, output, voice=voice.engine_voice_id or "",
                speed=voice.speed, pitch=voice.pitch, volume=voice.volume)
        if isinstance(voice, LibraryVoice):
            reference = self._builtin_reference(voice) if voice.origin == "builtin" else Path(voice.reference_audio_path or "")
            return VoxCPM2Provider().synthesize(text, output, reference=reference,
                reference_text=voice.reference_text, style=voice.style_prompt)
        with tempfile.TemporaryDirectory(dir=self.root) as temporary:
            reference = self._reference(voice, Path(temporary))
            return VoxCPM2Provider().synthesize(text, output, reference=reference,
                reference_text=voice.reference_text if voice.reference_audio_path else None, style=voice.style_prompt)

    def remove(self, voice_id: str) -> None:
        voice = self.get(voice_id)
        if voice.origin != "user":
            raise ValueError("Built-in voices cannot be removed")
        trash = self.root / "trash"
        trash.mkdir(parents=True, exist_ok=True)
        (self.root / "user" / str(UUID(voice.id))).replace(trash / str(UUID(voice.id)))

    @logged_process
    def use_in_project(self, voice_id: str, project_directory: Path) -> VoiceProfile:
        voice = self.get(voice_id)
        reference = None
        if voice.engine == "voxcpm2":
            source = self._builtin_reference(voice) if voice.origin == "builtin" else Path(voice.reference_audio_path or "")
            if not source.is_file():
                raise ValueError("Voice reference is missing")
            destination = project_directory / "assets" / "voices" / voice.id / "reference.wav"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            reference = str(destination.relative_to(project_directory))
        projects = ProjectService()
        project = projects.open_project(project_directory)
        existing = next((item for item in project.voice_profiles if item.library_voice_id == voice.id), None)
        if existing:
            return existing
        profile = VoiceProfile(name=voice.name, engine=VoiceEngine(voice.engine), engine_voice_id=voice.engine_voice_id,
            reference_audio_path=reference, reference_text=voice.reference_text, style_prompt=voice.style_prompt,
            library_voice_id=voice.id, speed=voice.speed, pitch=voice.pitch, volume=voice.volume)
        project.voice_profiles.append(profile)
        projects.save_project(project_directory, project)
        return profile
