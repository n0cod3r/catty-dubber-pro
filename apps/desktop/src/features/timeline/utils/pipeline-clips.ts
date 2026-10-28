import type { TranslationProgress, TtsProgress } from "@catty/contracts";

import type { EpisodeMedia } from "../deps/episodes";

export type PipelineClip = {
  id: string;
  start: number;
  duration: number;
  text: string;
  status: string;
  audioPath?: string;
  audioVersion?: string;
};

export function scopedProgress<T extends TranslationProgress | TtsProgress>(
  progress: T | null | undefined,
  projectDirectory: string,
  episodeId: string | undefined,
): T | null {
  return progress?.project_directory === projectDirectory &&
    progress.episode_id === episodeId &&
    (!progress.episode || progress.episode.id === episodeId)
    ? progress
    : null;
}

export function translationTimelineClips(
  episode: EpisodeMedia | null,
  progress: TranslationProgress | null,
): PipelineClip[] {
  const active = new Set(
    progress?.phase === "translating" ? progress.active_segment_ids : [],
  );
  return (episode?.dialogueSegments ?? [])
    .filter(
      (row) =>
        Number.isFinite(row.start) &&
        Number.isFinite(row.end) &&
        row.end > row.start,
    )
    .map((row) => ({
      id: `translation:${row.id}`,
      start: Math.max(0, row.start),
      duration: row.end - Math.max(0, row.start),
      text: row.translation?.text || "Not translated",
      status: active.has(row.id)
        ? "Translating"
        : row.translation?.status === "failed"
          ? "Failed"
          : row.translation?.text?.trim()
            ? "Ready"
            : "Pending",
    }))
    .filter((clip) => clip.duration > 0);
}

export function dubbingTimelineClips(
  episode: EpisodeMedia | null,
  progress: TtsProgress | null,
  pendingIds: string[],
  failedId: string | null,
): PipelineClip[] {
  const dubs = new Map(
    episode?.dubSegments?.map((dub) => [dub.dialogue_segment_id, dub]),
  );
  const pending = new Set(pendingIds);
  return (episode?.dialogueSegments ?? [])
    .filter(
      (row) =>
        row.translation?.text.trim() &&
        Number.isFinite(row.start) &&
        Number.isFinite(row.end) &&
        row.end > row.start,
    )
    .map((row) => {
      const dub = dubs.get(row.id);
      const status =
        failedId === row.id
          ? "Failed"
          : pending.has(row.id)
            ? progress?.phase === "generating" && progress.segment_id === row.id
              ? "Generating"
              : "Queued"
            : dub?.status === "ready" && dub.audio_path
              ? "Ready"
              : dub?.status === "outdated"
                ? "Outdated"
                : dub?.status === "failed"
                  ? "Failed"
                  : dub?.status === "generating"
                    ? "Interrupted"
                    : "Pending";
      const ready = status === "Ready";
      const measured = ready ? dub?.generated_duration : null;
      return {
        id: `dub:${row.id}`,
        start: Math.max(0, row.start),
        duration:
          measured && Number.isFinite(measured) && measured > 0
            ? measured
            : row.end - Math.max(0, row.start),
        text: row.translation!.text,
        status,
        audioPath: ready ? (dub?.audio_path ?? undefined) : undefined,
        audioVersion: ready ? (dub?.generated_at ?? undefined) : undefined,
      };
    })
    .filter((clip) => clip.duration > 0);
}
