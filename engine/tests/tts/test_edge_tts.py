from pathlib import Path

import pytest

from catty_engine.tts.edge import EdgeTTSProvider, EdgeTTSError


def test_rate_converts_multiplier_to_edge_percent():
    assert EdgeTTSProvider._rate(1.0) == "+0%"
    assert EdgeTTSProvider._rate(1.25) == "+25%"
    assert EdgeTTSProvider._rate(0.8) == "-20%"


def test_synthesize_validates_user_controls(tmp_path: Path):
    provider = EdgeTTSProvider()
    with pytest.raises(ValueError, match="speed"):
        provider.synthesize("សួស្តី", tmp_path / "a.mp3", voice="km-KH-SreymomNeural", speed=2.1)
    with pytest.raises(ValueError, match="pitch"):
        provider.synthesize("សួស្តី", tmp_path / "a.mp3", voice="km-KH-SreymomNeural", pitch=101)
    with pytest.raises(ValueError, match="volume"):
        provider.synthesize("សួស្តី", tmp_path / "a.mp3", voice="km-KH-SreymomNeural", volume=-101)


def test_failed_synthesis_removes_partial_file(tmp_path: Path, monkeypatch):
    provider = EdgeTTSProvider()
    output = tmp_path / "voice.mp3"

    async def fail(*args, **kwargs):
        partial = output.with_suffix(".mp3.part")
        partial.write_bytes(b"partial")
        raise RuntimeError("network")

    monkeypatch.setattr(provider, "_synthesize", fail)
    with pytest.raises(EdgeTTSError, match="network"):
        provider.synthesize("សួស្តី", output, voice="km-KH-SreymomNeural")

    assert not output.exists()
    assert not output.with_suffix(".mp3.part").exists()
