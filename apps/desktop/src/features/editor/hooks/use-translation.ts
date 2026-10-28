import { useCallback, useEffect, useRef, useState } from "react";

import type { PersistedEpisode, TranslationMode } from "@catty/contracts";

import { requestEngine } from "@/features/editor/deps/engine";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";

export function useTranslation(
  episode: EpisodeMedia | null,
  projectDirectory: string,
  onEpisodePersisted: (episode: PersistedEpisode) => void,
) {
  const [translating, setTranslating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const revision = useRef(0);

  useEffect(() => {
    revision.current += 1;
    setTranslating(false);
    setEditing(false);
    setError(null);
  }, [episode?.id, projectDirectory]);

  const translate = useCallback(async (mode: TranslationMode = "missing", segmentIds: string[] = []) => {
    if (!episode?.dialogueSegments?.length || translating || editing) return;
    if (mode === "selected" && segmentIds.length === 0) return;
    const ticket = ++revision.current;
    setTranslating(true);
    setError(null);
    try {
      const persisted = await requestEngine("translation.translate_episode", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        mode,
        segment_ids: segmentIds,
        overwrite_manual: false,
        batch_size: 12,
      });
      if (ticket !== revision.current) return;
      onEpisodePersisted(persisted);
      return true;
    } catch (cause) {
      if (ticket === revision.current)
        setError(cause instanceof Error ? cause.message : "មិនអាចបកប្រែទៅខ្មែរបានទេ។");
    } finally {
      if (ticket === revision.current) setTranslating(false);
    }
  }, [editing, episode, onEpisodePersisted, projectDirectory, translating]);

  const updateText = useCallback(async (segmentId: string, text: string, expectedText: string | null) => {
    if (!episode || translating || editing) return;
    if (text.trim() === (expectedText ?? "")) return true;
    const ticket = ++revision.current;
    setEditing(true);
    setError(null);
    try {
      const persisted = await requestEngine("project.dialogue_update_translation", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        segment_id: segmentId,
        text,
        expected_text: expectedText,
      });
      if (ticket !== revision.current) return;
      onEpisodePersisted(persisted);
      return true;
    } catch (cause) {
      if (ticket === revision.current)
        setError(cause instanceof Error ? cause.message : "មិនអាចរក្សាទុកការកែប្រែបានទេ។");
    } finally {
      if (ticket === revision.current) setEditing(false);
    }
  }, [editing, episode, onEpisodePersisted, projectDirectory, translating]);

  return { busy: translating || editing, translating, editing, error, translate, updateText };
}

export type TranslationEditing = ReturnType<typeof useTranslation>;
