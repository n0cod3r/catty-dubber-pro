import assert from "node:assert/strict";
import test from "node:test";

import {
  activeDialogueId,
  dialogueScrollDelta,
} from "../apps/desktop/src/features/editor/utils/dialogue-follow.ts";

const segments = [
  { id: "a", start: 1, end: 3 },
  { id: "b", start: 3, end: 5 },
  { id: "c", start: 7, end: 9 },
];
test("dialogue follows seeks and playback with exclusive end boundaries and silent gaps", () => {
  for (const [time, id] of [
    [0, null],
    [1, "a"],
    [2.99, "a"],
    [3, "b"],
    [6, null],
    [7, "c"],
    [2, "a"],
    [9, null],
    [NaN, null],
  ])
    assert.equal(activeDialogueId(segments, time), id);
  assert.equal(activeDialogueId([], 2), null);
});
test("dialogue follow leaves visible rows still and reveals offscreen rows in either direction", () => {
  assert.equal(dialogueScrollDelta(120, 160, 100, 300), 0);
  assert.equal(dialogueScrollDelta(80, 120, 100, 300), -20);
  assert.equal(dialogueScrollDelta(280, 330, 100, 300), 30);
  assert.equal(dialogueScrollDelta(320, 620, 100, 300), 220);
  assert.equal(dialogueScrollDelta(100, 500, 100, 300), 0);
});
