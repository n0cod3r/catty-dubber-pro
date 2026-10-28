import { useEffect, useRef, type PointerEvent, type RefObject } from "react";

import { clampFinite as clamp } from "@/shared/utils/math";

import { TIMELINE } from "../constants";

type Gesture = { id: number; x: number; bypassSnap: boolean; pending: boolean };

export function useTimelineScrub(
  viewportRef: RefObject<HTMLDivElement | null>,
  enabled: boolean,
  onSeek: (clientX: number, bypassSnap: boolean) => void,
  onScrubbingChange: (value: boolean) => void,
) {
  const gestureRef = useRef<Gesture | null>(null);
  const frameRef = useRef(0);
  const seekRef = useRef(onSeek);
  useEffect(() => {
    seekRef.current = onSeek;
  }, [onSeek]);
  useEffect(
    () => () => {
      cancelAnimationFrame(frameRef.current);
      gestureRef.current = null;
    },
    [],
  );

  function finish(event: PointerEvent<HTMLDivElement>, commit: boolean) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.id !== event.pointerId) return;
    if (commit) seekRef.current(event.clientX, event.shiftKey);
    gestureRef.current = null;
    cancelAnimationFrame(frameRef.current);
    onScrubbingChange(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
  }

  return {
    onPointerDown(event: PointerEvent<HTMLDivElement>) {
      if (
        !enabled ||
        event.button !== 0 ||
        gestureRef.current ||
        !(event.target as HTMLElement).closest("[data-timeline-surface]")
      )
        return;
      event.preventDefault();
      event.currentTarget.focus({ preventScroll: true });
      event.currentTarget.setPointerCapture(event.pointerId);
      gestureRef.current = {
        id: event.pointerId,
        x: event.clientX,
        bypassSnap: event.shiftKey,
        pending: false,
      };
      onScrubbingChange(true);
      seekRef.current(event.clientX, event.shiftKey);
      let previous = performance.now();
      const tick = (now: number) => {
        const viewport = viewportRef.current;
        const gesture = gestureRef.current;
        if (!viewport || !gesture) return;
        const rect = viewport.getBoundingClientRect();
        const left = rect.left + TIMELINE.headerWidth;
        const edgeDistance =
          gesture.x < left + 24
            ? gesture.x - left - 24
            : gesture.x > rect.right - 24
              ? gesture.x - rect.right + 24
              : 0;
        const before = viewport.scrollLeft;
        // Cap both velocity and elapsed time after a background-tab pause.
        viewport.scrollLeft +=
          (clamp(edgeDistance / 2, -20, 20) * Math.min(now - previous, 32)) /
          16;
        previous = now;
        if (gesture.pending || viewport.scrollLeft !== before) {
          gesture.pending = false;
          seekRef.current(gesture.x, gesture.bypassSnap);
        }
        frameRef.current = requestAnimationFrame(tick);
      };
      frameRef.current = requestAnimationFrame(tick);
    },
    onPointerMove(event: PointerEvent<HTMLDivElement>) {
      const gesture = gestureRef.current;
      if (!gesture || gesture.id !== event.pointerId) return;
      gesture.x = event.clientX;
      gesture.bypassSnap = event.shiftKey;
      gesture.pending = true;
    },
    onPointerUp: (event: PointerEvent<HTMLDivElement>) => finish(event, true),
    onPointerCancel: (event: PointerEvent<HTMLDivElement>) =>
      finish(event, false),
    onLostPointerCapture: (event: PointerEvent<HTMLDivElement>) =>
      finish(event, false),
  };
}
