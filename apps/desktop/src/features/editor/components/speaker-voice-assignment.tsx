import { useEffect, useState } from "react";

import { LoaderCircle, Users } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";

import { requestEngine } from "../deps/engine";
import type { TtsEditing } from "../hooks/use-tts";

type SpeakerWithVoice = NonNullable<EpisodeMedia["speakers"]>[number] & {
  voice_profile_id?: string | null;
};

export function SpeakerVoiceAssignment({
  episode,
  projectDirectory,
  tts,
}: {
  episode: EpisodeMedia;
  projectDirectory: string;
  tts: TtsEditing;
}) {
  const [assigned, setAssigned] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    void requestEngine("project.open", { project_directory: projectDirectory })
      .then((project) => {
        if (!active) return;
        const persistedEpisode = project.episodes.find(
          (item) => item.id === episode.id,
        );
        const profileToEngineVoice = new Map(
          project.voice_profiles
            .filter(
              (profile) => profile.engine === "edge" && profile.engine_voice_id,
            )
            .map((profile) => [profile.id, profile.engine_voice_id as string]),
        );
        const next: Record<string, string> = {};
        for (const speaker of (persistedEpisode?.speakers ??
          []) as SpeakerWithVoice[]) {
          if (!speaker.voice_profile_id) continue;
          const engineVoiceId = profileToEngineVoice.get(
            speaker.voice_profile_id,
          );
          if (engineVoiceId) next[speaker.id] = engineVoiceId;
        }
        setAssigned(next);
      })
      .catch(() => {
        if (active) setAssigned({});
      });
    return () => {
      active = false;
    };
  }, [episode.id, episode.speakers, projectDirectory]);

  if (!episode.speakers?.length) return null;

  return (
    <div className="border-b px-2 py-2">
      <div className="mb-1.5 flex items-center gap-1.5 text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
        <Users className="size-3" /> Voice assignment
      </div>
      <div className="space-y-1">
        {episode.speakers.map((speaker) => {
          const segmentCount = speaker.segment_ids.length;
          const currentVoice = assigned[speaker.id] ?? "";
          const assigning = tts.assigningSpeakerId === speaker.id;
          return (
            <div key={speaker.id} className="flex items-center gap-1.5">
              <span
                className="min-w-0 flex-1 truncate text-[10px]"
                title={speaker.name}
              >
                {speaker.name}
              </span>
              <span className="shrink-0 text-[8px] tabular-nums text-muted-foreground">
                {segmentCount} clips
              </span>
              {assigning && (
                <LoaderCircle className="size-3 animate-spin text-primary motion-reduce:animate-none" />
              )}
              <Select
                value={currentVoice}
                disabled={tts.generating || !!tts.assigningSpeakerId}
                onValueChange={(voiceId) => {
                  void tts
                    .assignSpeakerVoice(speaker.id, voiceId)
                    .then((saved) => {
                      if (saved)
                        setAssigned((current) => ({
                          ...current,
                          [speaker.id]: voiceId,
                        }));
                    });
                }}
              >
                <SelectTrigger
                  size="sm"
                  className="h-6 w-36 text-[9px]"
                  aria-label={`Voice for ${speaker.name}`}
                >
                  <SelectValue placeholder="Assign voice" />
                </SelectTrigger>
                <SelectContent align="end" className="min-w-56">
                  <SelectGroup>
                    {tts.voices.map((voice) => (
                      <SelectItem
                        key={voice.id}
                        value={voice.id}
                        className="text-[10px]"
                      >
                        {voice.name} · {voice.gender}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          );
        })}
      </div>
      <p className="mt-1.5 text-[8px] leading-snug text-muted-foreground">
        Changing a speaker voice keeps existing audio and marks affected clips
        outdated until regenerated.
      </p>
    </div>
  );
}
