import assert from "node:assert/strict";
import test from "node:test";

import { isMergeDialogueShortcut } from "../apps/desktop/src/features/editor/utils/dialogue-shortcuts.ts";

const event = {
  key: "m",
  ctrlKey: true,
  metaKey: false,
  shiftKey: true,
  altKey: false,
  repeat: false,
  isComposing: false,
  defaultPrevented: false,
};
test("merge dialogue shortcut supports Windows Control and macOS Command", () => {
  assert.equal(isMergeDialogueShortcut(event), true);
  assert.equal(
    isMergeDialogueShortcut({
      ...event,
      ctrlKey: false,
      metaKey: true,
      key: "M",
    }),
    true,
  );
});
test("merge shortcut ignores marker key, repeats, IME and handled events", () => {
  for (const overrides of [
    { ctrlKey: false },
    { shiftKey: false },
    { altKey: true },
    { repeat: true },
    { isComposing: true },
    { defaultPrevented: true },
    { key: "s" },
  ]) {
    assert.equal(isMergeDialogueShortcut({ ...event, ...overrides }), false);
  }
});
