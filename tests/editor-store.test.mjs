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
