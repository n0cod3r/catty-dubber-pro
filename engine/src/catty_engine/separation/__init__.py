"""Dialogue, music and effects separation."""
from .errors import SeparationError, SeparationModelMissing
from .mdx import (
    BACKGROUND_FILE_NAME,
    CHANNELS,
    SAMPLE_RATE,
    MdxBackgroundExtractor,
    MdxModelConfig,
    MdxSeparator,
    UVR_MDX_INST_HQ_3,
)
from .service import AudioSeparationService

__all__ = [
    "AudioSeparationService",
    "BACKGROUND_FILE_NAME",
    "CHANNELS",
    "MdxBackgroundExtractor",
    "MdxModelConfig",
    "MdxSeparator",
    "SAMPLE_RATE",
    "SeparationError",
    "SeparationModelMissing",
    "UVR_MDX_INST_HQ_3",
]
