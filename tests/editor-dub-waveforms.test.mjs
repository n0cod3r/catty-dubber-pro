import assert from "node:assert/strict";
import test from "node:test";

import { subscribeDubWaveform } from "../apps/desktop/src/features/timeline/services/dub-waveforms.ts";

test("generated waveforms use bounded decoders, real samples, cache versions and cancel unused work", () => {
  const previous = globalThis.Worker;
  const workers = [];
  class TestWorker {
    stopped = false;
    constructor() {
      workers.push(this);
    }
    postMessage(message) {
      this.message = message;
    }
    terminate() {
      this.stopped = true;
    }
    send(data) {
      this.onmessage({ data });
    }
  }
  globalThis.Worker = TestWorker;
  const stops = [];
  try {
    let first;
    stops.push(
      subscribeDubWaveform("audio?v=1", 2, (wave) => {
        first = wave;
      }),
    );
    stops.push(subscribeDubWaveform("second", 2, () => {}));
    stops.push(subscribeDubWaveform("third", 2, () => {}));
    assert.equal(workers.length, 2);
    assert.equal(workers[0].message.url, "audio?v=1");
    workers[0].send({ type: "audio-init", bins: 2 });
    workers[0].send({
      type: "audio-chunk",
      start: 0,
      min: new Float32Array([-0.25, -0.5]),
      max: new Float32Array([0.1, 0.75]),
    });
    workers[0].send({ type: "audio-done" });
    assert.equal(first.bars.length, 128);
    assert.equal(first.bars[0], 0.25);
    assert.equal(first.bars[127], 0.75);
    assert.equal(workers.length, 3); // Queued clip now has a decoder.
    assert.equal(workers[0].stopped, true);
    let cached;
    stops.push(
      subscribeDubWaveform("audio?v=1", 2, (wave) => {
        cached = wave;
      }),
    );
    assert.equal(cached, first);
    assert.equal(workers.length, 3);
    stops[1](); // Unmounting the second clip frees its decoder.
    assert.equal(workers[1].stopped, true);
    stops.push(subscribeDubWaveform("audio?v=2", 2, () => {}));
    assert.equal(workers.length, 4); // New generation does not reuse old peaks.
    let failure;
    stops.push(
      subscribeDubWaveform("broken", 2, (wave) => {
        failure = wave;
      }),
    );
    workers[3].send({ type: "audio-absent" });
    assert.equal(workers.length, 5);
    workers[4].onerror();
    assert.equal(failure.error, "Waveform unavailable");
  } finally {
    for (const stop of stops) stop();
    globalThis.Worker = previous;
  }
});
