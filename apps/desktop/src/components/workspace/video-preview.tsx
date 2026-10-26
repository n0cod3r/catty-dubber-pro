import { convertFileSrc } from "@tauri-apps/api/core";
import { Maximize2, Pause, Play, SkipBack, SkipForward, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { EpisodeMedia } from "../../features/episodes/types";
import { Button } from "../ui/button";

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds)) return "00:00:00.000";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

type VideoPreviewProps = {
  episode: EpisodeMedia | null;
  currentTime: number;
  seekRequest: { time: number; nonce: number } | null;
  onTimeChange: (time: number) => void;
  onMetadata: (metadata: Pick<EpisodeMedia, "durationSeconds" | "width" | "height">) => void;
};

export function VideoPreview({ episode, currentTime, seekRequest, onTimeChange, onMetadata }: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  const src = episode ? convertFileSrc(episode.path) : null;
  const duration = episode?.durationSeconds ?? 0;
  const progress = duration > 0 ? Math.min(100, (currentTime / duration) * 100) : 0;

  useEffect(() => {
    setPlaying(false);
  }, [episode?.id]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !seekRequest) return;
    if (Math.abs(video.currentTime - seekRequest.time) > 0.01) video.currentTime = seekRequest.time;
  }, [seekRequest]);

  async function togglePlayback() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) await video.play();
    else video.pause();
  }

  function seekRelative(delta: number) {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(0, Math.min(duration, video.currentTime + delta));
    onTimeChange(video.currentTime);
  }

  return (
    <section className="flex min-h-0 flex-col border-r border-catty-border bg-[#0d0c0b]">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-catty-border px-2.5">
        <span className="text-[9px] font-medium text-catty-text-soft">Preview</span>
        <span className="max-w-[55%] truncate text-[8px] text-catty-muted-2">{episode?.name ?? "No media loaded"}</span>
      </div>

      <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-black/40 p-3">
        <div className="flex size-full max-h-full max-w-[900px] items-center justify-center overflow-hidden rounded-catty-lg border border-catty-border-subtle bg-[#080807] shadow-2xl">
          {src ? (
            <video
              ref={videoRef}
              className="size-full object-contain"
              src={src}
              onLoadedMetadata={(event) => {
                const video = event.currentTarget;
                onMetadata({ durationSeconds: video.duration, width: video.videoWidth, height: video.videoHeight });
              }}
              onTimeUpdate={(event) => onTimeChange(event.currentTarget.currentTime)}
              onSeeked={(event) => onTimeChange(event.currentTarget.currentTime)}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onEnded={() => setPlaying(false)}
            />
          ) : (
            <div className="text-center">
              <div className="mx-auto mb-2 grid size-9 place-items-center rounded-full border border-catty-border bg-catty-panel text-catty-muted"><Play size={15} fill="currentColor" /></div>
              <p className="text-[10px] text-catty-muted">Import an episode to preview video</p>
            </div>
          )}
        </div>
      </div>

      <div className="flex h-10 shrink-0 items-center gap-1.5 border-t border-catty-border px-2.5">
        <Button variant="ghost" size="icon" aria-label="Back 5 seconds" disabled={!episode} onClick={() => seekRelative(-5)}><SkipBack size={13} /></Button>
        <Button variant="ghost" size="icon" aria-label={playing ? "Pause" : "Play"} disabled={!episode} onClick={togglePlayback}>{playing ? <Pause size={13} /> : <Play size={13} />}</Button>
        <Button variant="ghost" size="icon" aria-label="Forward 5 seconds" disabled={!episode} onClick={() => seekRelative(5)}><SkipForward size={13} /></Button>
        <span className="ml-1 font-mono text-[9px] text-catty-text-soft">{formatTime(currentTime)}</span>
        <span className="text-[9px] text-catty-muted-2">/ {formatTime(duration)}</span>
        <button
          className="mx-2 h-1 flex-1 overflow-hidden rounded-full bg-catty-surface"
          disabled={!episode || duration <= 0}
          aria-label="Seek video"
          onClick={(event) => {
            const video = videoRef.current;
            if (!video || duration <= 0) return;
            const rect = event.currentTarget.getBoundingClientRect();
            video.currentTime = ((event.clientX - rect.left) / rect.width) * duration;
            onTimeChange(video.currentTime);
          }}
        >
          <div className="h-full bg-catty-accent" style={{ width: `${progress}%` }} />
        </button>
        <Volume2 size={13} className="text-catty-muted" />
        <Button variant="ghost" size="icon" aria-label="Fullscreen" disabled={!episode} onClick={() => videoRef.current?.requestFullscreen()}><Maximize2 size={13} /></Button>
      </div>
    </section>
  );
}
