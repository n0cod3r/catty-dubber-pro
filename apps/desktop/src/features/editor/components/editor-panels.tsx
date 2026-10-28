import { useEffect, useRef, useState, type ReactNode } from "react";

import { clampFinite as clamp } from "@/shared/utils/math";

import { PanelResizeHandle } from "./panel-resize-handle";

function loadSize(key: string, fallback: number) {
  try {
    const value = Number(localStorage.getItem(key));
    return value > 0 && Number.isFinite(value) ? value : fallback;
  } catch {
    return fallback;
  }
}
function saveSize(key: string, value: number) {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    /* Storage is optional. */
  }
}

export function EditorPanels({
  preview,
  inspector,
  timeline,
}: {
  preview: ReactNode;
  inspector: ReactNode;
  timeline: ReactNode;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(() =>
    loadSize("catty:timeline-height", 300),
  );
  const [inspectorWidth, setInspectorWidth] = useState(() =>
    loadSize("catty:inspector-width", 320),
  );
  const [available, setAvailable] = useState({ width: 1000, height: 700 });
  const minHeight = Math.min(180, available.height * 0.4);
  const maxHeight = Math.max(minHeight, available.height - 166);
  const actualHeight = clamp(height, minHeight, maxHeight);
  const minWidth = Math.min(240, Math.max(0, (available.width - 6) / 2));
  const maxWidth = Math.max(
    minWidth,
    available.width - 6 - Math.min(280, available.width / 2),
  );
  const actualWidth = clamp(inspectorWidth, minWidth, maxWidth);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry)
        setAvailable({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
    });
    observer.observe(root);
    return () => observer.disconnect();
  }, []);
  useEffect(() => saveSize("catty:timeline-height", height), [height]);
  useEffect(
    () => saveSize("catty:inspector-width", inspectorWidth),
    [inspectorWidth],
  );

  return (
    <div
      ref={rootRef}
      className="grid min-h-0 flex-1 overflow-hidden"
      style={{ gridTemplateRows: `minmax(0, 1fr) 6px ${actualHeight}px` }}
    >
      <div
        className="grid min-h-0 min-w-0 overflow-hidden"
        style={{ gridTemplateColumns: `minmax(0, 1fr) 6px ${actualWidth}px` }}
      >
        <div
          id="editor-preview"
          className="flex min-h-0 min-w-0 flex-col overflow-hidden"
        >
          {preview}
        </div>
        <PanelResizeHandle
          orientation="vertical"
          label="Resize preview and inspector"
          controls="editor-preview editor-inspector"
          value={actualWidth}
          min={minWidth}
          max={maxWidth}
          reset={320}
          onChange={setInspectorWidth}
          valueAt={(x) =>
            (rootRef.current?.getBoundingClientRect().right ?? x) - x
          }
        />
        <div
          id="editor-inspector"
          className="flex min-h-0 min-w-0 flex-col overflow-hidden"
        >
          {inspector}
        </div>
      </div>
      <PanelResizeHandle
        orientation="horizontal"
        label="Resize timeline"
        controls="editor-timeline"
        value={actualHeight}
        min={minHeight}
        max={maxHeight}
        reset={300}
        onChange={setHeight}
        valueAt={(_, y) =>
          (rootRef.current?.getBoundingClientRect().bottom ?? y) - y
        }
      />
      <div id="editor-timeline" className="min-h-0 overflow-hidden">
        {timeline}
      </div>
    </div>
  );
}
