import { useCallback, useEffect, useRef, useState } from "react";

import { clamp } from "@/features/timeline/geometry";

// The editor clock must advance through gaps and beyond the original source's
// duration. Media elements follow clip source offsets; they do not own the clock.
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
    let frame = 0,
      previous = performance.now();
    const tick = (now: number) => {
      timeRef.current = Math.min(duration, timeRef.current + Math.max(0, now - previous) / 1000);
      previous = now;
      setTime(timeRef.current);
      if (timeRef.current >= duration) setPlaying(false);
      else frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [duration, playing]);
  return { currentTime, playing, setPlaying, seek };
}
