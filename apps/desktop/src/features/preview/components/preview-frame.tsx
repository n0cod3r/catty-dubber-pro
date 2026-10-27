import { useEffect, useRef, useState, type ReactNode } from "react";

import type { EpisodeMedia } from "@/features/preview/deps/episodes";

import { fitVideoFrame } from "../utils/video-geometry";

export function PreviewFrame({
  source,
  children,
}: {
  source: EpisodeMedia | null;
  children: (width: number) => ReactNode;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, []);
  const frame = fitVideoFrame(size.width, size.height, source?.width, source?.height);
  return (
    <div
      ref={hostRef}
      className="flex size-full min-h-0 items-center justify-center p-3"
      data-preview-viewport
    >
      <div className="relative shrink-0 overflow-hidden bg-black" data-preview-frame style={frame}>
        {children(frame.width)}
      </div>
    </div>
  );
}
