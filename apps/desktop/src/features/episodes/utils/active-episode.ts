import type { PersistedEpisode } from "@catty/contracts";

const STORAGE_PREFIX = "catty.active-episode.v1";

export function selectActiveEpisode(
  episodes: PersistedEpisode[],
  preferredId: string | null | undefined,
): PersistedEpisode | null {
  if (episodes.length === 0) return null;
  return episodes.find((episode) => episode.id === preferredId) ?? episodes[0] ?? null;
}

function storageKey(directory: string) {
  return `${STORAGE_PREFIX}:${directory}`;
}

export function readActiveEpisodeId(directory: string): string | null {
  try {
    return globalThis.localStorage?.getItem(storageKey(directory)) ?? null;
  } catch {
    return null;
  }
}

export function rememberActiveEpisode(directory: string, episodeId: string): void {
  try {
    globalThis.localStorage?.setItem(storageKey(directory), episodeId);
  } catch {
    /* Selection is a convenience; project data is unaffected. */
  }
}
