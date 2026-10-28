import assert from "node:assert/strict";
import test from "node:test";

import {
  encodeWave,
  normalNoise,
  readMonoWave,
} from "../apps/desktop/src/features/voice-runtime/services/audio.ts";

test("compact audio transports real PCM samples as mono WAV without changing sample count", () => {
  const source = new Float32Array([-1, -0.5, 0, 0.5, 1]);
  const result = readMonoWave(encodeWave(source, 16000));
  assert.equal(result.length, source.length);
  source.forEach((value, index) =>
    assert.ok(Math.abs(value - result[index]) <= 1 / 32768),
  );
  assert.throws(() => readMonoWave(encodeWave(source, 48000)), /16 kHz/);
  assert.throws(
    () => readMonoWave(encodeWave(source, 16000).slice(0, 46)),
    /truncated/,
  );
  assert.throws(
    () => readMonoWave(encodeWave(new Float32Array(), 16000)),
    /Reference/,
  );
});

test("compact diffusion noise is seedable, finite and approximately standard normal", () => {
  const first = normalNoise(42),
    repeat = normalNoise(42),
    other = normalNoise(7);
  const samples = Array.from({ length: 10000 }, first);
  assert.deepEqual(samples.slice(0, 20), Array.from({ length: 20 }, repeat));
  assert.notEqual(samples[0], other());
  assert.ok(samples.every(Number.isFinite));
  const mean = samples.reduce((sum, value) => sum + value, 0) / samples.length;
  const variance =
    samples.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
    samples.length;
  assert.ok(Math.abs(mean) < 0.05);
  assert.ok(Math.abs(variance - 1) < 0.1);
});
