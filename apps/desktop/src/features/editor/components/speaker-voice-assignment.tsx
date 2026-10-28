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

import type { TtsEditing } from "../hooks/use-tts";

export function SpeakerVoiceAssignment({
  episode,
  tts,
}: {
  episode: EpisodeMedia;
  tts: TtsEditing;
}) {
  if (!episode.speakers?.length) return null;

  return (
    <div className="border-b px-2 py-2">
      <div className="mb-1.5 flex items-center gap-1.5 text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
        <Users className="size-3" /> Voice assignment
      </div>
      <div className="space-y-1">
        {episode.speakers.map((speaker) => {
          const segmentCount = speaker.segment_ids.length;
          const currentVoice = tts.speakerVoiceIds[speaker.id] ?? "";
          const assigning = tts.assigningSpeakerId === speaker.id;
          return (
            <div key={speaker.id} className="flex items-center gap-1.5">
              <span className="min-w-0 flex-1 truncate text-[10px]" title={speaker.name}>
                {speaker.name}
              </span>
              <span className="shrink-0 text-[8px] tabular-nums text-muted-foreground">
                {segmentCount} clips
              </span>
              {assigning && <LoaderCircle className="size-3 animate-spin text-primary" />}
              <Select
                value={currentVoice}
                disabled={tts.generating || !!tts.assigningSpeakerId}
                onValueChange={(voiceId) => void tts.assignSpeakerVoice(speaker.id, voiceId)}
              >
                <SelectTrigger size="sm" className="h-6 w-36 text-[9px]" aria-label={`Voice for ${speaker.name}`}>
                  <SelectValue placeholder="Assign voice" />
                </SelectTrigger>
                <SelectContent align="end" className="min-w-56">
                  <SelectGroup>
                    {tts.voices.map((voice) => (
                      <SelectItem key={voice.id} value={voice.id} className="text-[10px]">
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
        Changing a speaker voice keeps existing audio and marks affected clips outdated until regenerated.
      </p>
    </div>
  );
}
