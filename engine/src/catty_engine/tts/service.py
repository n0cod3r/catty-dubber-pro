from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from catty_engine.project import ProjectService
from catty_engine.project.models import DubSegment, DubStatus, ProcessingStatus, VoiceEngine
from catty_engine.tts.edge import EdgeTTSProvider


class TTSService:
    def __init__(self, edge: EdgeTTSProvider | None = None) -> None:
        self.edge = edge or EdgeTTSProvider()

    def generate_segment(
        self,
        project_directory: Path,
        episode_id: UUID,
        dialogue_segment_id: UUID,
        voice_profile_id: UUID,
        *,
        speed: float = 1.0,
        pitch: int = 0,
        volume: int = 0,
    ) -> DubSegment:
        projects = ProjectService()
        project = projects.open_project(project_directory)
        episode = project.episode(episode_id)
        if episode is None:
            raise ValueError("Episode not found")
        dialogue = next(
            (item for item in episode.dialogue_segments if item.id == dialogue_segment_id),
            None,
        )
        if dialogue is None:
            raise ValueError("Dialogue segment not found")
        if dialogue.translation is None or not dialogue.translation.text.strip():
            raise ValueError("Dialogue segment has no Khmer translation")
        voice = project.voice_profile(voice_profile_id)
        if voice is None:
            raise ValueError("Voice profile not found")
        if voice.engine is not VoiceEngine.EDGE:
            raise ValueError("This TTS provider only supports Edge voice profiles")
        if not voice.engine_voice_id:
            raise ValueError("Edge voice profile has no engine voice id")

        existing = next(
            (item for item in episode.dub_segments if item.dialogue_segment_id == dialogue.id),
            None,
        )
        dub = existing or DubSegment(
            dialogue_segment_id=dialogue.id,
            voice_profile_id=voice.id,
            target_duration=dialogue.duration,
        )
        dub.voice_profile_id = voice.id
        dub.target_duration = dialogue.duration
        dub.speed = speed
        dub.pitch = pitch
        dub.volume = volume
        dub.status = DubStatus.GENERATING
        if existing is None:
            episode.dub_segments.append(dub)
        episode.processing.dubbing = ProcessingStatus.PROCESSING
        projects.save_project(project_directory, project)

        output = (
            project_directory
            / "assets"
            / "dubbing"
            / str(episode.id)
            / f"{dialogue.id}.mp3"
        )
        try:
            self.edge.synthesize(
                dialogue.translation.text,
                output,
                voice=voice.engine_voice_id,
                speed=speed,
                pitch=pitch,
                volume=volume,
            )
        except Exception:
            project = projects.open_project(project_directory)
            episode = project.episode(episode_id)
            if episode is not None:
                current = next(
                    (item for item in episode.dub_segments if item.id == dub.id), None
                )
                if current is not None:
                    current.status = DubStatus.FAILED
                episode.processing.dubbing = ProcessingStatus.FAILED
                projects.save_project(project_directory, project)
            raise

        project = projects.open_project(project_directory)
        episode = project.episode(episode_id)
        if episode is None:
            raise ValueError("Episode disappeared while generating dubbing")
        current = next(item for item in episode.dub_segments if item.id == dub.id)
        current.audio_path = str(output.relative_to(project_directory))
        current.status = DubStatus.READY
        current.generated_at = datetime.now(UTC)
        current.generated_duration = None
        if all(item.status is DubStatus.READY for item in episode.dub_segments):
            episode.processing.dubbing = ProcessingStatus.COMPLETED
        projects.save_project(project_directory, project)
        return current

    def preview(
        self,
        project_directory: Path,
        text: str,
        voice_id: str,
        *,
        speed: float = 1.0,
        pitch: int = 0,
        volume: int = 0,
    ) -> Path:
        output = project_directory / "cache" / "tts-preview.mp3"
        return self.edge.synthesize(
            text,
            output,
            voice=voice_id,
            speed=speed,
            pitch=pitch,
            volume=volume,
        )
