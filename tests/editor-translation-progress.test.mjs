import assert from "node:assert/strict";
import test from "node:test";

import { isCurrentTranslationProgress } from "../apps/desktop/src/features/editor/utils/translation-progress.ts";

test("translation progress is scoped to the operation, project and episode", () => {
  const event = {
    operation_id: "new",
    project_directory: "/project",
    episode_id: "ep",
    episode: { id: "ep" },
  };
  assert.equal(isCurrentTranslationProgress(event, "new", "/project", "ep"), true);
  assert.equal(isCurrentTranslationProgress(event, "old", "/project", "ep"), false);
  assert.equal(isCurrentTranslationProgress(event, "new", "/other-project", "ep"), false);
  assert.equal(isCurrentTranslationProgress(event, "new", "/project", "other-ep"), false);
  assert.equal(
    isCurrentTranslationProgress({ ...event, episode: { id: "wrong" } }, "new", "/project", "ep"),
    false,
  );
  assert.equal(
    isCurrentTranslationProgress({ ...event, episode: null }, "new", "/project", "ep"),
    true,
  );
});
