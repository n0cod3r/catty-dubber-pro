"""Translation provider contract and safe provider errors."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from .models import ConnectionTestResult, TranslationBatchRequest, TranslationBatchResult, TranslationModel


class ProviderErrorKind(StrEnum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TEMPORARY = "temporary"
    CONFIGURATION = "configuration"
    RESPONSE = "response"


class ProviderError(RuntimeError):
    """Safe provider failure with machine-readable retry semantics."""

    def __init__(self, message: str, *, kind: ProviderErrorKind | None = None, retry_after: float | None = None) -> None:
        super().__init__(message)
        lowered = message.lower()
        if kind is None and "rate limit" in lowered:
            kind = ProviderErrorKind.RATE_LIMIT
        elif kind is None and ("api key" in lowered or "credential" in lowered):
            kind = ProviderErrorKind.AUTH
        elif kind is None and ("temporarily unavailable" in lowered or "could not reach" in lowered):
            kind = ProviderErrorKind.TEMPORARY
        self.kind = kind or ProviderErrorKind.RESPONSE
        self.retry_after = retry_after


class TranslationProvider(Protocol):
    id: str

    def list_models(self) -> list[TranslationModel]: ...
    def test_connection(self) -> ConnectionTestResult: ...
    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult: ...
