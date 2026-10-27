export type MediaMapping = { source: string; offset: number };

export function isContinuousMedia(previous: MediaMapping | undefined, next: MediaMapping) {
  return (
    !!previous &&
    previous.source === next.source &&
    Number.isFinite(previous.offset) &&
    Number.isFinite(next.offset) &&
    Math.abs(previous.offset - next.offset) < 0.000001
  );
}

export function needsMediaSeek(
  previous: MediaMapping | undefined,
  next: MediaMapping,
  mediaTime: number,
  targetTime: number,
  playing: boolean,
  explicitSeek: boolean,
  seeking: boolean,
) {
  return (
    !seeking &&
    (explicitSeek ||
      !isContinuousMedia(previous, next) ||
      Math.abs(mediaTime - targetTime) > (playing ? 0.5 : 0.001))
  );
}
