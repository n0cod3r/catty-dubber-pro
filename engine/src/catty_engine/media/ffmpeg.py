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

    def _run(self, command: list[str], *, operation: str) -> None:
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            started = time.monotonic()
            while True:
                if self._cancelled():
                    raise AudioPreparationCancelled(f"{operation} cancelled")
                if time.monotonic() - started > 3600:
                    raise FFmpegError(f"{operation} exceeded one hour")
                try:
                    _, stderr = process.communicate(timeout=0.15)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode != 0:
                raise FFmpegError(stderr.strip() or f"{operation} failed")
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError(f"FFmpeg executable not found: {self._executable}") from exc
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()

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
        with tempfile.NamedTemporaryFile(
            prefix=".speech-", suffix=".wav", dir=destination.parent, delete=False
        ) as staged:
            temporary = Path(staged.name)
        try:
            self._run(
                [
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
                ],
                operation="Audio preparation",
            )
            if temporary.stat().st_size == 0:
                raise FFmpegError("FFmpeg created an empty audio file")
            temporary.replace(destination)
        except OSError as exc:
            raise FFmpegError(f"Could not prepare audio: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def create_playback_proxy(self, source: Path, destination: Path) -> None:
        source = source.expanduser().resolve()
        destination = destination.expanduser().resolve()
        if not source.is_file():
            raise FFmpegError(f"Media source is not a file: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=".proxy-", suffix=".mp4", dir=destination.parent, delete=False
        ) as staged:
            temporary = Path(staged.name)
        try:
            # Preview proxy owns both picture and monitoring audio. Keeping them in
            # one media element avoids drift caused by separately clocked video/audio
            # elements while editing. Original media remains untouched for export.
            self._run(
                [
                    self._executable,
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-vf",
                    "scale='min(1280,iw)':-2",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "24",
                    "-pix_fmt",
                    "yuv420p",
                    "-g",
                    "30",
                    "-keyint_min",
                    "30",
                    "-sc_threshold",
                    "0",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-movflags",
                    "+faststart",
                    str(temporary),
                ],
                operation="Playback proxy generation",
            )
            if temporary.stat().st_size == 0:
                raise FFmpegError("FFmpeg created an empty playback proxy")
            temporary.replace(destination)
        except OSError as exc:
            raise FFmpegError(f"Could not prepare playback proxy: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)
