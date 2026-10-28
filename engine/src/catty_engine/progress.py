"""Out-of-band UI progress on stderr; stdout remains the RPC response channel."""

from __future__ import annotations

import contextvars
import json
import re
import sys
from contextlib import contextmanager
from typing import Any


def emit_translation_progress(payload: dict[str, Any]) -> None:
    sys.stderr.write(
        json.dumps(
            {"catty_progress": "translation", "payload": payload}, ensure_ascii=False
        )
        + "\n"
    )
    sys.stderr.flush()


# Transcription previews are ephemeral. Only the completed event carries a saved
# episode; publishing draft ASR must never replace the persistent transcript.
_TRANSCRIPTION: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "transcription_progress", default=None
)


class TranscriptionProgressReporter:
    def __init__(self, operation_id, project_directory, episode_id):
        self.operation_id = operation_id
        self.project_directory = str(project_directory)
        self.episode_id = str(episode_id)
        self.total = 0
        self.completed = 0
        self.preview = []

    def publish(self, phase, episode=None):
        payload = {
            "operation_id": self.operation_id,
            "project_directory": self.project_directory,
            "episode_id": self.episode_id,
            "phase": phase,
            "completed": self.completed,
            "total": self.total,
            "preview_segments": self.preview,
            "episode": episode,
        }
        sys.stderr.write(
            json.dumps(
                {"catty_progress": "transcription", "payload": payload},
                ensure_ascii=False,
            )
            + "\n"
        )
        sys.stderr.flush()

    def observe(self, stage, attempt):
        if stage == "vad":
            self.total = len(attempt["vad_regions"])
            self.completed = 0
            self.preview = []
            self.publish("asr")
        elif stage == "asr":
            self.completed = min(self.total, len(attempt["raw_asr"]))
            preview = []
            for i, row in enumerate(attempt["raw_asr"]):
                region = row.get("vad_region")
                text = str(row.get("native", {}).get("text", "")).strip()
                times = row.get("absolute_word_timestamps") or []
                if not region or not text:
                    continue
                preview.append(
                    {
                        "id": f"draft-{region['start']}-{i}",
                        "start": times[0][0] if times else region["start"],
                        "end": times[-1][1] if times else region["end"],
                        "text": re.sub(
                            r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text
                        ),
                        "confidence": None,
                    }
                )
            self.preview = sorted(
                preview, key=lambda item: (item["start"], item["end"])
            )
            self.publish("asr")
        elif stage == "punctuation":
            self.publish("punctuation")

    def aligned(self, segments):
        self.preview = [
            {
                "id": f"aligned-{i}",
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "confidence": s.confidence,
            }
            for i, s in enumerate(segments)
        ]
        self.publish("alignment")


def transcription_progress():
    return _TRANSCRIPTION.get()


def report_transcription_phase(phase):
    reporter = transcription_progress()
    if reporter is not None:
        reporter.publish(phase)


@contextmanager
def transcription_progress_scope(operation_id, project_directory, episode_id):
    if operation_id is None:
        yield None
        return
    reporter = TranscriptionProgressReporter(
        operation_id, project_directory, episode_id
    )
    token = _TRANSCRIPTION.set(reporter)
    try:
        reporter.publish("preparing")
        yield reporter
    except BaseException:
        reporter.publish("failed")
        raise
    finally:
        _TRANSCRIPTION.reset(token)
