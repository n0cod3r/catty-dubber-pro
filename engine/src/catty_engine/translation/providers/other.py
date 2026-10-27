"""Local and configuration-ready providers without a translation workflow yet."""

from __future__ import annotations

from ..base import ProviderError
from ..models import ConnectionTestResult, TranslationModel


class LocalProvider:
    """Offline path placeholder. No translation model is integrated yet."""

    id = "local"

    def __init__(self, selected_model: str | None = None) -> None:
        self.selected_model = selected_model

    def list_models(self) -> list[TranslationModel]:
        return []

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            ok=False,
            message="Local translation model is not installed yet.",
        )


class ConfigurationOnlyProvider:
    """Metadata/config foundation for providers implemented in a later milestone."""

    def __init__(self, provider_id: str, name: str) -> None:
        self.id = provider_id
        self.name = name

    def list_models(self) -> list[TranslationModel]:
        raise ProviderError(
            f"{self.name} model discovery is not available yet."
        )

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            ok=False,
            message=f"{self.name} connection testing is not available yet.",
        )
