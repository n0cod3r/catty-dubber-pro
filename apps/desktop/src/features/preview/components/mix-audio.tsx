import { useRef } from "react";

import { useClipMediaSync } from "../hooks/use-clip-media-sync";

export function MixAudio({
  id,
  src,
  sourceTime,
  playing,
  muted,
  seekRevision,
  onError,
}: {
  id: string;
  src: string;
  sourceTime: number | null;
  playing: boolean;
  muted: boolean;
  seekRevision: number;
  onError: (message: string) => void;
}) {
  const ref = useRef<HTMLAudioElement>(null);
  useClipMediaSync(
    ref,
    sourceTime,
    playing && !muted,
    id,
    onError,
    seekRevision,
    { source: src, offset: 0 },
  );
  return (
    <audio
      hidden
      ref={ref}
      src={src}
      muted={muted}
      preload="auto"
      data-mix-audio={id}
    />
  );
}
