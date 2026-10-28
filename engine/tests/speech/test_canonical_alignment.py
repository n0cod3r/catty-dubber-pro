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
                {"start": 88000, "end": 90000, "text": "是裴国公的未婚妻哦。", "spk": 0},
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
