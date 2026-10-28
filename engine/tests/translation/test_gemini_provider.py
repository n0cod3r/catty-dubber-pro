import json

import pytest

from catty_engine.translation.base import ProviderError
from catty_engine.translation.models import TranslationBatchRequest, TranslationInput
from catty_engine.translation.providers.gemini import GeminiProvider, _parse_models


def test_filters_gemini_models_to_text_generation():
    models = _parse_models({"models": [{"name": "models/gemini-3.8-flash", "displayName": "Gemini 3.8 Flash", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/gemini-3.5-flash-lite", "displayName": "Gemini 3.5 Flash-Lite"}, {"name": "models/gemini-3.8-flash-tts", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/gemini-3.1-flash-image", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]}, {"name": "models/gemini-special-task", "supportedGenerationMethods": ["embedContent"]}]})
    assert [model.id for model in models] == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]


def test_list_models_follows_pagination_and_deduplicates():
    calls: list[str] = []
    def transport(url: str):
        calls.append(url)
        if "pageToken=next" in url:
            return {"models": [{"name": "models/gemini-3.5-flash-lite"}, {"name": "models/gemini-3.8-flash"}]}
        return {"models": [{"name": "models/gemini-3.8-flash"}], "nextPageToken": "next"}
    models = GeminiProvider(api_key="secret", selected_model=None, transport=transport).list_models()
    assert [model.id for model in models] == ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
    assert len(calls) == 2


def test_empty_text_model_list_is_actionable():
    provider = GeminiProvider(api_key="secret", selected_model=None, transport=lambda _url: {"models": []})
    with pytest.raises(ProviderError, match="no text-generation models"):
        provider.list_models()


def test_connection_validates_selected_model():
    provider = GeminiProvider(api_key="secret", selected_model="gemini-missing", transport=lambda _url: {"models": [{"name": "models/gemini-3.8-flash"}]})
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
    result = GeminiProvider(api_key=secret, selected_model=None, transport=failing).test_connection()
    assert result.ok is False
    assert secret not in result.message


def test_translate_batch_uses_structured_output_and_preserves_ids():
    captured: dict[str, object] = {}
    def generate(url: str, payload: dict[str, object]):
        captured["url"] = url
        captured["payload"] = payload
        return {"candidates": [{"content": {"parts": [{"text": '{"segments":[{"id":"a","text":"សួស្តី"},{"id":"b","text":"ទៅណា?"}]}' }]}}]}
    provider = GeminiProvider(api_key="secret", selected_model="gemini-3.8-flash", generation_transport=generate)
    result = provider.translate_batch(TranslationBatchRequest(segments=[TranslationInput(id="a", text="你好"), TranslationInput(id="b", text="去哪儿？")]))
    assert [item.id for item in result.segments] == ["a", "b"]
    assert result.segments[0].text == "សួស្តី"
    assert "generateContent" in str(captured["url"])
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "response_schema" in str(payload)
    user_prompt = payload["contents"][0]["parts"][0]["text"]
    request_body = json.loads(user_prompt)
    assert all("duration" not in segment and "start" not in segment and "end" not in segment for segment in request_body["segments"])


def test_translate_batch_rejects_missing_ids():
    provider = GeminiProvider(api_key="secret", selected_model="gemini-3.8-flash", generation_transport=lambda _url, _payload: {"candidates": [{"content": {"parts": [{"text": '{"segments":[{"id":"a","text":"សួស្តី"}]}' }]}}]})
    request = TranslationBatchRequest(segments=[TranslationInput(id="a", text="你好"), TranslationInput(id="b", text="再见")])
    with pytest.raises(ProviderError, match="missing or unexpected"):
        provider.translate_batch(request)
