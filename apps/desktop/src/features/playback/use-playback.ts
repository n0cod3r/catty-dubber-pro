import { useCallback, useState } from "react";

export function usePlayback() {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [seekRequest, setSeekRequest] = useState<{ time: number; nonce: number } | null>(null);

  const seek = useCallback(
    (time: number) => {
      const next = Math.max(0, Math.min(duration || time, time));
      setCurrentTime(next);
      setSeekRequest({ time: next, nonce: Date.now() });
    },
    [duration],
  );

  return {
    currentTime,
    duration,
    seekRequest,
    setCurrentTime,
    setDuration,
    seek,
  };
}
