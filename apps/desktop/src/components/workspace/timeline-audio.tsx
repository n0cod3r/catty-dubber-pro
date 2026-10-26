import { useRef } from "react";

import { useClipMediaSync } from "@/features/playback/use-clip-media-sync";
import type { TimelineClip } from "@/features/timeline/model";

export function TimelineAudio({
  clip,
  src,
  currentTime,
  playing,
  muted,
  onError,
}: {
  clip: TimelineClip;
  src: string;
  currentTime: number;
  playing: boolean;
  muted: boolean;
  onError: (message: string) => void;
}) {
  const ref = useRef<HTMLAudioElement>(null);
  useClipMediaSync(ref, clip.sourceStart + currentTime - clip.start, playing, clip.id, onError);
  return (
    <audio hidden ref={ref} src={src} muted={muted} preload="auto" data-audio-clip={clip.id} />
  );
}
