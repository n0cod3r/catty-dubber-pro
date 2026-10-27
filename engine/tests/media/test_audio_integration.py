import json
import shutil
import sys
import threading
import wave
from pathlib import Path
from uuid import uuid4

import pytest

from catty_engine.ipc import handle_request
from catty_engine.media.errors import (
    AudioPreparationCancelled,
    FFmpegError,
    FFmpegNotFoundError,
)
from catty_engine.media.ffmpeg import FFmpegRunner


def write_audio(path: Path) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(48_000)
        stream.writeframes(b"\0" * 19_200)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_rpc_prepares_real_audio_and_reuses_valid_cache(tmp_path: Path) -> None:
    source = tmp_path / "source with spaces.wav"
    write_audio(source)
    params = {
        "source": str(source),
        "project_directory": str(tmp_path / "project"),
        "episode_id": str(uuid4()),
    }
    request = {"version": 1, "id": "audio", "method": "audio.prepare", "params": params}
    first = handle_request(request)
    assert "error" not in first, json.dumps(first)
    asset = first["result"]
    output = Path(asset["path"])
    with wave.open(str(output), "rb") as stream:
        assert stream.getframerate() == 16_000
        assert stream.getnchannels() == 1
        assert stream.getsampwidth() == 2
        assert stream.getnframes() > 0
    modified = output.stat().st_mtime_ns
    second = handle_request({**request, "params": {**params, "existing_asset": asset}})
    assert second["result"] == asset
    assert output.stat().st_mtime_ns == modified
    assert not list(output.parent.glob(".speech-*"))


def test_cancelled_rpc_does_not_create_output(tmp_path: Path) -> None:
    marker = tmp_path / "cancel"
    marker.touch()
    response = handle_request(
        {
            "version": 1,
            "id": "cancel",
            "method": "audio.prepare",
            "params": {
                "source": "missing.wav",
                "project_directory": str(tmp_path / "project"),
                "episode_id": str(uuid4()),
                "cancel_file": str(marker),
            },
        }
    )
    assert response["error"]["code"] == "CANCELLED"
    assert not (tmp_path / "project").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX executable fixture")
def test_cancel_stops_child_and_preserves_cached_audio(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    write_audio(source)
    destination = tmp_path / "speech.wav"
    destination.write_bytes(b"existing valid cached output")
    executable = tmp_path / "fake-ffmpeg"
    executable.write_text(
        f"#!{sys.executable}\nimport sys,time\nfrom pathlib import Path\nPath(sys.argv[-1]).write_bytes(b'partial')\ntime.sleep(10)\n"
    )
    executable.chmod(0o700)
    cancelled = threading.Event()
    timer = threading.Timer(0.2, cancelled.set)
    timer.start()
    try:
        with pytest.raises(AudioPreparationCancelled):
            FFmpegRunner(executable, cancelled=cancelled.is_set).extract_speech_audio(
                source, destination
            )
    finally:
        timer.cancel()
    assert destination.read_bytes() == b"existing valid cached output"
    assert not list(tmp_path.glob(".speech-*"))


def test_missing_ffmpeg_does_not_damage_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    write_audio(source)
    destination = tmp_path / "speech.wav"
    destination.write_bytes(b"valid cached output")
    with pytest.raises(FFmpegNotFoundError):
        FFmpegRunner(tmp_path / "missing-ffmpeg").extract_speech_audio(
            source, destination
        )
    assert destination.read_bytes() == b"valid cached output"
    assert not list(tmp_path.glob(".speech-*"))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_video_without_audio_returns_error_and_leaves_no_partial(
    tmp_path: Path,
) -> None:
    import subprocess

    source = tmp_path / "silent.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=16x16:d=0.1",
            "-an",
            "-c:v",
            "mpeg4",
            str(source),
        ],
        check=True,
        timeout=10,
    )
    response = handle_request(
        {
            "version": 1,
            "id": "silent",
            "method": "audio.prepare",
            "params": {
                "source": str(source),
                "project_directory": str(tmp_path / "project"),
                "episode_id": str(uuid4()),
            },
        }
    )
    assert response["error"]["code"] == "FFMPEG_FAILED"
    assert not list((tmp_path / "project").rglob("*.wav"))


def test_preparation_cannot_overwrite_its_source(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    write_audio(source)
    original = source.read_bytes()
    with pytest.raises(FFmpegError, match="overwrite"):
        FFmpegRunner().extract_speech_audio(source, source)
    assert source.read_bytes() == original
