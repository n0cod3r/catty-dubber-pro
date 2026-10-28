import { memo, useEffect, useRef, useState } from "react";

import { convertFileSrc } from "@tauri-apps/api/core";
import { LoaderCircle, Play, Square } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatTime } from "@/shared/utils/time";

import { TIMELINE } from "../constants";
import {
  subscribeDubWaveform,
  type DubWaveform,
} from "../services/dub-waveforms";
import type { PipelineClip } from "../utils/pipeline-clips";

function audioUrl(path: string, root: string, version?: string) {
  const absolute = /^(\/|[A-Za-z]:[\\/]|\\\\)/.test(path)
    ? path
    : `${root}/${path}`;
  return `${convertFileSrc(absolute)}?v=${encodeURIComponent(version ?? "")}`;
}

function DubWave({ url, duration }: { url: string; duration: number }) {
  const [wave, setWave] = useState<DubWaveform | null>(null);
  useEffect(() => {
    setWave(null);
    return subscribeDubWaveform(url, duration, setWave);
  }, [url, duration]);
  if (!wave || wave.error)
    return (
      <span className="absolute bottom-1 left-1 text-[8px] text-muted-foreground">
        {wave?.error ?? "Decoding waveform…"}
      </span>
    );
  return (
    <svg
      aria-label="Generated speech waveform"
      className="pointer-events-none absolute inset-x-0 bottom-1 h-8 w-full text-emerald-300"
      viewBox="0 0 128 32"
      preserveAspectRatio="none"
    >
      <path
        stroke="currentColor"
        strokeWidth="0.7"
        d={wave.bars
          .map((peak, index) => `M${index} ${16 - peak * 15}V${16 + peak * 15}`)
          .join(" ")}
      />
    </svg>
  );
}

export const PipelineTrack = memo(function PipelineTrack({
  name,
  status,
  clips,
  duration,
  width,
  scrollLeft,
  viewportWidth,
  projectDirectory,
  onSeek,
}: {
  name: string;
  status: string;
  clips: PipelineClip[];
  duration: number;
  width: number;
  scrollLeft: number;
  viewportWidth: number;
  projectDirectory: string;
  onSeek: (time: number) => void;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioKeyRef = useRef<string | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);
  const playable = JSON.stringify(
    clips
      .filter((clip) => clip.audioPath)
      .map((clip) =>
        JSON.stringify([clip.id, clip.audioVersion, clip.audioPath]),
      ),
  );
  useEffect(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    setPlaying(null);
    return () => {
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, [projectDirectory]);
  useEffect(() => {
    if (
      audioKeyRef.current &&
      !(JSON.parse(playable) as string[]).includes(audioKeyRef.current)
    ) {
      audioRef.current?.pause();
      audioRef.current = null;
      audioKeyRef.current = null;
      setPlaying(null);
    }
  }, [playable]);
  async function audition(clip: PipelineClip) {
    audioRef.current?.pause();
    if (playing === clip.id) {
      audioRef.current = null;
      audioKeyRef.current = null;
      setPlaying(null);
      return;
    }
    if (!clip.audioPath) return;
    setAudioError(null);
    const audio = new Audio(
      audioUrl(clip.audioPath, projectDirectory, clip.audioVersion),
    );
    audioRef.current = audio;
    audioKeyRef.current = JSON.stringify([
      clip.id,
      clip.audioVersion,
      clip.audioPath,
    ]);
    setPlaying(clip.id);
    audio.onended = () => {
      if (audioRef.current === audio) setPlaying(null);
    };
    try {
      await audio.play();
    } catch {
      if (audioRef.current === audio) {
        setPlaying(null);
        setAudioError("Cannot play generated audio");
      }
    }
  }
  return (
    <>
      <div className="sticky left-0 z-30 flex flex-col justify-center gap-1 border-r border-b bg-card px-2">
        <span className="text-[10px] font-medium">{name}</span>
        <span role="status" className="text-[9px] text-muted-foreground">
          {status}
        </span>
        <span className="text-[8px] text-muted-foreground">
          {clips.length} clips · read-only
        </span>
        {audioError && (
          <span role="alert" className="text-[8px] text-destructive">
            {audioError}
          </span>
        )}
      </div>
      <div
        data-timeline-surface
        aria-label={name}
        className="relative touch-none overflow-hidden border-b bg-muted/5"
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
          const working =
            clip.status === "Generating" || clip.status === "Translating";
          return (
            <div
              key={clip.id}
              data-pipeline-clip={clip.id}
              className={cn(
                "absolute inset-y-1 overflow-hidden rounded border",
                clip.audioPath
                  ? "border-emerald-600/70 bg-emerald-950/60"
                  : "border-blue-500/60 bg-blue-950/40",
                working && "border-dashed border-primary",
                clip.status === "Failed" && "border-destructive",
              )}
              style={{ left, width: clipWidth }}
            >
              <button
                type="button"
                className="absolute inset-0 w-full text-left outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                aria-label={`${name}: ${clip.text}, ${clip.status}, ${formatTime(clip.start, true)}`}
                title={`${clip.status} · ${clip.text} · click to seek`}
                onPointerDown={(event) => event.stopPropagation()}
                onClick={() => onSeek(clip.start)}
              >
                <span className="absolute inset-x-0 top-0 flex h-5 items-center gap-1 truncate bg-black/25 px-1 text-[8px]">
                  {working && (
                    <LoaderCircle className="size-2.5 shrink-0 animate-spin motion-reduce:animate-none" />
                  )}
                  {clip.status} · {formatTime(clip.duration, true)}
                </span>
                {!clip.audioPath && (
                  <span className="absolute inset-x-0 top-7 truncate px-2 text-xs">
                    {clip.text}
                  </span>
                )}
                {clip.audioPath && (
                  <DubWave
                    key={clip.audioVersion + clip.audioPath}
                    url={audioUrl(
                      clip.audioPath,
                      projectDirectory,
                      clip.audioVersion,
                    )}
                    duration={clip.duration}
                  />
                )}
              </button>
              {clip.audioPath && (
                <button
                  type="button"
                  aria-label={`${playing === clip.id ? "Stop" : "Play"} generated speech: ${clip.text}`}
                  title="Preview generated speech"
                  className="absolute top-0 right-0 z-10 rounded bg-black/70 p-1 text-emerald-200"
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={() => void audition(clip)}
                >
                  {playing === clip.id ? (
                    <Square className="size-3" />
                  ) : (
                    <Play className="size-3" />
                  )}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
});
