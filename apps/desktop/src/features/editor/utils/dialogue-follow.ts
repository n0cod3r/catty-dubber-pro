export function activeDialogueId(
  segments: readonly { id: string; start: number; end: number }[],
  time: number,
): string | null {
  if (!Number.isFinite(time)) return null;
  return segments.find((segment) => time >= segment.start && time < segment.end)?.id ?? null;
}

// Scroll only the dialogue list, and only when its active row leaves view.
export function dialogueScrollDelta(
  rowTop: number,
  rowBottom: number,
  listTop: number,
  listBottom: number,
) {
  if (rowTop < listTop) return rowTop - listTop;
  if (rowBottom > listBottom)
    return rowTop > listTop ? Math.min(rowBottom - listBottom, rowTop - listTop) : 0;
  return 0;
}
