import { ALL_FORMATS, AudioSampleSink, CanvasSink, Input, UrlSource } from "mediabunny";

import { accumulatePeaks } from "../services/peaks";
import type { VisualRequest, VisualResponse } from "../types/media-visuals";

const scope = self as unknown as {
  onmessage: (event: MessageEvent<VisualRequest>) => void;
  postMessage: (data: VisualResponse, transfer?: Transferable[]) => void;
};
let sourceUrl = "";
let duration = 0;
let thumbnailQueue: number[] = [];
let videoRunning = false;
let videoInput: Input | null = null;
let videoSink: CanvasSink | null = null;
let videoFailed = false;

async function audio() {
  const input = new Input({
    source: new UrlSource(sourceUrl, { maxCacheSize: 16 * 1024 * 1024 }),
    formats: ALL_FORMATS,
  });
  try {
    const track = await input.getPrimaryAudioTrack();
    if (!track) {
      scope.postMessage({ type: "audio-absent" });
      return;
    }
    if (track.codec && /^(ac3|eac3)$/.test(track.codec)) {
      const { registerAc3Decoder } = await import("@mediabunny/ac3");
      registerAc3Decoder();
    }
    if (!(await track.canDecode()))
      throw new Error("This audio codec cannot be decoded in this browser.");
    const rate = Math.min(200, 1_000_000 / duration);
    const bins = Math.ceil(duration * rate);
    const min = new Float32Array(bins),
      max = new Float32Array(bins);
    scope.postMessage({ type: "audio-init", bins, rate });
    const sink = new AudioSampleSink(track);
    let sent = 0,
      peak = 0,
      lastUpdate = performance.now();
    const emit = (end: number) => {
      if (end <= sent) return;
      const low = min.slice(sent, end),
        high = max.slice(sent, end);
      scope.postMessage(
        { type: "audio-chunk", start: sent, min: low, max: high, progress: end / bins, peak },
        [low.buffer, high.buffer],
      );
      sent = end;
    };
    for await (const sample of sink.samples(0, duration)) {
      try {
        const channels = Array.from(
          { length: Math.min(2, sample.numberOfChannels) },
          (_, channel) => {
            const data = new Float32Array(sample.numberOfFrames);
            sample.copyTo(data, { planeIndex: channel, format: "f32-planar" });
            return data;
          },
        );
        peak = Math.max(
          peak,
          accumulatePeaks(min, max, channels, sample.timestamp, sample.sampleRate, rate),
        );
        if (performance.now() - lastUpdate > 200) {
          emit(
            Math.min(
              bins,
              Math.max(0, Math.floor((sample.timestamp + sample.duration) * rate) - 1),
            ),
          );
          lastUpdate = performance.now();
        }
      } finally {
        sample.close();
      }
    }
    emit(bins);
    scope.postMessage({ type: "audio-done" });
  } catch (cause) {
    scope.postMessage({
      type: "audio-error",
      message: cause instanceof Error ? cause.message : "Waveform decoding failed.",
    });
  } finally {
    input.dispose();
  }
}

async function thumbnails() {
  if (videoRunning || !sourceUrl || videoFailed) return;
  videoRunning = true;
  try {
    if (!videoSink) {
      videoInput = new Input({
        source: new UrlSource(sourceUrl, { maxCacheSize: 16 * 1024 * 1024 }),
        formats: ALL_FORMATS,
      });
      const track = await videoInput.getPrimaryVideoTrack();
      if (!track || !(await track.canDecode()))
        throw new Error("Video thumbnails are unavailable for this codec.");
      videoSink = new CanvasSink(track, { width: 160, height: 90, fit: "contain", poolSize: 1 });
    }
    while (thumbnailQueue.length) {
      const time = thumbnailQueue.shift();
      if (time === undefined) break;
      const frame = await videoSink.getCanvas(Math.min(time, Math.max(0, duration - 0.05)));
      if (!frame) continue;
      const bitmap = await createImageBitmap(frame.canvas);
      scope.postMessage({ type: "thumbnail", time, bitmap }, [bitmap]);
    }
  } catch (cause) {
    videoFailed = true;
    videoInput?.dispose();
    videoInput = null;
    videoSink = null;
    scope.postMessage({
      type: "video-error",
      message: cause instanceof Error ? cause.message : "Thumbnail decoding failed.",
    });
  } finally {
    videoRunning = false;
  }
}

scope.onmessage = ({ data }) => {
  if (data.type === "open") {
    sourceUrl = data.url;
    duration = data.duration;
    void audio();
  } else {
    // New viewport requests take priority over frames that have scrolled away.
    thumbnailQueue = [...new Set(data.times)].slice(0, 64);
    void thumbnails();
  }
};
