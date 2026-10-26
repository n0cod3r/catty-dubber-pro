from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import (
    FFmpegError,
    FFmpegNotFoundError,
)


class FFmpegRunner:
    def __init__(
        self,
        executable: str | Path = "ffmpeg",
    ) -> None:
        self._executable = str(executable)

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

        if not source.exists():
            raise FFmpegError(
                f"Media source does not exist: {source}"
            )

        if not source.is_file():
            raise FFmpegError(
                f"Media source is not a file: {source}"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        command = [
            self._executable,
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
            str(destination),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError(
                f"FFmpeg executable not found: {self._executable}"
            ) from exc
        except OSError as exc:
            raise FFmpegError(
                f"Could not start FFmpeg: {exc}"
            ) from exc

        if result.returncode != 0:
            destination.unlink(missing_ok=True)

            message = (
                result.stderr.strip()
                or "Unknown FFmpeg error"
            )

            raise FFmpegError(
                f"FFmpeg failed for {source}: {message}"
            )

        if not destination.exists():
            raise FFmpegError(
                "FFmpeg completed without creating "
                f"the output file: {destination}"
            )

        if destination.stat().st_size == 0:
            destination.unlink(missing_ok=True)

            raise FFmpegError(
                f"FFmpeg created an empty file: {destination}"
            )