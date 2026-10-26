import { useEffect, useRef, useState, type ReactNode } from "react";

import { clamp } from "@/features/timeline/geometry";

const STORAGE_KEY = "catty:timeline-height";
function loadHeight() {
  try {
    const value = Number(localStorage.getItem(STORAGE_KEY));
    return value > 0 && Number.isFinite(value) ? value : 300;
  } catch {
    return 300;
  }
}

export function EditorPanels({ children, timeline }: { children: ReactNode; timeline: ReactNode }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<number | null>(null);
  const [height, setHeight] = useState(loadHeight);
  const [available, setAvailable] = useState(700);
  const min = Math.min(180, available * 0.4);
  const max = Math.max(min, available - 166);
  const actualHeight = clamp(height, min, max);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setAvailable(entry.contentRect.height);
    });
    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(height));
    } catch {
      /* Storage is optional. */
    }
  }, [height]);

  return (
    <div
      ref={rootRef}
      className="grid min-h-0 flex-1 overflow-hidden"
      style={{ gridTemplateRows: `minmax(0, 1fr) 6px ${actualHeight}px` }}
    >
      <div className="grid min-h-0 min-w-0 grid-cols-[minmax(0,1fr)_minmax(240px,28%)] overflow-hidden">
        {children}
      </div>
      <div
        role="separator"
        tabIndex={0}
        aria-label="Resize timeline"
        aria-orientation="horizontal"
        aria-controls="editor-timeline"
        aria-valuemin={Math.round(min)}
        aria-valuemax={Math.round(max)}
        aria-valuenow={Math.round(actualHeight)}
        className="group relative z-10 cursor-row-resize touch-none border-y bg-card outline-none hover:bg-primary/30 focus-visible:bg-primary/40"
        onDoubleClick={() => setHeight(300)}
        onKeyDown={(event) => {
          const next =
            event.key === "ArrowUp"
              ? actualHeight + 16
              : event.key === "ArrowDown"
                ? actualHeight - 16
                : event.key === "Home"
                  ? min
                  : event.key === "End"
                    ? max
                    : null;
          if (next !== null) {
            event.preventDefault();
            setHeight(clamp(next, min, max));
          }
        }}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          dragRef.current = event.pointerId;
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (dragRef.current !== event.pointerId) return;
          const rect = rootRef.current?.getBoundingClientRect();
          if (rect) setHeight(clamp(rect.bottom - event.clientY, min, max));
        }}
        onPointerUp={(event) => {
          dragRef.current = null;
          if (event.currentTarget.hasPointerCapture(event.pointerId))
            event.currentTarget.releasePointerCapture(event.pointerId);
        }}
        onPointerCancel={() => {
          dragRef.current = null;
        }}
        onLostPointerCapture={() => {
          dragRef.current = null;
        }}
      >
        <span className="absolute inset-x-0 top-1/2 mx-auto h-px w-8 bg-muted-foreground/50" />
      </div>
      <div id="editor-timeline" className="min-h-0 overflow-hidden">
        {timeline}
      </div>
    </div>
  );
}
