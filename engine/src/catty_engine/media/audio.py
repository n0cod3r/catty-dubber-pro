from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class AudioAssetKind(StrEnum):
    SPEECH = "speech"
    MASTER = "master"
    BACKGROUND = "background"
    DIALOGUE = "dialogue"
    DUB = "dub"


class AudioAsset(BaseModel):
    path: str
    kind: AudioAssetKind

    sample_rate: int
    channels: int

    source_fingerprint: str

    created_at: datetime = Field(default_factory=utc_now)
