import { useCallback, useEffect, useRef, useState } from "react";

import type { PersistedEpisode } from "@catty/contracts";

import { requestEngine } from "@/features/editor/deps/engine";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";

export function useDialogueEditing(
  episode: EpisodeMedia | null,
  projectDirectory: string,
  onEpisodePersisted: (episode: PersistedEpisode) => void,
) {
  const [transcribing, setTranscribing] = useState(false);
  const [editing, setEditing] = useState(false);
  const operation = useRef(false);
  const alive = useRef(false);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const busy = transcribing || editing;
  const undoStack = useRef<Array<{ before: PersistedEpisode; after: PersistedEpisode }>>([]);
  const redoStack = useRef<Array<{ before: PersistedEpisode; after: PersistedEpisode }>>([]);
  const [historyCounts, setHistoryCounts] = useState({ undo: 0, redo: 0 });
  const loadPersistedEpisode = useCallback(async () => {
    const project = await requestEngine("project.open", { project_directory: projectDirectory });
    const persisted = project.episodes.find((item) => item.id === episode?.id);
    if (!persisted) throw new Error("Episode was not found.");
    return persisted;
  }, [episode?.id, projectDirectory]);
  const [error, setError] = useState<string | null>(null);
  const applyPersistedEpisode = useCallback(
    (persisted: PersistedEpisode) => {
      if (!alive.current) return;
      onEpisodePersisted(persisted);
    },
    [onEpisodePersisted],
  );

  const transcribe = async (engine: "paraformer" | "sense-small") => {
    if (!episode?.durationSeconds || operation.current) return;
    operation.current = true;
    setTranscribing(true);
    setError(null);
    try {
      await requestEngine("speech.transcribe", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        source: episode.path,
        source_start: 0,
        duration: episode.durationSeconds,
        language: "zh",
        asr_backend: engine,
        asr_config: {},
        vad_backend: "silero",
        vad_config: {},
      });
      const project = await requestEngine("project.open", { project_directory: projectDirectory });
      const persisted = project.episodes.find((item) => item.id === episode.id);
      if (!persisted) throw new Error("Episode was not found after transcription.");
      undoStack.current = [];
      redoStack.current = [];
      setHistoryCounts({ undo: undoStack.current.length, redo: redoStack.current.length });
      applyPersistedEpisode(persisted);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "មិនអាច Transcribe បានទេ។");
    } finally {
      operation.current = false;
      if (alive.current) setTranscribing(false);
    }
  };

  const split = async (segmentId: string, splitAt: number) => {
    if (!episode || operation.current) return;
    operation.current = true;
    setEditing(true);
    setError(null);
    try {
      const before = await loadPersistedEpisode();
      const persisted = await requestEngine("project.dialogue_split", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        segment_id: segmentId,
        split_at: splitAt,
      });
      undoStack.current = [...undoStack.current.slice(-49), { before, after: persisted }];
      redoStack.current = [];
      setHistoryCounts({ undo: undoStack.current.length, redo: redoStack.current.length });
      applyPersistedEpisode(persisted);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "មិនអាច Split segment បានទេ។");
    } finally {
      operation.current = false;
      if (alive.current) setEditing(false);
    }
  };

  const merge = useCallback(
    async (segmentId: string) => {
      if (!episode || operation.current) return;
      operation.current = true;
      setEditing(true);
      setError(null);
      try {
        const before = await loadPersistedEpisode();
        const persisted = await requestEngine("project.dialogue_merge_next", {
          project_directory: projectDirectory,
          episode_id: episode.id,
          segment_id: segmentId,
        });
        undoStack.current = [...undoStack.current.slice(-49), { before, after: persisted }];
        redoStack.current = [];
        setHistoryCounts({ undo: undoStack.current.length, redo: redoStack.current.length });
        applyPersistedEpisode(persisted);
        return true;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "មិនអាច Merge segment បានទេ។");
      } finally {
        operation.current = false;
        if (alive.current) setEditing(false);
      }
    },
    [episode, projectDirectory, applyPersistedEpisode, loadPersistedEpisode],
  );

  const restore = async (redo: boolean) => {
    const stack = redo ? redoStack.current : undoStack.current;
    const entry = stack.at(-1);
    if (!entry || !episode || operation.current) return;
    operation.current = true;
    setEditing(true);
    setError(null);
    try {
      const target = redo ? entry.after : entry.before;
      const expected = redo ? entry.before : entry.after;
      const persisted = await requestEngine("project.dialogue_restore", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        expected_segments: expected.dialogue_segments,
        dialogue_segments: target.dialogue_segments,
        speakers: target.speakers,
        dub_segments: target.dub_segments,
      });
      stack.pop();
      (redo ? undoStack.current : redoStack.current).push(entry);
      setHistoryCounts({ undo: undoStack.current.length, redo: redoStack.current.length });
      applyPersistedEpisode(persisted);
      return true;
    } catch (cause) {
      if (cause instanceof Error && cause.message.includes("Dialogue changed since this edit")) {
        // A genuine external edit invalidates these snapshots. Refresh directly
        // instead of leaving the editor stuck until the project is reopened.
        try {
          const latest = await loadPersistedEpisode();
          undoStack.current = [];
          redoStack.current = [];
          setHistoryCounts({ undo: 0, redo: 0 });
          applyPersistedEpisode(latest);
          setError(
            "Dialogue was updated elsewhere. Loaded the latest saved dialogue and reset undo history.",
          );
        } catch {
          setError("Could not refresh saved dialogue. Please reopen the project.");
        }
      } else setError(cause instanceof Error ? cause.message : "Could not restore dialogue.");
    } finally {
      operation.current = false;
      if (alive.current) setEditing(false);
    }
  };

  return { busy, transcribing, error, historyCounts, split, merge, transcribe, restore };
}
export type DialogueEditing = ReturnType<typeof useDialogueEditing>;
