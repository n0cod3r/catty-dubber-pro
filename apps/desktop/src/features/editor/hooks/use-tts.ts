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
import { isCurrentTtsProgress, ttsTargetIds } from "../utils/tts-progress";
import { DEFAULT_TTS_TUNING, type TtsTuning } from "../utils/voice-presets";

export type { TtsTuning } from "../utils/voice-presets";
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
  const [assigningSpeakerId, setAssigningSpeakerId] = useState<string | null>(
    null,
  );
  const [assigningSegmentId, setAssigningSegmentId] = useState<string | null>(
    null,
  );
  const [progress, setProgress] = useState<TtsProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const operationRef = useRef<string | null>(null);
  const revision = useRef(0);
  const unsubscribe = useRef<(() => void) | null>(null);
  const [pendingSegmentIds, setPendingSegmentIds] = useState<string[]>([]);
  const [failedSegmentId, setFailedSegmentId] = useState<string | null>(null);
  useEffect(() => {
    revision.current += 1;
    operationRef.current = null;
    setGenerating(false);
    setPreviewing(false);
    setAssigningSpeakerId(null);
    setAssigningSegmentId(null);
    setProgress(null);
    setPendingSegmentIds([]);
    setFailedSegmentId(null);
    setError(null);
    return () => {
      revision.current += 1;
      operationRef.current = null;
      unsubscribe.current?.();
      unsubscribe.current = null;
    };
  }, [episode?.id, projectDirectory]);

  useEffect(() => {
    let active = true;
    const refresh = () =>
      void requestEngine("tts.voices", {})
        .then((items) => {
          if (!active) return;
          const khmer = items.filter((voice) =>
            voice.locale.toLowerCase().startsWith("km"),
          );
          const available = khmer.length ? khmer : items;
          setVoices(available);
          setVoiceId((current) =>
            available.some((voice) => voice.id === current)
              ? current
              : (available[0]?.id ?? null),
          );
        })
        .catch((cause: unknown) => {
          if (active)
            setError(
              cause instanceof Error
                ? cause.message
                : "មិនអាចទាញយកសំឡេង Edge TTS បានទេ។",
            );
        });
    refresh();
    window.addEventListener("catty:voices-changed", refresh);
    return () => {
      active = false;
      window.removeEventListener("catty:voices-changed", refresh);
    };
  }, []);

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

  const assignSpeakerVoice = useCallback(
    async (speakerId: string, edgeVoiceId: string) => {
      if (!episode || generating || assigningSpeakerId || assigningSegmentId)
        return false;
      const ticket = revision.current;
      setAssigningSpeakerId(speakerId);
      setError(null);
      try {
        const profile = await requestEngine("tts.ensure_voice", {
          project_directory: projectDirectory,
          voice_id: edgeVoiceId,
          name:
            voices.find((item) => item.id === edgeVoiceId)?.name ?? edgeVoiceId,
        });
        if (ticket !== revision.current) return false;
        const persisted = await requestEngine("tts.generate", {
          project_directory: projectDirectory,
          episode_id: episode.id,
          voice_profile_id: profile.id,
          assign_speaker_id: speakerId,
          assign_only: true,
        });
        if (ticket !== revision.current) return false;
        onEpisodePersisted(persisted);
        return true;
      } catch (cause) {
        if (ticket === revision.current)
          setError(
            cause instanceof Error
              ? cause.message
              : "មិនអាច assign សំឡេងទៅ speaker បានទេ។",
          );
        return false;
      } finally {
        if (ticket === revision.current) setAssigningSpeakerId(null);
      }
    },
    [
      assigningSegmentId,
      assigningSpeakerId,
      episode,
      generating,
      onEpisodePersisted,
      projectDirectory,
      voices,
    ],
  );

  const assignSegmentVoice = useCallback(
    async (segmentId: string, edgeVoiceId: string | null) => {
      if (!episode || generating || assigningSpeakerId || assigningSegmentId)
        return false;
      const ticket = revision.current;
      setAssigningSegmentId(segmentId);
      setError(null);
      try {
        const profile = edgeVoiceId
          ? await requestEngine("tts.ensure_voice", {
              project_directory: projectDirectory,
              voice_id: edgeVoiceId,
              name:
                voices.find((item) => item.id === edgeVoiceId)?.name ??
                edgeVoiceId,
            })
          : null;
        if (ticket !== revision.current) return false;
        const persisted = await requestEngine("tts.assign_segment_voice", {
          project_directory: projectDirectory,
          episode_id: episode.id,
          segment_id: segmentId,
          voice_profile_id: profile?.id ?? null,
        });
        if (ticket !== revision.current) return false;
        onEpisodePersisted(persisted);
        return true;
      } catch (cause) {
        if (ticket === revision.current)
          setError(
            cause instanceof Error
              ? cause.message
              : "មិនអាច assign សំឡេងទៅបន្ទាត់នេះបានទេ។",
          );
        return false;
      } finally {
        if (ticket === revision.current) setAssigningSegmentId(null);
      }
    },
    [
      assigningSegmentId,
      assigningSpeakerId,
      episode,
      generating,
      onEpisodePersisted,
      projectDirectory,
      voices,
    ],
  );

  const generate = useCallback(
    async (
      mode: TtsGenerationMode,
      segmentIds: string[] = [],
      tuning: TtsTuning = DEFAULT_TTS_TUNING,
    ) => {
      if (!episode || !voiceId || operationRef.current) return;
      const targets = ttsTargetIds(episode, mode, segmentIds);
      if (!targets.length) return;
      setError(null);
      setGenerating(true);
      setProgress(null);
      setFailedSegmentId(null);
      setPendingSegmentIds(targets);
      const ticket = revision.current;
      const operationId = crypto.randomUUID();
      operationRef.current = operationId;
      const current = () =>
        revision.current === ticket && operationRef.current === operationId;
      let unlisten: (() => void) | undefined;
      let activeSegmentId: string | null = null;
      try {
        unlisten = await listenTtsProgress((event) => {
          if (
            !current() ||
            !isCurrentTtsProgress(
              event,
              operationId,
              projectDirectory,
              episode.id,
            )
          )
            return;
          setProgress(event);
          if (event.phase === "generating") activeSegmentId = event.segment_id;
          if (event.phase === "saved" && event.segment_id) {
            setPendingSegmentIds((ids) =>
              ids.filter((id) => id !== event.segment_id),
            );
            activeSegmentId = null;
          }
          if (event.phase === "failed") setFailedSegmentId(activeSegmentId);
          if (event.episode) onEpisodePersisted(event.episode);
        });
        if (!current()) return;
        unsubscribe.current = unlisten;
        const cancelFile = await prepareTtsCancel(operationId);
        if (!current()) return;
        const profile = await requestEngine("tts.ensure_voice", {
          project_directory: projectDirectory,
          voice_id: voiceId,
        });
        if (!current()) return;
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
        if (current()) onEpisodePersisted(persisted);
      } catch (cause) {
        if (!current()) return;
        setFailedSegmentId(activeSegmentId);
        setError(
          cause instanceof Error ? cause.message : "មិនអាចបង្កើតសំឡេងបានទេ។",
        );
        try {
          const latest = await requestEngine("project.open", {
            project_directory: projectDirectory,
          });
          const saved = latest.episodes.find((item) => item.id === episode.id);
          if (current() && saved) onEpisodePersisted(saved);
        } catch {
          /* Keep the generation error visible. */
        }
      } finally {
        unlisten?.();
        if (current()) {
          operationRef.current = null;
          unsubscribe.current = null;
          setGenerating(false);
          setPendingSegmentIds([]);
        }
      }
    },
    [episode, onEpisodePersisted, projectDirectory, voiceId],
  );

  const cancel = useCallback(async () => {
    const operationId = operationRef.current;
    if (!operationId || !generating) return;
    try {
      await cancelTts(operationId);
    } catch (cause) {
      if (operationRef.current === operationId)
        setError(
          cause instanceof Error ? cause.message : "មិនអាច cancel បានទេ។",
        );
    }
  }, [generating]);

  const preview = useCallback(
    async (
      segmentId: string,
      tuning: TtsTuning = DEFAULT_TTS_TUNING,
      voiceOverride?: string | null,
    ) => {
      const voice = voiceOverride ?? voiceId;
      if (!episode || !voice || previewing) return null;
      const segment = episode.dialogueSegments?.find(
        (item) => item.id === segmentId,
      );
      const text = segment?.translation?.text?.trim();
      if (!text) {
        setError("Segment នេះមិនទាន់មាន Khmer translation ទេ។");
        return null;
      }
      const ticket = revision.current;
      setPreviewing(true);
      setError(null);
      try {
        const result = await requestEngine("tts.preview", {
          project_directory: projectDirectory,
          text,
          voice_id: voice,
          speed: tuning.speed,
          pitch: tuning.pitch,
          volume: tuning.volume,
        });
        return ticket === revision.current ? result.path : null;
      } catch (cause) {
        if (ticket !== revision.current) return null;
        setError(
          cause instanceof Error ? cause.message : "មិនអាច preview សំឡេងបានទេ។",
        );
        return null;
      } finally {
        if (ticket === revision.current) setPreviewing(false);
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
    assigningSpeakerId,
    assigningSegmentId,
    progress,
    pendingSegmentIds,
    failedSegmentId,
    error,
    clearError: () => setError(null),
    dubByDialogue,
    assignSpeakerVoice,
    assignSegmentVoice,
    generate,
    preview,
    cancel,
  };
}
