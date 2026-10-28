import { useCallback, useEffect, useMemo, useState } from "react";

import type { VoiceProfile } from "@catty/contracts";

import type { EpisodeMedia } from "@/features/editor/deps/episodes";

import { requestEngine } from "../deps/engine";
import type { TtsEditing } from "./use-tts";

export type VoiceAssignments = ReturnType<typeof useVoiceAssignments>;

function profileOptionId(profile: VoiceProfile) {
  return profile.library_voice_id
    ? `library:${profile.library_voice_id}`
    : profile.engine_voice_id;
}

export function useVoiceAssignments(
  episode: EpisodeMedia | null,
  projectDirectory: string,
  tts: TtsEditing,
) {
  const [voiceBySpeaker, setVoiceBySpeaker] = useState<Record<string, string>>(
    {},
  );
  const [voiceBySegment, setVoiceBySegment] = useState<Record<string, string>>(
    {},
  );
  const episodeId = episode?.id;
  const assignmentKey = useMemo(
    () =>
      [
        ...(episode?.speakers ?? []).map(
          (speaker) => `s:${speaker.id}:${speaker.voice_profile_id ?? ""}`,
        ),
        ...(episode?.dialogueSegments ?? []).map(
          (segment) => `l:${segment.id}:${segment.voiceProfileId ?? ""}`,
        ),
      ].join("|"),
    [episode?.speakers, episode?.dialogueSegments],
  );

  useEffect(() => {
    let active = true;
    if (!episodeId) {
      setVoiceBySpeaker({});
      setVoiceBySegment({});
      return;
    }
    void requestEngine("project.open", {
      project_directory: projectDirectory,
    })
      .then((project) => {
        if (!active) return;
        const persisted = project.episodes.find(
          (item) => item.id === episodeId,
        );
        const profileToVoice = new Map<string, string>();
        for (const profile of project.voice_profiles) {
          const optionId = profileOptionId(profile);
          if (optionId) profileToVoice.set(profile.id, optionId);
        }
        const speakers: Record<string, string> = {};
        for (const speaker of persisted?.speakers ?? []) {
          if (!speaker.voice_profile_id) continue;
          const engineVoiceId = profileToVoice.get(speaker.voice_profile_id);
          if (engineVoiceId) speakers[speaker.id] = engineVoiceId;
        }
        const segments: Record<string, string> = {};
        for (const segment of persisted?.dialogue_segments ?? []) {
          if (!segment.voice_profile_id) continue;
          const engineVoiceId = profileToVoice.get(segment.voice_profile_id);
          if (engineVoiceId) segments[segment.id] = engineVoiceId;
        }
        setVoiceBySpeaker(speakers);
        setVoiceBySegment(segments);
      })
      .catch(() => {
        if (active) {
          setVoiceBySpeaker({});
          setVoiceBySegment({});
        }
      });
    return () => {
      active = false;
    };
  }, [episodeId, projectDirectory, assignmentKey]);

  const { assignSpeakerVoice, assignSegmentVoice } = tts;
  const assignSpeaker = useCallback(
    async (speakerId: string, edgeVoiceId: string) => {
      const saved = await assignSpeakerVoice(speakerId, edgeVoiceId);
      if (saved)
        setVoiceBySpeaker((current) => ({
          ...current,
          [speakerId]: edgeVoiceId,
        }));
      return saved;
    },
    [assignSpeakerVoice],
  );
  const assignSegment = useCallback(
    async (segmentId: string, edgeVoiceId: string | null) => {
      const saved = await assignSegmentVoice(segmentId, edgeVoiceId);
      if (saved)
        setVoiceBySegment((current) => {
          const next = { ...current };
          if (edgeVoiceId) next[segmentId] = edgeVoiceId;
          else delete next[segmentId];
          return next;
        });
      return saved;
    },
    [assignSegmentVoice],
  );

  return { voiceBySpeaker, voiceBySegment, assignSpeaker, assignSegment };
}
