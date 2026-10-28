import { useCallback, useEffect, useRef, useState } from "react";

import type { AudioAsset, PersistedEpisode } from "@catty/contracts";

import type { EpisodeMedia } from "@/features/editor/deps/episodes";

import { requestEngine } from "../deps/engine";

export type SeparationEditing = ReturnType<typeof useSeparation>;

export function useSeparation(
  episode: EpisodeMedia | null,
  projectDirectory: string,
  onEpisodePersisted: (episode: PersistedEpisode) => void,
) {
  const [separating, setSeparating] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const revision = useRef(0);

  useEffect(() => {
    revision.current += 1;
    setSeparating(false);
    setStartedAt(null);
    setError(null);
    return () => {
      revision.current += 1;
    };
  }, [episode?.id, projectDirectory]);

  const background: AudioAsset | null =
    episode?.audioAssets?.find((asset) => asset.kind === "background") ?? null;

  const separate = useCallback(async () => {
    if (!episode || separating) return;
    const ticket = revision.current;
    setSeparating(true);
    setStartedAt(Date.now());
    setError(null);
    try {
      const persisted = await requestEngine("project.separate_audio", {
        project_directory: projectDirectory,
        episode_id: episode.id,
      });
      if (ticket === revision.current) onEpisodePersisted(persisted);
    } catch (cause) {
      if (ticket !== revision.current) return;
      setError(
        cause instanceof Error ? cause.message : "មិនអាចបំបែកសំឡេងបានទេ។",
      );
      // The engine persists the failure state before answering; reload it so a
      // later project open shows the same result.
      try {
        const latest = await requestEngine("project.open", {
          project_directory: projectDirectory,
        });
        const saved = latest.episodes.find((item) => item.id === episode.id);
        if (ticket === revision.current && saved) onEpisodePersisted(saved);
      } catch {
        /* Keep the separation error visible. */
      }
    } finally {
      if (ticket === revision.current) setSeparating(false);
    }
  }, [episode, onEpisodePersisted, projectDirectory, separating]);

  return {
    background,
    separating,
    startedAt,
    error,
    separate,
    clearError: () => setError(null),
  };
}
