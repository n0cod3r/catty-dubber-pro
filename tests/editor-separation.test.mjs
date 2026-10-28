import assert from "node:assert/strict";
import test from "node:test";

import {
  separationNeedsModel,
  separationPhase,
} from "../apps/desktop/src/features/editor/utils/separation.ts";

test("separation phase trusts a prepared background over persisted status", () => {
  assert.equal(separationPhase("failed", true), "ready");
  assert.equal(separationPhase(undefined, true), "ready");
});

test("separation phase distinguishes interrupted runs from failures", () => {
  assert.equal(separationPhase("processing", false), "interrupted");
  assert.equal(separationPhase("queued", false), "interrupted");
  assert.equal(separationPhase("failed", false), "failed");
  assert.equal(separationPhase("idle", false), "idle");
  assert.equal(separationPhase(undefined, false), "idle");
  // A completed status without a stem means the asset is gone; allow a rerun.
  assert.equal(separationPhase("completed", false), "idle");
});

test("model missing detection matches engine errors", () => {
  assert.equal(
    separationNeedsModel(
      "The separation model is not installed. Install it in Settings first.",
    ),
    true,
  );
  assert.equal(separationNeedsModel("SEPARATION_MODEL_MISSING"), true);
  assert.equal(separationNeedsModel(null), false);
  assert.equal(separationNeedsModel("Dialogue separation failed"), false);
});
