// Bin by presentation timestamps rather than packet count: codec delay and gaps
// must not shift the waveform relative to the video.
export function accumulatePeaks(
  min: Float32Array,
  max: Float32Array,
  channels: Float32Array[],
  timestamp: number,
  sampleRate: number,
  binsPerSecond: number,
) {
  let peak = 0;
  const frames = channels[0]?.length ?? 0;
  for (let frame = 0; frame < frames; frame++) {
    const bin = Math.floor((timestamp + frame / sampleRate) * binsPerSecond);
    if (bin < 0 || bin >= min.length) continue;
    for (const channel of channels) {
      const value = channel[frame] ?? 0;
      if (!Number.isFinite(value)) continue;
      min[bin] = Math.min(min[bin] ?? 0, value);
      max[bin] = Math.max(max[bin] ?? 0, value);
      peak = Math.max(peak, Math.abs(value));
    }
  }
  return peak;
}
