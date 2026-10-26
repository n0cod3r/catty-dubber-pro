from __future__ import annotations


class MediaError(Exception):
    """Base error for media operations."""


class MediaProbeError(MediaError):
    """Raised when media metadata cannot be probed."""


class FFprobeNotFoundError(MediaProbeError):
    """Raised when ffprobe executable cannot be found."""