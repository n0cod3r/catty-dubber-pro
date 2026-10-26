import assert from "node:assert/strict";
import test from "node:test";

import {
  clamp,
  formatTime,
  pointerToTime,
  snapTime,
  visibleTicks,
} from "../apps/desktop/src/features/timeline/geometry.ts";

test("pointer coordinates include scroll offset and clamp at media edges", () => {
  assert.equal(pointerToTime(400, 200, 300, 1000, 100), 50);
  assert.equal(pointerToTime(-500, 200, 0, 1000, 100), 0);
  assert.equal(pointerToTime(2000, 200, 0, 1000, 100), 100);
  assert.equal(pointerToTime(400, 200, 0, 0, 100), 0);
});

test("snapping uses an eight-pixel threshold at every zoom level", () => {
  assert.equal(snapTime(4.95, [0, 5, 10], 100), 5);
  assert.equal(snapTime(4.8, [0, 5, 10], 100), 4.8);
  assert.equal(snapTime(4.95, [0, 5, 10], 1000), 4.95);
  assert.equal(snapTime(4.95, [0, 5, 10], 0), 4.95);
});

test("ruler only generates visible ticks for long episodes and high zoom", () => {
  for (const duration of [0.5, 12, 3600, 86400]) {
    for (const zoom of [1, 12, 64]) {
      const ticks = visibleTicks(duration, 1200 * zoom, 500 * (zoom - 1), 1200);
      assert.ok(ticks.length < 20);
      assert.ok(ticks.every((tick) => tick >= 0 && tick <= duration));
    }
  }
});

test("time displays hours correctly and guards invalid media values", () => {
  assert.equal(formatTime(3661.125, true), "01:01:01.125");
  assert.equal(formatTime(-1), "00:00:00");
  assert.equal(formatTime(Infinity), "00:00:00");
  assert.equal(clamp(NaN, 0, 10), 0);
});
