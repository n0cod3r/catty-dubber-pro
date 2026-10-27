from __future__ import annotations

from pathlib import Path

from .ffmpeg import FFmpegRunner
from .fingerprint import source_fingerprint

PLAYBACK_PROXY_FILE_NAME = "playback-proxy-av-v2.mp4"


class VideoProxyService:
    """Create a lightweight, seek-friendly H.264/AAC proxy for editor playback."""

    def __init__(self, runner: FFmpegRunner | None = None) -> None:
        self._runner = runner or FFmpegRunner()

    def prepare_playback_proxy(
        self,
        *,
        project_directory: Path,
        source: str | Path,
        existing_path: str | None = None,
        force: bool = False,
    ) -> str:
        source_path = Path(source).expanduser().resolve()
        fingerprint = source_fingerprint(source_path)
        destination = (
            project_directory
            / "assets"
            / "media"
            / fingerprint
            / "video"
            / PLAYBACK_PROXY_FILE_NAME
        ).resolve()

        if not force:
            if existing_path:
                existing = Path(existing_path).expanduser().resolve()
                if existing == destination and self._valid(destination):
                    return str(destination)
            if self._valid(destination):
                return str(destination)

        # FFmpeg writes to a staged file and atomically replaces destination, so
        # a failed rebuild never destroys the last usable proxy.
        self._runner.create_playback_proxy(source_path, destination)
        return str(destination)

    @staticmethod
    def _valid(path: Path) -> bool:
        return path.is_file() and path.stat().st_size > 0
