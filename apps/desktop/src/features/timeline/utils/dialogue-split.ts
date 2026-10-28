function hasSplittableText(text: string): boolean {
  return (text.match(/[\p{L}\p{N}]/gu) ?? []).length >= 2;
}

export function dialogueSplitTarget<
  T extends {
    id: string;
    start: number;
    end: number;
    sourceText?: string;
  },
>(
  sourceId: string | undefined,
  segments: readonly T[],
  selectedId: string | null,
  time: number,
): T | null {
  const prefix = `dialogue:${sourceId}:`;
  if (
    !sourceId ||
    !Number.isFinite(time) ||
    (selectedId && !selectedId.startsWith(prefix))
  )
    return null;
  const segment =
    segments.find(
      (segment) =>
        (!selectedId || selectedId === prefix + segment.id) &&
        time > segment.start + 0.05 &&
        time < segment.end - 0.05,
    ) ?? null;
  return segment && hasSplittableText(segment.sourceText ?? "")
    ? segment
    : null;
}
