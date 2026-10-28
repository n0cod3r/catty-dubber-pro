"""Translation provider registry and provider metadata."""

from __future__ import annotations

from catty_engine.settings.credentials import CredentialStore, DEFAULT_CREDENTIAL_ID
from catty_engine.settings.models import AppSettings, PROVIDER_IDS, TranslationProviderId

from .base import TranslationProvider
from .models import TranslationProviderInfo
from .providers.gemini import GeminiProvider
from .providers.other import ConfigurationOnlyProvider, LocalProvider

_PROVIDER_NAMES: dict[TranslationProviderId, str] = {
    "local": "Local",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "google": "Google Cloud",
    "baidu": "Baidu",
    "openai_compatible": "OpenAI-compatible",
}


def credential_ids(
    provider_id: TranslationProviderId,
    settings: AppSettings,
    credentials: CredentialStore,
) -> list[str]:
    if provider_id == "local":
        return []
    configured = list(getattr(settings.translation.providers, provider_id).credential_ids)
    if (
        credentials.has(provider_id, DEFAULT_CREDENTIAL_ID)
        and DEFAULT_CREDENTIAL_ID not in configured
    ):
        configured.insert(0, DEFAULT_CREDENTIAL_ID)
    return configured


def provider_infos(
    settings: AppSettings, credentials: CredentialStore
) -> list[TranslationProviderInfo]:
    result: list[TranslationProviderInfo] = []
    for provider_id in PROVIDER_IDS:
        name = _PROVIDER_NAMES[provider_id]
        provider_settings = getattr(settings.translation.providers, provider_id)
        result.append(
            TranslationProviderInfo(
                id=provider_id,
                name=name,
                offline=provider_id == "local",
                requires_credentials=provider_id != "local",
                supports_model_discovery=provider_id == "gemini",
                contextual=provider_id
                in {"gemini", "deepseek", "openai_compatible"},
                credential_configured=bool(
                    credential_ids(provider_id, settings, credentials)
                ),
                selected_model=provider_settings.selected_model,
            )
        )
    return result


def create_provider(
    provider_id: TranslationProviderId,
    settings: AppSettings,
    *,
    credential: str | None = None,
) -> TranslationProvider:
    provider_settings = getattr(settings.translation.providers, provider_id)
    if provider_id == "local":
        return LocalProvider(provider_settings.selected_model)
    if provider_id == "gemini":
        return GeminiProvider(
            api_key=credential,
            selected_model=provider_settings.selected_model,
        )
    return ConfigurationOnlyProvider(provider_id, _PROVIDER_NAMES[provider_id])
