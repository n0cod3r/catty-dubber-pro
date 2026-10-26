from __future__ import annotations

from pydantic import BaseModel


class MediaInfo(BaseModel):
    source_path: str

    duration: float | None = None

    width: int | None = None
    height: int | None = None
    fps: float | None = None

    video_codec: str | None = None
    audio_codec: str | None = None

    sample_rate: int | None = None
    channels: int | None = None