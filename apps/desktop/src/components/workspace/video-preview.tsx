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
import { PreviewFrame } from "@/components/workspace/preview-frame";
import { PreviewLayers } from "@/components/workspace/preview-layers";
import { TimelineAudio } from "@/components/workspace/timeline-audio";
import type { EpisodeMedia } from "@/features/episodes/types";
import { useClipMediaSync } from "@/features/playback/use-clip-media-sync";
import { formatTime } from "@/features/timeline/geometry";
import type { TimelineDocument } from "@/features/timeline/model";
import { activeVideoAt } from "@/features/timeline/preview";

type VideoPreviewProps = {
  document: TimelineDocument;
  episode: EpisodeMedia | null;
  currentTime: number;
  duration: number;
  playing: boolean;
  onPlayingChange: (value: boolean) => void;
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
  duration,
  playing,
  onPlayingChange,
  onSeek,
  onMetadata,
  muted,
  onMuteChange,
  onImport,
  importing,
}: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mediaError, setMediaError] = useState(false);
  const src = episode
    ? episode.path.startsWith("blob:")
      ? episode.path
      : convertFileSrc(episode.path)
    : undefined;
  const ready = duration > 0 && !mediaError;
  const activeVideo = activeVideoAt(document, currentTime, episode ? [episode] : []);
  const pictureVisible = activeVideo !== null;
  const frameSource = activeVideo?.source ?? episode;
  const reportPlaybackError = useCallback(
    (message: string) => {
      setNotice(message);
      onPlayingChange(false);
    },
    [onPlayingChange],
  );
  useClipMediaSync(
    videoRef,
    activeVideo ? activeVideo.clip.sourceStart + currentTime - activeVideo.clip.start : null,
    playing,
    activeVideo?.clip.id,
    reportPlaybackError,
  );
  const togglePlayback = useCallback(() => {
    if (!ready) return;
    setNotice(null);
    if (!playing && currentTime >= duration) onSeek(0);
    onPlayingChange(!playing);
  }, [currentTime, duration, onPlayingChange, onSeek, playing, ready]);
  const audibleClips = document.clips.filter(
    (clip) =>
      clip.kind === "audio" &&
      clip.sourceId === episode?.id &&
      currentTime >= clip.start &&
      currentTime < clip.start + clip.duration &&
      document.layers.some((layer) => layer.id === clip.trackId && !layer.muted),
  );

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
          currentTime +
            (event.key === "ArrowRight" ? 1 : -1) *
              (event.shiftKey
                ? 5
                : 1 /
                  (episode?.fps && Number.isFinite(episode.fps) && episode.fps > 0
                    ? episode.fps
                    : 30)),
        );
      }
      if (event.key === "Home" || event.key === "End") {
        event.preventDefault();
        onSeek(event.key === "Home" ? 0 : duration);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [currentTime, duration, episode?.fps, onSeek, ready, togglePlayback]);

  async function fullscreen() {
    try {
      await videoRef.current?.requestFullscreen();
    } catch {
      setNotice("Fullscreen is unavailable in this window.");
    }
  }

  return (
    <section
      className="@container flex min-h-0 min-w-0 flex-1 flex-col bg-background"
      aria-label="Video preview"
    >
      <div className="flex h-9 shrink-0 items-center gap-2 border-b bg-card px-3 text-[11px]">
        <Film className="size-3.5 text-muted-foreground" />
        <span className="font-medium">Preview</span>
        <span className="ml-auto truncate text-[10px] text-muted-foreground">
          {episode
            ? episode.width && episode.height
              ? `${frameSource?.width} × ${frameSource?.height}${activeVideo ? " · Timeline" : ""}`
              : "Reading media…"
            : "No media loaded"}
        </span>
      </div>
      <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-black/30">
        {src ? (
          <PreviewFrame source={frameSource}>
            {(frameWidth) => (
              <>
                <video
                  ref={videoRef}
                  src={src}
                  preload="metadata"
                  muted
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
                  onError={() => {
                    setMediaError(true);
                    onPlayingChange(false);
                    setNotice(
                      "This video could not be loaded. Check the file or try MP4 (H.264) or WebM.",
                    );
                  }}
                />
                <PreviewLayers
                  document={document}
                  currentTime={currentTime}
                  width={frameWidth}
                  frontVideoIndex={activeVideo?.layerIndex ?? -1}
                />
              </>
            )}
          </PreviewFrame>
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
        {src &&
          audibleClips.map((clip) => (
            <TimelineAudio
              key={clip.id}
              clip={clip}
              src={src}
              currentTime={currentTime}
              playing={playing}
              muted={muted}
              onError={reportPlaybackError}
            />
          ))}
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
      <div className="flex h-11 shrink-0 items-center justify-center gap-1 border-t bg-card px-2">
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
        <span className="mx-1 whitespace-nowrap font-mono text-[10px] tabular-nums">
          {formatTime(currentTime, true)}
          <span className="ml-2 hidden text-muted-foreground @min-[420px]:inline">
            / {formatTime(duration)}
          </span>
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
