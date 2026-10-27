import pytest

from catty_engine.translation.base import ProviderError
from catty_engine.translation.providers.gemini import GeminiProvider, _parse_models


def test_filters_gemini_models_to_text_generation():
    models = _parse_models(
        {
            "models": [
                {
                    "name": "models/gemini-3.8-flash",
                    "displayName": "Gemini 3.8 Flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-3.5-flash-lite",
                    "displayName": "Gemini 3.5 Flash-Lite",
                    # Current/future ListModels responses may omit method metadata.
                },
                {
                    "name": "models/gemini-3.8-flash-tts",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-3.1-flash-image",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-embedding-001",
                    "supportedGenerationMethods": ["embedContent"],
                },
                {
                    "name": "models/gemini-special-task",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }
    )
    assert [model.id for model in models] == [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
    ]


def test_list_models_follows_pagination_and_deduplicates():
    calls: list[str] = []

    def transport(url: str):
        calls.append(url)
        if "pageToken=next" in url:
            return {
                "models": [
                    {"name": "models/gemini-3.5-flash-lite"},
                    {"name": "models/gemini-3.8-flash"},
                ]
            }
        return {
            "models": [{"name": "models/gemini-3.8-flash"}],
            "nextPageToken": "next",
        }

    models = GeminiProvider(
        api_key="secret", selected_model=None, transport=transport
    ).list_models()
    assert [model.id for model in models] == [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
    ]
    assert len(calls) == 2


def test_empty_text_model_list_is_actionable():
    provider = GeminiProvider(
        api_key="secret",
        selected_model=None,
        transport=lambda _url: {"models": []},
    )
    with pytest.raises(ProviderError, match="no text-generation models"):
        provider.list_models()


def test_connection_validates_selected_model():
    provider = GeminiProvider(
        api_key="secret",
        selected_model="gemini-missing",
        transport=lambda _url: {"models": [{"name": "models/gemini-3.8-flash"}]},
    )
    result = provider.test_connection()
    assert result.ok is False
    assert "not available" in result.message


def test_missing_key_is_safe():
    provider = GeminiProvider(api_key=None, selected_model=None)
    assert provider.test_connection().ok is False
    with pytest.raises(ProviderError, match="API key"):
        provider.list_models()


def test_transport_url_is_not_exposed_by_connection_error():
    secret = "super-secret-key"

    def failing(_url: str):
        raise ProviderError("Gemini rejected the API key. Check the key and try again.")

    result = GeminiProvider(
        api_key=secret, selected_model=None, transport=failing
    ).test_connection()
    assert result.ok is False
    assert secret not in result.message
