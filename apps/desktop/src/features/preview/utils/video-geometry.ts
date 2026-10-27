import type { EpisodeMedia } from "@/features/preview/deps/episodes";
import type { TimelineDocument } from "@/features/preview/deps/timeline";

export function activeVideoAt(
  document: TimelineDocument,
  time: number,
  sources: readonly EpisodeMedia[],
) {
  const end = document.clips.reduce(
    (value, clip) => (clip.kind === "video" ? Math.max(value, clip.start + clip.duration) : value),
    0,
  );
  // Keep the final picture visible when playback stops exactly at the end.
  const sampleTime = time === end && end > 0 ? Math.max(0, time - 0.0000001) : time;
  for (let layerIndex = 0; layerIndex < document.layers.length; layerIndex++) {
    const layer = document.layers[layerIndex];
    if (!layer || layer.kind !== "video" || layer.hidden) continue;
    for (let index = document.clips.length - 1; index >= 0; index--) {
      const clip = document.clips[index];
      if (
        !clip ||
        clip.kind !== "video" ||
        clip.trackId !== layer.id ||
        sampleTime < clip.start ||
        sampleTime >= clip.start + clip.duration
      )
        continue;
      const source = sources.find((item) => item.id === clip.sourceId);
      if (source) return { clip, source, layerIndex };
    }
  }
  return null;
}

export function fitVideoFrame(
  width: number,
  height: number,
  sourceWidth: number | null | undefined,
  sourceHeight: number | null | undefined,
) {
  if (
    !sourceWidth ||
    !sourceHeight ||
    !Number.isFinite(sourceWidth) ||
    !Number.isFinite(sourceHeight) ||
    sourceWidth <= 0 ||
    sourceHeight <= 0 ||
    width <= 0 ||
    height <= 0
  )
    return { width: 0, height: 0 };
  const scale = Math.min(width / sourceWidth, height / sourceHeight);
  return { width: sourceWidth * scale, height: sourceHeight * scale };
}
