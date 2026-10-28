export function advancePlaybackClock(
  current: number,
  mediaTime: number | null,
  pendingSeek: number | null,
  elapsed: number,
  duration: number,
) {
  if (mediaTime !== null && Number.isFinite(mediaTime)) {
    if (pendingSeek !== null && Math.abs(mediaTime - pendingSeek) >= 0.18)
      return { time: current, pendingSeek };
    return {
      time: Math.max(0, Math.min(duration, mediaTime)),
      pendingSeek: null,
    };
  }
  return {
    time: Math.min(duration, current + Math.max(0, elapsed)),
    pendingSeek: null,
  };
}
