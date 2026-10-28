"""Non-destructive semantic reconstruction for fragmented ASR dialogue."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from catty_engine.project.models import DialogueSegment

MAX_GROUP_SEGMENTS = 4
MAX_GROUP_CHARS = 48
MAX_GAP_SECONDS = 0.65
SHORT_FRAGMENT_CHARS = 10
_TERMINAL = frozenset("。！？!?；;…")
_CLOSING_MARKS = frozenset("”’\"'」』）)】]〉》")


@dataclass(frozen=True)
class SemanticUnit:
    """Adjacent timed rows that appear to belong to one spoken utterance.

    This is translation-only metadata. It never changes DialogueSegment timing,
    IDs, source text, or persistence.
    """

    segment_ids: tuple[UUID, ...]
    text: str


def _speaker_compatible(left: DialogueSegment, right: DialogueSegment) -> bool:
    # Unknown diarization must not prevent reconstruction. When both speakers
    # are known, however, a speaker change is a hard semantic boundary.
    return (
        left.speaker_id is None
        or right.speaker_id is None
        or left.speaker_id == right.speaker_id
    )


def _ends_sentence(text: str) -> bool:
    candidate = text.rstrip()
    while candidate and candidate[-1] in _CLOSING_MARKS:
        candidate = candidate[:-1].rstrip()
    return bool(candidate) and candidate[-1] in _TERMINAL


def _looks_continuous(left: DialogueSegment, right: DialogueSegment) -> bool:
    left_text = left.source_text.strip()
    right_text = right.source_text.strip()
    if not left_text or not right_text:
        return False
    if right.start - left.end > MAX_GAP_SECONDS:
        return False
    if not _speaker_compatible(left, right):
        return False
    if _ends_sentence(left_text):
        return False
    # Be conservative: long adjacent subtitle sentences should remain separate.
    return (
        len(left_text) <= SHORT_FRAGMENT_CHARS
        or len(right_text) <= SHORT_FRAGMENT_CHARS
    )


def build_semantic_units(segments: Sequence[DialogueSegment]) -> list[SemanticUnit]:
    """Group likely ASR fragments without modifying the persisted segments."""
    if not segments:
        return []

    groups: list[list[DialogueSegment]] = [[segments[0]]]
    for segment in segments[1:]:
        current = groups[-1]
        combined_chars = sum(len(item.source_text.strip()) for item in current) + len(
            segment.source_text.strip()
        )
        if (
            len(current) < MAX_GROUP_SEGMENTS
            and combined_chars <= MAX_GROUP_CHARS
            and _looks_continuous(current[-1], segment)
        ):
            current.append(segment)
        else:
            groups.append([segment])

    return [
        SemanticUnit(
            segment_ids=tuple(item.id for item in group),
            text="".join(item.source_text.strip() for item in group),
        )
        for group in groups
    ]


def semantic_context_by_segment(
    segments: Sequence[DialogueSegment],
) -> dict[UUID, SemanticUnit]:
    """Return only reconstructed units; single-row units need no extra prompt."""
    result: dict[UUID, SemanticUnit] = {}
    for unit in build_semantic_units(segments):
        if len(unit.segment_ids) < 2:
            continue
        for segment_id in unit.segment_ids:
            result[segment_id] = unit
    return result
