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

    def _ensure_managed_paraformer(self) -> None:
        """Lazily provide Catty's canonical Paraformer recognizer when requested.

        Smart Transcribe deliberately builds speaker diarization separately from
        canonical ASR. The IPC path therefore may start with an empty registry;
        resolving Paraformer here keeps the transcript source independent from
        CAM++ while still using Catty-managed local model files.
        """
        if "paraformer" in self._backends:
            return

        from .model_manager import ModelManager
        from .paraformer import ParaformerBackend

        resolved = ModelManager().ensure_asr("paraformer")
        model = resolved.get("model")
        tokens = resolved.get("tokens")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Missing model configuration: model")
        if not isinstance(tokens, str) or not tokens.strip():
            raise ValueError("Missing model configuration: tokens")
        self.register(
            ParaformerBackend(
                model=Path(model),
                tokens=Path(tokens),
                model_name=str(resolved.get("model_name", "paraformer-zh")),
                num_threads=int(resolved.get("num_threads", 2)),
                provider=str(resolved.get("provider", "cpu")),
            )
        )

    def get(self, backend_id: str) -> AsrBackend:
        if backend_id == "paraformer" and backend_id not in self._backends:
            self._ensure_managed_paraformer()
        try:
            return self._backends[backend_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._backends)) or "none"
            raise ValueError(
                f"Unknown ASR backend '{backend_id}'. Available: {available}"
            ) from exc

    def ids(self) -> list[str]:
        return sorted(self._backends)
