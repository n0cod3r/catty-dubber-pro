from catty_engine.speech.models import TranscriptSegment
from catty_engine.speech.segmentation import split_long_dialogue


def _joined(segments: list[TranscriptSegment]) -> str:
    return "".join(segment.text for segment in segments)


def test_short_sentence_is_kept_unchanged() -> None:
    original = TranscriptSegment(
        start=1.0, end=4.0, text="你好。", speaker="S1", confidence=0.9
    )
    assert split_long_dialogue([original]) == [original]


def test_long_sentence_prefers_punctuation_and_preserves_text() -> None:
    text = "我今天本来不想来的，但是他说有很重要的事情，所以我还是过来了。"
    original = TranscriptSegment(start=0.0, end=8.0, text=text, speaker="S2")
    result = split_long_dialogue([original])
    assert len(result) == 2
    assert _joined(result) == text
    assert result[0].text.endswith("，")
    assert result[0].speaker == "S2"
    assert result[1].text.startswith("所以")
    assert result[0].start == 0.0
    assert result[-1].end == 8.0
    assert all(later.start >= earlier.end for earlier, later in zip(result, result[1:]))


def test_no_punctuation_uses_proportional_fallback() -> None:
    text = "字" * 30
    original = TranscriptSegment(start=2.0, end=22.0, text=text)
    result = split_long_dialogue([original])
    assert len(result) > 1
    assert _joined(result) == text
    assert result[0].start == 2.0
    assert result[-1].end == 22.0
    assert all(segment.end > segment.start for segment in result)
    assert all(later.start >= earlier.end for earlier, later in zip(result, result[1:]))
    assert all(segment.end - segment.start <= 6.0 + 1e-6 for segment in result)


def test_tiny_tail_is_merged_into_previous_piece() -> None:
    text = "字" * 100
    original = TranscriptSegment(start=0.0, end=61.0, text=text)
    result = split_long_dialogue([original])
    assert _joined(result) == text
    assert len(result) > 1
    assert all(segment.end - segment.start >= 0.8 for segment in result)
    assert result[-1].end == 61.0


def test_two_character_sentence_is_not_split() -> None:
    original = TranscriptSegment(start=2.0, end=10.0, text="你好")
    assert split_long_dialogue([original]) == [original]
