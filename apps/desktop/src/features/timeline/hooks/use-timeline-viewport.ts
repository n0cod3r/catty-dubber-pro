import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { clampFinite as clamp } from "@/shared/utils/math";

import { TIMELINE } from "../constants";
import { pointerToTime } from "../utils/geometry";

export function useTimelineViewport(duration: number, currentTime: number, follow: boolean) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const currentTimeRef = useRef(currentTime);
  useEffect(() => {
    currentTimeRef.current = currentTime;
  }, [currentTime]);
  const [viewportWidth, setViewportWidth] = useState(800);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [scrubbing, setScrubbing] = useState(false);
  const anchorRef = useRef<{ time: number; offset: number } | null>(null);
  const previousTimeRef = useRef(currentTime);
  const width = Math.max(1, viewportWidth * zoom);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const observer = new ResizeObserver(() =>
      setViewportWidth(Math.max(1, viewport.clientWidth - TIMELINE.headerWidth)),
    );
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  const changeZoom = useCallback(
    (next: number, clientX?: number) => {
      const viewport = viewportRef.current;
      if (!viewport) return;
      const left = viewport.getBoundingClientRect().left + TIMELINE.headerWidth;
      const offset =
        clientX === undefined
          ? clamp(
              (currentTimeRef.current / duration) * width - viewport.scrollLeft,
              0,
              viewportWidth,
            )
          : clamp(clientX - left, 0, viewportWidth);
      anchorRef.current = { time: ((viewport.scrollLeft + offset) / width) * duration, offset };
      setZoom(clamp(next, TIMELINE.minZoom, TIMELINE.maxZoom));
    },
    [duration, viewportWidth, width],
  );

  useLayoutEffect(() => {
    const anchor = anchorRef.current;
    const viewport = viewportRef.current;
    if (anchor && viewport) {
      viewport.scrollLeft = (anchor.time / duration) * width - anchor.offset;
      setScrollLeft(viewport.scrollLeft);
      anchorRef.current = null;
    }
  }, [duration, width, zoom]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const wheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      changeZoom(zoom * Math.exp(-event.deltaY * 0.005), event.clientX);
    };
    viewport.addEventListener("wheel", wheel, { passive: false });
    return () => viewport.removeEventListener("wheel", wheel);
  }, [changeZoom, zoom]);

  useEffect(() => {
    const changed = previousTimeRef.current !== currentTime;
    previousTimeRef.current = currentTime;
    const viewport = viewportRef.current;
    if (!changed || !viewport || !follow || scrubbing) return;
    const position = (currentTime / duration) * width;
    const left = viewport.scrollLeft;
    if (position < left || position > left + viewportWidth - 24) {
      viewport.scrollLeft = Math.max(0, position - viewportWidth * 0.2);
    }
  }, [currentTime, duration, follow, scrubbing, viewportWidth, width]);

  const timeAt = useCallback(
    (clientX: number) => {
      const viewport = viewportRef.current;
      if (!viewport) return 0;
      return pointerToTime(
        clientX,
        viewport.getBoundingClientRect().left + TIMELINE.headerWidth,
        viewport.scrollLeft,
        width,
        duration,
      );
    },
    [duration, width],
  );

  function fit() {
    anchorRef.current = { time: 0, offset: 0 };
    setZoom(1);
    if (viewportRef.current) viewportRef.current.scrollLeft = 0;
  }

  return {
    viewportRef,
    viewportWidth,
    scrollLeft,
    setScrollLeft,
    zoom,
    width,
    scrubbing,
    setScrubbing,
    changeZoom,
    timeAt,
    fit,
  };
}
