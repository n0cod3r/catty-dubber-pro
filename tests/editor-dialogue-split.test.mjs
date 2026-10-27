import assert from "node:assert/strict";
import test from "node:test";

import { dialogueSplitTarget } from "../apps/desktop/src/features/timeline/utils/dialogue-split.ts";

const segments = [
  { id: "first", start: 1, end: 4 },
  { id: "second", start: 4, end: 8 },
];
test("timeline dialogue split resolves the persisted UUID rather than locally splitting a subtitle", () => {
  assert.equal(dialogueSplitTarget("source", segments, "dialogue:source:first", 2)?.id, "first");
  assert.equal(dialogueSplitTarget("source", segments, null, 5)?.id, "second");
  assert.equal(dialogueSplitTarget("source", segments, "video:source", 2), null);
  assert.equal(dialogueSplitTarget("source", segments, "dialogue:other:first", 2), null);
});
test("timeline dialogue split rejects boundaries, stale selection and wrong time", () => {
  for (const time of [1, 1.02, 3.99, 4, 5, NaN])
    assert.equal(dialogueSplitTarget("source", segments, "dialogue:source:first", time), null);
  assert.equal(dialogueSplitTarget("source", segments, "dialogue:source:old", 2), null);
});
