import type { VisualResponse } from "../types/media-visuals";

export type DubWaveform = { bars: number[]; error?: string };
type Job = {
  url: string;
  duration: number;
  listeners: Set<(wave: DubWaveform) => void>;
  worker?: Worker;
};

const cache = new Map<string, DubWaveform>();
const jobs = new Map<string, Job>();
let running = 0;

// Only visible clips subscribe. Bound concurrent decoders and retain small peak arrays,
// never decoded audio buffers. Unmounting cancels unused work.
function pump() {
  for (const [key, job] of jobs) {
    if (running >= 2) break;
    if (job.worker) continue;
    let worker: Worker;
    let settled = false;
    const finish = (wave: DubWaveform) => {
      if (settled || jobs.get(key) !== job) return;
      settled = true;
      worker?.terminate();
      jobs.delete(key);
      running -= 1;
      cache.set(key, wave);
      while (cache.size > 64) cache.delete(cache.keys().next().value!);
      for (const listener of job.listeners) listener(wave);
      pump();
    };
    running += 1;
    try {
      worker = new Worker(
        new URL("../workers/media-visuals.worker.ts", import.meta.url),
        { type: "module" },
      );
      job.worker = worker;
      let min = new Float32Array(),
        max = new Float32Array();
      worker.onerror = () =>
        finish({ bars: [], error: "Waveform unavailable" });
      worker.onmessage = ({ data }: MessageEvent<VisualResponse>) => {
        if (data.type === "audio-init") {
          min = new Float32Array(data.bins);
          max = new Float32Array(data.bins);
        } else if (data.type === "audio-chunk") {
          min.set(data.min, data.start);
          max.set(data.max, data.start);
        } else if (data.type === "audio-done") {
          const bars = Array.from({ length: 128 }, (_, index) => {
            let peak = 0;
            const end = Math.min(
              min.length,
              Math.ceil(((index + 1) / 128) * min.length),
            );
            for (
              let bin = Math.floor((index / 128) * min.length);
              bin < end;
              bin++
            )
              peak = Math.max(
                peak,
                Math.abs(min[bin] ?? 0),
                Math.abs(max[bin] ?? 0),
              );
            return Math.min(1, peak);
          });
          finish({ bars });
        } else if (data.type === "audio-error" || data.type === "audio-absent")
          finish({ bars: [], error: "Waveform unavailable" });
      };
      worker.postMessage({
        type: "open",
        url: job.url,
        duration: job.duration,
      });
    } catch {
      finish({ bars: [], error: "Waveform unavailable" });
    }
  }
}

export function subscribeDubWaveform(
  url: string,
  duration: number,
  listener: (wave: DubWaveform) => void,
) {
  const key = JSON.stringify([url, duration]);
  const cached = cache.get(key);
  if (cached) {
    cache.delete(key);
    cache.set(key, cached);
    listener(cached);
    return () => {};
  }
  const job = jobs.get(key) ?? { url, duration, listeners: new Set() };
  job.listeners.add(listener);
  jobs.set(key, job);
  pump();
  return () => {
    job.listeners.delete(listener);
    if (!job.listeners.size && jobs.get(key) === job) {
      if (job.worker) {
        job.worker.terminate();
        running -= 1;
      }
      jobs.delete(key);
      pump();
    }
  };
}
