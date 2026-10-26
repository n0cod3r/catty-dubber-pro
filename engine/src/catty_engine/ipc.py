"""Versioned, one-request JSON transport for short desktop engine operations."""

from __future__ import annotations

import json
import shutil
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catty_engine.media.errors import FFprobeNotFoundError, MediaProbeError
from catty_engine.media.probe import MediaProbeService


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    id: str = Field(min_length=1, max_length=128)
    method: Literal["health", "media.probe"]
    params: dict[str, Any] = Field(default_factory=dict)


class ProbeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)


def handle_request(payload: Any) -> dict[str, Any]:
    request_id = payload.get("id") if isinstance(payload, dict) else None
    response: dict[str, Any] = {"version": 1, "id": request_id}
    try:
        request = Request.model_validate(payload)
        if request.method == "health":
            if request.params:
                raise ValueError("health does not accept parameters")
            result = {
                "name": "catty-engine",
                "version": "0.1.0",
                "capabilities": ["media.probe"],
                "ffprobe_available": shutil.which("ffprobe") is not None,
            }
        else:
            params = ProbeParams.model_validate(request.params)
            result = MediaProbeService().probe(params.path).model_dump(mode="json")
        response["result"] = result
    except FFprobeNotFoundError as exc:
        response["error"] = {"code": "FFPROBE_NOT_FOUND", "message": str(exc)}
    except MediaProbeError as exc:
        response["error"] = {"code": "MEDIA_PROBE_FAILED", "message": str(exc)}
    except (ValidationError, ValueError) as exc:
        response["error"] = {"code": "INVALID_REQUEST", "message": str(exc)}
    except Exception:
        response["error"] = {
            "code": "ENGINE_ERROR",
            "message": "The engine could not complete the request.",
        }
    return response


def run_rpc() -> None:
    import sys

    try:
        payload = json.load(sys.stdin)
        response = handle_request(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        response = {
            "version": 1,
            "id": None,
            "error": {
                "code": "INVALID_JSON",
                "message": "Expected a JSON request on stdin.",
            },
        }
    # stdout is exclusively protocol data. Diagnostics belong on stderr.
    print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
