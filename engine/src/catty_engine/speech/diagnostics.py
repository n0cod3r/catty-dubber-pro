"""Observational Smart Transcribe traces. Never changes model inputs or results."""

from __future__ import annotations

import contextvars
import functools
import importlib.metadata
import json
import logging
import math
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from catty_engine.progress import report_transcription_phase, transcription_progress

logger = logging.getLogger(__name__)
_CURRENT: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "transcription_trace", default=None
)
_FIELDS = {
    "key",
    "text",
    "sentence",
    "value",
    "timestamp",
    "timestamps",
    "words",
    "punc_array",
    "sentence_info",
    "raw_text",
    "start",
    "end",
    "start_time",
    "end_time",
    "spk",
}


def snapshot(value):
    """Copy stage text/timing only, before FunASR mutates timestamps in place."""
    if isinstance(value, dict):
        return {str(k): snapshot(v) for k, v in value.items() if k in _FIELDS}
    if isinstance(value, (list, tuple)):
        return [snapshot(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if hasattr(value, "tolist"):
        return snapshot(value.tolist())
    return str(value)


def current_trace():
    return _CURRENT.get()


def overlap(interval, regions):
    a, b = interval
    pieces = sorted(
        (max(a, x[0]), min(b, x[1])) for x in regions if min(b, x[1]) > max(a, x[0])
    )
    end, total = a, 0.0
    for left, right in pieces:
        total += max(0.0, right - max(left, end))
        end = max(end, right)
    return round(total, 6)


def suspicious_gaps(final, vad, raw_asr, parsed, start, end):
    """A gap is a review candidate, not proof of missing audible speech."""
    intervals = sorted(
        (max(start, s["start"]), min(end, s["end"]))
        for s in final
        if s["end"] > start and s["start"] < end
    )
    gaps, cursor = [], start
    for left, right in [*intervals, (end, end)]:
        if left - cursor >= 0.5:
            interval = (cursor, left)
            vad_seconds = overlap(interval, [(s["start"], s["end"]) for s in vad])
            words = [
                t for row in raw_asr for t in row.get("absolute_word_timestamps", [])
            ]
            raw_seconds = overlap(interval, words)
            parsed_seconds = overlap(interval, [(s["start"], s["end"]) for s in parsed])
            hint = "no_vad_support_silence_or_vad_miss"
            if vad_seconds >= 0.25:
                hint = "vad_supported_gap_inspect_raw_asr_and_alignment"
                if raw_seconds > 0:
                    hint = "asr_timestamps_present_inspect_punctuation_and_sentence_parsing"
                if parsed_seconds > 0:
                    hint = "parsed_dialogue_present_inspect_semantic_split"
            gaps.append(
                {
                    "start": round(cursor, 6),
                    "end": round(left, 6),
                    "duration": round(left - cursor, 6),
                    "vad_overlap_seconds": vad_seconds,
                    "raw_asr_timestamp_overlap_seconds": raw_seconds,
                    "parsed_overlap_seconds": parsed_seconds,
                    "suspicious": vad_seconds >= 0.25,
                    "hint": hint,
                }
            )
        cursor = max(cursor, right)
    return gaps


class TranscriptionTrace:
    def __init__(self, project_directory, episode_id, start, duration):
        self.path = (
            Path(project_directory)
            / "cache"
            / "transcription"
            / str(episode_id)
            / "smart-transcribe-debug.json"
        )
        self.start, self.end = start, start + duration
        try:
            version = importlib.metadata.version("funasr")
        except importlib.metadata.PackageNotFoundError:
            version = "unavailable"
        self.data = {
            "schema_version": 1,
            "run_id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "episode_id": str(episode_id),
            "funasr_version": version,
            "status": "running",
            "source_start": start,
            "duration": duration,
            "timestamp_unit": "seconds_absolute_source_except_native_fields_ms",
            "attempts": [],
            "vad_regions": [],
            "raw_asr": [],
            "punctuated": [],
            "parsed_segments": [],
            "final_segments": [],
            "dropped_regions": [],
            "gaps": [],
            "notes": [
                "Observations from the original inference, no additional VAD/ASR runs.",
                "Raw ASR native timestamps are milliseconds relative to their VAD chunk; absolute_word_timestamps are converted copies.",
                "Punctuation text is merged-range text, not an independently timed segment.",
                "No VAD support cannot distinguish silence from a VAD miss without listening to audio.",
                "Gap review thresholds (0.5s gap, 0.25s VAD overlap) affect diagnostics only.",
            ],
        }
        self.attempt = None
        self.queue = []
        self.cursor = 0

    def observe(self, stage, value, input_count=None):
        if self.attempt is None:
            return
        self.attempt.setdefault("observed_stages", []).append(stage)
        rows = snapshot(value)
        if stage == "vad":
            for row in rows:
                for left, right in row.get("value", []):
                    self.attempt["vad_regions"].append(
                        {
                            "start": self.start + left / 1000,
                            "end": self.start + right / 1000,
                            "native_start_ms": left,
                            "native_end_ms": right,
                        }
                    )
            self.queue = sorted(
                self.attempt["vad_regions"],
                key=lambda region: region["native_end_ms"] - region["native_start_ms"],
            )
            self.cursor = 0
            for region in self.attempt["vad_regions"]:
                logger.info(
                    "[TRANSCRIBE DEBUG] VAD %.3f → %.3f speech",
                    region["start"],
                    region["end"],
                )
        elif stage == "asr":
            # FunASR sorts VAD chunks by duration before batching. Do not pretend
            # one-to-one alignment when a batch returns fewer/more results.
            known = input_count == len(rows) and self.cursor + input_count <= len(
                self.queue
            )
            for index, row in enumerate(rows):
                region = self.queue[self.cursor + index] if known else None
                absolute = []
                if region:
                    for pair in row.get("timestamp", []):
                        if isinstance(pair, list) and len(pair) >= 2:
                            absolute.append(
                                [
                                    region["start"] + pair[0] / 1000,
                                    region["start"] + pair[1] / 1000,
                                ]
                            )
                    for pair in row.get("timestamps", []):
                        if (
                            isinstance(pair, dict)
                            and "start_time" in pair
                            and "end_time" in pair
                        ):
                            absolute.append(
                                [
                                    region["start"] + pair["start_time"],
                                    region["start"] + pair["end_time"],
                                ]
                            )
                self.attempt["raw_asr"].append(
                    {
                        "vad_region": region,
                        "mapping": "duration_sorted_vad_order"
                        if known
                        else "unavailable_result_count_mismatch",
                        "native": row,
                        "absolute_word_timestamps": absolute,
                    }
                )
                logger.info(
                    "[TRANSCRIBE DEBUG] ASR chunk=%s; word_times=%s; text=%r",
                    region,
                    absolute,
                    str(row.get("text", ""))[:200],
                )
                if region and not str(row.get("text", "")).strip():
                    self.attempt["dropped_regions"].append(
                        {"stage": "asr", "reason": "empty_asr_text", **region}
                    )
            if not known:
                self.attempt["capture_warnings"].append(
                    f"ASR input/result count mismatch: {input_count}/{len(rows)}; chunk mapping is unavailable"
                )
            self.cursor += input_count or 0
        elif stage == "punctuation":
            self.attempt["punctuated"].extend(rows)
            for row in rows:
                logger.info(
                    "[TRANSCRIBE DEBUG] CT-PUNC %r", str(row.get("text", ""))[:200]
                )

    def safe(self, callback, *args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except Exception:
            logger.warning(
                "[TRANSCRIBE DEBUG] Capture failed; inference unchanged", exc_info=True
            )
            self.data.setdefault("capture_errors", []).append(
                "Stage capture failed; see logs"
            )

    def finish(self, segments=None, error=None):
        if self.attempt:
            for field in ("vad_regions", "raw_asr", "punctuated", "dropped_regions"):
                self.data[field] = self.attempt[field]
        observed = self.attempt.get("observed_stages", []) if self.attempt else []
        self.data["stage_observed"] = {
            stage: stage in observed for stage in ("vad", "asr", "punctuation")
        }
        if segments is not None:
            self.data["final_segments"] = [s.model_dump(mode="json") for s in segments]
        self.data["status"] = "failed" if error else "completed"
        if error:
            self.data["error"] = type(error).__name__ + ": " + str(error)
        self.data["gaps"] = suspicious_gaps(
            self.data["final_segments"],
            self.data["vad_regions"],
            self.data["raw_asr"],
            self.data["parsed_segments"],
            self.start,
            self.end,
        )
        for gap in self.data["gaps"]:
            if not self.data["stage_observed"]["vad"]:
                gap["hint"] = "vad_stage_not_observed_cannot_classify"
                gap["suspicious"] = None
            if gap["suspicious"]:
                self.data["dropped_regions"].append({"stage": "coverage_review", **gap})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
        logger.info(
            "[TRANSCRIBE DEBUG] %s: VAD=%d raw-ASR=%d punctuated=%d final=%d; artifact=%s",
            self.data["status"],
            len(self.data["vad_regions"]),
            len(self.data["raw_asr"]),
            len(self.data["punctuated"]),
            len(self.data["final_segments"]),
            self.path,
        )
        for segment in self.data["final_segments"]:
            logger.info(
                "[TRANSCRIBE DEBUG] FINAL %.3f → %.3f %r",
                segment["start"],
                segment["end"],
                segment["text"][:200],
            )
        for gap in self.data["gaps"]:
            logger.info(
                "[TRANSCRIBE DEBUG] GAP %.3f → %.3f; VAD overlap %.3fs; %s",
                gap["start"],
                gap["end"],
                gap["vad_overlap_seconds"],
                gap["hint"],
            )


def trace_transcription(function):
    @functools.wraps(function)
    def run(self, **kwargs):
        if kwargs.get("backend_id") != "paraformer":
            return function(self, **kwargs)
        try:
            trace = TranscriptionTrace(
                kwargs["project_directory"],
                kwargs["episode_id"],
                kwargs["source_start"],
                kwargs["duration"],
            )
        except Exception:
            logger.warning(
                "[TRANSCRIBE DEBUG] Could not initialize capture; inference unchanged",
                exc_info=True,
            )
            return function(self, **kwargs)
        self._diagnostic_run_id = trace.data["run_id"]
        token = _CURRENT.set(trace)
        try:
            result = function(self, **kwargs)
        except BaseException as error:
            trace.safe(trace.finish, error=error)
            raise
        else:
            trace.safe(trace.finish, result.segments)
            return result
        finally:
            _CURRENT.reset(token)

    return run


@contextmanager
def capture_pipeline(pipeline, *, return_spk_res):
    trace = current_trace()
    if trace is None:
        yield
        return
    attempt = {
        "return_spk_res": return_spk_res,
        "vad_regions": [],
        "raw_asr": [],
        "punctuated": [],
        "dropped_regions": [],
        "capture_warnings": [],
    }
    trace.data["attempts"].append(attempt)
    trace.attempt, trace.queue, trace.cursor = attempt, [], 0
    original = getattr(pipeline, "inference", None)
    if original is None:
        attempt["capture_warnings"].append(
            "Pipeline exposes no inference hook; internal stages unavailable"
        )
        yield
        return
    own = "inference" in getattr(pipeline, "__dict__", {})

    def observed(*args, **kwargs):
        model = kwargs.get(
            "model", args[2] if len(args) > 2 else getattr(pipeline, "model", None)
        )
        stage = next(
            (
                name
                for name, attribute in [
                    ("vad", "vad_model"),
                    ("punctuation", "punc_model"),
                    ("asr", "model"),
                ]
                if model is not None and model is getattr(pipeline, attribute, None)
            ),
            None,
        )
        if stage == "vad":
            report_transcription_phase("vad")
        elif stage == "punctuation":
            report_transcription_phase("punctuation")
        output = original(*args, **kwargs)
        if stage:
            input_data = kwargs.get("input", args[0] if args else None)
            count = (
                len(input_data)
                if stage == "asr" and isinstance(input_data, (list, tuple))
                else None
            )
            trace.safe(trace.observe, stage, output, count)
            reporter = transcription_progress()
            if reporter is not None:
                trace.safe(reporter.observe, stage, attempt)
            if stage == "punctuation" and isinstance(input_data, str):
                attempt["punctuation_input_text"] = input_data
        return output

    try:
        pipeline.inference = observed
    except Exception:
        attempt["capture_warnings"].append(
            "Could not install inference observation hook"
        )
        yield
        return
    try:
        yield
    finally:
        try:
            if own:
                pipeline.inference = original
            else:
                del pipeline.inference
        except Exception:
            logger.warning(
                "[TRANSCRIBE DEBUG] Could not restore inference observation hook",
                exc_info=True,
            )


def record_persisted_dialogue(project_directory, episode, run_id):
    """Confirm the final persistent boundary, without touching project.json."""
    if run_id is None:
        return
    path = (
        Path(project_directory)
        / "cache"
        / "transcription"
        / str(episode.id)
        / "smart-transcribe-debug.json"
    )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("run_id") != run_id or data.get("status") != "completed":
            return
        data["persisted_segments"] = [
            s.model_dump(mode="json") for s in episode.dialogue_segments
        ]
        expected = [
            {"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in data["final_segments"]
        ]
        actual = [
            {"start": s.start, "end": s.end, "text": s.source_text}
            for s in episode.dialogue_segments
        ]
        data["persistence_matches_final"] = expected == actual
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
        logger.info(
            "[TRANSCRIBE DEBUG] project.json saved: %d segments; matches final=%s",
            len(actual),
            expected == actual,
        )
    except Exception:
        logger.warning(
            "[TRANSCRIBE DEBUG] Could not annotate persistence; project save unchanged",
            exc_info=True,
        )
