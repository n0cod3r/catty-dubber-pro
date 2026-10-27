import { useRef } from "react";

import type { TimelineClip } from "@/features/preview/deps/timeline";

import { useClipMediaSync } from "../hooks/use-clip-media-sync";

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
