import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { convertFileSrc } from "@tauri-apps/api/core";

import type { EpisodeMedia } from "@/features/timeline/deps/episodes";

import type {
  VisualRequest,
  VisualResponse,
  Waveform,
} from "../types/media-visuals";

export function useMediaVisuals(episode: EpisodeMedia | null) {
  const workerRef = useRef<Worker | null>(null);
  const framesRef = useRef(new Map<number, ImageBitmap>());
  const waveRef = useRef<Waveform | null>(null);
  const [revision, setRevision] = useState(0);
  const [videoError, setVideoError] = useState<string | null>(null);
  const duration = episode?.durationSeconds ?? 0;
  const path = episode?.playbackPath || episode?.path;

  useEffect(() => {
    if (!path || duration <= 0) return;
    const frames = framesRef.current;
    let worker: Worker;
    try {
      worker = new Worker(
        new URL("../workers/media-visuals.worker.ts", import.meta.url),
        {
          type: "module",
        },
      );
    } catch {
      setVideoError("Media workers are unavailable in this browser.");
      return;
    }
    workerRef.current = worker;
    setRevision((value) => value + 1);
    const fail = (message: string) => {
      setVideoError(message);
      waveRef.current = {
        min: new Float32Array(),
        max: new Float32Array(),
        rate: 1,
        peak: 0,
        progress: 0,
        status: "error",
        error: message,
      };
      setRevision((value) => value + 1);
    };
    worker.onerror = () =>
      fail("Media analysis failed. You can still use the editor.");
    worker.onmessage = ({ data }: MessageEvent<VisualResponse>) => {
      if (data.type === "thumbnail") {
        frames.get(data.time)?.close();
        frames.delete(data.time);
        frames.set(data.time, data.bitmap);
        while (frames.size > 256) {
          const first = frames.keys().next().value;
          if (first === undefined) break;
          frames.get(first)?.close();
          frames.delete(first);
        }
      } else if (data.type === "video-error") setVideoError(data.message);
      else if (data.type === "audio-init")
        waveRef.current = {
          min: new Float32Array(data.bins),
          max: new Float32Array(data.bins),
          rate: data.rate,
          peak: 0,
          progress: 0,
          status: "loading",
        };
      else if (data.type === "audio-chunk" && waveRef.current) {
        waveRef.current.min.set(data.min, data.start);
        waveRef.current.max.set(data.max, data.start);
        waveRef.current.peak = data.peak;
        waveRef.current.progress = data.progress;
      } else if (data.type === "audio-done" && waveRef.current) {
        waveRef.current.status = "ready";
        waveRef.current.progress = 1;
      } else if (data.type === "audio-error" || data.type === "audio-absent")
        waveRef.current = {
          min: new Float32Array(),
          max: new Float32Array(),
          rate: 1,
          peak: 0,
          progress: 0,
          status: data.type === "audio-absent" ? "absent" : "error",
          error: data.type === "audio-error" ? data.message : undefined,
        };
      setRevision((value) => value + 1);
    };
    const message: VisualRequest = {
      type: "open",
      url: path.startsWith("blob:") ? path : convertFileSrc(path),
      duration,
    };
    worker.postMessage(message);
    // The keyed editor session owns all GPU bitmaps, decode work and source URLs.
    return () => {
      worker.terminate();
      workerRef.current = null;
      for (const bitmap of frames.values()) bitmap.close();
      frames.clear();
      waveRef.current = null;
    };
  }, [duration, path]);

  const requestFrames = useCallback((times: number[]) => {
    const missing = times.filter((time) => !framesRef.current.has(time));
    if (missing.length)
      workerRef.current?.postMessage({
        type: "thumbnails",
        times: missing,
      } satisfies VisualRequest);
  }, []);

  return useMemo(
    () => ({
      frames: framesRef,
      waveform: waveRef,
      revision,
      videoError,
      requestFrames,
      available: duration > 0 && workerRef.current !== null,
    }),
    [duration, revision, videoError, requestFrames],
  );
}
export type MediaVisuals = ReturnType<typeof useMediaVisuals>;
