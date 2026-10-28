export function formatTime(seconds: number, milliseconds = false) {
  const value = Math.floor(
    Math.max(0, Number.isFinite(seconds) ? seconds : 0) * 1000,
  );
  const hours = Math.floor(value / 3_600_000);
  const minutes = Math.floor(value / 60_000) % 60;
  const secs = Math.floor(value / 1000) % 60;
  const clock = [hours, minutes, secs]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  return milliseconds
    ? `${clock}.${String(value % 1000).padStart(3, "0")}`
    : clock;
}
