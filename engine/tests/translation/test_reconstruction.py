from uuid import uuid4

from catty_engine.project import DialogueSegment
from catty_engine.settings.models import AppSettings
from catty_engine.translation.providers.other import _hy_mt2_prompt
from catty_engine.translation.reconstruction import (
    build_semantic_units,
    semantic_context_by_segment,
)
from catty_engine.translation.service import TranslationService


def segment(start: float, end: float, text: str, speaker_id=None) -> DialogueSegment:
    return DialogueSegment(
        start=start,
        end=end,
        source_language="zh",
        source_text=text,
        speaker_id=speaker_id,
    )


def test_fragmented_chinese_is_reconstructed_without_changing_rows() -> None:
    speaker = uuid4()
    rows = [
        segment(0.0, 0.6, "裴国", speaker),
        segment(0.65, 1.2, "公的未婚", speaker),
        segment(1.25, 2.1, "妻哦未婚妻哪来？", speaker),
    ]
    original = [(row.id, row.start, row.end, row.source_text) for row in rows]
    units = build_semantic_units(rows)
    assert len(units) == 1
    assert units[0].text == "裴国公的未婚妻哦未婚妻哪来？"
    assert units[0].segment_ids == tuple(row.id for row in rows)
    assert [(row.id, row.start, row.end, row.source_text) for row in rows] == original


def test_reconstruction_stops_at_punctuation_speaker_change_and_large_gap() -> None:
    a, b = uuid4(), uuid4()
    rows = [
        segment(0.0, 0.5, "你好。", a),
        segment(0.55, 1.0, "你是谁", a),
        segment(1.05, 1.5, "未婚妻", b),
        segment(3.0, 3.4, "太医", b),
    ]
    assert [unit.text for unit in build_semantic_units(rows)] == [
        "你好。",
        "你是谁",
        "未婚妻",
        "太医",
    ]
    assert semantic_context_by_segment(rows) == {}


def test_long_complete_subtitles_are_not_merged_just_because_they_are_adjacent() -> (
    None
):
    speaker = uuid4()
    rows = [
        segment(0.0, 2.0, "传说中长着翅膀的山海异兽", speaker),
        segment(2.05, 4.0, "你们说的其实都不完全正确", speaker),
    ]
    assert len(build_semantic_units(rows)) == 2


def test_service_attaches_reconstruction_to_original_segment_only_as_context(
    tmp_path,
) -> None:
    projects = __import__(
        "catty_engine.project", fromlist=["ProjectService"]
    ).ProjectService()
    project = projects.create_project(tmp_path, "Reconstruction")
    episode = project.add_episode("episode.mp4")
    episode.dialogue_segments = [
        segment(0.0, 0.5, "裴国"),
        segment(0.55, 1.0, "公的未婚"),
        segment(1.05, 1.8, "妻哦未婚妻哪来？"),
    ]
    settings = AppSettings()
    request = TranslationService(projects)._build_request(
        project, episode.id, [episode.dialogue_segments[1]], settings
    )
    item = request.segments[0]
    assert item.text == "公的未婚"
    assert item.semantic_context == "裴国公的未婚妻哦未婚妻哪来？"


def test_local_prompt_marks_reconstructed_utterance_as_read_only_context() -> None:
    from catty_engine.translation.models import (
        TranslationBatchRequest,
        TranslationInput,
    )

    item = TranslationInput(
        id="middle", text="公的未婚", semantic_context="裴国公的未婚妻哦未婚妻哪来？"
    )
    request = TranslationBatchRequest(segments=[item])
    prompt = _hy_mt2_prompt(item, request)
    assert "Reconstructed utterance: 裴国公的未婚妻哦未婚妻哪来？" in prompt
    assert "translate ONLY Current" in prompt
    assert "Current: 公的未婚" in prompt


def test_sentence_end_inside_closing_quote_is_a_boundary() -> None:
    speaker = uuid4()
    rows = [
        segment(0.0, 0.6, "“你好。”", speaker),
        segment(0.65, 1.2, "我们走吧", speaker),
    ]
    assert len(build_semantic_units(rows)) == 2
    assert semantic_context_by_segment(rows) == {}
