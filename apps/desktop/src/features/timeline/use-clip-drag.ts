import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type PointerEvent,
  type RefObject,
} from "react";

import { clamp, snapClipStart, TIMELINE } from "./geometry";
import {
  clipEditGroup,
  resolveClipDrag,
  type TimelineAction,
  type TimelineDocument,
} from "./model";

type Gesture = {
  id: number;
  clipId: string;
  x: number;
  y: number;
  latestX: number;
  latestY: number;
  scroll: number;
  shift: boolean;
  moved: boolean;
  flush?: () => void;
  lastKey?: string;
  candidate: Extract<TimelineAction, { type: "move-clip" }> | null;
};
type Draft = { document: TimelineDocument; valid: boolean; start: number };

export function useClipDrag(
  model: TimelineDocument,
  viewportRef: RefObject<HTMLDivElement | null>,
  pixelsPerSecond: number,
  snap: boolean,
  snapPoints: number[],
  onSelect: (id: string) => void,
  dispatch: Dispatch<TimelineAction>,
) {
  const gestureRef = useRef<Gesture | null>(null);
  const frameRef = useRef(0);
  const [draft, setDraft] = useState<Draft | null>(null);
  useEffect(() => () => cancelAnimationFrame(frameRef.current), []);

  function cancel() {
    gestureRef.current = null;
    cancelAnimationFrame(frameRef.current);
    setDraft(null);
  }
  function begin(event: PointerEvent<HTMLDivElement>) {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-clip-id]");
    if (!button) return false;
    if (event.button !== 0 || gestureRef.current) return true;
    const clipId = button.dataset.clipId;
    if (!clipId) return true;
    onSelect(clipId);
    if (!clipEditGroup(model, clipId).length) return true;
    event.preventDefault();
    event.currentTarget.focus({ preventScroll: true });
    event.currentTarget.setPointerCapture(event.pointerId);
    const gesture: Gesture = {
      id: event.pointerId,
      clipId,
      x: event.clientX,
      y: event.clientY,
      latestX: event.clientX,
      latestY: event.clientY,
      scroll: event.currentTarget.scrollLeft,
      shift: event.shiftKey,
      moved: false,
      candidate: null,
    };
    gestureRef.current = gesture;
    const clip = model.clips.find((item) => item.id === clipId);
    if (!clip) return true;
    const groupIds = new Set(clipEditGroup(model, clipId).map((item) => item.id));
    const points = [
      ...snapPoints,
      ...model.clips
        .filter((item) => !groupIds.has(item.id))
        .flatMap((item) => [item.start, item.start + item.duration]),
    ];
    let previous = performance.now();
    const update = (now: number) => {
      const viewport = viewportRef.current;
      if (gestureRef.current !== gesture || !viewport) return;
      if (Math.hypot(gesture.latestX - gesture.x, gesture.latestY - gesture.y) >= 4)
        gesture.moved = true;
      if (gesture.moved) {
        const rect = viewport.getBoundingClientRect();
        const edge =
          gesture.latestX < rect.left + TIMELINE.headerWidth + 24
            ? gesture.latestX - rect.left - TIMELINE.headerWidth - 24
            : gesture.latestX > rect.right - 24
              ? gesture.latestX - rect.right + 24
              : 0;
        viewport.scrollLeft += (clamp(edge / 2, -20, 20) * Math.min(32, now - previous)) / 16;
        let start = Math.max(
          0,
          clip.start +
            (gesture.latestX - gesture.x + viewport.scrollLeft - gesture.scroll) / pixelsPerSecond,
        );
        if (snap && !gesture.shift)
          start = snapClipStart(start, clip.duration, points, pixelsPerSecond);
        const lane = window.document
          .elementFromPoint(gesture.latestX, gesture.latestY)
          ?.closest<HTMLElement>("[data-track-drop]");
        const trackId = lane?.dataset.trackDrop;
        const key = `${trackId}:${start}`;
        if (gesture.lastKey !== key) {
          gesture.lastKey = key;
          const next = trackId ? resolveClipDrag(model, clipId, start, trackId) : null;
          gesture.candidate =
            next && trackId ? { type: "move-clip", id: clipId, start: next.start, trackId } : null;
          setDraft({
            document: next?.document ?? model,
            valid: next !== null,
            start: next?.start ?? start,
          });
        }
      }
      previous = now;
      frameRef.current = requestAnimationFrame(update);
    };
    gesture.flush = () => update(performance.now());
    frameRef.current = requestAnimationFrame(update);
    return true;
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    const gesture = gestureRef.current;
    if (gesture?.id === event.pointerId) {
      gesture.latestX = event.clientX;
      gesture.latestY = event.clientY;
      gesture.shift = event.shiftKey;
    }
  }
  function finish(event: PointerEvent<HTMLDivElement>, commit: boolean) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.id !== event.pointerId) return;
    if (commit) {
      gesture.latestX = event.clientX;
      gesture.latestY = event.clientY;
      gesture.shift = event.shiftKey;
      cancelAnimationFrame(frameRef.current);
      gesture.flush?.();
    }
    if (commit && gesture.moved && gesture.candidate) dispatch(gesture.candidate);
    cancel();
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
  }
  return { draft, cancel, begin, move, finish };
}
