from __future__ import annotations

from pathlib import Path
from typing import Protocol

import sherpa_onnx

from .models import SpeechRegion
from .wav import read_mono_pcm16


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


class SileroVad:
    """Local Silero VAD backed by sherpa-onnx.

    The model file is deliberately external to the engine package so Catty's
    model manager can install/update models without coupling app releases to
    model releases.
    """

    id = "silero"

    def __init__(
        self,
        model: str | Path,
        *,
        threshold: float = 0.5,
        min_silence_duration: float = 0.20,
        min_speech_duration: float = 0.10,
        max_speech_duration: float = 30.0,
    ) -> None:
        self._model = Path(model).expanduser().resolve()
        if not self._model.is_file():
            raise FileNotFoundError(f"Silero VAD model not found: {self._model}")
        self._threshold = threshold
        self._min_silence_duration = min_silence_duration
        self._min_speech_duration = min_speech_duration
        self._max_speech_duration = max_speech_duration

    def detect(
        self,
        audio: Path,
        *,
        start: float = 0,
        duration: float | None = None,
    ) -> list[SpeechRegion]:
        sample_rate, samples = read_mono_pcm16(audio, start=start, duration=duration)
        if sample_rate != 16_000:
            raise ValueError(f"Silero VAD expects 16 kHz audio, got {sample_rate} Hz")
        if samples.size == 0:
            return []

        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(self._model)
        config.silero_vad.threshold = self._threshold
        config.silero_vad.min_silence_duration = self._min_silence_duration
        config.silero_vad.min_speech_duration = self._min_speech_duration
        config.silero_vad.max_speech_duration = self._max_speech_duration
        config.sample_rate = sample_rate
        window_size = config.silero_vad.window_size
        vad = sherpa_onnx.VoiceActivityDetector(
            config,
            buffer_size_in_seconds=max(60, int((duration or 60) + 10)),
        )

        offset = 0
        while offset + window_size <= samples.size:
            vad.accept_waveform(samples[offset : offset + window_size])
            offset += window_size
        if offset < samples.size:
            tail = samples[offset:]
            if tail.size < window_size:
                import numpy as np

                tail = np.pad(tail, (0, window_size - tail.size))
            vad.accept_waveform(tail)
        vad.flush()

        regions: list[SpeechRegion] = []
        while not vad.empty():
            segment = vad.front
            relative_start = segment.start / sample_rate
            segment_duration = len(segment.samples) / sample_rate
            regions.append(
                SpeechRegion(
                    start=start + relative_start,
                    end=start + relative_start + segment_duration,
                )
            )
            vad.pop()
        return regions


class WholeClipVad:
    """Deterministic fallback useful for tests and model-less development."""

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
