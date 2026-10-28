import assert from "node:assert/strict";
import test from "node:test";

import {
  isContinuousMedia,
  needsMediaSeek,
} from "../apps/desktop/src/features/preview/utils/media-sync.ts";

test("adjacent source splits keep A/V running without a boundary seek", () => {
  const left = { source: "proxy.mp4", offset: 0 };
  const splitTime = 30.003;
  const right = { source: "proxy.mp4", offset: splitTime - splitTime };
  assert.equal(isContinuousMedia(left, right), true);
  assert.equal(
    needsMediaSeek(left, right, 30.04, 30.03, true, false, false),
    false,
  );
  assert.equal(
    isContinuousMedia({ ...left, offset: 2 }, { ...right, offset: 2 + 1e-12 }),
    true,
  );
});
test("source jumps, gaps and explicit seeks still synchronize", () => {
  const mapping = { source: "proxy.mp4", offset: 0 };
  assert.equal(
    needsMediaSeek(undefined, mapping, 0, 5, true, false, false),
    true,
  );
  assert.equal(
    needsMediaSeek(
      mapping,
      { ...mapping, offset: 4 },
      5,
      9,
      true,
      false,
      false,
    ),
    true,
  );
  assert.equal(
    needsMediaSeek(
      mapping,
      { ...mapping, source: "other.mp4" },
      5,
      5,
      true,
      false,
      false,
    ),
    true,
  );
  assert.equal(
    needsMediaSeek(mapping, mapping, 5, 5.04, true, true, false),
    true,
  );
  assert.equal(
    needsMediaSeek(mapping, mapping, 5, 5.04, false, false, false),
    true,
  );
  assert.equal(needsMediaSeek(mapping, mapping, 5, 9, true, true, true), false);
});
