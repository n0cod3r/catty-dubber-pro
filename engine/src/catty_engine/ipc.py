from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService
from catty_engine.media.errors import (
    AudioPreparationCancelled,
    FFmpegError,
    FFmpegNotFoundError,
    FFprobeNotFoundError,
    MediaError,
    MediaProbeError,
)
from catty_engine.media.ffmpeg import FFmpegRunner
from catty_engine.media.probe import MediaProbeService
from catty_engine.project import ProjectService
from catty_engine.speech.runtime import create_asr_registry, create_vad
from catty_engine.speech.transcription import TranscriptionService

PROTOCOL_VERSION = 1


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    id: str = Field(min_length=1, max_length=128)
    method: Literal[
        "health",
        "system.hello",
        "system.shutdown",
        "media.probe",
        "audio.prepare",
        "project.create",
        "project.open",
        "project.prepare_episode",
        "project.import_episode",
        "speech.transcribe",
    ]
    params: dict[str, Any] = Field(default_factory=dict)


class ProbeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)


class ProjectCreateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    name: str = Field(min_length=1)


class ProjectOpenParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path


class ProjectPrepareEpisodeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    episode_id: UUID


class ProjectImportEpisodeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    project_name: str = Field(min_length=1)
    source: str = Field(min_length=1)


class AudioPrepareParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    episode_id: UUID
    source: str = Field(min_length=1)
    existing_asset: AudioAsset | None = None
    cancel_file: Path | None = None


class SpeechTranscribeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    episode_id: UUID
    source: str = Field(min_length=1)
    source_start: float = Field(ge=0)
    duration: float = Field(gt=0)
    language: str = Field(default="zh", min_length=1)
    asr_backend: str = Field(default="paraformer", min_length=1)
    asr_config: dict[str, Any]
    vad_backend: str = Field(default="silero", min_length=1)
    vad_config: dict[str, Any]
    existing_asset: AudioAsset | None = None


def _hello() -> dict[str, Any]:
    return {
        "name": "catty-engine",
        "version": "0.1.0",
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": [
            "media.probe",
            "audio.prepare",
            "project.create",
            "project.open",
            "project.prepare_episode",
            "project.import_episode",
            "speech.transcribe",
            "asr.paraformer",
            "vad.silero",
            "system.shutdown",
        ],
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "ffprobe_available": shutil.which("ffprobe") is not None,
    }


def _open_or_create_project(directory: Path, name: str):
    service = ProjectService()
    project_file = directory / "project.json"
    project = (
        service.open_project(directory)
        if project_file.exists()
        else service.create_project(directory, name)
    )
    return service, project


def handle_request(payload: Any) -> dict[str, Any]:
    request_id = payload.get("id") if isinstance(payload, dict) else None
    response: dict[str, Any] = {"version": PROTOCOL_VERSION, "id": request_id}
    try:
        request = Request.model_validate(payload)
        if request.method in {"health", "system.hello"}:
            if request.params:
                raise ValueError(f"{request.method} does not accept parameters")
            result = _hello()
        elif request.method == "system.shutdown":
            if request.params:
                raise ValueError("system.shutdown does not accept parameters")
            result = {"shutting_down": True}
        elif request.method == "project.create":
            create_params = ProjectCreateParams.model_validate(request.params)
            if (create_params.project_directory / "project.json").exists():
                raise ValueError("A Catty project already exists in this folder")
            result = ProjectService().create_project(
                create_params.project_directory, create_params.name
            ).model_dump(mode="json")
        elif request.method == "project.open":
            open_params = ProjectOpenParams.model_validate(request.params)
            result = ProjectService().open_project(open_params.project_directory).model_dump(
                mode="json"
            )
        elif request.method == "project.prepare_episode":
            prepare_params = ProjectPrepareEpisodeParams.model_validate(request.params)
            service = ProjectService()
            project = service.open_project(prepare_params.project_directory)
            episode = service.prepare_episode_audio(
                prepare_params.project_directory, project, prepare_params.episode_id
            )
            episode = service.prepare_episode_proxy(
                prepare_params.project_directory, project, episode.id
            )
            result = episode.model_dump(mode="json")
        elif request.method == "project.import_episode":
            import_params = ProjectImportEpisodeParams.model_validate(request.params)
            service, project = _open_or_create_project(
                import_params.project_directory, import_params.project_name
            )
            episode = service.import_episode(
                directory=import_params.project_directory,
                project=project,
                source_path=import_params.source,
                prepare_audio=True,
            )
            result = episode.model_dump(mode="json")
        elif request.method == "audio.prepare":
            audio_params = AudioPrepareParams.model_validate(request.params)

            def cancelled() -> bool:
                return audio_params.cancel_file is not None and audio_params.cancel_file.exists()

            if cancelled():
                raise AudioPreparationCancelled("Audio preparation cancelled")
            asset = AudioPreparationService(runner=FFmpegRunner(cancelled=cancelled)).prepare_speech_audio(
                project_directory=audio_params.project_directory,
                episode_id=audio_params.episode_id,
                source=audio_params.source,
                existing_asset=audio_params.existing_asset,
            )
            result = asset.model_dump(mode="json")
        elif request.method == "speech.transcribe":
            speech_params = SpeechTranscribeParams.model_validate(request.params)
            registry = create_asr_registry(speech_params.asr_backend, speech_params.asr_config)
            vad = create_vad(speech_params.vad_backend, speech_params.vad_config)
            transcription = TranscriptionService(asr_backends=registry, vad=vad).transcribe(
                project_directory=speech_params.project_directory,
                episode_id=speech_params.episode_id,
                source=speech_params.source,
                backend_id=speech_params.asr_backend,
                language=speech_params.language,
                source_start=speech_params.source_start,
                duration=speech_params.duration,
                existing_asset=speech_params.existing_asset,
            )
            result = transcription.model_dump(mode="json")
        else:
            probe_params = ProbeParams.model_validate(request.params)
            result = MediaProbeService().probe(probe_params.path).model_dump(mode="json")
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
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        response["error"] = {"code": "INVALID_REQUEST", "message": str(exc)}
    except Exception:
        response["error"] = {
            "code": "ENGINE_ERROR",
            "message": "The engine could not complete the request.",
        }
    return response


def _write_response(response: dict[str, Any]) -> None:
    print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)


def run_rpc() -> None:
    try:
        payload = json.load(sys.stdin)
        response = handle_request(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        response = {
            "version": PROTOCOL_VERSION,
            "id": None,
            "error": {"code": "INVALID_JSON", "message": "Expected a JSON request on stdin."},
        }
    _write_response(response)


def run_server() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        payload: Any = None
        try:
            payload = json.loads(line)
            response = handle_request(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            response = {
                "version": PROTOCOL_VERSION,
                "id": None,
                "error": {
                    "code": "INVALID_JSON",
                    "message": "Expected one JSON request per line.",
                },
            }
        _write_response(response)
        if (
            isinstance(payload, dict)
            and payload.get("method") == "system.shutdown"
            and "error" not in response
        ):
            break
