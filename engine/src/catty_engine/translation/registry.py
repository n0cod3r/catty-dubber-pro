"""Translation provider registry and provider metadata."""

from __future__ import annotations

from catty_engine.settings.credentials import CredentialStore
from catty_engine.settings.models import AppSettings, TranslationProviderId

from .base import TranslationProvider
from .models import TranslationProviderInfo
from .providers.gemini import GeminiProvider
from .providers.other import ConfigurationOnlyProvider, LocalProvider

_PROVIDER_NAMES: dict[str, str] = {
    "local": "Local",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "google": "Google Cloud",
    "baidu": "Baidu",
    "openai_compatible": "OpenAI-compatible",
}


def provider_infos(settings: AppSettings, credentials: CredentialStore) -> list[TranslationProviderInfo]:
    result: list[TranslationProviderInfo] = []
    for provider_id, name in _PROVIDER_NAMES.items():
        provider_settings = getattr(settings.translation.providers, provider_id)
        result.append(
            TranslationProviderInfo(
                id=provider_id,
                name=name,
                offline=provider_id == "local",
                requires_credentials=provider_id != "local",
                supports_model_discovery=provider_id == "gemini",
                contextual=provider_id in {"gemini", "deepseek", "openai_compatible"},
                credential_configured=(
                    False if provider_id == "local" else credentials.has(provider_id)
                ),
                selected_model=provider_settings.selected_model,
            )
        )
    return result


def create_provider(
    provider_id: TranslationProviderId,
    settings: AppSettings,
    credentials: CredentialStore,
    *,
    temporary_credential: str | None = None,
) -> TranslationProvider:
    provider_settings = getattr(settings.translation.providers, provider_id)
    if provider_id == "local":
        return LocalProvider(provider_settings.selected_model)
    if provider_id == "gemini":
        return GeminiProvider(
            api_key=temporary_credential or credentials.get("gemini"),
            selected_model=provider_settings.selected_model,
        )
    return ConfigurationOnlyProvider(provider_id, _PROVIDER_NAMES[provider_id])
