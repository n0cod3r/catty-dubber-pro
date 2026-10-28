"""Provider-facing translation types and contextual batch contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TranslationModel(BaseModel):
    id: str
    name: str
    description: str | None = None


class TranslationProviderInfo(BaseModel):
    id: str
    name: str
    offline: bool
    requires_credentials: bool
    supports_model_discovery: bool
    contextual: bool
    credential_configured: bool = False
    selected_model: str | None = None


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str


class GlossaryTerm(BaseModel):
    source: str
    target: str
    note: str | None = None


class TranslationContextLine(BaseModel):
    id: str
    text: str
    speaker: str | None = None


class TranslationInput(BaseModel):
    id: str
    text: str
    speaker: str | None = None
    previous: list[TranslationContextLine] = Field(default_factory=list)
    next: list[TranslationContextLine] = Field(default_factory=list)
    # Full source utterance reconstructed from adjacent ASR fragments. The
    # provider still translates only `text` for this original timed row.
    semantic_context: str | None = None


class TranslationBatchRequest(BaseModel):
    source_language: str = "zh"
    target_language: str = "km"
    style: str = "natural_dubbing"
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    custom_instructions: str | None = None
    use_context: bool = True
    use_speaker_context: bool = True
    segments: list[TranslationInput]


class TranslationOutput(BaseModel):
    id: str
    text: str


class TranslationBatchResult(BaseModel):
    provider: str
    model: str
    segments: list[TranslationOutput]
