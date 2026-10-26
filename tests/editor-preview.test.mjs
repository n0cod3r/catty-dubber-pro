import assert from "node:assert/strict";
import test from "node:test";

import { activeVideoAt, fitVideoFrame } from "../apps/desktop/src/features/timeline/preview.ts";

const landscape = { id: "landscape", width: 1920, height: 1080 };
const portrait = { id: "portrait", width: 1080, height: 1920 };
const document = {
  layers: [
    { id: "top", kind: "video", hidden: false },
    { id: "bottom", kind: "video", hidden: false },
  ],
  clips: [
    { id: "base", kind: "video", trackId: "bottom", sourceId: "landscape", start: 0, duration: 20 },
    { id: "overlay", kind: "video", trackId: "top", sourceId: "portrait", start: 5, duration: 5 },
  ],
};

test("preview detects the front visible timeline video and source dimensions", () => {
  assert.equal(activeVideoAt(document, 4, [landscape, portrait]).source.id, "landscape");
  assert.equal(activeVideoAt(document, 5, [landscape, portrait]).source.id, "portrait");
  assert.equal(activeVideoAt(document, 10, [landscape, portrait]).source.id, "landscape");
  assert.equal(activeVideoAt(document, 20, [landscape, portrait]).source.id, "landscape");
  const hidden = {
    ...document,
    layers: [{ ...document.layers[0], hidden: true }, document.layers[1]],
  };
  assert.equal(activeVideoAt(hidden, 6, [landscape, portrait]).source.id, "landscape");
  assert.equal(activeVideoAt(document, 6, [landscape]).source.id, "landscape");
  assert.equal(activeVideoAt(document, 30, [landscape, portrait]), null);
});

test("preview fits landscape and portrait video within both resizable dimensions", () => {
  assert.deepEqual(fitVideoFrame(800, 300, 1920, 1080), { width: (300 * 16) / 9, height: 300 });
  const portrait = fitVideoFrame(300, 500, 1080, 1920);
  assert.ok(Math.abs(portrait.width - 281.25) < 1e-9);
  assert.ok(Math.abs(portrait.height - 500) < 1e-9);
  const narrow = fitVideoFrame(280, 200, 1920, 1080);
  assert.equal(narrow.width, 280);
  assert.equal(narrow.width / narrow.height, 16 / 9);
});

test("preview waits for valid video metadata instead of assuming a fixed aspect ratio", () => {
  for (const dimensions of [
    [null, null],
    [0, 1080],
    [1920, -1],
    [Infinity, 1080],
  ]) {
    assert.deepEqual(fitVideoFrame(800, 300, ...dimensions), { width: 0, height: 0 });
  }
});
