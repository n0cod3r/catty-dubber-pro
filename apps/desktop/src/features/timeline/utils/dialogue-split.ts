export function dialogueSplitTarget(
  sourceId: string | undefined,
  segments: readonly { id: string; start: number; end: number }[],
  selectedId: string | null,
  time: number,
) {
  const prefix = `dialogue:${sourceId}:`;
  if (!sourceId || !Number.isFinite(time) || (selectedId && !selectedId.startsWith(prefix)))
    return null;
  return (
    segments.find(
      (segment) =>
        (!selectedId || selectedId === prefix + segment.id) &&
        time > segment.start + 0.05 &&
        time < segment.end - 0.05,
    ) ?? null
  );
}
