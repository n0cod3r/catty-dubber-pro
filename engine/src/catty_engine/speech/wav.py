from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


class WaveFormatError(ValueError):
    pass


def read_mono_pcm16(
    path: str | Path,
    *,
    start: float = 0,
    duration: float | None = None,
) -> tuple[int, NDArray[np.float32]]:
    """Read a time range from the engine's prepared mono PCM16 WAV."""
    source = Path(path)
    if start < 0:
        raise ValueError("start must be >= 0")
    if duration is not None and duration <= 0:
        raise ValueError("duration must be > 0")

    with wave.open(str(source), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise WaveFormatError("Expected mono 16-bit PCM WAV")
        sample_rate = wav.getframerate()
        start_frame = min(round(start * sample_rate), wav.getnframes())
        wav.setpos(start_frame)
        frames = (
            wav.getnframes() - start_frame
            if duration is None
            else min(round(duration * sample_rate), wav.getnframes() - start_frame)
        )
        raw = wav.readframes(frames)

    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32)
    samples /= 32768.0
    return sample_rate, samples
