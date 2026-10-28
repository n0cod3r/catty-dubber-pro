from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from .library import VoiceDraft, VoiceLibrary


class VoiceIdParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice_id: str


class UseVoiceParams(VoiceIdParams):
    project_directory: Path


class PreviewParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice_id: str | None = None
    draft: VoiceDraft | None = None

    @model_validator(mode="after")
    def one_source(self) -> PreviewParams:
        if (self.voice_id is None) == (self.draft is None):
            raise ValueError("Supply a voice_id or a draft")
        return self


def dispatch(method: str, params: dict[str, Any]) -> Any:
    library = VoiceLibrary()
    if method == "tts.library_list":
        if params:
            raise ValueError("Voice listing does not accept parameters")
        return [voice.model_dump(mode="json") for voice in library.list()]
    if method == "tts.library_create":
        return library.create(VoiceDraft.model_validate(params)).model_dump(mode="json")
    if method == "tts.library_preview":
        parsed = PreviewParams.model_validate(params)
        return {"path": str(library.preview(voice_id=parsed.voice_id, draft=parsed.draft))}
    if method == "tts.library_remove":
        library.remove(VoiceIdParams.model_validate(params).voice_id)
        return {"removed": True}
    if method == "tts.library_use":
        use = UseVoiceParams.model_validate(params)
        return library.use_in_project(use.voice_id, use.project_directory).model_dump(mode="json")
    raise ValueError("Unknown voice library operation")
