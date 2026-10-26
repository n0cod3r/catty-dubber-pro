from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import SpeechRegion, TranscriptSegment


class AsrBackend(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def model(self) -> str: ...

    def transcribe(
        self,
        audio: Path,
        regions: list[SpeechRegion],
        *,
        language: str,
    ) -> list[TranscriptSegment]: ...


class AsrBackendRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, AsrBackend] = {}

    def register(self, backend: AsrBackend) -> None:
        if backend.id in self._backends:
            raise ValueError(f"ASR backend already registered: {backend.id}")
        self._backends[backend.id] = backend

    def get(self, backend_id: str) -> AsrBackend:
        try:
            return self._backends[backend_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._backends)) or "none"
            raise ValueError(
                f"Unknown ASR backend '{backend_id}'. Available: {available}"
            ) from exc

    def ids(self) -> list[str]:
        return sorted(self._backends)
