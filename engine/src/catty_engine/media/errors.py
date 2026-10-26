from __future__ import annotations


class MediaError(Exception):
    """Base error for media operations."""


class MediaProbeError(MediaError):
    """Raised when media metadata cannot be probed."""


class FFprobeNotFoundError(MediaProbeError):
    """Raised when ffprobe executable cannot be found."""


class FFmpegError(MediaError):
    """Raised when an FFmpeg operation fails."""


class FFmpegNotFoundError(FFmpegError):
    """Raised when the FFmpeg executable cannot be found."""


class AudioPreparationCancelled(MediaError):
    """Raised when the user cancels audio extraction."""
