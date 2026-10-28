"""Gemini provider for model discovery and contextual Khmer translation."""

from __future__ import annotations
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable
from ..base import ProviderError
from ..models import (
    ConnectionTestResult,
    TranslationBatchRequest,
    TranslationBatchResult,
    TranslationModel,
    TranslationOutput,
)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_SECONDS = 45
_EXCLUDED = (
    "embedding",
    "aqa",
    "imagen",
    "veo",
    "image",
    "banana",
    "audio",
    "tts",
    "live",
    "transcribe",
    "omni",
    "robotics",
    "computer-use",
    "deep-research",
)
_TEXT_GENERATION_METHODS = {"generateContent", "streamGenerateContent"}


def _decode_response(response: Any) -> dict[str, Any]:
    try:
        payload = json.loads(response.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderError("Gemini returned an unreadable response.") from exc
    if not isinstance(payload, dict):
        raise ProviderError("Gemini returned an unreadable response.")
    return payload


def _request_json(url: str, timeout: int = TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Catty-Dubber-Pro/0.1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _decode_response(response)
    except urllib.error.HTTPError as exc:
        raise ProviderError(_http_message(exc.code)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(
            "Could not reach Gemini. Check the internet connection and retry."
        ) from exc


def _post_json(
    url: str, payload: dict[str, Any], timeout: int = TIMEOUT_SECONDS
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Catty-Dubber-Pro/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _decode_response(response)
    except urllib.error.HTTPError as exc:
        raise ProviderError(_http_message(exc.code)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(
            "Could not reach Gemini. Check the internet connection and retry."
        ) from exc


def _http_message(status: int) -> str:
    if status in (400, 401, 403):
        return "Gemini rejected the request or API key. Check the selected model and API key."
    if status == 404:
        return "The selected Gemini model is not available. Refresh models and choose another."
    if status == 429:
        return "Gemini rate limit reached. Try again later."
    if status >= 500:
        return "Gemini is temporarily unavailable."
    return f"Gemini request failed (HTTP {status})."


class GeminiProvider:
    id = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None,
        selected_model: str | None,
        transport: Callable[[str], dict[str, Any]] | None = None,
        generation_transport: Callable[[str, dict[str, Any]], dict[str, Any]]
        | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self.selected_model = selected_model or None
        self._transport = transport or _request_json
        self._generation_transport = generation_transport or _post_json

    def _url(self, path: str, **params: str) -> str:
        return f"{BASE_URL}/{path}?{urllib.parse.urlencode({'key': self._api_key or '', **params})}"

    def list_models(self) -> list[TranslationModel]:
        if not self._api_key:
            raise ProviderError("Add a Gemini API key first.")
        models = []
        page_token = None
        seen_tokens: set[str] = set()
        while True:
            params = {"pageSize": "1000"}
            if page_token:
                params["pageToken"] = page_token
            payload = self._transport(self._url("models", **params))
            models.extend(_parse_models(payload))
            next_token = payload.get("nextPageToken")
            if (
                not isinstance(next_token, str)
                or not next_token
                or next_token in seen_tokens
            ):
                break
            seen_tokens.add(next_token)
            page_token = next_token
        result = sorted({m.id: m for m in models}.values(), key=lambda m: m.id)
        if not result:
            raise ProviderError(
                "Gemini connected, but no text-generation models were returned for this API key."
            )
        return result

    def test_connection(self) -> ConnectionTestResult:
        if not self._api_key:
            return ConnectionTestResult(ok=False, message="Add a Gemini API key first.")
        try:
            models = self.list_models()
        except ProviderError as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        if self.selected_model and not any(m.id == self.selected_model for m in models):
            return ConnectionTestResult(
                ok=False,
                message=f"Connected to Gemini, but model '{self.selected_model}' is not available for this API key.",
            )
        return ConnectionTestResult(
            ok=True,
            message=f"Connected to Gemini. {len(models)} text model(s) available.",
        )

    def translate_batch(
        self, request: TranslationBatchRequest
    ) -> TranslationBatchResult:
        if not self._api_key:
            raise ProviderError("Add a Gemini API key first.")
        if not self.selected_model:
            raise ProviderError("Select a Gemini model before translating.")
        if not request.segments:
            raise ProviderError("Translation batch is empty.")
        payload = {
            "system_instruction": {"parts": [{"text": _system_prompt(request)}]},
            "contents": [{"role": "user", "parts": [{"text": _user_prompt(request)}]}],
            "generationConfig": {
                "temperature": 0.25,
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "OBJECT",
                    "properties": {
                        "segments": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "id": {"type": "STRING"},
                                    "text": {"type": "STRING"},
                                },
                                "required": ["id", "text"],
                            },
                        }
                    },
                    "required": ["segments"],
                },
            },
        }
        raw = self._generation_transport(
            self._url(f"models/{self.selected_model}:generateContent"), payload
        )
        outputs = _parse_translation_response(raw)
        _validate_outputs(request, outputs)
        return TranslationBatchResult(
            provider=self.id, model=self.selected_model, segments=outputs
        )


def _system_prompt(request: TranslationBatchRequest) -> str:
    style = {
        "natural_dubbing": "Natural spoken Khmer suitable for drama dubbing. Preserve meaning, emotion, relationships and register; avoid Chinese word-for-word phrasing.",
        "literal": "Accurate Khmer that stays close to the source meaning while remaining grammatical and understandable.",
        "short_conversational": "Concise, natural conversational Khmer. Preserve all important meaning without unnecessary wording.",
    }.get(request.style, request.style)
    rules = [
        "You are Catty Dubber Pro's professional Chinese-to-Khmer dialogue translator.",
        f"Translate from {request.source_language} to {request.target_language}.",
        f"Style: {style}",
        "Translate only the requested segment IDs. Never invent, remove, merge, reorder, or duplicate IDs.",
        "When semantic_context is present, it is the reconstructed full utterance from fragmented ASR. Use it only to understand the requested fragment; do not translate the whole semantic_context into every segment.",
        "Return Khmer dialogue only in each text field; no explanations or notes.",
        "Follow glossary terms exactly when they apply.",
        "Do not shorten or expand text to fit timestamps; voice timing is handled later by dubbing controls.",
    ]
    if request.custom_instructions:
        rules.append(f"Project instructions: {request.custom_instructions.strip()}")
    return "\n".join(rules)


def _user_prompt(request: TranslationBatchRequest) -> str:
    segments: list[dict[str, Any]] = []
    for item in request.segments:
        value: dict[str, Any] = {"id": item.id, "text": item.text}
        if item.semantic_context:
            value["semantic_context"] = item.semantic_context
        if request.use_speaker_context and item.speaker:
            value["speaker"] = item.speaker
        if request.use_context:
            value["previous"] = [line.model_dump(mode="json") for line in item.previous]
            value["next"] = [line.model_dump(mode="json") for line in item.next]
        segments.append(value)
    return json.dumps(
        {
            "glossary": [item.model_dump(mode="json") for item in request.glossary],
            "segments": segments,
        },
        ensure_ascii=False,
    )


def _parse_translation_response(payload: dict[str, Any]) -> list[TranslationOutput]:
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        items = json.loads(text)["segments"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ProviderError("Gemini returned an invalid translation response.") from exc
    if not isinstance(items, list):
        raise ProviderError("Gemini returned an invalid translation response.")
    try:
        return [TranslationOutput.model_validate(item) for item in items]
    except (TypeError, ValueError) as exc:
        raise ProviderError("Gemini returned invalid translation segments.") from exc


def _validate_outputs(
    request: TranslationBatchRequest, outputs: list[TranslationOutput]
) -> None:
    expected = [i.id for i in request.segments]
    returned = [i.id for i in outputs]
    if len(returned) != len(set(returned)):
        raise ProviderError("Gemini returned duplicate translation segment IDs.")
    if set(returned) != set(expected):
        raise ProviderError(
            "Gemini returned missing or unexpected translation segment IDs."
        )
    if any(not i.text.strip() for i in outputs):
        raise ProviderError("Gemini returned an empty translation.")


def _parse_models(payload: dict[str, Any]) -> list[TranslationModel]:
    items = payload.get("models")
    if not isinstance(items, list):
        raise ProviderError("Gemini returned an unreadable model list.")
    models = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.startswith("models/"):
            continue
        model_id = name.removeprefix("models/")
        lowered = model_id.lower()
        if not lowered.startswith("gemini-") or any(
            token in lowered for token in _EXCLUDED
        ):
            continue
        methods = item.get("supportedGenerationMethods")
        if (
            isinstance(methods, list)
            and methods
            and {m for m in methods if isinstance(m, str)}.isdisjoint(
                _TEXT_GENERATION_METHODS
            )
        ):
            continue
        display = item.get("displayName")
        description = item.get("description")
        models.append(
            TranslationModel(
                id=model_id,
                name=str(display) if isinstance(display, str) else model_id,
                description=str(description) if isinstance(description, str) else None,
            )
        )
    return models
