from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catty_engine.logging import logged_request
from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService
from catty_engine.media.errors import AudioPreparationCancelled, FFmpegError, FFmpegNotFoundError, FFprobeNotFoundError, MediaError, MediaProbeError
from catty_engine.media.ffmpeg import FFmpegRunner
from catty_engine.media.probe import MediaProbeService
from catty_engine.project import ProjectService
from catty_engine.project.models import DialogueSegment, DubSegment, EpisodeSpeaker
from catty_engine.settings.service import SettingsError
from catty_engine.translation.base import ProviderError

PROTOCOL_VERSION = 1
EngineMethod = Literal[
    "health", "system.hello", "system.shutdown", "media.probe", "audio.prepare",
    "project.create", "project.open", "project.prepare_episode", "project.rebuild_proxy",
    "project.import_episode", "project.dialogue_split", "project.dialogue_merge_next",
    "project.dialogue_restore", "project.dialogue_update_text", "project.dialogue_update_translation",
    "project.dialogue_assign_speaker", "speech.transcribe", "settings.get", "settings.update",
    "settings.credential_add", "settings.credential_remove",
    "translation.providers", "translation.models", "translation.test_connection",
    "translation.translate_episode", "models.list", "models.install", "models.install_status", "models.remove",
]

class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    id: str = Field(min_length=1, max_length=128)
    method: EngineMethod
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

class DialogueEditParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_directory: Path
    episode_id: UUID
    segment_id: UUID

class DialogueSpeakerParams(DialogueEditParams):
    speaker_id: UUID | None
    expected_speaker_id: UUID | None
    create_new: bool = False

class DialogueTextParams(DialogueEditParams):
    text: str = Field(min_length=1, max_length=100000)
    expected_text: str

class DialogueTranslationParams(DialogueEditParams):
    text: str = Field(min_length=1, max_length=100000)
    expected_text: str | None = None

class DialogueSplitParams(DialogueEditParams):
    split_at: float = Field(ge=0)

class DialogueRestoreParams(ProjectPrepareEpisodeParams):
    expected_segments: list[DialogueSegment]
    dialogue_segments: list[DialogueSegment]
    speakers: list[EpisodeSpeaker]
    dub_segments: list[DubSegment]

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

class TranslationEpisodeParams(ProjectPrepareEpisodeParams):
    mode: Literal["missing", "all", "selected"] = "missing"
    segment_ids: list[UUID] = Field(default_factory=list)
    overwrite_manual: bool = False
    batch_size: int = Field(default=12, ge=1, le=20)


def _hello() -> dict[str, Any]:
    return {
        "name": "catty-engine", "version": "0.1.0", "protocol_version": PROTOCOL_VERSION,
        "capabilities": [
            "media.probe", "audio.prepare", "project.create", "project.open",
            "project.prepare_episode", "project.rebuild_proxy", "project.import_episode",
            "project.dialogue_split", "project.dialogue_merge_next", "project.dialogue_restore",
            "project.dialogue_update_text", "project.dialogue_update_translation",
            "project.dialogue_assign_speaker", "speech.transcribe", "settings.get", "settings.update",
            "settings.credential_add", "settings.credential_remove",
            "translation.providers", "translation.models", "translation.test_connection",
            "translation.translate_episode", "models.list", "models.install", "models.install_status", "models.remove",
            "speakers.funasr-campplus", "asr.paraformer", "asr.sense-small", "vad.silero", "system.shutdown",
        ],
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "ffprobe_available": shutil.which("ffprobe") is not None,
    }


def _open_or_create_project(directory: Path, name: str):
    service = ProjectService()
    project = service.open_project(directory) if (directory / "project.json").exists() else service.create_project(directory, name)
    return service, project


@logged_request
def handle_request(payload: Any) -> dict[str, Any]:
    request_id = payload.get("id") if isinstance(payload, dict) else None
    response: dict[str, Any] = {"version": PROTOCOL_VERSION, "id": request_id}
    result: Any
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
        elif request.method == "settings.get":
            if request.params:
                raise ValueError("settings.get does not accept parameters")
            from catty_engine.settings.rpc import snapshot
            result = snapshot()
        elif request.method == "settings.update":
            from catty_engine.settings.rpc import update
            result = update(request.params)
        elif request.method == "settings.credential_add":
            from catty_engine.settings.rpc import add_credential
            result = add_credential(request.params)
        elif request.method == "settings.credential_remove":
            from catty_engine.settings.rpc import remove_credential
            result = remove_credential(request.params)
        elif request.method == "translation.providers":
            if request.params:
                raise ValueError("translation.providers does not accept parameters")
            from catty_engine.settings.rpc import providers
            result = providers()
        elif request.method == "translation.models":
            from catty_engine.settings.rpc import models
            result = models(request.params)
        elif request.method == "translation.test_connection":
            from catty_engine.settings.rpc import test_connection
            result = test_connection(request.params)
        elif request.method == "models.list":
            if request.params:
                raise ValueError("models.list does not accept parameters")
            from catty_engine.settings.rpc import model_list
            result = model_list()
        elif request.method == "models.install":
            from catty_engine.settings.rpc import model_install
            result = model_install(request.params)
        elif request.method == "models.install_status":
            from catty_engine.settings.rpc import model_install_status
            result = model_install_status(request.params)
        elif request.method == "models.remove":
            from catty_engine.settings.rpc import model_remove
            result = model_remove(request.params)
        elif request.method == "translation.translate_episode":
            translation_params = TranslationEpisodeParams.model_validate(request.params)
            from catty_engine.translation.service import TranslationService
            result = TranslationService().translate_episode(
                translation_params.project_directory,
                translation_params.episode_id,
                mode=translation_params.mode,
                segment_ids=set(translation_params.segment_ids),
                overwrite_manual=translation_params.overwrite_manual,
                batch_size=translation_params.batch_size,
            ).model_dump(mode="json")
        elif request.method == "project.create":
            create_params = ProjectCreateParams.model_validate(request.params)
            if (create_params.project_directory / "project.json").exists():
                raise ValueError("A Catty project already exists in this folder")
            result = ProjectService().create_project(create_params.project_directory, create_params.name).model_dump(mode="json")
        elif request.method == "project.open":
            open_params = ProjectOpenParams.model_validate(request.params)
            result = ProjectService().open_project(open_params.project_directory).model_dump(mode="json")
        elif request.method in {"project.prepare_episode", "project.rebuild_proxy"}:
            prepare_params = ProjectPrepareEpisodeParams.model_validate(request.params)
            service = ProjectService()
            project = service.open_project(prepare_params.project_directory)
            if request.method == "project.prepare_episode":
                episode = service.prepare_episode_audio(prepare_params.project_directory, project, prepare_params.episode_id)
                episode = service.prepare_episode_proxy(prepare_params.project_directory, project, episode.id)
            else:
                episode = service.prepare_episode_proxy(prepare_params.project_directory, project, prepare_params.episode_id, force=True)
            result = episode.model_dump(mode="json")
        elif request.method == "project.import_episode":
            import_params = ProjectImportEpisodeParams.model_validate(request.params)
            service, project = _open_or_create_project(import_params.project_directory, import_params.project_name)
            result = service.import_episode(import_params.project_directory, project, import_params.source, prepare_audio=True).model_dump(mode="json")
        elif request.method == "project.dialogue_assign_speaker":
            speaker_params = DialogueSpeakerParams.model_validate(request.params)
            service = ProjectService()
            project = service.open_project(speaker_params.project_directory)
            result = service.assign_dialogue_speaker(speaker_params.project_directory, project, speaker_params.episode_id, speaker_params.segment_id, speaker_params.speaker_id, speaker_params.expected_speaker_id, create_new=speaker_params.create_new).model_dump(mode="json")
        elif request.method == "project.dialogue_update_text":
            text_params = DialogueTextParams.model_validate(request.params)
            service = ProjectService()
            project = service.open_project(text_params.project_directory)
            result = service.update_dialogue_text(text_params.project_directory, project, text_params.episode_id, text_params.segment_id, text_params.text, text_params.expected_text).model_dump(mode="json")
        elif request.method == "project.dialogue_update_translation":
            dialogue_translation_params = DialogueTranslationParams.model_validate(request.params)
            service = ProjectService()
            project = service.open_project(dialogue_translation_params.project_directory)
            result = service.update_dialogue_translation(dialogue_translation_params.project_directory, project, dialogue_translation_params.episode_id, dialogue_translation_params.segment_id, dialogue_translation_params.text, dialogue_translation_params.expected_text).model_dump(mode="json")
        elif request.method == "project.dialogue_split":
            split_params = DialogueSplitParams.model_validate(request.params)
            service = ProjectService()
            project = service.open_project(split_params.project_directory)
            result = service.split_dialogue_segment(split_params.project_directory, project, split_params.episode_id, split_params.segment_id, split_params.split_at).model_dump(mode="json")
        elif request.method == "project.dialogue_merge_next":
            merge_params = DialogueEditParams.model_validate(request.params)
            service = ProjectService()
            project = service.open_project(merge_params.project_directory)
            result = service.merge_dialogue_segment_with_next(merge_params.project_directory, project, merge_params.episode_id, merge_params.segment_id).model_dump(mode="json")
        elif request.method == "project.dialogue_restore":
            restore_params = DialogueRestoreParams.model_validate(request.params)
            service = ProjectService()
            project = service.open_project(restore_params.project_directory)
            result = service.restore_dialogue(restore_params.project_directory, project, restore_params.episode_id, restore_params.expected_segments, restore_params.dialogue_segments, restore_params.speakers, restore_params.dub_segments).model_dump(mode="json")
        elif request.method == "audio.prepare":
            audio_params = AudioPrepareParams.model_validate(request.params)
            def cancelled() -> bool:
                return audio_params.cancel_file is not None and audio_params.cancel_file.exists()
            if cancelled():
                raise AudioPreparationCancelled("Audio preparation cancelled")
            result = AudioPreparationService(runner=FFmpegRunner(cancelled=cancelled)).prepare_speech_audio(project_directory=audio_params.project_directory, episode_id=audio_params.episode_id, source=audio_params.source, existing_asset=audio_params.existing_asset).model_dump(mode="json")
        elif request.method == "speech.transcribe":
            speech_params = SpeechTranscribeParams.model_validate(request.params)
            from catty_engine.speech.runtime import create_transcription_service
            transcription = create_transcription_service(backend_id=speech_params.asr_backend, asr_config=speech_params.asr_config, vad_backend=speech_params.vad_backend, vad_config=speech_params.vad_config).transcribe(project_directory=speech_params.project_directory, episode_id=speech_params.episode_id, source=speech_params.source, backend_id=speech_params.asr_backend, language=speech_params.language, source_start=speech_params.source_start, duration=speech_params.duration, existing_asset=speech_params.existing_asset)
            service = ProjectService()
            project = service.open_project(speech_params.project_directory)
            service.replace_dialogue_segments(speech_params.project_directory, project, speech_params.episode_id, transcription.segments, source_language=speech_params.language, speaker_error=transcription.speaker_error)
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
        response["error"] = {"code": "FFMPEG_FAILED", "message": str(exc)}
    except FFprobeNotFoundError as exc:
        response["error"] = {"code": "FFPROBE_NOT_FOUND", "message": str(exc)}
    except MediaProbeError as exc:
        response["error"] = {"code": "MEDIA_PROBE_FAILED", "message": str(exc)}
    except MediaError as exc:
        response["error"] = {"code": "MEDIA_ERROR", "message": str(exc)}
    except (SettingsError, ProviderError) as exc:
        response["error"] = {"code": "CONFIGURATION_ERROR", "message": str(exc)}
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        response["error"] = {"code": "INVALID_REQUEST", "message": str(exc)}
    except Exception:
        traceback.print_exc(file=sys.stderr)
        response["error"] = {"code": "ENGINE_ERROR", "message": "The engine could not complete the request. See engine diagnostics."}
    return response


def _write_response(response: dict[str, Any]) -> None:
    print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)

def _invalid_json_response() -> dict[str, Any]:
    return {"version": PROTOCOL_VERSION, "id": None, "error": {"code": "INVALID_JSON", "message": "Expected one JSON request per line."}}

def run_rpc() -> None:
    try:
        response = handle_request(json.load(sys.stdin))
    except (json.JSONDecodeError, UnicodeDecodeError):
        response = _invalid_json_response()
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
            response = _invalid_json_response()
        _write_response(response)
