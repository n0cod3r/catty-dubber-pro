from __future__ import annotations

import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from .errors import AudioPreparationCancelled, FFmpegError, FFmpegNotFoundError


class FFmpegRunner:
    def __init__(
        self,
        executable: str | Path = "ffmpeg",
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._executable = str(executable)
        self._cancelled = cancelled or (lambda: False)

    def extract_speech_audio(
        self,
        source: Path,
        destination: Path,
        *,
        sample_rate: int = 16_000,
        channels: int = 1,
    ) -> None:
        source = source.expanduser().resolve()
        destination = destination.expanduser().resolve()
        if source == destination:
            raise FFmpegError("Prepared audio must not overwrite its source file")
        if not source.is_file():
            raise FFmpegError(f"Media source is not a file: {source}")
        if self._cancelled():
            raise AudioPreparationCancelled("Audio preparation cancelled")
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Publish only a complete WAV. Cancellation and failures keep any prior
        # valid cached asset intact and remove the staged output.
        with tempfile.NamedTemporaryFile(
            prefix=".speech-", suffix=".wav", dir=destination.parent, delete=False
        ) as staged:
            temporary = Path(staged.name)
        process: subprocess.Popen[str] | None = None
        try:
            command = [
                self._executable,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-map",
                "0:a:0",
                "-ac",
                str(channels),
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                str(temporary),
            ]
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            started = time.monotonic()
            while True:
                if self._cancelled():
                    raise AudioPreparationCancelled("Audio preparation cancelled")
                if time.monotonic() - started > 3600:
                    raise FFmpegError("Audio preparation exceeded one hour")
                try:
                    _, stderr = process.communicate(timeout=0.15)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if self._cancelled():
                raise AudioPreparationCancelled("Audio preparation cancelled")
            if process.returncode != 0:
                raise FFmpegError(
                    f"FFmpeg failed for {source}: {stderr.strip() or 'Unknown FFmpeg error'}"
                )
            if temporary.stat().st_size == 0:
                raise FFmpegError("FFmpeg created an empty audio file")
            temporary.replace(destination)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError(
                f"FFmpeg executable not found: {self._executable}"
            ) from exc
        except OSError as exc:
            raise FFmpegError(f"Could not prepare audio: {exc}") from exc
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
            temporary.unlink(missing_ok=True)
