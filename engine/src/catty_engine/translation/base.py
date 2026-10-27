"""Translation provider contract and safe provider errors."""

from __future__ import annotations

from typing import Protocol

from .models import (
    ConnectionTestResult,
    TranslationBatchRequest,
    TranslationBatchResult,
    TranslationModel,
)


class ProviderError(RuntimeError):
    """Safe, user-facing provider failure. Messages never contain secrets."""


class TranslationProvider(Protocol):
    id: str

    def list_models(self) -> list[TranslationModel]: ...

    def test_connection(self) -> ConnectionTestResult: ...

    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult: ...
