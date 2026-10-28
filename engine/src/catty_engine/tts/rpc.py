from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from catty_engine.progress import emit_tts_progress
from catty_engine.project import ProjectService
from catty_engine.tts.service import TTSGenerationCancelled, TTSService
from catty_engine.tts.edge import EdgeTTSError
import logging


class TTSVoicesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TTSEnsureVoiceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    voice_id: str = Field(min_length=1)
    name: str | None = None


class TTSGenerateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str | None = Field(default=None, min_length=1, max_length=128)
    project_directory: Path
    episode_id: UUID
    voice_profile_id: UUID
    mode: Literal["missing", "all", "selected"] = "missing"
    segment_ids: list[UUID] = Field(default_factory=list)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: int = Field(default=0, ge=-100, le=100)
    volume: int = Field(default=0, ge=-100, le=100)
    cancel_file: Path | None = None
    assign_speaker_id: UUID | None = None
    assign_only: bool = False

    @model_validator(mode="after")
    def validate_assignment(self) -> TTSGenerateParams:
        if self.assign_only and self.assign_speaker_id is None:
            raise ValueError("assign_only requires assign_speaker_id")
        return self


class TTSAssignSegmentVoiceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    episode_id: UUID
    segment_id: UUID
    voice_profile_id: UUID | None = None


class TTSPreviewParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    text: str = Field(min_length=1, max_length=100000)
    voice_id: str = Field(min_length=1)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: int = Field(default=0, ge=-100, le=100)
    volume: int = Field(default=0, ge=-100, le=100)


def _episode(project_directory: Path, episode_id: UUID) -> dict[str, Any] | None:
    project = ProjectService().open_project(project_directory)
    episode = project.episode(episode_id)
    return episode.model_dump(mode="json") if episode is not None else None


def list_voices(params: dict[str, Any]) -> list[dict[str, Any]]:
    TTSVoicesParams.model_validate(params)
    from .library import VoiceLibrary
    try:
        voices: list[dict[str, Any]] = [dict(item) for item in TTSService().list_edge_voices()]
    except EdgeTTSError:
        logging.getLogger(__name__).warning("Edge voice discovery unavailable; local voice library remains available")
        voices = []
    for voice in VoiceLibrary().list():
        voices.append({"id": f"library:{voice.id}", "name": f"{'Built-in' if voice.origin == 'builtin' else 'My voices'} · {voice.name} ({voice.engine})",
            "locale": "km-KH", "gender": voice.gender, "engine": voice.engine,
            "tuning": {"speed": voice.speed, "pitch": voice.pitch, "volume": voice.volume}})
    return voices


def ensure_voice(params: dict[str, Any]) -> dict[str, Any]:
    parsed = TTSEnsureVoiceParams.model_validate(params)
    if parsed.voice_id.startswith("library:"):
        from .library import VoiceLibrary
        return VoiceLibrary().use_in_project(parsed.voice_id.removeprefix("library:"), parsed.project_directory).model_dump(mode="json")
    return TTSService().ensure_edge_voice_profile(
        parsed.project_directory, voice_id=parsed.voice_id, name=parsed.name
    ).model_dump(mode="json")


def assign_segment_voice(params: dict[str, Any]) -> dict[str, Any]:
    parsed = TTSAssignSegmentVoiceParams.model_validate(params)
    episode = TTSService().assign_segment_voice(
        parsed.project_directory,
        parsed.episode_id,
        parsed.segment_id,
        parsed.voice_profile_id,
    )
    return episode.model_dump(mode="json")


def preview(params: dict[str, Any]) -> dict[str, str]:
    parsed = TTSPreviewParams.model_validate(params)
    if parsed.voice_id.startswith("library:"):
        from .library import VoiceLibrary
        return {"path": str(VoiceLibrary().preview(voice_id=parsed.voice_id.removeprefix("library:"), text=parsed.text))}
    output = TTSService().preview(
        parsed.project_directory,
        parsed.text,
        parsed.voice_id,
        speed=parsed.speed,
        pitch=parsed.pitch,
        volume=parsed.volume,
    )
    return {"path": str(output)}


def generate(params: dict[str, Any]) -> dict[str, Any]:
    parsed = TTSGenerateParams.model_validate(params)
    service = TTSService()

    if parsed.assign_speaker_id is not None:
        episode = service.assign_speaker_voice(
            parsed.project_directory,
            parsed.episode_id,
            parsed.assign_speaker_id,
            parsed.voice_profile_id,
        )
        if parsed.assign_only:
            return episode.model_dump(mode="json")

    last_completed = 0
    last_total = 0

    def progress(phase, completed, total, segment_id, segment) -> None:
        nonlocal last_completed, last_total
        last_completed, last_total = completed, total
        if parsed.operation_id is None:
            return
        emit_tts_progress(
            {
                "operation_id": parsed.operation_id,
                "project_directory": str(parsed.project_directory),
                "episode_id": str(parsed.episode_id),
                "phase": phase,
                "completed": completed,
                "total": total,
                "segment_id": str(segment_id) if segment_id else None,
                "segment": segment.model_dump(mode="json") if segment else None,
                "episode": _episode(parsed.project_directory, parsed.episode_id)
                if phase in {"saved", "completed", "cancelled", "failed"}
                else None,
            }
        )

    try:
        service.generate_episode(
            parsed.project_directory,
            parsed.episode_id,
            parsed.voice_profile_id,
            mode=parsed.mode,
            segment_ids=set(parsed.segment_ids),
            speed=parsed.speed,
            pitch=parsed.pitch,
            volume=parsed.volume,
            cancel_file=parsed.cancel_file,
            on_progress=progress,
        )
    except TTSGenerationCancelled:
        pass
    except Exception:
        progress("failed", last_completed, last_total, None, None)
        raise
    return _episode(parsed.project_directory, parsed.episode_id) or {}
