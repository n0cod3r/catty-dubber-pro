export const THUMB_WIDTH = 96;
export function clipRenderWindow(
  start: number,
  duration: number,
  pixelsPerSecond: number,
  scrollLeft: number,
  viewportWidth: number,
) {
  const clipLeft = start * pixelsPerSecond;
  const clipWidth = Math.max(1, duration * pixelsPerSecond);
  const left = Math.max(0, Math.floor(scrollLeft - clipLeft - THUMB_WIDTH));
  const right = Math.min(clipWidth, Math.ceil(scrollLeft + viewportWidth - clipLeft + THUMB_WIDTH));
  return { left, width: Math.max(0, right - left), clipWidth };
}
export function thumbnailTiles(
  sourceStart: number,
  left: number,
  width: number,
  pixelsPerSecond: number,
  sourceDuration: number,
) {
  const tiles: { x: number; time: number }[] = [];
  if (width <= 0 || pixelsPerSecond <= 0) return tiles;
  for (let x = Math.floor(left / THUMB_WIDTH) * THUMB_WIDTH; x < left + width; x += THUMB_WIDTH) {
    tiles.push({
      x,
      time:
        Math.round(
          Math.min(
            Math.max(0, sourceDuration - 0.05),
            sourceStart + (x + THUMB_WIDTH / 2) / pixelsPerSecond,
          ) * 100,
        ) / 100,
    });
  }
  return tiles;
}
