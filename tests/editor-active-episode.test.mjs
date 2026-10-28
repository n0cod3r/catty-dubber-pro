import assert from "node:assert/strict";
import test from "node:test";

import { selectActiveEpisode } from "../apps/desktop/src/features/episodes/utils/active-episode.ts";

const episode = (id) => ({ id });

test("the remembered episode is restored instead of always opening the first", () => {
  const episodes = [episode("first"), episode("second")];
  assert.equal(selectActiveEpisode(episodes, "second")?.id, "second");
  assert.equal(selectActiveEpisode(episodes, null)?.id, "first");
  assert.equal(selectActiveEpisode(episodes, "removed")?.id, "first");
  assert.equal(selectActiveEpisode([], "second"), null);
});
