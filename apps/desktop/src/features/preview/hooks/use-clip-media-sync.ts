import { useEffect, useRef, type RefObject } from "react";

import { clampFinite as clamp } from "@/shared/utils/math";

import { needsMediaSeek, type MediaMapping } from "../utils/media-sync";

export function useClipMediaSync(
  ref: RefObject<HTMLMediaElement | null>,
  sourceTime: number | null,
  playing: boolean,
  clipId: string | undefined,
  onError: (message: string) => void,
  seekRevision = 0,
  mapping?: MediaMapping,
) {
  const seekRef = useRef(-1);
  const pendingRef = useRef(false);
  const mappingRef = useRef<MediaMapping | undefined>(undefined);
  const source = mapping?.source ?? clipId ?? "";
  const offset = mapping?.offset ?? 0;
  useEffect(() => {
    const media = ref.current;
    if (!media) return;
    const synchronize = () => {
      if (sourceTime === null || media.readyState < 1) {
        if (sourceTime === null) mappingRef.current = undefined;
        media.pause();
        return;
      }
      const time = clamp(
        sourceTime,
        0,
        Number.isFinite(media.duration) ? Math.max(0, media.duration - 0.001) : 0,
      );
      const nextMapping = { source, offset };
      if (
        needsMediaSeek(
          mappingRef.current,
          nextMapping,
          media.currentTime,
          time,
          playing,
          seekRef.current !== seekRevision,
          media.seeking,
        )
      )
        media.currentTime = time;
      if (!media.seeking || Math.abs(media.currentTime - time) < 0.05) {
        mappingRef.current = nextMapping;
        seekRef.current = seekRevision;
      }
      if (media.ended && time >= media.duration - 0.05) return;
      if (!playing) media.pause();
      else if (media.paused && !pendingRef.current) {
        pendingRef.current = true;
        void media
          .play()
          .catch((cause: unknown) => {
            if (!(cause instanceof DOMException && cause.name === "AbortError"))
              onError("Playback could not start. Try Play again.");
          })
          .finally(() => {
            pendingRef.current = false;
          });
      }
    };
    synchronize();
    media.addEventListener("loadeddata", synchronize);
    return () => media.removeEventListener("loadeddata", synchronize);
  }, [source, offset, onError, playing, ref, sourceTime, seekRevision]);
  useEffect(() => {
    const media = ref.current;
    return () => {
      media?.pause();
    };
  }, [ref]);
}
