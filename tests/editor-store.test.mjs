import assert from "node:assert/strict";
import test from "node:test";

import { createTimelineStore } from "../apps/desktop/src/features/timeline/stores/timeline-store.ts";

const initialize = { sourceId: "source", name: "Episode", duration: 20 };

test("timeline sessions isolate documents and undo history", () => {
  const first = createTimelineStore();
  const second = createTimelineStore();
  first.getState().initialize(initialize);
  first.getState().split({ time: 5, selectedId: null });
  assert.equal(first.getState().history.present.clips.length, 4);
  assert.equal(second.getState().history.present.clips.length, 0);
  assert.equal(second.getState().history.past.length, 0);
  first.getState().undo();
  assert.equal(first.getState().history.present.clips.length, 2);
  first.getState().redo();
  assert.equal(first.getState().history.present.clips.length, 4);
  assert.equal(createTimelineStore().getState().history.present.initialized, false);
});

test("timeline actions are stable and rejected edits do not notify subscribers", () => {
  const store = createTimelineStore();
  const initializeSource = store.getState().initialize;
  let notifications = 0;
  const unsubscribe = store.subscribe(() => notifications++);
  store.getState().undo();
  assert.equal(notifications, 0);
  initializeSource(initialize);
  assert.equal(notifications, 1);
  assert.equal(store.getState().initialize, initializeSource);
  unsubscribe();
});

test("persisted dialogue edits replace subtitles and restore in a new editor session", () => {
  const store = createTimelineStore();
  const original = [{ id: "original", start: 2, end: 10, text: "你好世界" }];
  store.getState().initialize(initialize);
  store.getState().syncDialogue({ sourceId: "source", segments: original });
  const split = [
    { id: "left", start: 2, end: 6, text: "你好" },
    { id: "right", start: 6, end: 10, text: "世界" },
  ];
  store.getState().syncDialogue({ sourceId: "source", segments: split });
  store.getState().syncDialogue({ sourceId: "source", segments: split });
  const subtitles = (session) =>
    session
      .getState()
      .history.present.clips.filter((clip) => clip.trackId === "dialogue-subtitles");
  assert.equal(subtitles(store).length, 2);
  assert.deepEqual(
    subtitles(store).map((clip) => [clip.start, clip.duration, clip.text]),
    [
      [2, 4, "你好"],
      [6, 4, "世界"],
    ],
  );
  assert.equal(
    store.getState().history.present.layers.filter((layer) => layer.id === "dialogue-subtitles")
      .length,
    1,
  );
  const reopened = createTimelineStore();
  reopened.getState().initialize(initialize);
  reopened.getState().syncDialogue({ sourceId: "source", segments: split });
  assert.deepEqual(subtitles(reopened), subtitles(store));
  const merged = [{ id: "merged", start: 2, end: 10, text: "你好世界" }];
  store.getState().syncDialogue({ sourceId: "source", segments: merged });
  assert.equal(subtitles(store).length, 1);
  assert.equal(subtitles(store)[0].duration, 8);
  assert.equal(
    store.getState().history.present.clips.filter((clip) => clip.kind !== "subtitle").length,
    2,
  );
});
