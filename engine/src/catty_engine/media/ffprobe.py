from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .errors import FFprobeNotFoundError, MediaProbeError


class FFprobeRunner:
    def __init__(
        self,
        executable: str | Path = "ffprobe",
    ) -> None:
        self._executable = str(executable)

    def probe(self, source: Path) -> dict[str, Any]:
        source = source.expanduser().resolve()

        if not source.exists():
            raise MediaProbeError(f"Media file does not exist: {source}")

        if not source.is_file():
            raise MediaProbeError(f"Media source is not a file: {source}")

        command = [
            self._executable,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(source),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired as exc:
            raise MediaProbeError(f"ffprobe timed out for {source}") from exc
        except FileNotFoundError as exc:
            raise FFprobeNotFoundError(
                f"ffprobe executable not found: {self._executable}"
            ) from exc
        except OSError as exc:
            raise MediaProbeError(f"Could not start ffprobe: {exc}") from exc

        if result.returncode != 0:
            message = result.stderr.strip() or "Unknown ffprobe error"

            raise MediaProbeError(f"ffprobe failed for {source}: {message}")

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MediaProbeError(
                f"ffprobe returned invalid JSON for {source}"
            ) from exc

        if not isinstance(payload, dict):
            raise MediaProbeError(f"ffprobe returned unexpected data for {source}")

        return payload
