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
_EXCLUDED = ("embedding", "aqa", "imagen", "veo", "audio", "tts", "live")


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
        payload = self._transport(self._url("models", pageSize="1000"))
        return _parse_models(payload)

    def test_connection(self) -> ConnectionTestResult:
        if not self._api_key:
            return ConnectionTestResult(
                ok=False, message="Add a Gemini API key first."
            )
        try:
            payload = self._transport(self._url("models", pageSize="1"))
        except ProviderError as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        models = payload.get("models")
        if not isinstance(models, list):
            return ConnectionTestResult(
                ok=False, message="Gemini returned an unreadable response."
            )
        return ConnectionTestResult(ok=True, message="Connected to Gemini.")


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
        methods = item.get("supportedGenerationMethods")
        if not isinstance(methods, list) or "generateContent" not in methods:
            continue
        lowered = model_id.lower()
        if any(token in lowered for token in _EXCLUDED):
            continue
        if not any(token in lowered for token in ("gemini", "gemma")):
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
    return sorted(models, key=lambda model: model.id)
