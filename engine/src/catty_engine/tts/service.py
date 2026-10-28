from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Literal
from uuid import UUID, uuid4

from catty_engine.project import ProjectService
from catty_engine.project.models import (
    DubSegment,
    DubStatus,
    Episode,
    ProcessingStatus,
    VoiceEngine,
    VoiceProfile,
)
from catty_engine.tts.edge import EdgeTTSProvider

GenerationMode = Literal["missing", "all", "selected"]
ProgressCallback = Callable[[str, int, int, UUID | None, DubSegment | None], None]


class TTSGenerationCancelled(RuntimeError):
    """Raised between segments when the user cancels a dubbing batch."""


class TTSService:
    def __init__(self, edge: EdgeTTSProvider | None = None) -> None:
        self.edge = edge or EdgeTTSProvider()

    def list_edge_voices(self) -> list[dict[str, str]]:
        return self.edge.list_voices()

    def ensure_edge_voice_profile(
        self,
        project_directory: Path,
        *,
        voice_id: str,
        name: str | None = None,
    ) -> VoiceProfile:
        voice_id = voice_id.strip()
        if not voice_id:
            raise ValueError("Edge voice id cannot be empty")
        projects = ProjectService()
        project = projects.open_project(project_directory)
        existing = next(
            (
                voice
                for voice in project.voice_profiles
                if voice.engine is VoiceEngine.EDGE
                and voice.engine_voice_id == voice_id
            ),
            None,
        )
        if existing is not None:
            return existing
        profile = VoiceProfile(
            name=(name or voice_id).strip() or voice_id,
            engine=VoiceEngine.EDGE,
            language="km-KH",
            engine_voice_id=voice_id,
        )
        project.voice_profiles.append(profile)
        projects.save_project(project_directory, project)
        return profile

    def assign_speaker_voice(
        self,
        project_directory: Path,
        episode_id: UUID,
        speaker_id: UUID,
        voice_profile_id: UUID,
    ) -> Episode:
        projects = ProjectService()
        project = projects.open_project(project_directory)
        episode = project.episode(episode_id)
        if episode is None:
            raise ValueError("Episode not found")
        speaker = next((item for item in episode.speakers if item.id == speaker_id), None)
        if speaker is None:
            raise ValueError("Speaker not found")
        if project.voice_profile(voice_profile_id) is None:
            raise ValueError("Voice profile not found")
        if speaker.voice_profile_id == voice_profile_id:
            return episode
        speaker.voice_profile_id = voice_profile_id
        affected = set(speaker.segment_ids)
        for dub in episode.dub_segments:
            if dub.dialogue_segment_id in affected and dub.status is DubStatus.READY:
                dub.status = DubStatus.OUTDATED
        episode.processing.dubbing = ProcessingStatus.IDLE
        projects.save_project(project_directory, project)
        return episode

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
            (
                item
                for item in episode.dub_segments
                if item.dialogue_segment_id == dialogue.id
            ),
            None,
        )
        old_status = existing.status if existing else None
        old_audio_path = existing.audio_path if existing else None
        old_generated_at = existing.generated_at if existing else None
        old_generated_duration = existing.generated_duration if existing else None
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
        temp_output = output.with_name(f".{output.stem}.{uuid4().hex}.tmp.mp3")
        try:
            self.edge.synthesize(
                dialogue.translation.text,
                temp_output,
                voice=voice.engine_voice_id,
                speed=speed,
                pitch=pitch,
                volume=volume,
            )
            if not temp_output.exists() or temp_output.stat().st_size == 0:
                raise RuntimeError("TTS provider produced no audio")
            output.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_output, output)
        except Exception:
            temp_output.unlink(missing_ok=True)
            project = projects.open_project(project_directory)
            episode = project.episode(episode_id)
            if episode is not None:
                current = next(
                    (item for item in episode.dub_segments if item.id == dub.id), None
                )
                if current is not None:
                    if old_audio_path:
                        current.audio_path = old_audio_path
                        current.generated_at = old_generated_at
                        current.generated_duration = old_generated_duration
                        current.status = old_status or DubStatus.READY
                    else:
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
        self._finalize_dubbing_status(episode)
        projects.save_project(project_directory, project)
        return current

    @staticmethod
    def _finalize_dubbing_status(episode: Episode) -> None:
        translated = [
            dialogue.id
            for dialogue in episode.dialogue_segments
            if dialogue.translation is not None
            and dialogue.translation.text.strip()
        ]
        ready = {
            dub.dialogue_segment_id
            for dub in episode.dub_segments
            if dub.status is DubStatus.READY
        }
        if translated and all(segment_id in ready for segment_id in translated):
            episode.processing.dubbing = ProcessingStatus.COMPLETED
        elif any(dub.status is DubStatus.FAILED for dub in episode.dub_segments):
            episode.processing.dubbing = ProcessingStatus.FAILED
        else:
            episode.processing.dubbing = ProcessingStatus.IDLE

    def generate_episode(
        self,
        project_directory: Path,
        episode_id: UUID,
        voice_profile_id: UUID,
        *,
        mode: GenerationMode = "missing",
        segment_ids: set[UUID] | None = None,
        speed: float = 1.0,
        pitch: int = 0,
        volume: int = 0,
        cancel_file: Path | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> list[DubSegment]:
        project = ProjectService().open_project(project_directory)
        episode = project.episode(episode_id)
        if episode is None:
            raise ValueError("Episode not found")
        selected = segment_ids or set()
        existing = {item.dialogue_segment_id: item for item in episode.dub_segments}
        targets: list[UUID] = []
        for dialogue in episode.dialogue_segments:
            if dialogue.translation is None or not dialogue.translation.text.strip():
                continue
            if mode == "selected" and dialogue.id not in selected:
                continue
            current = existing.get(dialogue.id)
            if mode == "missing" and current is not None and current.status is DubStatus.READY:
                continue
            targets.append(dialogue.id)
        if mode == "selected" and not selected:
            raise ValueError("Selected TTS generation requires at least one segment")

        total = len(targets)
        if on_progress is not None:
            on_progress("started", 0, total, None, None)
        results: list[DubSegment] = []
        for index, segment_id in enumerate(targets):
            if cancel_file is not None and cancel_file.exists():
                if on_progress is not None:
                    on_progress("cancelled", len(results), total, segment_id, None)
                raise TTSGenerationCancelled("Voice generation cancelled")
            if on_progress is not None:
                on_progress("generating", index, total, segment_id, None)
            latest = ProjectService().open_project(project_directory)
            latest_episode = latest.episode(episode_id)
            latest_dialogue = (
                next(
                    item
                    for item in latest_episode.dialogue_segments
                    if item.id == segment_id
                )
                if latest_episode is not None
                else None
            )
            assigned_voice = voice_profile_id
            if (
                latest_dialogue is not None
                and latest_dialogue.speaker_id is not None
                and latest_episode is not None
            ):
                speaker = next(
                    (
                        item
                        for item in latest_episode.speakers
                        if item.id == latest_dialogue.speaker_id
                    ),
                    None,
                )
                if speaker is not None and speaker.voice_profile_id is not None:
                    assigned_voice = speaker.voice_profile_id
            generated = self.generate_segment(
                project_directory,
                episode_id,
                segment_id,
                assigned_voice,
                speed=speed,
                pitch=pitch,
                volume=volume,
            )
            results.append(generated)
            if on_progress is not None:
                on_progress("saved", len(results), total, segment_id, generated)
        if on_progress is not None:
            on_progress("completed", len(results), total, None, None)
        return results

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
        output = project_directory / "cache" / "tts-preview" / f"{uuid4()}.mp3"
        return self.edge.synthesize(
            text,
            output,
            voice=voice_id,
            speed=speed,
            pitch=pitch,
            volume=volume,
        )
