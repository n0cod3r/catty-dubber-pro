"""RPC-facing application settings operations."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from catty_engine.translation.registry import create_provider, credential_ids, provider_infos

from .credentials import CredentialStore, DEFAULT_CREDENTIAL_ID
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


class CredentialAddParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: TranslationProviderId
    credential: str


class CredentialRemoveParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: TranslationProviderId
    credential_id: str


def _stores() -> tuple[SettingsService, CredentialStore]:
    return SettingsService(), CredentialStore()


def _credential_snapshot(settings: AppSettings, credentials: CredentialStore) -> dict[str, list[str]]:
    return {provider_id: credential_ids(provider_id, settings, credentials) for provider_id in PROVIDER_IDS if provider_id != "local"}


def snapshot() -> dict[str, Any]:
    service, credentials = _stores()
    settings = service.get()
    ids = _credential_snapshot(settings, credentials)
    return {
        "settings": settings.model_dump(mode="json"),
        "credentials": {provider_id: bool(values) for provider_id, values in ids.items()},
        "credential_ids": ids,
    }


def _replace_credentials(provider_id: TranslationProviderId, raw: str | None, settings: AppSettings, service: SettingsService, credentials: CredentialStore) -> None:
    provider_settings = getattr(settings.translation.providers, provider_id)
    existing = credential_ids(provider_id, settings, credentials)
    if raw is None:
        for credential_id in existing:
            credentials.delete(provider_id, credential_id)
        service.update({"translation": {"providers": {provider_id: {"credential_ids": []}}}})
        return
    secrets = [value.strip() for value in re.split(r"[\n,]+", raw) if value.strip()]
    if not secrets:
        return
    new_ids: list[str] = []
    for index, secret in enumerate(secrets):
        credential_id = DEFAULT_CREDENTIAL_ID if index == 0 else uuid4().hex[:12]
        credentials.set(provider_id, secret, credential_id)
        new_ids.append(credential_id)
    for credential_id in existing:
        if credential_id not in new_ids:
            credentials.delete(provider_id, credential_id)
    provider_settings.credential_ids = [value for value in new_ids if value != DEFAULT_CREDENTIAL_ID]
    service.update({"translation": {"providers": {provider_id: {"credential_ids": provider_settings.credential_ids}}}})


def update(params: dict[str, Any]) -> dict[str, Any]:
    parsed = SettingsUpdateParams.model_validate(params)
    service, credentials = _stores()
    settings = service.update(parsed.settings.model_dump(mode="json"))
    for provider_key, secret in parsed.credentials.items():
        provider_id = provider_key.split(":", 1)[0]
        if provider_id not in PROVIDER_IDS or provider_id == "local":
            raise ValueError(f"Unsupported credential provider: {provider_key}")
        _replace_credentials(provider_id, secret, settings, service, credentials)
    return snapshot()


def add_credential(params: dict[str, Any]) -> dict[str, Any]:
    parsed = CredentialAddParams.model_validate(params)
    if parsed.provider == "local":
        raise ValueError("Local translation does not use API credentials")
    secret = parsed.credential.strip()
    if not secret:
        raise ValueError("Credential must not be empty")

    service, credentials = _stores()
    settings = service.get()
    existing = credential_ids(parsed.provider, settings, credentials)
    credential_id = DEFAULT_CREDENTIAL_ID if not existing else uuid4().hex[:12]
    credentials.set(parsed.provider, secret, credential_id)

    if credential_id != DEFAULT_CREDENTIAL_ID:
        provider_settings = getattr(settings.translation.providers, parsed.provider)
        configured = list(provider_settings.credential_ids)
        if credential_id not in configured:
            configured.append(credential_id)
            service.update({"translation": {"providers": {parsed.provider: {"credential_ids": configured}}}})
    return snapshot()


def remove_credential(params: dict[str, Any]) -> dict[str, Any]:
    parsed = CredentialRemoveParams.model_validate(params)
    if parsed.provider == "local":
        raise ValueError("Local translation does not use API credentials")

    service, credentials = _stores()
    settings = service.get()
    existing = credential_ids(parsed.provider, settings, credentials)
    if parsed.credential_id not in existing:
        raise ValueError("Credential does not exist")

    credentials.delete(parsed.provider, parsed.credential_id)
    provider_settings = getattr(settings.translation.providers, parsed.provider)
    configured = [value for value in provider_settings.credential_ids if value != parsed.credential_id]
    service.update({"translation": {"providers": {parsed.provider: {"credential_ids": configured}}}})
    return snapshot()


def providers() -> list[dict[str, Any]]:
    service, credentials = _stores()
    return [item.model_dump(mode="json") for item in provider_infos(service.get(), credentials)]


def _provider_for_request(parsed: ProviderParams):
    service, credentials = _stores()
    settings = service.get()
    secret = parsed.credential
    if secret is None and parsed.provider != "local":
        ids = credential_ids(parsed.provider, settings, credentials)
        secret = credentials.get(parsed.provider, ids[0]) if ids else None
    return create_provider(parsed.provider, settings, credential=secret)


def models(params: dict[str, Any]) -> list[dict[str, Any]]:
    provider = _provider_for_request(ProviderParams.model_validate(params))
    return [item.model_dump(mode="json") for item in provider.list_models()]


def test_connection(params: dict[str, Any]) -> dict[str, Any]:
    provider = _provider_for_request(ProviderParams.model_validate(params))
    return provider.test_connection().model_dump(mode="json")
