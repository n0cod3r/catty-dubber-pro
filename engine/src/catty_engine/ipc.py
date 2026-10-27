from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catty_engine.media.audio import AudioAsset
from catty_engine.media.audio_preparation import AudioPreparationService
from catty_engine.media.errors import AudioPreparationCancelled, FFmpegError, FFmpegNotFoundError, FFprobeNotFoundError, MediaError, MediaProbeError
from catty_engine.media.ffmpeg import FFmpegRunner
from catty_engine.media.probe import MediaProbeService
from catty_engine.project import ProjectService
from catty_engine.project.models import DialogueSegment, EpisodeSpeaker, DubSegment
from catty_engine.speech.runtime import create_asr_registry, create_vad
from catty_engine.speech.transcription import TranscriptionService

PROTOCOL_VERSION = 1
EngineMethod = Literal["health", "system.hello", "system.shutdown", "media.probe", "audio.prepare", "project.create", "project.open", "project.prepare_episode", "project.rebuild_proxy", "project.import_episode", "project.dialogue_split", "project.dialogue_merge_next", "project.dialogue_restore", "project.dialogue_update_text", "project.dialogue_assign_speaker", "speech.transcribe"]

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

def _hello() -> dict[str, Any]:
    return {"name": "catty-engine", "version": "0.1.0", "protocol_version": PROTOCOL_VERSION, "capabilities": ["media.probe", "audio.prepare", "project.create", "project.open", "project.prepare_episode", "project.rebuild_proxy", "project.import_episode", "project.dialogue_split", "project.dialogue_merge_next", "project.dialogue_restore", "project.dialogue_update_text", "project.dialogue_assign_speaker", "speech.transcribe", "speakers.funasr-campplus", "asr.paraformer", "asr.sense-small", "vad.silero", "system.shutdown"], "ffmpeg_available": shutil.which("ffmpeg") is not None, "ffprobe_available": shutil.which("ffprobe") is not None}

def _open_or_create_project(directory: Path, name: str):
    service = ProjectService()
    project = service.open_project(directory) if (directory / "project.json").exists() else service.create_project(directory, name)
    return service, project

def handle_request(payload: Any) -> dict[str, Any]:
    request_id = payload.get("id") if isinstance(payload, dict) else None
    response: dict[str, Any] = {"version": PROTOCOL_VERSION, "id": request_id}
    try:
        request = Request.model_validate(payload)
        if request.method in {"health", "system.hello"}:
            if request.params: raise ValueError(f"{request.method} does not accept parameters")
            result = _hello()
        elif request.method == "system.shutdown":
            if request.params: raise ValueError("system.shutdown does not accept parameters")
            result = {"shutting_down": True}
        elif request.method == "project.create":
            project_create_params = ProjectCreateParams.model_validate(request.params)
            if (project_create_params.project_directory / "project.json").exists(): raise ValueError("A Catty project already exists in this folder")
            result = ProjectService().create_project(project_create_params.project_directory, project_create_params.name).model_dump(mode="json")
        elif request.method == "project.open":
            project_open_params = ProjectOpenParams.model_validate(request.params)
            result = ProjectService().open_project(project_open_params.project_directory).model_dump(mode="json")
        elif request.method in {"project.prepare_episode", "project.rebuild_proxy"}:
            project_prepare_episode_params = ProjectPrepareEpisodeParams.model_validate(request.params)
            service = ProjectService(); project = service.open_project(project_prepare_episode_params.project_directory)
            if request.method == "project.prepare_episode":
                episode = service.prepare_episode_audio(project_prepare_episode_params.project_directory, project, project_prepare_episode_params.episode_id)
                episode = service.prepare_episode_proxy(project_prepare_episode_params.project_directory, project, episode.id)
            else:
                episode = service.prepare_episode_proxy(project_prepare_episode_params.project_directory, project, project_prepare_episode_params.episode_id, force=True)
            result = episode.model_dump(mode="json")
        elif request.method == "project.import_episode":
            project_import_episode_params = ProjectImportEpisodeParams.model_validate(request.params)
            service, project = _open_or_create_project(project_import_episode_params.project_directory, project_import_episode_params.project_name)
            result = service.import_episode(project_import_episode_params.project_directory, project, project_import_episode_params.source, prepare_audio=True).model_dump(mode="json")
        elif request.method == "project.dialogue_assign_speaker":
            dialogue_speaker_params = DialogueSpeakerParams.model_validate(request.params)
            service = ProjectService(); project = service.open_project(dialogue_speaker_params.project_directory)
            result = service.assign_dialogue_speaker(dialogue_speaker_params.project_directory, project, dialogue_speaker_params.episode_id, dialogue_speaker_params.segment_id, dialogue_speaker_params.speaker_id, dialogue_speaker_params.expected_speaker_id, create_new=dialogue_speaker_params.create_new).model_dump(mode="json")
        elif request.method == "project.dialogue_update_text":
            dialogue_text_params = DialogueTextParams.model_validate(request.params)
            service = ProjectService(); project = service.open_project(dialogue_text_params.project_directory)
            result = service.update_dialogue_text(dialogue_text_params.project_directory, project, dialogue_text_params.episode_id, dialogue_text_params.segment_id, dialogue_text_params.text, dialogue_text_params.expected_text).model_dump(mode="json")
        elif request.method == "project.dialogue_split":
            dialogue_split_params = DialogueSplitParams.model_validate(request.params)
            service = ProjectService(); project = service.open_project(dialogue_split_params.project_directory)
            result = service.split_dialogue_segment(dialogue_split_params.project_directory, project, dialogue_split_params.episode_id, dialogue_split_params.segment_id, dialogue_split_params.split_at).model_dump(mode="json")
        elif request.method == "project.dialogue_merge_next":
            dialogue_edit_params = DialogueEditParams.model_validate(request.params)
            service = ProjectService(); project = service.open_project(dialogue_edit_params.project_directory)
            result = service.merge_dialogue_segment_with_next(dialogue_edit_params.project_directory, project, dialogue_edit_params.episode_id, dialogue_edit_params.segment_id).model_dump(mode="json")
        elif request.method == "project.dialogue_restore":
            dialogue_restore_params = DialogueRestoreParams.model_validate(request.params)
            service = ProjectService(); project = service.open_project(dialogue_restore_params.project_directory)
            result = service.restore_dialogue(dialogue_restore_params.project_directory, project, dialogue_restore_params.episode_id, dialogue_restore_params.expected_segments, dialogue_restore_params.dialogue_segments, dialogue_restore_params.speakers, dialogue_restore_params.dub_segments).model_dump(mode="json")
        elif request.method == "audio.prepare":
            audio_prepare_params = AudioPrepareParams.model_validate(request.params)
            def cancelled() -> bool: return audio_prepare_params.cancel_file is not None and audio_prepare_params.cancel_file.exists()
            if cancelled(): raise AudioPreparationCancelled("Audio preparation cancelled")
            result = AudioPreparationService(runner=FFmpegRunner(cancelled=cancelled)).prepare_speech_audio(project_directory=audio_prepare_params.project_directory, episode_id=audio_prepare_params.episode_id, source=audio_prepare_params.source, existing_asset=audio_prepare_params.existing_asset).model_dump(mode="json")
        elif request.method == "speech.transcribe":
            speech_transcribe_params = SpeechTranscribeParams.model_validate(request.params)
            from catty_engine.speakers.funasr import FunASRSpeakerPipeline
            from catty_engine.speech.backends import AsrBackendRegistry
            from catty_engine.speech.vad import WholeClipVad
            registry = create_asr_registry(speech_transcribe_params.asr_backend, speech_transcribe_params.asr_config) if speech_transcribe_params.asr_backend != "paraformer" else AsrBackendRegistry()
            vad = create_vad(speech_transcribe_params.vad_backend, speech_transcribe_params.vad_config) if speech_transcribe_params.asr_backend != "paraformer" else WholeClipVad()
            transcription = TranscriptionService(asr_backends=registry, vad=vad, speaker_pipeline=FunASRSpeakerPipeline()).transcribe(project_directory=speech_transcribe_params.project_directory, episode_id=speech_transcribe_params.episode_id, source=speech_transcribe_params.source, backend_id=speech_transcribe_params.asr_backend, language=speech_transcribe_params.language, source_start=speech_transcribe_params.source_start, duration=speech_transcribe_params.duration, existing_asset=speech_transcribe_params.existing_asset)
            service = ProjectService(); project = service.open_project(speech_transcribe_params.project_directory)
            service.replace_dialogue_segments(speech_transcribe_params.project_directory, project, speech_transcribe_params.episode_id, transcription.segments, source_language=speech_transcribe_params.language)
            result = transcription.model_dump(mode="json")
        else:
            probe_params = ProbeParams.model_validate(request.params)
            result = MediaProbeService().probe(probe_params.path).model_dump(mode="json")
        response["result"] = result
    except AudioPreparationCancelled as exc: response["error"] = {"code": "CANCELLED", "message": str(exc)}
    except FFmpegNotFoundError as exc: response["error"] = {"code": "FFMPEG_NOT_FOUND", "message": str(exc)}
    except FFmpegError as exc: response["error"] = {"code": "FFMPEG_FAILED", "message": str(exc)}
    except FFprobeNotFoundError as exc: response["error"] = {"code": "FFPROBE_NOT_FOUND", "message": str(exc)}
    except MediaProbeError as exc: response["error"] = {"code": "MEDIA_PROBE_FAILED", "message": str(exc)}
    except MediaError as exc: response["error"] = {"code": "MEDIA_ERROR", "message": str(exc)}
    except (ValidationError, ValueError, FileNotFoundError) as exc: response["error"] = {"code": "INVALID_REQUEST", "message": str(exc)}
    except Exception:
        traceback.print_exc(file=sys.stderr)
        response["error"] = {"code": "ENGINE_ERROR", "message": "The engine could not complete the request. See engine diagnostics."}
    return response

def _write_response(response: dict[str, Any]) -> None:
    print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)

def run_rpc() -> None:
    try: response = handle_request(json.load(sys.stdin))
    except (json.JSONDecodeError, UnicodeDecodeError): response = {"version": PROTOCOL_VERSION, "id": None, "error": {"code": "INVALID_JSON", "message": "Expected a JSON request on stdin."}}
    _write_response(response)

def run_server() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line: continue
        payload: Any = None
        try:
            payload = json.loads(line); response = handle_request(payload)
        except (json.JSONDecodeError, UnicodeDecodeError): response = {"version": PROTOCOL_VERSION, "id": None, "error": {"code": "INVALID_JSON", "message": "Expected one JSON request per line."}}
        _write_response(response)
        if isinstance(payload, dict) and payload.get("method") == "system.shutdown" and "error" not in response: break
