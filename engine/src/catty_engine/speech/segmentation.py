"""Post-ASR dialogue splitting for subtitles, translation and TTS.

Recognition keeps full VAD context. This module only shortens already-timed,
punctuated sentences so downstream per-line work stays practical. Splits prefer
Chinese punctuation over proportional timing, and never invent word timestamps.
"""

from __future__ import annotations

import math

from .models import TranscriptSegment

MAX_DIALOGUE_DURATION = 6.0
MIN_DIALOGUE_DURATION = 0.8
MIN_PIECE_CHARACTERS = 2

STRONG_PUNCTUATION = frozenset("。！？；!?;")
WEAK_PUNCTUATION = frozenset("，、,:")
_EPSILON = 1e-6


def _candidate_indices(text: str) -> list[tuple[int, int]]:
    """Return (characters-before-cut, strength) after each punctuation mark."""
    return [
        (index + 1, 2 if character in STRONG_PUNCTUATION else 1)
        for index, character in enumerate(text)
        if character in STRONG_PUNCTUATION or character in WEAK_PUNCTUATION
    ]


def _time_at(segment: TranscriptSegment, index: int, total: int) -> float:
    if index <= 0:
        return segment.start
    if index >= total:
        return segment.end
    return segment.start + (segment.end - segment.start) * (index / total)


def _choose_boundaries(
    segment: TranscriptSegment, max_duration: float
) -> list[int]:
    text = segment.text
    total = len(text)
    duration = segment.end - segment.start
    if total < 2 or duration <= max_duration + _EPSILON:
        return []

    candidates = _candidate_indices(text)
    max_chars = max(
        MIN_PIECE_CHARACTERS, math.floor(max_duration / duration * total)
    )
    min_chars = max(
        MIN_PIECE_CHARACTERS, math.floor(MIN_DIALOGUE_DURATION / duration * total)
    )
    boundaries: list[int] = []
    left = 0
    while _time_at(segment, left, total) + max_duration < segment.end - _EPSILON:
        window_start = min(total, left + min_chars)
        window_end = min(total - MIN_PIECE_CHARACTERS, left + max_chars)
        if window_end <= left:
            break
        window_start = min(window_start, window_end)
        window = [
            candidate
            for candidate in candidates
            if left < candidate[0] <= window_end and candidate[0] >= window_start
        ]
        strong = [candidate for candidate in window if candidate[1] == 2]
        pool = strong or window
        cut = max(pool, key=lambda candidate: candidate[0])[0] if pool else window_end
        if cut <= left:
            cut = min(total - 1, left + 1)
        boundaries.append(cut)
        left = cut
    return boundaries


def _build_pieces(
    segment: TranscriptSegment, boundaries: list[int]
) -> list[TranscriptSegment]:
    total = len(segment.text)
    edges = [0, *boundaries, total]
    pieces: list[TranscriptSegment] = []
    for start_index, end_index in zip(edges, edges[1:]):
        text = segment.text[start_index:end_index].strip()
        if not text:
            continue
        start = _time_at(segment, start_index, total)
        end = _time_at(segment, end_index, total)
        if end <= start:
            continue
        pieces.append(
            segment.model_copy(update={"start": start, "end": end, "text": text})
        )
    return pieces


def _merge_short_pieces(
    pieces: list[TranscriptSegment], min_duration: float
) -> list[TranscriptSegment]:
    if len(pieces) < 2:
        return pieces
    merged = [pieces[0]]
    for piece in pieces[1:]:
        previous = merged[-1]
        if piece.end - piece.start < min_duration:
            merged[-1] = previous.model_copy(
                update={"end": piece.end, "text": f"{previous.text}{piece.text}"}
            )
        else:
            merged.append(piece)
    if len(merged) > 1 and merged[0].end - merged[0].start < min_duration:
        first, second = merged[0], merged[1]
        merged[1] = second.model_copy(
            update={"start": first.start, "text": f"{first.text}{second.text}"}
        )
        merged.pop(0)
    return merged


def split_long_dialogue(
    segments: list[TranscriptSegment],
    *,
    max_duration: float = MAX_DIALOGUE_DURATION,
) -> list[TranscriptSegment]:
    """Split long recognized sentences without changing source text or order."""
    if max_duration <= 0:
        raise ValueError("max_duration must be > 0")
    result: list[TranscriptSegment] = []
    for segment in segments:
        if segment.end - segment.start <= max_duration + _EPSILON:
            result.append(segment)
            continue
        boundaries = _choose_boundaries(segment, max_duration)
        pieces = _build_pieces(segment, boundaries)
        if not pieces:
            result.append(segment)
            continue
        result.extend(_merge_short_pieces(pieces, MIN_DIALOGUE_DURATION))
    return result
