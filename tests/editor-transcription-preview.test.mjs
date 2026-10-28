import assert from "node:assert/strict";
import test from "node:test";

import { createTimelineStore } from "../apps/desktop/src/features/timeline/stores/timeline-store.ts";
import {
  activeTranscriptionPreview,
  transcriptionPreviewClips,
} from "../apps/desktop/src/features/timeline/utils/transcription-preview.ts";

const progress = {
  operation_id: "run-1",
  project_directory: "/project",
  episode_id: "episode-1",
  phase: "asr",
  completed: 1,
  total: 3,
  preview_segments: [{ id: "draft-1", start: 2, end: 4, text: "你好" }],
  episode: null,
};

test("live drafts only appear for the active project and episode until completion", () => {
  const select = (
    value,
    active = true,
    project = "/project",
    episode = "episode-1",
  ) => activeTranscriptionPreview(value, active, project, episode);
  assert.equal(select(progress), progress);
  assert.equal(select(progress, false), null);
  assert.equal(select(progress, true, "/other"), null);
  assert.equal(select(progress, true, "/project", "episode-2"), null);
  assert.equal(select(null), null);
  for (const phase of ["completed", "failed"]) {
    assert.equal(select({ ...progress, phase }), null);
  }
  assert.equal(select({ ...progress, phase: "saving" }).phase, "saving");
});

test("out-of-order chunk snapshots produce sorted, bounded, unique draft clips", () => {
  const clips = transcriptionPreviewClips(
    {
      ...progress,
      preview_segments: [
        { id: "later", start: 8, end: 15, text: "Later" },
        ...progress.preview_segments,
        { id: "draft-1", start: 2, end: 4, text: "Updated" },
        { id: "early", start: -1, end: 1, text: "Early" },
        { id: "bad", start: NaN, end: 4, text: "Invalid" },
        { id: "zero", start: 4, end: 4, text: "Empty" },
        { id: "outside", start: 11, end: 12, text: "Outside" },
      ],
    },
    10,
  );
  assert.deepEqual(
    clips.map(({ start, duration, text }) => [start, duration, text]),
    [
      [0, 1, "Early"],
      [2, 2, "Updated"],
      [8, 2, "Later"],
    ],
  );
  assert.equal(clips[1].id, transcriptionPreviewClips(progress, 10)[0].id);
  assert.notEqual(
    clips[1].id,
    transcriptionPreviewClips({ ...progress, operation_id: "retry" }, 10)[0].id,
  );
});

test("draft updates never change saved dialogue, media, or undo/redo history", () => {
  const store = createTimelineStore();
  store
    .getState()
    .initialize({ sourceId: "episode-1", name: "Episode", duration: 10 });
  store.getState().syncDialogue({
    sourceId: "episode-1",
    segments: [{ id: "saved", start: 1, end: 3, text: "Saved dialogue" }],
  });
  store.getState().split({ time: 5, selectedId: null });
  store.getState().undo();
  const history = store.getState().history;
  const before = structuredClone(history);
  transcriptionPreviewClips(progress, 10);
  transcriptionPreviewClips(
    { ...progress, phase: "alignment", preview_segments: [] },
    10,
  );
  activeTranscriptionPreview(
    { ...progress, phase: "failed" },
    true,
    "/project",
    "episode-1",
  );
  assert.equal(store.getState().history, history);
  assert.deepEqual(history, before);
  store.getState().redo();
  assert.equal(store.getState().history.future.length, 0);
});
