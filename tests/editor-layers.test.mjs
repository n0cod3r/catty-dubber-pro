import assert from "node:assert/strict";
import test from "node:test";

import { accumulatePeaks } from "../apps/desktop/src/features/timeline/services/peaks.ts";
import {
  createTimeline,
  splitCandidates,
} from "../apps/desktop/src/features/timeline/stores/timeline-edits.ts";
import { createTimelineStore } from "../apps/desktop/src/features/timeline/stores/timeline-store.ts";
import {
  clipRenderWindow,
  thumbnailTiles,
} from "../apps/desktop/src/features/timeline/utils/render-window.ts";

const initialize = {
  type: "initialize",
  sourceId: "episode",
  name: "episode.webm",
  duration: 100,
};
const layer = {
  id: "caption-2",
  kind: "subtitle",
  name: "Caption 2",
  hidden: false,
  locked: false,
  muted: false,
};
function edit(history, action) {
  const store = createTimelineStore(history);
  action(store.getState());
  return store.getState().history;
}

const initialized = () =>
  edit(createTimeline(), (actions) => actions.initialize(initialize));

test("layers are independent, reorderable, and undoable without losing source clips", () => {
  let state = edit(initialized(), (actions) => actions.addLayer({ layer }));
  assert.equal(state.present.layers[0].id, layer.id);
  state = edit(state, (actions) =>
    actions.moveLayer({ id: layer.id, direction: 1 }),
  );
  assert.equal(state.present.layers[1].id, layer.id);
  state = edit(state, (actions) => actions.undo());
  assert.equal(state.present.layers[0].id, layer.id);
  state = edit(state, (actions) => actions.removeLayer({ id: layer.id }));
  assert.equal(
    state.present.layers.some((item) => item.id === layer.id),
    false,
  );
  assert.equal(state.present.clips.length, 2);
});

test("splitting linked source clips preserves exact source offsets for thumbnails and waves", () => {
  let state = edit(initialized(), (actions) =>
    actions.split({ time: 30, selectedId: "video:source" }),
  );
  assert.equal(state.present.clips.length, 4);
  for (const kind of ["video", "audio"]) {
    const clips = state.present.clips.filter((clip) => clip.kind === kind);
    assert.deepEqual(
      clips.map((clip) => [clip.start, clip.duration, clip.sourceStart]),
      [
        [0, 30, 0],
        [30, 70, 30],
      ],
    );
  }
  state = edit(state, (actions) =>
    actions.split({ time: 50, selectedId: "video:source" }),
  );
  assert.equal(state.present.clips.length, 6);
  assert.equal(
    state.present.clips.find(
      (clip) => clip.kind === "audio" && clip.start === 50,
    ).sourceStart,
    50,
  );
});

test("locks protect a whole linked split and disallow layer changes", () => {
  let state = edit(initialized(), (actions) =>
    actions.toggleLayer({ id: "audio", property: "locked" }),
  );
  assert.deepEqual(splitCandidates(state.present, 30, null), []);
  assert.equal(
    edit(state, (actions) => actions.split({ time: 30, selectedId: null })),
    state,
  );
  assert.equal(
    edit(state, (actions) => actions.moveLayer({ id: "audio", direction: -1 })),
    state,
  );
  assert.equal(
    edit(state, (actions) =>
      actions.toggleLayer({ id: "audio", property: "muted" }),
    ),
    state,
  );
});

test("clip kinds must match their layer; source and populated layers cannot be removed", () => {
  let state = edit(initialized(), (actions) => actions.addLayer({ layer }));
  const clip = {
    id: "caption",
    trackId: layer.id,
    kind: "subtitle",
    sourceStart: 0,
    start: 5,
    duration: 10,
    name: "Caption",
    text: "Hello",
  };
  assert.equal(
    edit(state, (actions) =>
      actions.addClip({ clip: { ...clip, kind: "video" } }),
    ),
    state,
  );
  state = edit(state, (actions) => actions.addClip({ clip }));
  assert.equal(
    edit(state, (actions) => actions.removeLayer({ id: layer.id })),
    state,
  );
  assert.equal(
    edit(state, (actions) => actions.removeLayer({ id: "video" })),
    state,
  );
  state = edit(state, (actions) =>
    actions.updateText({ id: clip.id, text: "សួស្តី" }),
  );
  assert.equal(
    state.present.clips.find((item) => item.id === clip.id).text,
    "សួស្តី",
  );
});

test("metadata initialization rebases edits made before loading and cannot be undone", () => {
  let state = edit(createTimeline(), (actions) => actions.addLayer({ layer }));
  state = edit(state, (actions) => actions.initialize(initialize));
  state = edit(state, (actions) => actions.undo());
  assert.equal(state.present.clips.length, 2);
  assert.equal(state.present.initialized, true);
  assert.equal(
    state.present.layers.some((item) => item.id === layer.id),
    false,
  );
});

test("audio bins use real timestamps, preserve stereo transients, and keep silence silent", () => {
  const min = new Float32Array(6),
    max = new Float32Array(6);
  const peak = accumulatePeaks(
    min,
    max,
    [
      new Float32Array([0.25, -0.5, 0, 0]),
      new Float32Array([-0.75, 0.5, 0, 0]),
    ],
    2,
    2,
    1,
  );
  assert.equal(peak, 0.75);
  assert.deepEqual(Array.from(min), [0, 0, -0.75, 0, 0, 0]);
  assert.deepEqual(Array.from(max), [0, 0, 0.5, 0, 0, 0]);
});

test("canvas allocations and thumbnail requests stay bounded even at extreme zoom", () => {
  const window = clipRenderWindow(0, 7200, 10000, 2_000_000, 1200);
  assert.ok(window.width <= 1200 + 2 * 96 + 2);
  const tiles = thumbnailTiles(30, window.left, window.width, 10000, 7200);
  assert.ok(tiles.length <= 16);
  assert.ok(tiles.every((tile) => tile.time >= 30 && tile.time < 7200));
  const right = clipRenderWindow(50, 10, 20, 0, 600);
  assert.equal(right.width, 0);
});

test("document history is bounded and new edits invalidate redo", () => {
  let state = initialized();
  for (let count = 0; count < 150; count++)
    state = edit(state, (actions) =>
      actions.toggleLayer({ id: "video", property: "hidden" }),
    );
  assert.equal(state.past.length, 100);
  state = edit(state, (actions) => actions.undo());
  assert.equal(state.future.length, 1);
  state = edit(state, (actions) => actions.addLayer({ layer }));
  assert.equal(state.future.length, 0);
});

test("source clips move as a linked pair with preserved source offsets and one undo entry", () => {
  let state = initialized();
  const before = state;
  state = edit(state, (actions) =>
    actions.moveClip({ id: "video:source", start: 5, trackId: "video" }),
  );
  assert.deepEqual(
    state.present.clips.map((clip) => [clip.start, clip.sourceStart]),
    [
      [5, 0],
      [5, 0],
    ],
  );
  assert.equal(state.past.length, 1);
  assert.deepEqual(
    edit(state, (actions) => actions.undo()).present,
    before.present,
  );
  const removed = edit(state, (actions) =>
    actions.removeClip({ id: "video:source" }),
  );
  assert.equal(removed.present.clips.length, 0);
  assert.equal(
    edit(removed, (actions) => actions.initialize(initialize)),
    removed,
    "metadata must not restore deleted source clips",
  );
  assert.deepEqual(
    edit(removed, (actions) => actions.undo()).present,
    state.present,
  );
});

test("editing one split segment affects only its corresponding linked segment", () => {
  let state = edit(initialized(), (actions) =>
    actions.split({ time: 30, selectedId: null }),
  );
  state = edit(state, (actions) =>
    actions.moveClip({ id: "video:source@30", start: 40, trackId: "video" }),
  );
  assert.deepEqual(
    state.present.clips
      .filter((clip) => clip.kind === "audio")
      .map((clip) => [clip.start, clip.sourceStart, clip.duration]),
    [
      [0, 0, 30],
      [40, 30, 70],
    ],
  );
  state = edit(state, (actions) =>
    actions.removeClip({ id: "audio:source@30" }),
  );
  assert.equal(state.present.clips.length, 2);
  assert.ok(
    state.present.clips.every(
      (clip) => clip.start === 0 && clip.duration === 30,
    ),
  );
});

test("clip moves reject collisions, negative/invalid times, wrong types, and locked linked layers", () => {
  const state = edit(initialized(), (actions) =>
    actions.split({ time: 30, selectedId: null }),
  );
  for (const start of [-1, NaN, Infinity, 20]) {
    assert.equal(
      edit(state, (actions) =>
        actions.moveClip({ id: "video:source@30", start, trackId: "video" }),
      ),
      state,
    );
  }
  assert.equal(
    edit(state, (actions) =>
      actions.moveClip({ id: "video:source@30", start: 40, trackId: "audio" }),
    ),
    state,
  );
  const locked = edit(state, (actions) =>
    actions.toggleLayer({ id: "audio", property: "locked" }),
  );
  assert.equal(
    edit(locked, (actions) =>
      actions.moveClip({ id: "video:source@30", start: 40, trackId: "video" }),
    ),
    locked,
  );
  assert.equal(
    edit(locked, (actions) => actions.removeClip({ id: "video:source@30" })),
    locked,
  );
});

test("clips transfer to compatible layers while linked audio retains its own layer", () => {
  let state = edit(initialized(), (actions) =>
    actions.addLayer({ layer: { ...layer, id: "video2", kind: "video" } }),
  );
  state = edit(state, (actions) =>
    actions.moveClip({ id: "video:source", start: 2, trackId: "video2" }),
  );
  assert.equal(
    state.present.clips.find((clip) => clip.kind === "video").trackId,
    "video2",
  );
  assert.equal(
    state.present.clips.find((clip) => clip.kind === "audio").trackId,
    "audio",
  );
  assert.equal(
    state.present.clips.find((clip) => clip.kind === "audio").start,
    2,
  );
});

test("an added source is removable independently of the original linked source", () => {
  let state = edit(initialized(), (actions) =>
    actions.addClip({
      clip: {
        id: "extra",
        kind: "audio",
        trackId: "dub",
        sourceId: "episode",
        start: 0,
        duration: 100,
        sourceStart: 0,
        name: "extra",
      },
    }),
  );
  state = edit(state, (actions) => actions.removeClip({ id: "extra" }));
  assert.equal(state.present.clips.length, 2);
  assert.ok(state.present.clips.every((clip) => clip.linkId === "source"));
});

test("split, move away, and snap back rejoins both source segments without a gap", async () => {
  const { snapClipStart } =
    await import("../apps/desktop/src/features/timeline/utils/geometry.ts");
  let state = edit(initialized(), (actions) =>
    actions.split({ time: 30.003, selectedId: null }),
  );
  state = edit(state, (actions) =>
    actions.moveClip({
      id: "video:source@30.003",
      start: 40,
      trackId: "video",
    }),
  );
  const right = state.present.clips.find(
    (clip) => clip.id === "video:source@30.003",
  );
  const firstEnd = 30.003;
  const snapped = snapClipStart(
    firstEnd - 0.03,
    right.duration,
    [firstEnd],
    100,
  );
  state = edit(state, (actions) =>
    actions.moveClip({ id: right.id, start: snapped, trackId: "video" }),
  );
  for (const kind of ["video", "audio"]) {
    const clips = state.present.clips
      .filter((clip) => clip.kind === kind)
      .sort((a, b) => a.start - b.start);
    assert.equal(clips[0].start + clips[0].duration, clips[1].start);
    assert.equal(clips[1].sourceStart, firstEnd);
  }
});

test("manual dragging with snapping off stops at contact instead of rejecting pointer overshoot", async () => {
  const { resolveClipDrag } =
    await import("../apps/desktop/src/features/timeline/stores/timeline-edits.ts");
  let state = edit(initialized(), (actions) =>
    actions.split({ time: 30.003, selectedId: null }),
  );
  state = edit(state, (actions) =>
    actions.moveClip({
      id: "video:source@30.003",
      start: 40,
      trackId: "video",
    }),
  );
  const placement = resolveClipDrag(
    state.present,
    "video:source@30.003",
    29.95,
    "video",
  );
  assert.equal(placement.start, 30.003);
  for (const kind of ["video", "audio"]) {
    const clips = placement.document.clips
      .filter((clip) => clip.kind === kind)
      .sort((a, b) => a.start - b.start);
    assert.equal(clips[0].start + clips[0].duration, clips[1].start);
  }
  assert.equal(
    resolveClipDrag(state.present, "video:source@30.003", 30.009, "video")
      .start,
    30.009,
    "a small positive gap must not magnetically snap",
  );
  const undoable = edit(state, (actions) =>
    actions.moveClip({
      id: "video:source@30.003",
      start: placement.start,
      trackId: "video",
    }),
  );
  assert.deepEqual(
    edit(undoable, (actions) => actions.undo()).present,
    state.present,
  );
});

test("manual contact also clamps a left clip against its right neighbor", async () => {
  const { resolveClipDrag } =
    await import("../apps/desktop/src/features/timeline/stores/timeline-edits.ts");
  let state = edit(initialized(), (actions) =>
    actions.split({ time: 30, selectedId: null }),
  );
  state = edit(state, (actions) =>
    actions.moveClip({ id: "video:source@30", start: 40, trackId: "video" }),
  );
  const placement = resolveClipDrag(
    state.present,
    "video:source",
    10.04,
    "video",
  );
  assert.equal(placement.start, 10);
  assert.equal(
    resolveClipDrag(state.present, "video:source", 9.99, "video").start,
    9.99,
  );
  const locked = edit(state, (actions) =>
    actions.toggleLayer({ id: "audio", property: "locked" }),
  );
  assert.equal(
    resolveClipDrag(locked.present, "video:source", 10.04, "video"),
    null,
  );
  assert.equal(
    resolveClipDrag(state.present, "video:source", 10.04, "audio"),
    null,
  );
});
