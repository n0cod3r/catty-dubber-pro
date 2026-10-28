import { useMemo } from "react";

import type { TranscriptionProgress } from "@catty/contracts";
import { LoaderCircle } from "lucide-react";

import { formatTime } from "@/shared/utils/time";

import { TIMELINE } from "../constants";
import { transcriptionPreviewClips } from "../utils/transcription-preview";

const labels: Record<TranscriptionProgress["phase"], string> = {
  preparing: "Preparing audio…",
  loading: "Loading speech models…",
  vad: "Detecting speech…",
  asr: "Recognizing dialogue…",
  punctuation: "Adding punctuation…",
  alignment: "Aligning dialogue…",
  saving: "Saving dialogue…",
  completed: "Complete",
  failed: "Failed",
};

export function TranscriptionPreviewTrack({
  progress,
  duration,
  width,
  scrollLeft,
  viewportWidth,
  onSeek,
}: {
  progress: TranscriptionProgress;
  duration: number;
  width: number;
  scrollLeft: number;
  viewportWidth: number;
  onSeek: (time: number) => void;
}) {
  const clips = useMemo(
    () => transcriptionPreviewClips(progress, duration),
    [progress, duration],
  );
  return (
    <>
      <div className="sticky left-0 z-30 flex flex-col justify-center gap-1 border-r border-b bg-card px-2">
        <span className="flex items-center gap-1.5 text-[10px] font-medium text-primary">
          <LoaderCircle className="size-3 animate-spin motion-reduce:animate-none" />
          Live dialogue · draft
        </span>
        <span role="status" className="text-[9px] text-muted-foreground">
          {labels[progress.phase]}
          {progress.phase === "asr" && progress.total > 0
            ? ` ${progress.completed}/${progress.total} chunks`
            : ""}
        </span>
        <span className="text-[8px] text-muted-foreground">
          {clips.length} clips · read-only
        </span>
      </div>
      <div
        data-timeline-surface
        aria-label="Live transcription preview"
        className="relative touch-none overflow-hidden border-b bg-primary/5"
        style={{ height: TIMELINE.trackHeight }}
      >
        {clips.map((clip) => {
          const left = (clip.start / duration) * width;
          const clipWidth = Math.max(1, (clip.duration / duration) * width);
          if (
            left + clipWidth < scrollLeft - 96 ||
            left > scrollLeft + viewportWidth + 96
          )
            return null;
          return (
            <button
              key={clip.id}
              type="button"
              data-transcription-clip={clip.id}
              aria-label={`Draft: ${clip.text}, ${formatTime(clip.start, true)} to ${formatTime(clip.start + clip.duration, true)}`}
              title="Draft transcription · click to seek · timing and text may change"
              className="absolute inset-y-1 overflow-hidden rounded border border-dashed border-primary/70 bg-primary/15 text-left text-[10px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
              style={{ left, width: clipWidth }}
              onPointerDown={(event) => event.stopPropagation()}
              onClick={() => onSeek(clip.start)}
            >
              <span className="absolute inset-x-0 top-0 truncate bg-black/20 px-1.5 py-1 text-[8px] text-primary">
                Draft · {formatTime(clip.start, true)}
              </span>
              <span className="absolute inset-x-0 top-7 truncate px-2 text-xs">
                {clip.text}
              </span>
            </button>
          );
        })}
        {!clips.length && (
          <span
            className="absolute top-7 left-3 text-[10px] text-muted-foreground"
            style={{ transform: `translateX(${scrollLeft}px)` }}
          >
            Dialogue clips appear as speech is recognized…
          </span>
        )}
      </div>
    </>
  );
}
