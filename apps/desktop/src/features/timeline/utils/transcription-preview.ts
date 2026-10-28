import type { TranscriptionProgress } from "@catty/contracts";

import type { TimelineClip } from "../types.ts";

export function activeTranscriptionPreview(
  progress: TranscriptionProgress | null | undefined,
  active: boolean,
  projectDirectory: string | undefined,
  episodeId: string | undefined,
) {
  return active &&
    progress?.project_directory === projectDirectory &&
    progress?.episode_id === episodeId &&
    progress?.phase !== "completed" &&
    progress?.phase !== "failed"
    ? (progress ?? null)
    : null;
}

// Presentation only: these clips never enter the document, playback, or undo history.
export function transcriptionPreviewClips(
  progress: TranscriptionProgress,
  duration: number,
): TimelineClip[] {
  const clips = new Map<string, TimelineClip>();
  for (const segment of progress.preview_segments) {
    if (!Number.isFinite(segment.start) || !Number.isFinite(segment.end))
      continue;
    const start = Math.max(0, segment.start);
    const end = Math.min(duration, segment.end);
    if (end <= start) continue;
    const id = `transcription:${progress.operation_id}:${segment.id}`;
    clips.set(id, {
      id,
      trackId: "transcription-preview",
      kind: "subtitle",
      sourceId: progress.episode_id,
      sourceStart: start,
      start,
      duration: end - start,
      name: segment.text,
      text: segment.text,
    });
  }
  return [...clips.values()].sort((a, b) => a.start - b.start);
}
