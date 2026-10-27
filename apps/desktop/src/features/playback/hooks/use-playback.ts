import { useCallback, useEffect, useRef, useState } from "react";

import { clampFinite as clamp } from "@/shared/utils/math";

// Media elements own smooth frame presentation. The React editor clock only
// needs enough updates for the playhead, timecode and clip activation. Updating
// the entire editor tree at display refresh rate made playback unnecessarily
// expensive, especially while waveform/timeline UI is mounted.
const UI_FRAME_MS = 1000 / 30;

export function usePlayback(duration: number) {
  const [currentTime, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timeRef = useRef(0);

  const seek = useCallback(
    (time: number) => {
      if (!Number.isFinite(time)) return;
      timeRef.current = clamp(time, 0, duration);
      setTime(timeRef.current);
    },
    [duration],
  );

  useEffect(() => {
    timeRef.current = clamp(timeRef.current, 0, duration);
    setTime(timeRef.current);
    if (duration <= 0) setPlaying(false);
  }, [duration]);

  useEffect(() => {
    if (!playing || duration <= 0) return;

    let frame = 0;
    let previous = performance.now();
    let lastPublished = previous;

    const tick = (now: number) => {
      timeRef.current = Math.min(duration, timeRef.current + Math.max(0, now - previous) / 1000);
      previous = now;

      if (now - lastPublished >= UI_FRAME_MS || timeRef.current >= duration) {
        setTime(timeRef.current);
        lastPublished = now;
      }

      if (timeRef.current >= duration) {
        setPlaying(false);
      } else {
        frame = requestAnimationFrame(tick);
      }
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [duration, playing]);

  return { currentTime, playing, setPlaying, seek };
}
