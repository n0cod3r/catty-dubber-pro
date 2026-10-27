"""RPC-facing application settings operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from catty_engine.translation.registry import create_provider, provider_infos

from .credentials import CredentialStore
from .models import AppSettings, PROVIDER_IDS, TranslationProviderId
from .service import SettingsService


class SettingsUpdateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: AppSettings
    credentials: dict[str, str | None] = Field(default_factory=dict)


class ProviderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: TranslationProviderId
    credential: str | None = None


def _stores() -> tuple[SettingsService, CredentialStore]:
    return SettingsService(), CredentialStore()


def snapshot() -> dict[str, Any]:
    service, credentials = _stores()
    settings = service.get()
    return {
        "settings": settings.model_dump(mode="json"),
        "credentials": {
            provider_id: credentials.has(provider_id)
            for provider_id in PROVIDER_IDS
            if provider_id != "local"
        },
    }


def update(params: dict[str, Any]) -> dict[str, Any]:
    parsed = SettingsUpdateParams.model_validate(params)
    service, credentials = _stores()
    # Validate the complete settings object before changing credentials.
    service.update(parsed.settings.model_dump(mode="json"))
    for provider_id, secret in parsed.credentials.items():
        if provider_id not in PROVIDER_IDS or provider_id == "local":
            raise ValueError(f"Unsupported credential provider: {provider_id}")
        if secret is None:
            credentials.delete(provider_id)
        elif secret.strip():
            credentials.set(provider_id, secret)
    return snapshot()


def providers() -> list[dict[str, Any]]:
    service, credentials = _stores()
    return [
        item.model_dump(mode="json")
        for item in provider_infos(service.get(), credentials)
    ]


def models(params: dict[str, Any]) -> list[dict[str, Any]]:
    parsed = ProviderParams.model_validate(params)
    service, credentials = _stores()
    provider = create_provider(
        parsed.provider,
        service.get(),
        credentials,
        temporary_credential=parsed.credential,
    )
    return [item.model_dump(mode="json") for item in provider.list_models()]


def test_connection(params: dict[str, Any]) -> dict[str, Any]:
    parsed = ProviderParams.model_validate(params)
    service, credentials = _stores()
    provider = create_provider(
        parsed.provider,
        service.get(),
        credentials,
        temporary_credential=parsed.credential,
    )
    return provider.test_connection().model_dump(mode="json")
