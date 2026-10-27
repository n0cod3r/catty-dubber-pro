"""Gemini provider: credential test and dynamic text-model discovery."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ..base import ProviderError
from ..models import ConnectionTestResult, TranslationModel

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_SECONDS = 15

# Translation needs ordinary text-capable Gemini models. Specialized media/live/task
# endpoints may also contain "gemini" in their IDs, so exclude them explicitly.
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


def _request_json(url: str, timeout: int = TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Catty-Dubber-Pro/0.1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ProviderError(_http_message(exc.code)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(
            "Could not reach Gemini. Check the internet connection and retry."
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderError("Gemini returned an unreadable response.") from exc
    if not isinstance(payload, dict):
        raise ProviderError("Gemini returned an unreadable response.")
    return payload


def _http_message(status: int) -> str:
    if status in (400, 401, 403):
        return "Gemini rejected the API key. Check the key and try again."
    if status == 404:
        return "Gemini model endpoint was not found."
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
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self.selected_model = selected_model or None
        self._transport = transport or _request_json

    def _url(self, path: str, **params: str) -> str:
        query = urllib.parse.urlencode({"key": self._api_key or "", **params})
        return f"{BASE_URL}/{path}?{query}"

    def list_models(self) -> list[TranslationModel]:
        if not self._api_key:
            raise ProviderError("Add a Gemini API key first.")

        models: list[TranslationModel] = []
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            params = {"pageSize": "1000"}
            if page_token:
                params["pageToken"] = page_token
            payload = self._transport(self._url("models", **params))
            models.extend(_parse_models(payload))

            next_token = payload.get("nextPageToken")
            if not isinstance(next_token, str) or not next_token or next_token in seen_tokens:
                break
            seen_tokens.add(next_token)
            page_token = next_token

        unique = {model.id: model for model in models}
        result = sorted(unique.values(), key=lambda model: model.id)
        if not result:
            raise ProviderError(
                "Gemini connected, but no text-generation models were returned for this API key."
            )
        return result

    def test_connection(self) -> ConnectionTestResult:
        if not self._api_key:
            return ConnectionTestResult(
                ok=False, message="Add a Gemini API key first."
            )
        try:
            models = self.list_models()
        except ProviderError as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

        if self.selected_model and not any(
            model.id == self.selected_model for model in models
        ):
            return ConnectionTestResult(
                ok=False,
                message=(
                    f"Connected to Gemini, but model '{self.selected_model}' "
                    "is not available for this API key."
                ),
            )
        return ConnectionTestResult(
            ok=True,
            message=f"Connected to Gemini. {len(models)} text model(s) available.",
        )


def _parse_models(payload: dict[str, Any]) -> list[TranslationModel]:
    items = payload.get("models")
    if not isinstance(items, list):
        raise ProviderError("Gemini returned an unreadable model list.")

    models: list[TranslationModel] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.startswith("models/"):
            continue

        model_id = name.removeprefix("models/")
        lowered = model_id.lower()
        if not lowered.startswith("gemini-"):
            continue
        if any(token in lowered for token in _EXCLUDED):
            continue

        # Older ListModels responses advertise generateContent here. Newer model
        # metadata may omit the field, so absence must not turn a valid Gemini text
        # model into an empty selector. When methods are present, still reject a
        # model that explicitly has no standard text-generation method.
        methods = item.get("supportedGenerationMethods")
        if isinstance(methods, list) and methods:
            advertised = {method for method in methods if isinstance(method, str)}
            if advertised.isdisjoint(_TEXT_GENERATION_METHODS):
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
