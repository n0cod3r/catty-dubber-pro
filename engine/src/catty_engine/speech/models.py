from __future__ import annotations

from pydantic import BaseModel, Field


class SpeechRegion(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    confidence: float | None = Field(default=None, ge=0, le=1)


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class TranscriptionResult(BaseModel):
    backend: str
    model: str
    language: str
    segments: list[TranscriptSegment]
