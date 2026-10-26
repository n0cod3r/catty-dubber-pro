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

test("a split clip snaps flush when returning despite trailing-edge rounding", async () => {
  const { snapClipStart } = await import("../apps/desktop/src/features/timeline/geometry.ts");
  const firstEnd = 4.803;
  const duration = 12.008 - firstEnd;
  for (const candidate of [firstEnd - 0.05, firstEnd + 0.05, firstEnd + 0.000000000000001]) {
    assert.equal(snapClipStart(candidate, duration, [0, firstEnd], 80), firstEnd);
  }
  assert.equal(snapClipStart(3.95, 2, [6], 80), 4, "trailing edge can snap to a real target");
  assert.equal(snapClipStart(3.5, 2, [6], 80), 3.5, "do not snap outside eight pixels");
});
