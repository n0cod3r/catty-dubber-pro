import { memo, useEffect, useRef } from "react";

import type { MediaVisuals } from "../hooks/use-media-visuals";
import type { TimelineClip } from "../types";
import { clipRenderWindow, THUMB_WIDTH, thumbnailTiles } from "../utils/render-window";

type Props = {
  clip: TimelineClip;
  pixelsPerSecond: number;
  scrollLeft: number;
  viewportWidth: number;
  sourceDuration: number;
  visuals: MediaVisuals;
};

export const ClipMediaCanvas = memo(function ClipMediaCanvas({
  clip,
  pixelsPerSecond,
  scrollLeft,
  viewportWidth,
  sourceDuration,
  visuals,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const window = clipRenderWindow(
    clip.start,
    clip.duration,
    pixelsPerSecond,
    scrollLeft,
    viewportWidth,
  );
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || window.width <= 0) return;
    const height = 46;
    const scale = Math.min(2, devicePixelRatio || 1);
    canvas.width = Math.ceil(window.width * scale);
    canvas.height = height * scale;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(scale, scale);
    if (clip.kind === "video") {
      const tiles = thumbnailTiles(
        clip.sourceStart,
        window.left,
        window.width,
        pixelsPerSecond,
        sourceDuration,
      );
      for (const tile of tiles) {
        const bitmap = visuals.frames.current.get(tile.time);
        if (!bitmap) {
          ctx.fillStyle = "#ffffff08";
          ctx.fillRect(tile.x - window.left, 0, THUMB_WIDTH - 1, height);
          continue;
        }
        ctx.drawImage(bitmap, tile.x - window.left, 0, THUMB_WIDTH - 1, height);
      }
    } else {
      const wave = visuals.waveform.current;
      if (!wave || wave.min.length === 0) return;
      const gain = 0.9 / Math.max(0.01, wave.peak);
      ctx.fillStyle = "#8ee5b4";
      for (let x = 0; x < window.width; x += 2) {
        const time = clip.sourceStart + (window.left + x) / pixelsPerSecond;
        const from = Math.max(0, Math.floor(time * wave.rate));
        const to = Math.min(
          wave.min.length,
          Math.max(from + 1, Math.ceil((time + 2 / pixelsPerSecond) * wave.rate)),
        );
        let low = 0,
          high = 0;
        for (let bin = from; bin < to; bin++) {
          low = Math.min(low, wave.min[bin] ?? 0);
          high = Math.max(high, wave.max[bin] ?? 0);
        }
        if (time * wave.rate > wave.progress * wave.min.length) continue;
        const top = height / 2 - Math.min(1, high * gain) * (height / 2 - 2);
        const bottom = height / 2 - Math.max(-1, low * gain) * (height / 2 - 2);
        ctx.fillRect(x, top, 1.5, Math.max(1, bottom - top));
      }
    }
  }, [
    clip.kind,
    clip.sourceStart,
    pixelsPerSecond,
    sourceDuration,
    visuals.frames,
    visuals.waveform,
    visuals.revision,
    window.left,
    window.width,
  ]);

  if (window.width <= 0) return null;
  return (
    <canvas
      ref={canvasRef}
      aria-label={clip.kind === "video" ? "Video frame thumbnails" : "Decoded audio waveform"}
      data-media-canvas={clip.kind}
      data-ready={
        clip.kind === "video"
          ? visuals.frames.current.size > 0
          : visuals.waveform.current?.status === "ready"
      }
      className="pointer-events-none absolute top-5"
      style={{ left: window.left, width: window.width, height: 46 }}
    />
  );
});
