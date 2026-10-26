from __future__ import annotations

from pathlib import Path
from typing import Any

from .backends import AsrBackendRegistry
from .paraformer import ParaformerBackend
from .vad import SileroVad, VadBackend


def create_asr_registry(backend_id: str, config: dict[str, Any]) -> AsrBackendRegistry:
    """Build installed ASR backends without leaking model-specific config upstream.

    Add future model families here; the transcription service and IPC contract stay
    unchanged because callers select a backend ID plus an opaque config object.
    """
    registry = AsrBackendRegistry()
    if backend_id == "paraformer":
        registry.register(
            ParaformerBackend(
                model=Path(_required(config, "model")),
                tokens=Path(_required(config, "tokens")),
                model_name=str(config.get("model_name", "paraformer-zh")),
                num_threads=int(config.get("num_threads", 2)),
                provider=str(config.get("provider", "cpu")),
            )
        )
        return registry
    raise ValueError(f"Unsupported ASR backend: {backend_id}")


def create_vad(backend_id: str, config: dict[str, Any]) -> VadBackend:
    if backend_id == "silero":
        return SileroVad(
            model=Path(_required(config, "model")),
            threshold=float(config.get("threshold", 0.5)),
            min_silence_duration=float(config.get("min_silence_duration", 0.20)),
            min_speech_duration=float(config.get("min_speech_duration", 0.10)),
            max_speech_duration=float(config.get("max_speech_duration", 30.0)),
        )
    raise ValueError(f"Unsupported VAD backend: {backend_id}")


def _required(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing model configuration: {key}")
    return value
