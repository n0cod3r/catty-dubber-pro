from __future__ import annotations

from catty_engine.logging import logged_process

from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol

from .models import MediaInfo

from .errors import MediaProbeError
from .ffprobe import FFprobeRunner


class ProbeRunner(Protocol):
    def probe(
        self,
        source: Path,
    ) -> dict[str, Any]: ...


class MediaProbeService:
    def __init__(
        self,
        runner: ProbeRunner | None = None,
    ) -> None:
        self._runner: ProbeRunner = runner or FFprobeRunner()

    @logged_process
    def probe(self, source: str | Path) -> MediaInfo:
        path = Path(source).expanduser().resolve()
        payload = self._runner.probe(path)

        streams = payload.get("streams", [])
        format_info = payload.get("format", {})

        if not isinstance(streams, list):
            streams = []

        if not isinstance(format_info, dict):
            format_info = {}

        video_stream = self._first_stream(streams, "video")
        audio_stream = self._first_stream(streams, "audio")

        duration = self._duration(
            format_info=format_info,
            video_stream=video_stream,
            audio_stream=audio_stream,
        )

        return MediaInfo(
            source_path=str(path),
            duration=duration,
            width=self._optional_int(video_stream.get("width")),
            height=self._optional_int(video_stream.get("height")),
            fps=self._fps(video_stream),
            video_codec=self._optional_string(video_stream.get("codec_name")),
            audio_codec=self._optional_string(audio_stream.get("codec_name")),
            sample_rate=self._optional_int(audio_stream.get("sample_rate")),
            channels=self._optional_int(audio_stream.get("channels")),
        )

    @staticmethod
    def _first_stream(
        streams: list[Any],
        codec_type: str,
    ) -> dict[str, Any]:
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
                return stream

        return {}

    @staticmethod
    def _duration(
        *,
        format_info: dict[str, Any],
        video_stream: dict[str, Any],
        audio_stream: dict[str, Any],
    ) -> float | None:
        candidates = [
            format_info.get("duration"),
            video_stream.get("duration"),
            audio_stream.get("duration"),
        ]

        for candidate in candidates:
            value = MediaProbeService._optional_float(candidate)

            if value is not None and value >= 0:
                return value

        return None

    @staticmethod
    def _fps(
        video_stream: dict[str, Any],
    ) -> float | None:
        for key in ("avg_frame_rate", "r_frame_rate"):
            raw = video_stream.get(key)

            if raw is None:
                continue

            try:
                fraction = Fraction(str(raw))

                if fraction.denominator == 0:
                    continue

                fps = float(fraction)

                if fps > 0:
                    return fps
            except (ValueError, ZeroDivisionError):
                continue

        return None

    @staticmethod
    def _optional_string(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        text = str(value).strip()

        return text or None

    @staticmethod
    def _optional_int(
        value: Any,
    ) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_float(
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class BatchMediaProbeResult:
    def __init__(self) -> None:
        self.media: dict[Path, MediaInfo] = {}
        self.errors: dict[Path, MediaProbeError] = {}


class BatchMediaProbeService:
    def __init__(
        self,
        probe: MediaProbeService | None = None,
    ) -> None:
        self._probe = probe or MediaProbeService()

    @logged_process
    def probe(
        self,
        sources: list[str | Path],
    ) -> BatchMediaProbeResult:
        result = BatchMediaProbeResult()

        for source in sources:
            path = Path(source).expanduser().resolve()

            try:
                result.media[path] = self._probe.probe(path)
            except MediaProbeError as exc:
                result.errors[path] = exc

        return result
