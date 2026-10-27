import assert from "node:assert/strict";
import test from "node:test";

import { createDialogueSessionGuard } from "../apps/desktop/src/features/editor/utils/dialogue-session.ts";

const scope = (project, episode) => JSON.stringify([project, episode]);

test("dialogue requests cannot cross episode or project scopes", () => {
  const guard = createDialogueSessionGuard();
  const first = scope("/project-a", "episode-a");
  assert.equal(guard.begin(first), null);
  guard.reset(first);
  const oldRequest = guard.begin(first);
  assert.ok(oldRequest);
  assert.equal(guard.begin(first), null);
  guard.reset(scope("/project-a", "episode-b"));
  assert.equal(guard.isCurrent(oldRequest), false);
  assert.equal(guard.begin(first), null);
  guard.reset(scope("/project-b", "episode-a"));
  assert.equal(guard.begin(first), null);
  guard.reset(first);
  assert.equal(guard.isCurrent(oldRequest), false);
  const current = guard.begin(first);
  assert.ok(current);
  assert.equal(guard.finish(oldRequest), false);
  assert.equal(guard.isCurrent(current), true);
  assert.equal(guard.begin(first), null);
  assert.equal(guard.finish(current), true);
  assert.ok(guard.begin(first));
});

test("late request completion cannot publish results or release a new session lock", async () => {
  const guard = createDialogueSessionGuard();
  const first = scope("/project", "first");
  const second = scope("/project", "second");
  guard.reset(first);
  const ticket = guard.begin(first);
  let resolve;
  const pending = new Promise((done) => {
    resolve = done;
  });
  let published = false;
  let released = false;
  const task = (async () => {
    try {
      await pending;
      if (!guard.isCurrent(ticket)) return;
      published = true;
    } finally {
      released = guard.finish(ticket);
    }
  })();
  guard.reset(second);
  const newTicket = guard.begin(second);
  resolve();
  await task;
  assert.equal(published, false);
  assert.equal(released, false);
  assert.equal(guard.isCurrent(newTicket), true);
  guard.reset(null);
  assert.equal(guard.isCurrent(newTicket), false);
  assert.equal(guard.begin(second), null);
});
