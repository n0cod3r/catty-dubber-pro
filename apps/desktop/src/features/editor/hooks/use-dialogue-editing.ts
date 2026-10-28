import { useCallback, useEffect, useRef, useState } from "react";

import type { PersistedEpisode, TranscriptionProgress } from "@catty/contracts";

import { requestEngine, listenTranscriptionProgress } from "@/features/editor/deps/engine";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";

import { createDialogueSessionGuard } from "../utils/dialogue-session";

export function useDialogueEditing(
  episode: EpisodeMedia | null,
  projectDirectory: string,
  onEpisodePersisted: (episode: PersistedEpisode) => void,
) {
  const [transcribing, setTranscribing] = useState(false);
  const [progress, setProgress] = useState<TranscriptionProgress | null>(null);
  const [transcriptionStartedAt, setTranscriptionStartedAt] = useState<number | null>(null);
  const unsubscribeTranscription = useRef<(() => void) | null>(null);
  const [editing, setEditing] = useState(false);
  const sessionGuard = useRef(createDialogueSessionGuard());
  const sessionScope = JSON.stringify([projectDirectory, episode?.id ?? null]);
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
  const [speakerWarning, setSpeakerWarning] = useState<string | null>(null);
  useEffect(() => {
    const guard = sessionGuard.current;
    guard.reset(JSON.stringify([projectDirectory, episode?.id ?? null]));
    undoStack.current = [];
    redoStack.current = [];
    setHistoryCounts({ undo: 0, redo: 0 });
    setError(null);
    setSpeakerWarning(null);
    setTranscribing(false);
    setProgress(null);
    setTranscriptionStartedAt(null);
    setEditing(false);
    return () => {
      guard.reset(null);
      unsubscribeTranscription.current?.();
      unsubscribeTranscription.current = null;
    };
  }, [episode?.id, projectDirectory]);

  const transcribe = async (engine: "paraformer" | "sense-small") => {
    if (!episode?.durationSeconds) return;
    const ticket = sessionGuard.current.begin(sessionScope);
    if (!ticket) return;
    const operationId = crypto.randomUUID();
    setProgress(null);
    setTranscriptionStartedAt(Date.now());
    setTranscribing(true);
    setError(null);
    setSpeakerWarning(null);
    let unlisten: (() => void) | undefined;
    try {
      unlisten = await listenTranscriptionProgress((update) => {
        if (!sessionGuard.current.isCurrent(ticket) || update.operation_id !== operationId || update.project_directory !== projectDirectory || update.episode_id !== episode.id || (update.episode && update.episode.id !== episode.id)) return;
        setProgress(update);
        if (update.phase === "completed" && update.episode) onEpisodePersisted(update.episode);
      });
      if (!sessionGuard.current.isCurrent(ticket)) return;
      unsubscribeTranscription.current = unlisten;
      const transcription = await requestEngine("speech.transcribe", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        source: episode.path,
        source_start: 0,
        duration: episode.durationSeconds,
        language: "zh",
        asr_backend: engine,
        operation_id: operationId,
        asr_config: {},
        vad_backend: "silero",
        vad_config: {},
      });
      if (!sessionGuard.current.isCurrent(ticket)) return;
      const project = await requestEngine("project.open", { project_directory: projectDirectory });
      if (!sessionGuard.current.isCurrent(ticket)) return;
      const persisted = project.episodes.find((item) => item.id === episode.id);
      if (!persisted) throw new Error("Episode was not found after transcription.");
      undoStack.current = [];
      redoStack.current = [];
      setHistoryCounts({ undo: undoStack.current.length, redo: redoStack.current.length });
      setSpeakerWarning(transcription.speaker_error ?? null);
      onEpisodePersisted(persisted);
      return true;
    } catch (cause) {
      if (!sessionGuard.current.isCurrent(ticket)) return;
      setError(cause instanceof Error ? cause.message : "មិនអាច Transcribe បានទេ។");
    } finally {
      unlisten?.();
      if (sessionGuard.current.finish(ticket)) { unsubscribeTranscription.current = null; setTranscribing(false); }
    }
  };

  const split = async (segmentId: string, splitAt: number) => {
    if (!episode) return;
    const ticket = sessionGuard.current.begin(sessionScope);
    if (!ticket) return;
    setEditing(true);
    setError(null);
    try {
      const before = await loadPersistedEpisode();
      if (!sessionGuard.current.isCurrent(ticket)) return;
      const persisted = await requestEngine("project.dialogue_split", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        segment_id: segmentId,
        split_at: splitAt,
      });
      if (!sessionGuard.current.isCurrent(ticket)) return;
      undoStack.current = [...undoStack.current.slice(-49), { before, after: persisted }];
      redoStack.current = [];
      setHistoryCounts({ undo: undoStack.current.length, redo: redoStack.current.length });
      onEpisodePersisted(persisted);
      return true;
    } catch (cause) {
      if (!sessionGuard.current.isCurrent(ticket)) return;
      setError(cause instanceof Error ? cause.message : "មិនអាច Split segment បានទេ។");
    } finally {
      if (sessionGuard.current.finish(ticket)) setEditing(false);
    }
  };

  const updateText = async (segmentId: string, text: string, expectedText: string) => {
    if (!episode) return;
    if (text.trim() === expectedText) return true;
    const ticket = sessionGuard.current.begin(sessionScope);
    if (!ticket) return;
    setEditing(true);
    setError(null);
    try {
      const before = await loadPersistedEpisode();
      if (!sessionGuard.current.isCurrent(ticket)) return;
      const persisted = await requestEngine("project.dialogue_update_text", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        segment_id: segmentId,
        text,
        expected_text: expectedText,
      });
      if (!sessionGuard.current.isCurrent(ticket)) return;
      undoStack.current = [...undoStack.current.slice(-49), { before, after: persisted }];
      redoStack.current = [];
      setHistoryCounts({ undo: undoStack.current.length, redo: 0 });
      onEpisodePersisted(persisted);
      return true;
    } catch (cause) {
      if (sessionGuard.current.isCurrent(ticket))
        setError(cause instanceof Error ? cause.message : "Could not save dialogue text.");
    } finally {
      if (sessionGuard.current.finish(ticket)) setEditing(false);
    }
  };

  const assignSpeaker = async (
    segmentId: string,
    speakerId: string | null,
    expectedSpeakerId: string | null,
    createNew = false,
  ) => {
    if (!episode) return;
    const ticket = sessionGuard.current.begin(sessionScope);
    if (!ticket) return;
    setEditing(true);
    setError(null);
    try {
      const before = await loadPersistedEpisode();
      if (!sessionGuard.current.isCurrent(ticket)) return;
      const persisted = await requestEngine("project.dialogue_assign_speaker", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        segment_id: segmentId,
        speaker_id: speakerId,
        expected_speaker_id: expectedSpeakerId,
        create_new: createNew,
      });
      if (!sessionGuard.current.isCurrent(ticket)) return;
      undoStack.current = [...undoStack.current.slice(-49), { before, after: persisted }];
      redoStack.current = [];
      setHistoryCounts({ undo: undoStack.current.length, redo: 0 });
      onEpisodePersisted(persisted);
      return true;
    } catch (cause) {
      if (sessionGuard.current.isCurrent(ticket))
        setError(cause instanceof Error ? cause.message : "Could not correct speaker.");
    } finally {
      if (sessionGuard.current.finish(ticket)) setEditing(false);
    }
  };

  const merge = useCallback(
    async (segmentId: string) => {
      if (!episode) return;
      const ticket = sessionGuard.current.begin(sessionScope);
      if (!ticket) return;
      setEditing(true);
      setError(null);
      try {
        const before = await loadPersistedEpisode();
        if (!sessionGuard.current.isCurrent(ticket)) return;
        const persisted = await requestEngine("project.dialogue_merge_next", {
          project_directory: projectDirectory,
          episode_id: episode.id,
          segment_id: segmentId,
        });
        if (!sessionGuard.current.isCurrent(ticket)) return;
        undoStack.current = [...undoStack.current.slice(-49), { before, after: persisted }];
        redoStack.current = [];
        setHistoryCounts({ undo: undoStack.current.length, redo: redoStack.current.length });
        onEpisodePersisted(persisted);
        return true;
      } catch (cause) {
        if (!sessionGuard.current.isCurrent(ticket)) return;
        setError(cause instanceof Error ? cause.message : "មិនអាច Merge segment បានទេ។");
      } finally {
        if (sessionGuard.current.finish(ticket)) setEditing(false);
      }
    },
    [episode, projectDirectory, sessionScope, onEpisodePersisted, loadPersistedEpisode],
  );

  const restore = async (redo: boolean) => {
    const stack = redo ? redoStack.current : undoStack.current;
    const entry = stack.at(-1);
    if (!entry || !episode) return;
    const ticket = sessionGuard.current.begin(sessionScope);
    if (!ticket) return;
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
      if (!sessionGuard.current.isCurrent(ticket)) return;
      stack.pop();
      (redo ? undoStack.current : redoStack.current).push(entry);
      setHistoryCounts({ undo: undoStack.current.length, redo: redoStack.current.length });
      onEpisodePersisted(persisted);
      return true;
    } catch (cause) {
      if (!sessionGuard.current.isCurrent(ticket)) return;
      if (cause instanceof Error && cause.message.includes("Dialogue changed since this edit")) {
        // A genuine external edit invalidates these snapshots. Refresh directly
        // instead of leaving the editor stuck until the project is reopened.
        try {
          const latest = await loadPersistedEpisode();
          if (!sessionGuard.current.isCurrent(ticket)) return;
          undoStack.current = [];
          redoStack.current = [];
          setHistoryCounts({ undo: 0, redo: 0 });
          onEpisodePersisted(latest);
          setError(
            "Dialogue was updated elsewhere. Loaded the latest saved dialogue and reset undo history.",
          );
        } catch {
          if (!sessionGuard.current.isCurrent(ticket)) return;
          setError("Could not refresh saved dialogue. Please reopen the project.");
        }
      } else setError(cause instanceof Error ? cause.message : "Could not restore dialogue.");
    } finally {
      if (sessionGuard.current.finish(ticket)) setEditing(false);
    }
  };

  return {
    busy,
    transcribing,
    progress,
    transcriptionStartedAt,
    error,
    speakerWarning,
    historyCounts,
    split,
    merge,
    updateText,
    assignSpeaker,
    transcribe,
    restore,
  };
}
export type DialogueEditing = ReturnType<typeof useDialogueEditing>;
