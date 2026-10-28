import assert from "node:assert/strict";
import test from "node:test";

import {
  isCurrentTtsProgress,
  ttsTargetIds,
} from "../apps/desktop/src/features/editor/utils/tts-progress.ts";
import {
  dubbingTimelineClips,
  scopedProgress,
  translationTimelineClips,
} from "../apps/desktop/src/features/timeline/utils/pipeline-clips.ts";

const rows = [
  {
    id: "a",
    start: 2,
    end: 4,
    translation: { text: "ខ្មែរ", status: "translated" },
  },
  {
    id: "b",
    start: 6,
    end: 8,
    translation: { text: "ថ្មី", status: "edited" },
  },
  { id: "c", start: 9, end: 10, translation: null },
];
const dub = {
  id: "dub-a",
  dialogue_segment_id: "a",
  status: "ready",
  audio_path: "/audio/a.mp3",
  generated_at: "v1",
  generated_duration: 2.5,
};
const episode = { id: "episode", dialogueSegments: rows, dubSegments: [dub] };
const event = {
  operation_id: "run",
  project_directory: "/project",
  episode_id: "episode",
  phase: "generating",
  completed: 0,
  total: 2,
  segment_id: "a",
  episode: null,
};

test("TTS progress rejects wrong operation, project, episode and embedded episode", () => {
  assert.equal(isCurrentTtsProgress(event, "run", "/project", "episode"), true);
  for (const change of [
    { operation_id: "old" },
    { project_directory: "/other" },
    { episode_id: "other" },
    { episode: { id: "other" } },
  ]) {
    assert.equal(
      isCurrentTtsProgress(
        { ...event, ...change },
        "run",
        "/project",
        "episode",
      ),
      false,
    );
    if (!change.operation_id)
      assert.equal(
        scopedProgress({ ...event, ...change }, "/project", "episode"),
        null,
      );
  }
});

test("generation targets match engine missing/all/selected rules", () => {
  assert.deepEqual(ttsTargetIds(episode, "missing", []), ["b"]);
  assert.deepEqual(ttsTargetIds(episode, "all", []), ["a", "b"]);
  assert.deepEqual(ttsTargetIds(episode, "selected", ["a", "c"]), ["a"]);
  assert.deepEqual(ttsTargetIds(episode, "selected", []), []);
});

test("translation clips keep stable identities while active batches become saved Khmer", () => {
  const before = structuredClone(episode);
  const active = translationTimelineClips(episode, {
    phase: "translating",
    active_segment_ids: ["b"],
  });
  assert.deepEqual(
    active.map((clip) => clip.status),
    ["Ready", "Translating", "Pending"],
  );
  const saved = translationTimelineClips(episode, {
    phase: "saved",
    active_segment_ids: [],
  });
  assert.equal(saved[1].id, active[1].id);
  assert.equal(saved[1].text, "ថ្មី");
  assert.equal(saved[1].status, "Ready");
  assert.deepEqual(episode, before);
});

test("TTS clips change queued → generating → ready without duplicating or changing source timing", () => {
  const pending = dubbingTimelineClips(episode, event, ["a", "b"], null);
  assert.deepEqual(
    pending.map((clip) => clip.status),
    ["Generating", "Queued"],
  );
  assert.equal(pending[0].audioPath, undefined); // Do not use stale audio while regenerating.
  const saved = dubbingTimelineClips(
    episode,
    { ...event, phase: "saved" },
    ["b"],
    null,
  );
  assert.equal(saved[0].id, pending[0].id);
  assert.equal(saved[0].start, 2);
  assert.equal(saved[0].duration, 2.5); // Measured audio, no invented duration fit.
  assert.equal(saved[0].audioPath, "/audio/a.mp3");
  assert.equal(saved[1].status, "Queued");
  const reopened = dubbingTimelineClips(
    structuredClone(episode),
    null,
    [],
    null,
  );
  assert.equal(reopened[0].status, "Ready");
  assert.equal(reopened.length, 2);
});

test("cancelled and failed runs retain successful clips, outdated audio is never shown as ready", () => {
  assert.equal(dubbingTimelineClips(episode, null, [], "b")[0].status, "Ready");
  assert.equal(
    dubbingTimelineClips(episode, null, [], "b")[1].status,
    "Failed",
  );
  const outdated = dubbingTimelineClips(
    { ...episode, dubSegments: [{ ...dub, status: "outdated" }] },
    null,
    [],
    null,
  );
  assert.equal(outdated[0].status, "Outdated");
  assert.equal(outdated[0].audioPath, undefined);
});
