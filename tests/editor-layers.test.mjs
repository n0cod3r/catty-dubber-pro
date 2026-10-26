import assert from "node:assert/strict";
import test from "node:test";

import { accumulatePeaks } from "../apps/desktop/src/features/media-visuals/peaks.ts";
import {
  clipRenderWindow,
  thumbnailTiles,
} from "../apps/desktop/src/features/media-visuals/render-window.ts";
import {
  createTimeline,
  splitCandidates,
  timelineReducer,
} from "../apps/desktop/src/features/timeline/model.ts";

const initialize = { type: "initialize", sourceId: "episode", name: "episode.webm", duration: 100 };
const layer = {
  id: "caption-2",
  kind: "subtitle",
  name: "Caption 2",
  hidden: false,
  locked: false,
  muted: false,
};
const initialized = () => timelineReducer(createTimeline(), initialize);

test("layers are independent, reorderable, and undoable without losing source clips", () => {
  let state = timelineReducer(initialized(), { type: "add-layer", layer });
  assert.equal(state.present.layers[0].id, layer.id);
  state = timelineReducer(state, { type: "move-layer", id: layer.id, direction: 1 });
  assert.equal(state.present.layers[1].id, layer.id);
  state = timelineReducer(state, { type: "undo" });
  assert.equal(state.present.layers[0].id, layer.id);
  state = timelineReducer(state, { type: "remove-layer", id: layer.id });
  assert.equal(
    state.present.layers.some((item) => item.id === layer.id),
    false,
  );
  assert.equal(state.present.clips.length, 2);
});

test("splitting linked source clips preserves exact source offsets for thumbnails and waves", () => {
  let state = timelineReducer(initialized(), {
    type: "split",
    time: 30,
    selectedId: "video:source",
  });
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
  state = timelineReducer(state, { type: "split", time: 50, selectedId: "video:source" });
  assert.equal(state.present.clips.length, 6);
  assert.equal(
    state.present.clips.find((clip) => clip.kind === "audio" && clip.start === 50).sourceStart,
    50,
  );
});

test("locks protect a whole linked split and disallow layer changes", () => {
  let state = timelineReducer(initialized(), {
    type: "toggle-layer",
    id: "audio",
    property: "locked",
  });
  assert.deepEqual(splitCandidates(state.present, 30, null), []);
  assert.equal(timelineReducer(state, { type: "split", time: 30, selectedId: null }), state);
  assert.equal(timelineReducer(state, { type: "move-layer", id: "audio", direction: -1 }), state);
  assert.equal(
    timelineReducer(state, { type: "toggle-layer", id: "audio", property: "muted" }),
    state,
  );
});

test("clip kinds must match their layer; source and populated layers cannot be removed", () => {
  let state = timelineReducer(initialized(), { type: "add-layer", layer });
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
    timelineReducer(state, { type: "add-clip", clip: { ...clip, kind: "video" } }),
    state,
  );
  state = timelineReducer(state, { type: "add-clip", clip });
  assert.equal(timelineReducer(state, { type: "remove-layer", id: layer.id }), state);
  assert.equal(timelineReducer(state, { type: "remove-layer", id: "video" }), state);
  state = timelineReducer(state, { type: "update-text", id: clip.id, text: "សួស្តី" });
  assert.equal(state.present.clips.find((item) => item.id === clip.id).text, "សួស្តី");
});

test("metadata initialization rebases edits made before loading and cannot be undone", () => {
  let state = timelineReducer(createTimeline(), { type: "add-layer", layer });
  state = timelineReducer(state, initialize);
  state = timelineReducer(state, { type: "undo" });
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
    [new Float32Array([0.25, -0.5, 0, 0]), new Float32Array([-0.75, 0.5, 0, 0])],
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
    state = timelineReducer(state, { type: "toggle-layer", id: "video", property: "hidden" });
  assert.equal(state.past.length, 100);
  state = timelineReducer(state, { type: "undo" });
  assert.equal(state.future.length, 1);
  state = timelineReducer(state, { type: "add-layer", layer });
  assert.equal(state.future.length, 0);
});
