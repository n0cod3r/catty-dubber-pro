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
        # Compatibility for older callers that constructed an empty registry for
        # Smart Transcribe. This no longer downloads/loads the sherpa small model;
        # the canonical backend is the same integrated FunASR large pipeline used
        # by create_asr_registry(). New callers should use that factory directly.
        if backend_id == "paraformer" and backend_id not in self._backends:
            from catty_engine.speakers.funasr import FunASRParaformerBackend

            self.register(FunASRParaformerBackend())
        try:
            return self._backends[backend_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._backends)) or "none"
            raise ValueError(
                f"Unknown ASR backend '{backend_id}'. Available: {available}"
            ) from exc

    def ids(self) -> list[str]:
        return sorted(self._backends)
