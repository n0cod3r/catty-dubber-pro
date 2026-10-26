from pathlib import Path
from typing import Any

import pytest

from catty_engine.media import MediaProbeService


class FakeFFprobeRunner:
    def __init__(
        self,
        payload: dict[str, Any],
    ) -> None:
        self.payload = payload

    def probe(
        self,
        source: Path,
    ) -> dict[str, Any]:
        return self.payload


def test_probe_video_and_audio_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "EP01.mp4"
    source.touch()

    runner = FakeFFprobeRunner(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "24000/1001",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
            "format": {
                "duration": "183.42",
            },
        }
    )

    service = MediaProbeService(
        runner=runner,
    )

    media = service.probe(source)

    assert media.source_path == str(source.resolve())
    assert media.duration == pytest.approx(183.42)

    assert media.width == 1920
    assert media.height == 1080

    assert media.fps == pytest.approx(23.976, abs=0.001)

    assert media.video_codec == "h264"
    assert media.audio_codec == "aac"

    assert media.sample_rate == 48000
    assert media.channels == 2


def test_probe_handles_missing_audio(
    tmp_path: Path,
) -> None:
    source = tmp_path / "silent.mp4"
    source.touch()

    runner = FakeFFprobeRunner(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1280,
                    "height": 720,
                    "avg_frame_rate": "30/1",
                }
            ],
            "format": {
                "duration": "10.0",
            },
        }
    )

    service = MediaProbeService(
        runner=runner,
    )

    media = service.probe(source)

    assert media.duration == 10.0
    assert media.fps == 30.0

    assert media.audio_codec is None
    assert media.sample_rate is None
    assert media.channels is None


def test_probe_falls_back_to_r_frame_rate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "EP02.mp4"
    source.touch()

    runner = FakeFFprobeRunner(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "width": 3840,
                    "height": 2160,
                    "avg_frame_rate": "0/0",
                    "r_frame_rate": "25/1",
                }
            ],
            "format": {
                "duration": "42.5",
            },
        }
    )

    service = MediaProbeService(
        runner=runner,  # type: ignore[arg-type]
    )

    media = service.probe(source)

    assert media.fps == 25.0