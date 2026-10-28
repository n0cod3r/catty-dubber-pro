import type { TtsGenerationMode, TtsProgress } from "@catty/contracts";

import type { EpisodeMedia } from "../deps/episodes";

export function isCurrentTtsProgress(
  event: TtsProgress,
  operationId: string,
  projectDirectory: string,
  episodeId: string,
) {
  return (
    event.operation_id === operationId &&
    event.project_directory === projectDirectory &&
    event.episode_id === episodeId &&
    (!event.episode || event.episode.id === episodeId)
  );
}

export function ttsTargetIds(
  episode: EpisodeMedia,
  mode: TtsGenerationMode,
  selected: string[],
) {
  const ready = new Set(
    episode.dubSegments
      ?.filter((dub) => dub.status === "ready")
      .map((dub) => dub.dialogue_segment_id),
  );
  return (episode.dialogueSegments ?? [])
    .filter(
      (row) =>
        row.translation?.text.trim() &&
        (mode !== "selected" || selected.includes(row.id)) &&
        (mode !== "missing" || !ready.has(row.id)),
    )
    .map((row) => row.id);
}
