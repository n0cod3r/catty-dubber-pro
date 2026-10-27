import pytest

from catty_engine.translation.base import ProviderError
from catty_engine.translation.providers.gemini import GeminiProvider, _parse_models


def test_filters_gemini_models_to_generate_content():
    models = _parse_models({"models": [
        {"name": "models/gemini-2.5-flash", "displayName": "Gemini Flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/imagen-3", "supportedGenerationMethods": ["generateContent"]},
    ]})
    assert [model.id for model in models] == ["gemini-2.5-flash"]


def test_missing_key_is_safe():
    provider = GeminiProvider(api_key=None, selected_model=None)
    assert provider.test_connection().ok is False
    with pytest.raises(ProviderError, match="API key"):
        provider.list_models()


def test_transport_url_is_not_exposed_by_connection_error():
    secret = "super-secret-key"
    def failing(_url: str):
        raise ProviderError("Gemini rejected the API key. Check the key and try again.")
    result = GeminiProvider(api_key=secret, selected_model=None, transport=failing).test_connection()
    assert result.ok is False
    assert secret not in result.message
