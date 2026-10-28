import copy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from catty_engine.speakers.funasr import _run_generate, parse_sentences
from catty_engine.speech.diagnostics import (
    TranscriptionTrace,
    _CURRENT,
    record_persisted_dialogue,
    suspicious_gaps,
    trace_transcription,
)
from catty_engine.project import DialogueSegment, ProjectService


class Pipeline:
    def __init__(self):
        self.model, self.vad_model, self.punc_model = object(), object(), object()
        self.generations = 0

    def inference(self, input, **kwargs):
        if kwargs["model"] is self.vad_model:
            return [{"value": [[1000, 4000], [5000, 6000]]}]
        if kwargs["model"] is self.punc_model:
            return [{"text": "你好。世界！", "punc_array": [1, 2]}]
        return [
            {
                "text": "你好",
                "timestamp": [[0, 500]],
                "spk_embedding": "must not be captured",
            }
            for _ in input
        ]

    def generate(self, **kwargs):
        self.generations += 1
        assert kwargs == {
            "input": "samples",
            "fs": 16000,
            "batch_size_s": 30,
            "disable_pbar": True,
            "sentence_timestamp": True,
            "return_spk_res": True,
        }
        self.inference("audio", model=self.vad_model)
        raw = self.inference(["short", "long"], model=self.model)
        raw[0]["timestamp"][0][0] = 5000
        self.inference("你好世界", model=self.punc_model)
        return [
            {
                "text": "你好。世界！",
                "sentence_info": [
                    {"start": 1000, "end": 1500, "text": "你好。"},
                    {"start": 5000, "end": 5500, "text": "世界！"},
                ],
            }
        ]


def test_stage_capture_preserves_output_generate_arguments_and_internal_state(tmp_path):
    pipeline = Pipeline()
    original, _ = _run_generate(
        pipeline,
        "samples",
        16000,
        source_start=0,
        return_spk_res=True,
    )
    original = copy.deepcopy(original)
    trace = TranscriptionTrace(tmp_path, uuid4(), 12, 10)
    token = _CURRENT.set(trace)
    try:
        observed, raw_asr = _run_generate(
            pipeline,
            "samples",
            16000,
            source_start=12,
            return_spk_res=True,
        )
        segments = parse_sentences(observed, start=12, duration=10)
        trace.data["parsed_segments"] = [s.model_dump(mode="json") for s in segments]
        trace.finish(segments)
    finally:
        _CURRENT.reset(token)
    assert observed == original and pipeline.generations == 2
    assert "inference" not in vars(pipeline)
    assert raw_asr[0]["vad_region"]["start"] == 17
    assert raw_asr[1]["vad_region"]["start"] == 13
    data = json.loads(trace.path.read_text())
    assert data["raw_asr"][0]["vad_region"]["start"] == 17
    assert data["raw_asr"][1]["vad_region"]["start"] == 13
    assert data["raw_asr"][0]["native"]["timestamp"] == [[0, 500]]
    assert data["raw_asr"][0]["absolute_word_timestamps"] == [[17, 17.5]]
    assert "spk_embedding" not in data["raw_asr"][0]["native"]
    assert data["attempts"][0]["punctuation_input_text"] == "你好世界"
    assert data["punctuated"][0]["text"] == "你好。世界！"
    assert len(data["final_segments"]) == 2


def test_gap_analysis_distinguishes_vad_support_and_does_not_claim_silence_is_a_bug():
    final = [
        {"start": 0, "end": 35.79},
        {"start": 39.22, "end": 97.27},
        {"start": 106.11, "end": 110},
    ]
    vad = [{"start": 97.5, "end": 105.8}]
    gaps = suspicious_gaps(final, vad, [], [], 0, 110)
    assert gaps[0]["duration"] == 3.43 and gaps[0]["suspicious"] is False
    assert gaps[1]["duration"] == 8.84 and gaps[1]["suspicious"] is True
    assert gaps[1]["vad_overlap_seconds"] == 8.3
    raw = [{"absolute_word_timestamps": [[98, 100]]}]
    gaps = suspicious_gaps(final, vad, raw, [], [], 0, 110)
    assert "punctuation" in gaps[1]["hint"]
    gaps = suspicious_gaps(final, vad, raw, [{"start": 98, "end": 100}], 0, 110)
    assert "semantic_split" in gaps[1]["hint"]


def test_parser_drops_are_explained_without_changing_segments(tmp_path):
    trace = TranscriptionTrace(tmp_path, uuid4(), 0, 2)
    token = _CURRENT.set(trace)
    try:
        trace.attempt = {"dropped_regions": []}
        result = parse_sentences(
            [
                {
                    "sentence_info": [
                        {"start": 0, "end": 100, "text": "，"},
                        {"start": 100, "end": 500, "text": "你好"},
                        {"start": 900, "end": 800, "text": "世界"},
                    ]
                }
            ],
            start=0,
            duration=2,
        )
        assert [s.text for s in result] == ["你好"]
        assert [s["reason"] for s in trace.attempt["dropped_regions"]] == [
            "punctuation_only",
            "invalid_or_clipped_timing",
        ]
    finally:
        _CURRENT.reset(token)


def test_artifact_write_failure_does_not_change_transcription_or_exceptions(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        TranscriptionTrace,
        "finish",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("read only")),
    )

    @trace_transcription
    def transcribe(self, **kwargs):
        return SimpleNamespace(segments=[])

    args = dict(
        backend_id="paraformer",
        project_directory=tmp_path,
        episode_id=uuid4(),
        source_start=0,
        duration=1,
    )
    assert transcribe(SimpleNamespace(), **args).segments == []

    @trace_transcription
    def fail(self, **kwargs):
        raise ValueError("original error")

    with pytest.raises(ValueError, match="original error"):
        fail(SimpleNamespace(), **args)


def test_persistence_annotation_is_debug_only_and_ignores_stale_runs(tmp_path):
    projects = ProjectService()
    project = projects.create_project(tmp_path, "Trace")
    episode = project.add_episode("video.mp4")
    episode.dialogue_segments = [
        DialogueSegment(start=0, end=1, source_text="你好", source_language="zh")
    ]
    projects.save_project(tmp_path, project)
    original = (tmp_path / "project.json").read_bytes()
    trace = TranscriptionTrace(tmp_path, episode.id, 0, 1)
    trace.data["final_segments"] = [{"start": 0, "end": 1, "text": "你好"}]
    trace.finish()
    record_persisted_dialogue(tmp_path, episode, "stale")
    assert "persisted_segments" not in json.loads(trace.path.read_text())
    record_persisted_dialogue(tmp_path, episode, trace.data["run_id"])
    data = json.loads(trace.path.read_text())
    assert data["persistence_matches_final"] is True
    assert data["persisted_segments"][0]["id"] == str(episode.dialogue_segments[0].id)
    assert (tmp_path / "project.json").read_bytes() == original


def test_inference_hook_is_restored_when_generation_raises(tmp_path):
    class Broken(Pipeline):
        def generate(self, **kwargs):
            self.generations += 1
            self.inference("audio", model=self.vad_model)
            raise RuntimeError("ASR failure")

    pipeline = Broken()
    trace = TranscriptionTrace(tmp_path, uuid4(), 0, 10)
    token = _CURRENT.set(trace)
    try:
        with pytest.raises(RuntimeError, match="ASR failure"):
            _run_generate(
                pipeline,
                "samples",
                16000,
                source_start=0,
                return_spk_res=True,
            )
    finally:
        _CURRENT.reset(token)
    assert "inference" not in vars(pipeline)
    assert pipeline.generations == 1
    assert len(trace.attempt["vad_regions"]) == 2
