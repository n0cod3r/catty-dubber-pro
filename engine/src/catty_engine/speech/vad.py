from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import SpeechRegion


class VadBackend(Protocol):
    @property
    def id(self) -> str: ...

    def detect(
        self,
        audio: Path,
        *,
        start: float = 0,
        duration: float | None = None,
    ) -> list[SpeechRegion]: ...


class WholeClipVad:
    """Fallback backend used until an installed VAD model is selected.

    It preserves the pipeline contract without pretending to detect speech:
    the selected clip is treated as one candidate region. Silero/other VADs
    can replace it through the same protocol without changing transcription.
    """

    id = "whole-clip"

    def detect(
        self,
        audio: Path,
        *,
        start: float = 0,
        duration: float | None = None,
    ) -> list[SpeechRegion]:
        del audio
        if duration is None or duration <= 0:
            raise ValueError("A positive clip duration is required")
        return [SpeechRegion(start=start, end=start + duration)]
