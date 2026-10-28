import { useCallback, useEffect, useMemo, useState } from "react";

import type { EpisodeMedia } from "@/features/editor/deps/episodes";

import { requestEngine } from "../deps/engine";
import type { TtsEditing } from "./use-tts";

type SpeakerWithVoice = NonNullable<EpisodeMedia["speakers"]>[number] & {
  voice_profile_id?: string | null;
};

export function useSpeakerVoices(
  episode: EpisodeMedia | null,
  projectDirectory: string,
  tts: TtsEditing,
) {
  const [voiceBySpeaker, setVoiceBySpeaker] = useState<Record<string, string>>(
    {},
  );
  const episodeId = episode?.id;
  const speakerKey = useMemo(
    () =>
      ((episode?.speakers ?? []) as SpeakerWithVoice[])
        .map((speaker) => `${speaker.id}:${speaker.voice_profile_id ?? ""}`)
        .join("|"),
    [episode?.speakers],
  );

  useEffect(() => {
    let active = true;
    if (!episodeId) {
      setVoiceBySpeaker({});
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
        const profileToVoice = new Map(
          project.voice_profiles
            .filter(
              (profile) => profile.engine === "edge" && profile.engine_voice_id,
            )
            .map((profile) => [profile.id, profile.engine_voice_id as string]),
        );
        const next: Record<string, string> = {};
        for (const speaker of (persisted?.speakers ??
          []) as SpeakerWithVoice[]) {
          if (!speaker.voice_profile_id) continue;
          const engineVoiceId = profileToVoice.get(speaker.voice_profile_id);
          if (engineVoiceId) next[speaker.id] = engineVoiceId;
        }
        setVoiceBySpeaker(next);
      })
      .catch(() => {
        if (active) setVoiceBySpeaker({});
      });
    return () => {
      active = false;
    };
  }, [episodeId, projectDirectory, speakerKey]);

  const { assignSpeakerVoice } = tts;
  const assign = useCallback(
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

  return { voiceBySpeaker, assign };
}
