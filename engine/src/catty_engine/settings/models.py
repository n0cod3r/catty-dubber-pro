"""Application-level settings models (never stored inside project.json)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


TranslationProviderId = Literal["local", "gemini", "deepseek", "google", "baidu", "openai_compatible"]
TranslationStyle = Literal["natural_dubbing", "literal", "short_conversational"]
ComputeDevice = Literal["auto", "cpu", "cuda", "mps"]
PROVIDER_IDS: tuple[TranslationProviderId, ...] = ("local", "gemini", "deepseek", "google", "baidu", "openai_compatible")


class LocalProviderSettings(SettingsModel):
    selected_model: str | None = None


class CloudProviderSettings(SettingsModel):
    selected_model: str | None = None
    credential_ids: list[str] = Field(default_factory=list)


class GeminiProviderSettings(CloudProviderSettings):
    pass


class OpenAiCompatibleSettings(CloudProviderSettings):
    base_url: str = ""


class TranslationProviders(SettingsModel):
    local: LocalProviderSettings = Field(default_factory=LocalProviderSettings)
    gemini: GeminiProviderSettings = Field(default_factory=GeminiProviderSettings)
    deepseek: CloudProviderSettings = Field(default_factory=CloudProviderSettings)
    google: CloudProviderSettings = Field(default_factory=CloudProviderSettings)
    baidu: CloudProviderSettings = Field(default_factory=CloudProviderSettings)
    openai_compatible: OpenAiCompatibleSettings = Field(default_factory=OpenAiCompatibleSettings)


class TranslationSettings(SettingsModel):
    provider: TranslationProviderId = "local"
    target_language: str = "km"
    style: TranslationStyle = "natural_dubbing"
    use_context: bool = True
    use_speaker_context: bool = True
    duration_aware: bool = True
    providers: TranslationProviders = Field(default_factory=TranslationProviders)


class GeneralSettings(SettingsModel):
    language: str = "km"
    follow_playhead: bool = True


class TtsSettings(SettingsModel):
    engine: Literal["edge", "voxcpm2"] = "edge"
    voice: str | None = None


class VoiceCloneSettings(SettingsModel):
    model: str = "VoxCPM2"
    reference_audio: str | None = None


class PerformanceSettings(SettingsModel):
    device: ComputeDevice = "auto"
    cpu_threads: int | None = Field(default=None, ge=1, le=32)


class StorageSettings(SettingsModel):
    projects_directory: str | None = None
    models_directory: str | None = None
    exports_directory: str | None = None


class AppSettings(SettingsModel):
    schema_version: int = 1
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    translation: TranslationSettings = Field(default_factory=TranslationSettings)
    tts: TtsSettings = Field(default_factory=TtsSettings)
    voice_clone: VoiceCloneSettings = Field(default_factory=VoiceCloneSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
