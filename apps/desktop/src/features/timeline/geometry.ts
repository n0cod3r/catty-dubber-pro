export const TIMELINE = {
  headerWidth: 176,
  rulerHeight: 32,
  trackHeight: 76,
  minZoom: 1,
  maxZoom: 64,
} as const;

export function clamp(value: number, min: number, max: number) {
  return Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : min;
}

export function formatTime(seconds: number, milliseconds = false) {
  const value = Math.floor(Math.max(0, Number.isFinite(seconds) ? seconds : 0) * 1000);
  const hours = Math.floor(value / 3_600_000);
  const minutes = Math.floor(value / 60_000) % 60;
  const secs = Math.floor(value / 1000) % 60;
  const clock = [hours, minutes, secs].map((part) => String(part).padStart(2, "0")).join(":");
  return milliseconds ? `${clock}.${String(value % 1000).padStart(3, "0")}` : clock;
}

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

export function snapTime(time: number, points: readonly number[], pixelsPerSecond: number) {
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

export function rulerInterval(pixelsPerSecond: number) {
  // Labels stay at least 80px apart, including for feature-length episodes.
  const target = 80 / Math.max(pixelsPerSecond, 0.000001);
  const magnitude = 10 ** Math.floor(Math.log10(target));
  return ([1, 2, 5, 10].find((multiple) => multiple * magnitude >= target) ?? 10) * magnitude;
}

export function visibleTicks(duration: number, width: number, scroll: number, viewport: number) {
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
