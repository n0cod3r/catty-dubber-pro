export function normalNoise(seed: number) {
  const uniform = () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let value = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
  return () =>
    Math.sqrt(-2 * Math.log(Math.max(Number.EPSILON, uniform()))) *
    Math.cos(2 * Math.PI * uniform());
}

export function encodeWave(
  samples: Float32Array,
  sampleRate: number,
): ArrayBuffer {
  const result = new ArrayBuffer(44 + samples.length * 2),
    view = new DataView(result);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++)
      view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, result.byteLength - 8, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const value = Math.max(-1, Math.min(1, samples[i]!));
    view.setInt16(
      44 + i * 2,
      Math.round(value * (value < 0 ? 32768 : 32767)),
      true,
    );
  }
  return result;
}

export function readMonoWave(buffer: ArrayBuffer): Float32Array {
  const view = new DataView(buffer);
  let channels = 0,
    rate = 0,
    bits = 0,
    format = 0;
  for (let offset = 12; offset + 8 <= view.byteLength;) {
    const id = String.fromCharCode(...new Uint8Array(buffer, offset, 4));
    const size = view.getUint32(offset + 4, true),
      start = offset + 8;
    if (start + size > view.byteLength)
      throw new Error("Reference WAV is truncated");
    if (id === "fmt ") {
      format = view.getUint16(start, true);
      channels = view.getUint16(start + 2, true);
      rate = view.getUint32(start + 4, true);
      bits = view.getUint16(start + 14, true);
    }
    if (id === "data") {
      if (channels !== 1 || rate !== 16000 || bits !== 16 || format !== 1)
        throw new Error("Reference must be normalized to 16 kHz mono PCM16");
      if (size <= 0 || size % 2 || size / 2 > rate * 30)
        throw new Error("Reference exceeds 30 seconds");
      return Float32Array.from(
        { length: size / 2 },
        (_, i) => view.getInt16(start + i * 2, true) / 32768,
      );
    }
    offset = start + size + (size % 2);
  }
  throw new Error("Reference WAV has no audio data");
}
