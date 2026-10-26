import { useCallback, useRef, useState } from "react";

import { clamp } from "@/features/timeline/geometry";

export function usePlayback() {
  const [currentTime, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [seekRequest, setSeekRequest] = useState<{ time: number; nonce: number } | null>(null);
  const sequence = useRef(0);

  const setCurrentTime = useCallback((time: number) => {
    if (Number.isFinite(time)) setTime(Math.max(0, time));
  }, []);

  const seek = useCallback(
    (time: number) => {
      if (!Number.isFinite(time) || duration <= 0) return;
      const next = clamp(time, 0, duration);
      setTime(next);
      setSeekRequest({ time: next, nonce: ++sequence.current });
    },
    [duration],
  );

  return { currentTime, duration, seekRequest, setCurrentTime, setDuration, seek };
}
