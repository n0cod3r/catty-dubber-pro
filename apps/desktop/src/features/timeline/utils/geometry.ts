import { clampFinite as clamp } from "../../../shared/utils/math.ts";

export function pointerToTime(
  x: number,
  left: number,
  scroll: number,
  width: number,
  duration: number,
) {
  if (width <= 0 || duration <= 0) return 0;
  return clamp(((x - left + scroll) / width) * duration, 0, duration);
}

export function snapTime(
  time: number,
  points: readonly number[],
  pixelsPerSecond: number,
) {
  if (pixelsPerSecond <= 0) return time;
  let closest = time;
  let distance = 8 / pixelsPerSecond;
  for (const point of points) {
    const nextDistance = Math.abs(point - time);
    if (nextDistance < distance) {
      closest = point;
      distance = nextDistance;
    }
  }
  return closest;
}

// Compare only real edge targets. Computing an unsnapped trailing edge as
// (start + duration) - duration introduces rounding errors that can beat a
// valid leading-edge snap by a few ulps.
export function snapClipStart(
  start: number,
  duration: number,
  points: readonly number[],
  pixelsPerSecond: number,
) {
  if (
    !Number.isFinite(start) ||
    !Number.isFinite(duration) ||
    pixelsPerSecond <= 0
  )
    return start;
  let closest = start;
  let distance = 8 / pixelsPerSecond;
  for (const point of points) {
    for (const candidate of [point, point - duration]) {
      if (!Number.isFinite(candidate) || candidate < 0) continue;
      const nextDistance = Math.abs(candidate - start);
      if (nextDistance < distance) {
        closest = candidate;
        distance = nextDistance;
      }
    }
  }
  return closest;
}

export function rulerInterval(pixelsPerSecond: number) {
  // Labels stay at least 80px apart, including for feature-length episodes.
  const target = 80 / Math.max(pixelsPerSecond, 0.000001);
  const magnitude = 10 ** Math.floor(Math.log10(target));
  return (
    ([1, 2, 5, 10].find((multiple) => multiple * magnitude >= target) ?? 10) *
    magnitude
  );
}

export function visibleTicks(
  duration: number,
  width: number,
  scroll: number,
  viewport: number,
) {
  if (duration <= 0 || width <= 0) return [];
  const step = rulerInterval(width / duration);
  const first = Math.max(0, Math.floor(((scroll / width) * duration) / step));
  const last = Math.min(
    Math.floor(duration / step),
    Math.ceil((((scroll + viewport) / width) * duration) / step),
  );
  return Array.from(
    { length: Math.max(0, last - first + 1) },
    (_, index) => (first + index) * step,
  );
}
