from __future__ import annotations

from pathlib import Path
from typing import Any

from .backends import AsrBackendRegistry
from .model_manager import ModelManager
from .sense_voice import SenseVoiceBackend
from .vad import SileroVad, VadBackend


def create_asr_registry(backend_id: str, config: dict[str, Any]) -> AsrBackendRegistry:
    """Build the requested ASR backend.

    Chinese Paraformer uses Catty's integrated FunASR large-model stack so VAD,
    punctuation, sentence timing and CAM++ share one recognition pass. SenseVoice
    remains the lightweight sherpa-onnx alternative.
    """
    registry = AsrBackendRegistry()
    if backend_id == "paraformer":
        from catty_engine.speakers.funasr import FunASRParaformerBackend

        registry.register(FunASRParaformerBackend())
        return registry
    if backend_id == "sense-small":
        resolved = config or ModelManager().ensure_asr(backend_id)
        registry.register(
            SenseVoiceBackend(
                model=Path(_required(resolved, "model")),
                tokens=Path(_required(resolved, "tokens")),
                model_name=str(resolved.get("model_name", "sense-voice-small")),
                language=str(resolved.get("language", "auto")),
                use_itn=bool(resolved.get("use_itn", True)),
                num_threads=int(resolved.get("num_threads", 2)),
                provider=str(resolved.get("provider", "cpu")),
            )
        )
        return registry
    raise ValueError(f"Unsupported ASR backend: {backend_id}")


def create_vad(backend_id: str, config: dict[str, Any]) -> VadBackend:
    resolved = config or ModelManager().ensure_vad(backend_id)
    if backend_id == "silero":
        return SileroVad(
            model=Path(_required(resolved, "model")),
            threshold=float(resolved.get("threshold", 0.5)),
            min_silence_duration=float(resolved.get("min_silence_duration", 0.20)),
            min_speech_duration=float(resolved.get("min_speech_duration", 0.10)),
            max_speech_duration=float(resolved.get("max_speech_duration", 30.0)),
        )
    raise ValueError(f"Unsupported VAD backend: {backend_id}")


def _required(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing model configuration: {key}")
    return value
