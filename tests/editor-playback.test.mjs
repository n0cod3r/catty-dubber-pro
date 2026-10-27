import assert from "node:assert/strict";
import test from "node:test";

import { advancePlaybackClock } from "../apps/desktop/src/features/playback/utils/clock.ts";

test("playback follows native media and holds during buffering instead of seeking ahead", () => {
  assert.deepEqual(advancePlaybackClock(5, 5, null, 2, 30), { time: 5, pendingSeek: null });
  assert.equal(advancePlaybackClock(5, 5.04, null, 1, 30).time, 5.04);
});
test("explicit seeks wait for media while timeline gaps advance without a media clock", () => {
  assert.deepEqual(advancePlaybackClock(12, 5, 12, 0.03, 30), { time: 12, pendingSeek: 12 });
  assert.deepEqual(advancePlaybackClock(12, 12.02, 12, 0.03, 30), {
    time: 12.02,
    pendingSeek: null,
  });
  assert.equal(advancePlaybackClock(12, null, null, 0.5, 30).time, 12.5);
  assert.equal(advancePlaybackClock(29, null, null, 2, 30).time, 30);
});
