import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  EdgeVoice,
  PersistedEpisode,
  TtsGenerationMode,
  TtsProgress,
} from "@catty/contracts";

import type { EpisodeMedia } from "@/features/editor/deps/episodes";

import {
  cancelTts,
  listenTtsProgress,
  prepareTtsCancel,
  requestEngine,
} from "../deps/engine";

export type TtsTuning = { speed: number; pitch: number; volume: number };
export type TtsEditing = ReturnType<typeof useTts>;

export function useTts(
  episode: EpisodeMedia | null,
  projectDirectory: string,
  onEpisodePersisted: (episode: PersistedEpisode) => void,
) {
  const [voices, setVoices] = useState<EdgeVoice[]>([]);
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [progress, setProgress] = useState<TtsProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const operationRef = useRef<string | null>(null);

  useEffect(() => {
    let active = true;
    void requestEngine("tts.voices", {})
      .then((items) => {
        if (!active) return;
        const khmer = items.filter((voice) =>
          voice.locale.toLowerCase().startsWith("km"),
        );
        const available = khmer.length ? khmer : items;
        setVoices(available);
        setVoiceId((current) => current ?? available[0]?.id ?? null);
      })
      .catch((cause: unknown) => {
        if (active)
          setError(
            cause instanceof Error
              ? cause.message
              : "មិនអាចទាញយកសំឡេង Edge TTS បានទេ។",
          );
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let unlisten: (() => void) | undefined;
    void listenTtsProgress((event) => {
      if (
        event.episode_id !== episode?.id ||
        event.operation_id !== operationRef.current
      )
        return;
      setProgress(event);
      if (event.episode) onEpisodePersisted(event.episode);
      if (["completed", "cancelled", "failed"].includes(event.phase))
        setGenerating(false);
    }).then((stop) => {
      if (active) unlisten = stop;
      else stop();
    });
    return () => {
      active = false;
      unlisten?.();
    };
  }, [episode?.id, onEpisodePersisted]);

  const dubByDialogue = useMemo(
    () =>
      new Map(
        (episode?.dubSegments ?? []).map((dub) => [
          dub.dialogue_segment_id,
          dub,
        ]),
      ),
    [episode?.dubSegments],
  );

  const generate = useCallback(
    async (
      mode: TtsGenerationMode,
      segmentIds: string[] = [],
      tuning: TtsTuning = { speed: 1, pitch: 0, volume: 0 },
    ) => {
      if (!episode || !voiceId || generating) return;
      setError(null);
      setGenerating(true);
      setProgress(null);
      const operationId = crypto.randomUUID();
      operationRef.current = operationId;
      try {
        const cancelFile = await prepareTtsCancel(operationId);
        const profile = await requestEngine("tts.ensure_voice", {
          project_directory: projectDirectory,
          voice_id: voiceId,
        });
        const persisted = await requestEngine("tts.generate", {
          operation_id: operationId,
          project_directory: projectDirectory,
          episode_id: episode.id,
          voice_profile_id: profile.id,
          mode,
          segment_ids: segmentIds,
          speed: tuning.speed,
          pitch: tuning.pitch,
          volume: tuning.volume,
          cancel_file: cancelFile,
        });
        onEpisodePersisted(persisted);
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : "មិនអាចបង្កើតសំឡេងបានទេ។",
        );
      } finally {
        setGenerating(false);
      }
    },
    [episode, generating, onEpisodePersisted, projectDirectory, voiceId],
  );

  const cancel = useCallback(async () => {
    const operationId = operationRef.current;
    if (!operationId || !generating) return;
    try {
      await cancelTts(operationId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "មិនអាច cancel បានទេ។");
    }
  }, [generating]);

  const preview = useCallback(
    async (
      segmentId: string,
      tuning: TtsTuning = { speed: 1, pitch: 0, volume: 0 },
    ) => {
      if (!episode || !voiceId || previewing) return null;
      const segment = episode.dialogueSegments?.find(
        (item) => item.id === segmentId,
      );
      const text = segment?.translation?.text?.trim();
      if (!text) {
        setError("Segment នេះមិនទាន់មាន Khmer translation ទេ។");
        return null;
      }
      setPreviewing(true);
      setError(null);
      try {
        const result = await requestEngine("tts.preview", {
          project_directory: projectDirectory,
          text,
          voice_id: voiceId,
          speed: tuning.speed,
          pitch: tuning.pitch,
          volume: tuning.volume,
        });
        return result.path;
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : "មិនអាច preview សំឡេងបានទេ។",
        );
        return null;
      } finally {
        setPreviewing(false);
      }
    },
    [episode, previewing, projectDirectory, voiceId],
  );

  return {
    voices,
    voiceId,
    setVoiceId,
    generating,
    previewing,
    progress,
    error,
    clearError: () => setError(null),
    dubByDialogue,
    generate,
    preview,
    cancel,
  };
}
