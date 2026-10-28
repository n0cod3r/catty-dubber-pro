from __future__ import annotations


class SeparationError(Exception):
    """Base error for source separation."""


class SeparationModelMissing(SeparationError):
    """Raised when the separation model has not been installed."""
