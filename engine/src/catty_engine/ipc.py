"""Versioned, one-request JSON transport for short desktop engine operations."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import UUID
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catty_engine.media.errors import (
    AudioPreparationCancelled,
    FFmpegNotFoundError,
    FFmpegError,
    FFprobeNotFoundError,
    MediaProbeError,
    MediaError,
)
from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService
from catty_engine.media.ffmpeg import FFmpegRunner
from catty_engine.media.probe import MediaProbeService


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    id: str = Field(min_length=1, max_length=128)
    method: Literal["health", "media.probe", "audio.prepare"]
    params: dict[str, Any] = Field(default_factory=dict)


class ProbeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)


class AudioPrepareParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    episode_id: UUID
    source: str = Field(min_length=1)
    existing_asset: AudioAsset | None = None
    cancel_file: Path | None = None


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
                "capabilities": ["media.probe", "audio.prepare"],
                "ffmpeg_available": shutil.which("ffmpeg") is not None,
                "ffprobe_available": shutil.which("ffprobe") is not None,
            }
        elif request.method == "audio.prepare":
            audio_params = AudioPrepareParams.model_validate(request.params)

            def cancelled() -> bool:
                return (
                    audio_params.cancel_file is not None
                    and audio_params.cancel_file.exists()
                )

            if cancelled():
                raise AudioPreparationCancelled("Audio preparation cancelled")
            asset = AudioPreparationService(
                runner=FFmpegRunner(cancelled=cancelled)
            ).prepare_speech_audio(
                project_directory=audio_params.project_directory,
                episode_id=audio_params.episode_id,
                source=audio_params.source,
                existing_asset=audio_params.existing_asset,
            )
            result = asset.model_dump(mode="json")
        else:
            params = ProbeParams.model_validate(request.params)
            result = MediaProbeService().probe(params.path).model_dump(mode="json")
        response["result"] = result
    except AudioPreparationCancelled as exc:
        response["error"] = {"code": "CANCELLED", "message": str(exc)}
    except FFmpegNotFoundError as exc:
        response["error"] = {"code": "FFMPEG_NOT_FOUND", "message": str(exc)}
    except FFmpegError as exc:
        response["error"] = {"code": "AUDIO_PREPARATION_FAILED", "message": str(exc)}
    except FFprobeNotFoundError as exc:
        response["error"] = {"code": "FFPROBE_NOT_FOUND", "message": str(exc)}
    except MediaProbeError as exc:
        response["error"] = {"code": "MEDIA_PROBE_FAILED", "message": str(exc)}
    except MediaError as exc:
        response["error"] = {"code": "MEDIA_ERROR", "message": str(exc)}
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
