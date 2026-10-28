import type { TranslationProgress } from "@catty/contracts";

export function isCurrentTranslationProgress(
  progress: TranslationProgress,
  operationId: string,
  projectDirectory: string,
  episodeId: string,
) {
  return (
    progress.operation_id === operationId &&
    progress.project_directory === projectDirectory &&
    progress.episode_id === episodeId &&
    (!progress.episode || progress.episode.id === episodeId)
  );
}
