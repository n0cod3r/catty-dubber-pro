from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from catty_engine.speech.wav import WaveFormatError, read_mono_pcm16


def write_wave(path: Path, *, channels: int = 1) -> None:
    sample_rate = 16_000
    values = [
        int(10_000 * math.sin(2 * math.pi * 440 * i / sample_rate))
        for i in range(sample_rate)
    ]
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = b"".join(struct.pack("<h", value) * channels for value in values)
        output.writeframes(frames)


def test_reads_selected_wave_range(tmp_path: Path) -> None:
    audio = tmp_path / "speech.wav"
    write_wave(audio)

    sample_rate, samples = read_mono_pcm16(audio, start=0.25, duration=0.5)

    assert sample_rate == 16_000
    assert samples.shape == (8_000,)
    assert samples.dtype.name == "float32"
    assert float(abs(samples).max()) <= 1


def test_rejects_non_mono_prepared_audio(tmp_path: Path) -> None:
    audio = tmp_path / "stereo.wav"
    write_wave(audio, channels=2)

    with pytest.raises(WaveFormatError, match="mono"):
        read_mono_pcm16(audio)
