"""Speech detection, ASR and diarization orchestration."""

from .backends import AsrBackend, AsrBackendRegistry
from .models import SpeechRegion, TranscriptSegment, TranscriptionResult
from .segmentation import MAX_DIALOGUE_DURATION, split_long_dialogue
from .transcription import TranscriptionService
from .vad import SileroVad, VadBackend, WholeClipVad

__all__ = [
    "AsrBackend",
    "AsrBackendRegistry",
    "MAX_DIALOGUE_DURATION",
    "SileroVad",
    "SpeechRegion",
    "TranscriptSegment",
    "TranscriptionResult",
    "TranscriptionService",
    "VadBackend",
    "WholeClipVad",
    "split_long_dialogue",
]
