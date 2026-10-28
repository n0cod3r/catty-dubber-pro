from catty_engine.speakers.funasr import _ProductionCapture
from catty_engine.speech.canonical_alignment import align_observed_paraformer


def _raw(start: float, text: str, times: list[list[float]]):
    return {
        "vad_region": {"start": start, "end": times[-1][1]},
        "native": {"text": " ".join(text)},
        "absolute_word_timestamps": times,
    }


def test_alignment_preserves_real_vad_gaps_instead_of_compressing_time():
    result = [
        {
            "text": "是裴国公的未婚妻哦。未婚妻哪来的？",
            # Reproduces the failure mode: sentence_info has compressed/wrong
            # timing after FunASR merges separated VAD chunks.
            "sentence_info": [
                {
                    "start": 88000,
                    "end": 90000,
                    "text": "是裴国公的未婚妻哦。",
                    "spk": 0,
                },
                {"start": 93000, "end": 97000, "text": "未婚妻哪来的？", "spk": 1},
            ],
        }
    ]
    raw = [
        _raw(
            107.53,
            "是裴国公的未婚妻哦",
            [
                [107.44, 107.86],
                [107.86, 108.10],
                [108.10, 108.16],
                [108.16, 108.40],
                [108.40, 108.58],
                [108.58, 109.24],
                [109.24, 109.30],
                [109.30, 109.60],
                [109.60, 110.19],
            ],
        ),
        _raw(
            113.83,
            "未婚妻哪来的",
            [
                [114.04, 114.10],
                [114.10, 114.16],
                [114.16, 114.28],
                [114.28, 114.34],
                [114.34, 115.06],
                [115.24, 115.36],
            ],
        ),
    ]

    segments = align_observed_paraformer(result, raw, start=0.0, duration=123.53)

    assert segments is not None
    assert [segment.text for segment in segments] == [
        "是裴国公的未婚妻哦。",
        "未婚妻哪来的？",
    ]
    assert (segments[0].start, segments[0].end) == (107.44, 110.19)
    assert (segments[1].start, segments[1].end) == (114.04, 115.36)
    assert [segment.speaker for segment in segments] == ["S1", "S2"]


def test_alignment_refuses_to_invent_timing_when_character_counts_do_not_match():
    result = [{"text": "你好。", "sentence_info": []}]
    raw = [
        {
            "vad_region": {"start": 1.0, "end": 2.0},
            "native": {"text": "你好"},
            "absolute_word_timestamps": [[1.0, 1.5]],
        }
    ]

    assert align_observed_paraformer(result, raw, start=0.0, duration=3.0) is None


def test_alignment_recovers_text_when_fun_asr_sentence_info_is_punctuation_only():
    # Actual failure shape: raw ASR and punctuated text retain dialogue, but
    # sentence_info relocates the last text and leaves punctuation-only tails.
    result = [
        {
            "text": "我叫宋之，是裴国公的未婚妻哦，",
            "sentence_info": [
                {"start": 106110, "end": 107175, "text": "未婚妻啊啊，", "spk": 1},
                {"start": 107440, "end": 110185, "text": "，", "spk": 1},
            ],
        }
    ]
    raw = [
        _raw(
            106.2,
            "我叫宋之",
            [[106.11, 106.41], [106.41, 106.47], [106.47, 106.77], [106.77, 107.175]],
        ),
        _raw(
            107.53,
            "是裴国公的未婚妻哦",
            [
                [107.44, 107.859],
                [107.859, 108.1],
                [108.1, 108.16],
                [108.16, 108.4],
                [108.4, 108.58],
                [108.58, 109.24],
                [109.24, 109.3],
                [109.3, 109.6],
                [109.6, 110.185],
            ],
        ),
    ]
    aligned = align_observed_paraformer(result, raw, start=0, duration=123.53)
    assert aligned is not None
    assert [s.text for s in aligned] == ["我叫宋之，", "是裴国公的未婚妻哦，"]
    assert [(s.start, s.end) for s in aligned] == [(106.11, 107.175), (107.44, 110.185)]


def test_production_capture_restores_duration_sorted_vad_chunks_to_source_time():
    capture = _ProductionCapture(source_start=10.0, return_spk_res=True)
    capture.observe(
        "vad",
        [{"value": [[0, 1000], [2000, 5000]]}],
        None,
    )

    # FunASR sorts VAD chunks by duration before ASR inference: 1s then 3s.
    capture.observe(
        "asr",
        [
            {"text": "你", "timestamp": [[100, 500]]},
            {"text": "好", "timestamp": [[200, 900]]},
        ],
        2,
    )

    assert [row["native"]["text"] for row in capture.raw_asr] == ["你", "好"]
    assert capture.raw_asr[0]["absolute_word_timestamps"] == [[10.1, 10.5]]
    assert capture.raw_asr[1]["absolute_word_timestamps"] == [[12.2, 12.9]]
    assert all(row["mapping"] == "duration_sorted_vad_order" for row in capture.raw_asr)


def test_production_capture_recovers_absolute_timing_from_final_result():
    capture = _ProductionCapture(source_start=10.0, return_spk_res=True)
    capture.capture_result(
        [{"text": "你好。", "timestamp": [[100, 500], [500, 900]]}]
    )

    assert capture.raw_asr[0]["mapping"] == "funasr_result_word_timestamps"
    assert capture.raw_asr[0]["absolute_word_timestamps"] == [[10.1, 10.5], [10.5, 10.9]]
    assert capture.raw_asr[0]["vad_region"] is None
