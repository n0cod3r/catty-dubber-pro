import { useCallback, useEffect, useRef, useState } from "react";

import type { PersistedEpisode, TranslationMode, TranslationProgress } from "@catty/contracts";

import { requestEngine, listenTranslationProgress } from "@/features/editor/deps/engine";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";

import { isCurrentTranslationProgress } from "../utils/translation-progress";

export function useTranslation(
  episode: EpisodeMedia | null,
  projectDirectory: string,
  onEpisodePersisted: (episode: PersistedEpisode) => void,
) {
  const [translating, setTranslating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const revision = useRef(0);
  const locked = useRef(false);
  const unsubscribe = useRef<(() => void) | null>(null);
  const [progress, setProgress] = useState<TranslationProgress | null>(null);

  useEffect(() => {
    revision.current += 1;
    setTranslating(false);
    setEditing(false);
    setError(null);
    setProgress(null);
    locked.current = false;
    return () => {
      revision.current += 1;
      unsubscribe.current?.();
      unsubscribe.current = null;
    };
  }, [episode?.id, projectDirectory]);

  const translate = useCallback(async (mode: TranslationMode = "missing", segmentIds: string[] = []) => {
    if (!episode?.dialogueSegments?.length || locked.current) return;
    if (mode === "selected" && segmentIds.length === 0) return;
    const ticket = ++revision.current;
    const operationId = crypto.randomUUID();
    locked.current = true;
    setProgress(null);
    setTranslating(true);
    setError(null);
    let unlisten: (() => void) | undefined;
    try {
      unlisten = await listenTranslationProgress((update) => {
        if (ticket !== revision.current || !isCurrentTranslationProgress(update, operationId, projectDirectory, episode.id)) return;
        setProgress(update);
        if (update.episode) onEpisodePersisted(update.episode);
      });
      if (ticket !== revision.current) return;
      unsubscribe.current = unlisten;
      const persisted = await requestEngine("translation.translate_episode", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        mode,
        operation_id: operationId,
        segment_ids: segmentIds,
        overwrite_manual: false,
        batch_size: 12,
      });
      if (ticket !== revision.current) return;
      onEpisodePersisted(persisted);
      return true;
    } catch (cause) {
      if (ticket === revision.current) {
        setError(cause instanceof Error ? cause.message : "មិនអាចបកប្រែទៅខ្មែរបានទេ។");
        // A failed cloud batch may follow successful durable batches. Restore
        // those even if the final progress event raced the error response.
        try {
          const latest = await requestEngine("project.open", { project_directory: projectDirectory });
          if (ticket === revision.current) {
            const saved = latest.episodes.find((item) => item.id === episode.id);
            if (saved) onEpisodePersisted(saved);
          }
        } catch { /* Keep the original translation error visible. */ }
      }
    } finally {
      unlisten?.();
      if (ticket === revision.current) {
        revision.current += 1; // Ignore progress callbacks queued after the final RPC reply.
        unsubscribe.current = null;
        locked.current = false;
        setTranslating(false);
      }
    }
  }, [episode, onEpisodePersisted, projectDirectory]);

  const updateText = useCallback(async (segmentId: string, text: string, expectedText: string | null) => {
    if (!episode || locked.current) return;
    if (text.trim() === (expectedText ?? "")) return true;
    const ticket = ++revision.current;
    locked.current = true;
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
      if (ticket === revision.current) { locked.current = false; setEditing(false); }
    }
  }, [episode, onEpisodePersisted, projectDirectory]);

  return { busy: translating || editing, translating, editing, error, progress, translate, updateText };
}

export type TranslationEditing = ReturnType<typeof useTranslation>;
