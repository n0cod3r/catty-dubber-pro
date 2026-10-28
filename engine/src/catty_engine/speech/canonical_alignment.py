"""Build canonical Chinese dialogue from observed Paraformer word timestamps.

FunASR's merged ``sentence_info`` can lose VAD-gap offsets after it concatenates
per-VAD ASR chunks for punctuation/speaker processing.  The raw Paraformer stage
still owns the correct chunk-relative word timestamps.  This module aligns the
punctuated text back onto those absolute timestamps without changing recognized
text or running another model pass.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from .models import TranscriptSegment

_STRONG = frozenset("。！？；!?;")
_WEAK = frozenset("，、,:：")


def _is_alignment_character(character: str) -> bool:
    category = unicodedata.category(character)
    return not character.isspace() and not category.startswith(("P", "S", "Z", "C"))


def _spoken_characters(text: str) -> list[str]:
    return [character for character in text if _is_alignment_character(character)]


def _speaker_ranges(result: list[dict[str, Any]]) -> list[tuple[int, int, int]]:
    """Return speaker ranges in spoken-character coordinates, not timestamps."""
    ranges: list[tuple[int, int, int]] = []
    cursor = 0
    for sentence in result[0].get("sentence_info", []) if result else []:
        value = sentence.get("sentence") or sentence.get("text", "")
        if isinstance(value, list):
            value = "".join(str(item) for item in value)
        length = len(_spoken_characters(str(value)))
        end = cursor + length
        speaker = sentence.get("spk")
        if length and speaker is not None:
            ranges.append((cursor, end, int(speaker)))
        cursor = end
    return ranges


def _speaker_for_span(
    left: int, right: int, ranges: list[tuple[int, int, int]]
) -> int | None:
    overlap: dict[int, int] = {}
    for start, end, speaker in ranges:
        amount = max(0, min(right, end) - max(left, start))
        if amount:
            overlap[speaker] = overlap.get(speaker, 0) + amount
    return max(overlap, key=overlap.get) if overlap else None


def align_observed_paraformer(
    result: list[dict[str, Any]],
    raw_asr: list[dict[str, Any]],
    *,
    start: float,
    duration: float,
) -> list[TranscriptSegment] | None:
    """Return word-timed punctuated dialogue, or ``None`` when alignment is unsafe.

    The function is deliberately strict.  It is used only when every recognized
    spoken character can be paired one-to-one with an observed Paraformer word
    timestamp and with the final punctuated text.  Any mismatch falls back to
    FunASR ``sentence_info`` rather than inventing timing.
    """
    if not result or not raw_asr:
        return None
    punctuated = str(result[0].get("text", "")).strip()
    if not punctuated:
        return None

    timed: list[tuple[str, float, float]] = []
    ordered = sorted(
        raw_asr,
        key=lambda row: float((row.get("vad_region") or {}).get("start", float("inf"))),
    )
    for row in ordered:
        native = row.get("native") or {}
        characters = _spoken_characters(str(native.get("text", "")))
        timestamps = row.get("absolute_word_timestamps") or []
        if len(characters) != len(timestamps):
            return None
        for character, pair in zip(characters, timestamps, strict=True):
            if not isinstance(pair, list) or len(pair) < 2:
                return None
            left, right = float(pair[0]), float(pair[1])
            if right <= left:
                return None
            timed.append((character, left, right))

    punctuated_characters = _spoken_characters(punctuated)
    if punctuated_characters != [character for character, _, _ in timed]:
        return None
    if not timed:
        return None

    speaker_ranges = _speaker_ranges(result)
    labels: dict[int, str] = {}
    segments: list[TranscriptSegment] = []
    text_buffer: list[str] = []
    word_left = 0
    word_cursor = 0

    def flush() -> None:
        nonlocal text_buffer, word_left
        if word_cursor <= word_left:
            return
        text = "".join(text_buffer).strip()
        if not text:
            return
        first = timed[word_left]
        last = timed[word_cursor - 1]
        left = max(start, first[1])
        right = min(start + duration, last[2])
        if right <= left:
            return
        cluster = _speaker_for_span(word_left, word_cursor, speaker_ranges)
        speaker = labels.setdefault(cluster, f"S{len(labels) + 1}") if cluster is not None else None
        segments.append(TranscriptSegment(start=left, end=right, text=text, speaker=speaker))
        text_buffer = []
        word_left = word_cursor

    for character in punctuated:
        if _is_alignment_character(character):
            if word_cursor >= len(timed) or character != timed[word_cursor][0]:
                return None
            text_buffer.append(character)
            word_cursor += 1
            continue
        if character.isspace():
            continue
        text_buffer.append(character)
        if character in _STRONG or character in _WEAK:
            flush()

    flush()
    if word_cursor != len(timed):
        return None
    return segments or None
