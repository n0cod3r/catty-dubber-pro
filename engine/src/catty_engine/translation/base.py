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

    def __init__(self, message: str, *, kind: ProviderErrorKind = ProviderErrorKind.RESPONSE, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


class TranslationProvider(Protocol):
    id: str

    def list_models(self) -> list[TranslationModel]: ...
    def test_connection(self) -> ConnectionTestResult: ...
    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult: ...
