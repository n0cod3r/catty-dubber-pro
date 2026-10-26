from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from catty_engine.media.models import MediaInfo

SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProcessingStatus(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DubStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    OUTDATED = "outdated"
    FAILED = "failed"


class TranslationStatus(StrEnum):
    PENDING = "pending"
    TRANSLATED = "translated"
    EDITED = "edited"
    FAILED = "failed"


class VoiceEngine(StrEnum):
    EDGE = "edge"
    VOXCPM2 = "voxcpm2"

class Translation(BaseModel):
    language: str = "km"
    text: str = ""

    status: TranslationStatus = TranslationStatus.PENDING

    provider: str | None = None
    manually_edited: bool = False


class DialogueSegment(BaseModel):
    id: UUID = Field(default_factory=uuid4)

    start: float
    end: float

    speaker_id: UUID | None = None

    source_language: str
    source_text: str

    confidence: float | None = None

    translation: Translation | None = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_timing(self) -> DialogueSegment:
        if self.start < 0:
            raise ValueError("segment start cannot be negative")

        if self.end <= self.start:
            raise ValueError("segment end must be greater than start")

        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


class EpisodeSpeaker(BaseModel):
    id: UUID = Field(default_factory=uuid4)

    name: str

    character_id: UUID | None = None

    segment_ids: list[UUID] = Field(default_factory=list)


class Character(BaseModel):
    """
    Project-level character.

    Episode speakers may be mapped to the same character across
    multiple episodes.
    """

    id: UUID = Field(default_factory=uuid4)

    name: str

    voice_profile_id: UUID | None = None

    created_at: datetime = Field(default_factory=utc_now)


class VoiceProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)

    name: str

    engine: VoiceEngine
    language: str = "km-KH"

    engine_voice_id: str | None = None

    reference_audio_path: str | None = None

    created_at: datetime = Field(default_factory=utc_now)


class DubSegment(BaseModel):
    id: UUID = Field(default_factory=uuid4)

    dialogue_segment_id: UUID

    voice_profile_id: UUID

    audio_path: str | None = None

    generated_duration: float | None = None
    target_duration: float

    status: DubStatus = DubStatus.PENDING

    generated_at: datetime | None = None


class EpisodeProcessingState(BaseModel):
    media: ProcessingStatus = ProcessingStatus.IDLE
    transcription: ProcessingStatus = ProcessingStatus.IDLE
    speakers: ProcessingStatus = ProcessingStatus.IDLE
    translation: ProcessingStatus = ProcessingStatus.IDLE
    dubbing: ProcessingStatus = ProcessingStatus.IDLE
    separation: ProcessingStatus = ProcessingStatus.IDLE
    mixing: ProcessingStatus = ProcessingStatus.IDLE


class Episode(BaseModel):
    id: UUID = Field(default_factory=uuid4)

    name: str
    order: int

    media: MediaInfo

    speakers: list[EpisodeSpeaker] = Field(default_factory=list)
    dialogue_segments: list[DialogueSegment] = Field(default_factory=list)
    dub_segments: list[DubSegment] = Field(default_factory=list)

    processing: EpisodeProcessingState = Field(
        default_factory=EpisodeProcessingState
    )

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GlossaryEntry(BaseModel):
    source: str
    target: str

    note: str | None = None


class TranslationProfile(BaseModel):
    source_language: str = "zh"
    target_language: str = "km"

    style: str = "natural"

    glossary: list[GlossaryEntry] = Field(default_factory=list)


class ProjectSettings(BaseModel):
    translation: TranslationProfile = Field(
        default_factory=TranslationProfile
    )


class Project(BaseModel):
    schema_version: int = SCHEMA_VERSION

    id: UUID = Field(default_factory=uuid4)

    name: str

    episodes: list[Episode] = Field(default_factory=list)

    characters: list[Character] = Field(default_factory=list)
    voice_profiles: list[VoiceProfile] = Field(default_factory=list)

    settings: ProjectSettings = Field(default_factory=ProjectSettings)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def episode(self, episode_id: UUID) -> Episode | None:
        return next(
            (
                episode
                for episode in self.episodes
                if episode.id == episode_id
            ),
            None,
        )

    def character(self, character_id: UUID) -> Character | None:
        return next(
            (
                character
                for character in self.characters
                if character.id == character_id
            ),
            None,
        )

    def voice_profile(
        self,
        voice_profile_id: UUID,
    ) -> VoiceProfile | None:
        return next(
            (
                voice
                for voice in self.voice_profiles
                if voice.id == voice_profile_id
            ),
            None,
        )

    def add_episode(self, source_path: str) -> Episode:
        path = Path(source_path)

        episode = Episode(
            name=path.stem,
            order=len(self.episodes),
            media=MediaInfo(
                source_path=str(path),
            ),
        )

        self.episodes.append(episode)
        self.updated_at = utc_now()

        return episode