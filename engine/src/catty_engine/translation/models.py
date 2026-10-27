"""Provider-facing translation types shared with the settings UI."""

from __future__ import annotations

from pydantic import BaseModel


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
