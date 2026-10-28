from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from catty_engine.progress import emit_tts_progress
from catty_engine.project import ProjectService
from catty_engine.tts.service import TTSGenerationCancelled, TTSService


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


def list_voices(params: dict[str, Any]) -> list[dict[str, str]]:
    TTSVoicesParams.model_validate(params)
    return TTSService().list_edge_voices()


def ensure_voice(params: dict[str, Any]) -> dict[str, Any]:
    parsed = TTSEnsureVoiceParams.model_validate(params)
    return TTSService().ensure_edge_voice_profile(
        parsed.project_directory, voice_id=parsed.voice_id, name=parsed.name
    ).model_dump(mode="json")


def preview(params: dict[str, Any]) -> dict[str, str]:
    parsed = TTSPreviewParams.model_validate(params)
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

    def progress(phase, completed, total, segment_id, segment) -> None:
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
                if phase in {"saved", "completed", "cancelled"}
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
        # Cancellation is a successful partial operation: already generated
        # segments remain durable and the caller receives the latest episode.
        pass
    return _episode(parsed.project_directory, parsed.episode_id) or {}
