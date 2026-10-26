import { useCallback, useEffect, useRef, useState } from "react";

import { convertFileSrc } from "@tauri-apps/api/core";
import {
  AlertTriangle,
  Film,
  Maximize2,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Upload,
  Volume2,
  VolumeX,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { PreviewLayers } from "@/components/workspace/preview-layers";
import type { EpisodeMedia } from "@/features/episodes/types";
import { clamp, formatTime } from "@/features/timeline/geometry";
import type { TimelineDocument } from "@/features/timeline/model";

type VideoPreviewProps = {
  document: TimelineDocument;
  episode: EpisodeMedia | null;
  currentTime: number;
  seekRequest: { time: number; nonce: number } | null;
  onTimeChange: (time: number) => void;
  onSeek: (time: number) => void;
  onMetadata: (metadata: Pick<EpisodeMedia, "durationSeconds" | "width" | "height">) => void;
  muted: boolean;
  onMuteChange: (muted: boolean) => void;
  onImport: () => void;
  importing: boolean;
};

export function VideoPreview({
  episode,
  document,
  currentTime,
  seekRequest,
  onTimeChange,
  onSeek,
  onMetadata,
  muted,
  onMuteChange,
  onImport,
  importing,
}: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [mediaError, setMediaError] = useState(false);
  const duration = episode?.durationSeconds ?? 0;
  const src = episode
    ? episode.path.startsWith("blob:")
      ? episode.path
      : convertFileSrc(episode.path)
    : undefined;
  const ready = duration > 0 && !mediaError;
  const pictureVisible = document.layers.some(
    (layer) =>
      layer.kind === "video" &&
      !layer.hidden &&
      document.clips.some(
        (clip) =>
          clip.trackId === layer.id &&
          currentTime >= clip.start &&
          currentTime <= clip.start + clip.duration,
      ),
  );
  const audioAudible = document.layers.some(
    (layer) =>
      layer.kind === "audio" &&
      !layer.muted &&
      document.clips.some(
        (clip) =>
          clip.trackId === layer.id &&
          currentTime >= clip.start &&
          currentTime <= clip.start + clip.duration,
      ),
  );

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !seekRequest || video.readyState < 1) return;
    video.currentTime = clamp(
      seekRequest.time,
      0,
      Number.isFinite(video.duration) ? video.duration : 0,
    );
  }, [seekRequest]);

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => {
      const video = videoRef.current;
      if (video) onTimeChange(video.currentTime);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [onTimeChange, playing]);

  const togglePlayback = useCallback(async () => {
    const video = videoRef.current;
    if (!video || !ready) return;
    try {
      setNotice(null);
      if (video.paused) await video.play();
      else video.pause();
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setNotice("Playback could not start. Try Play again or import a supported video.");
    }
  }, [ready]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || !ready)
        return;
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        target.closest(
          "input, textarea, select, button, a, [contenteditable]:not([contenteditable=false]), [role=slider], [role=separator]",
        )
      )
        return;
      if (event.code === "Space") {
        event.preventDefault();
        if (!event.repeat) void togglePlayback();
      }
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        onSeek(
          (videoRef.current?.currentTime ?? 0) +
            (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 5 : 1 / 30),
        );
      }
      if (event.key === "Home" || event.key === "End") {
        event.preventDefault();
        onSeek(event.key === "Home" ? 0 : duration);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [duration, onSeek, ready, togglePlayback]);

  async function fullscreen() {
    try {
      await videoRef.current?.requestFullscreen();
    } catch {
      setNotice("Fullscreen is unavailable in this window.");
    }
  }

  return (
    <section
      className="flex min-h-0 min-w-0 flex-col border-r bg-background"
      aria-label="Video preview"
    >
      <div className="flex h-9 shrink-0 items-center gap-2 border-b bg-card px-3 text-[11px]">
        <Film className="size-3.5 text-muted-foreground" />
        <span className="font-medium">Preview</span>
        <span className="ml-auto truncate text-[10px] text-muted-foreground">
          {episode
            ? episode.width && episode.height
              ? `${episode.width} × ${episode.height}`
              : "Reading media…"
            : "No media loaded"}
        </span>
      </div>
      <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-black/30 p-5">
        {src ? (
          <video
            ref={videoRef}
            src={src}
            preload="metadata"
            muted={muted || !audioAudible}
            playsInline
            aria-label={episode?.name}
            className="size-full object-contain"
            style={{ visibility: pictureVisible ? "visible" : "hidden" }}
            onLoadedMetadata={(event) => {
              const video = event.currentTarget;
              if (!Number.isFinite(video.duration) || video.duration <= 0) {
                setMediaError(true);
                setNotice("This media has no valid duration. Import a finite video file.");
                return;
              }
              setMediaError(false);
              setNotice(null);
              onMetadata({
                durationSeconds: video.duration,
                width: video.videoWidth,
                height: video.videoHeight,
              });
            }}
            onTimeUpdate={(event) => onTimeChange(event.currentTarget.currentTime)}
            onSeeked={(event) => onTimeChange(event.currentTarget.currentTime)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onError={() => {
              setMediaError(true);
              setPlaying(false);
              setNotice(
                "This video could not be loaded. Check the file or try MP4 (H.264) or WebM.",
              );
            }}
          />
        ) : (
          <div className="max-w-xs text-center">
            <div className="mx-auto mb-4 grid size-14 place-items-center rounded-xl border bg-card">
              <Film className="size-6 text-muted-foreground" strokeWidth={1.3} />
            </div>
            <h2 className="text-sm font-medium">Your story starts here</h2>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              Import an episode to preview the source video and build your Khmer dubbing timeline.
            </p>
            <Button className="mt-5" size="sm" onClick={onImport} disabled={importing}>
              <Upload />
              Import episode
            </Button>
            <p className="mt-3 text-[10px] text-muted-foreground">MP4, MOV, MKV, WebM, M4V, AVI</p>
          </div>
        )}
        <PreviewLayers document={document} currentTime={currentTime} episode={episode} />
        {notice && (
          <div
            role="alert"
            className="absolute right-4 bottom-4 left-4 flex items-start gap-2 rounded-lg border bg-popover p-3 text-xs shadow-lg"
          >
            <AlertTriangle className="size-4 shrink-0 text-primary" />
            <span className="flex-1">{notice}</span>
            {mediaError ? (
              <Button
                size="xs"
                variant="outline"
                onClick={() => {
                  setNotice(null);
                  setMediaError(false);
                  videoRef.current?.load();
                }}
              >
                Retry
              </Button>
            ) : (
              <Button size="xs" variant="ghost" onClick={() => setNotice(null)}>
                Dismiss
              </Button>
            )}
          </div>
        )}
      </div>
      <div className="flex h-11 shrink-0 items-center justify-center gap-2 border-t bg-card px-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Back 5 seconds"
          disabled={!ready}
          onClick={() => onSeek(currentTime - 5)}
        >
          <SkipBack />
        </Button>
        <Button
          variant={playing ? "secondary" : "ghost"}
          size="icon-sm"
          aria-label={playing ? "Pause" : "Play"}
          title="Play / pause (Space)"
          disabled={!ready}
          onClick={() => void togglePlayback()}
        >
          {playing ? <Pause /> : <Play />}
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Forward 5 seconds"
          disabled={!ready}
          onClick={() => onSeek(currentTime + 5)}
        >
          <SkipForward />
        </Button>
        <span className="mx-2 whitespace-nowrap font-mono text-[10px] tabular-nums">
          {formatTime(currentTime, true)}
          <span className="ml-2 text-muted-foreground">/ {formatTime(duration)}</span>
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={muted ? "Unmute preview" : "Mute preview"}
          aria-pressed={muted}
          disabled={!episode}
          onClick={() => onMuteChange(!muted)}
        >
          {muted ? <VolumeX /> : <Volume2 />}
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Fullscreen preview"
          disabled={!ready}
          onClick={() => void fullscreen()}
        >
          <Maximize2 />
        </Button>
      </div>
    </section>
  );
}
