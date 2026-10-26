import { useMemo, useRef, useState } from "react";

import { Lock, Magnet, Minus, Plus, Scan, Scissors, Volume2 } from "lucide-react";

import type { EpisodeMedia } from "../../features/episodes/types";
import { Button } from "../ui/button";

const tracks = [
  { name: "VIDEO", label: "Video", tone: "bg-[#493225] border-[#805137]" },
  { name: "SOURCE AUDIO", label: "Original audio", tone: "bg-[#26382f] border-[#3d624d]" },
  { name: "DIALOGUE", label: "Transcript", tone: "bg-[#282d3b] border-[#414b69]" },
  { name: "KHMER DUB", label: "Generated dub", tone: "bg-[#3b2c3c] border-[#68486a]" },
];

function formatClock(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

function rulerStep(duration: number, zoom: number) {
  const visible = duration / zoom;
  if (visible <= 12) return 1;
  if (visible <= 30) return 2;
  if (visible <= 70) return 5;
  if (visible <= 160) return 10;
  return 30;
}

type TimelineProps = {
  episode: EpisodeMedia | null;
  currentTime: number;
  onSeek: (time: number) => void;
};

export function Timeline({ episode, currentTime, onSeek }: TimelineProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [snap, setSnap] = useState(true);
  const [draggingPlayhead, setDraggingPlayhead] = useState(false);
  const duration = Math.max(episode?.durationSeconds ?? 0, 1);
  const contentWidth = Math.max(100, zoom * 100);
  const step = rulerStep(duration, zoom);

  const ticks = useMemo(() => {
    const values: number[] = [];
    for (let value = 0; value <= duration; value += step) values.push(value);
    if (values.at(-1) !== duration) values.push(duration);
    return values;
  }, [duration, step]);

  function timeFromPointer(clientX: number) {
    const viewport = viewportRef.current;
    if (!viewport || !episode) return null;
    const rect = viewport.getBoundingClientRect();
    const x = clientX - rect.left + viewport.scrollLeft;
    return Math.max(0, Math.min(duration, (x / viewport.scrollWidth) * duration));
  }

  function seekFromPointer(clientX: number) {
    const time = timeFromPointer(clientX);
    if (time !== null) onSeek(time);
  }

  function startScrub(event: React.PointerEvent) {
    if (!episode) return;
    setDraggingPlayhead(true);
    seekFromPointer(event.clientX);
    const move = (moveEvent: PointerEvent) => seekFromPointer(moveEvent.clientX);
    const up = () => {
      setDraggingPlayhead(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  const playheadLeft = `${(currentTime / duration) * 100}%`;

  return (
    <section className="flex h-full min-h-0 flex-col bg-[#11100e] select-none">
      <div className="flex h-9 shrink-0 items-center border-b border-catty-border bg-[#151310] px-2">
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon" aria-label="Split">
            <Scissors size={12} />
          </Button>
          <Button
            variant={snap ? "default" : "ghost"}
            size="icon"
            aria-label="Toggle snapping"
            onClick={() => setSnap((value) => !value)}
          >
            <Magnet size={12} />
          </Button>
          <span className="mx-1 h-4 w-px bg-catty-border" />
          <span className="min-w-[72px] font-mono text-[9px] tabular-nums text-catty-text-soft">
            {formatClock(currentTime)}
          </span>
          <span className="text-[8px] text-catty-muted-2">
            / {episode ? formatClock(duration) : "00:00.000"}
          </span>
        </div>

        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom out"
            onClick={() => setZoom((value) => Math.max(1, value / 1.25))}
          >
            <Minus size={12} />
          </Button>
          <input
            className="h-1 w-24 cursor-pointer accent-current"
            type="range"
            min="1"
            max="12"
            step="0.05"
            value={zoom}
            aria-label="Timeline zoom"
            onChange={(event) => setZoom(Number(event.target.value))}
          />
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom in"
            onClick={() => setZoom((value) => Math.min(12, value * 1.25))}
          >
            <Plus size={12} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Fit timeline"
            onClick={() => {
              setZoom(1);
              viewportRef.current?.scrollTo({ left: 0 });
            }}
          >
            <Scan size={12} />
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[132px_minmax(0,1fr)] overflow-hidden">
        <div className="z-30 border-r border-catty-border-subtle bg-[#151411]">
          <div className="flex h-7 items-center border-b border-catty-border-subtle px-2 text-[8px] font-medium text-catty-muted-2">
            TRACKS
          </div>
          {tracks.map((track, index) => (
            <div
              className="flex h-[46px] items-center gap-2 border-b border-catty-border-subtle px-2"
              key={track.name}
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-[8px] font-semibold tracking-wide text-catty-text-soft">
                  {track.name}
                </div>
                <div className="mt-0.5 truncate text-[7px] text-catty-muted-2">{track.label}</div>
              </div>
              {(index === 1 || index === 3) && <Volume2 size={10} className="text-catty-muted-2" />}
              <Lock size={9} className="text-catty-muted-2/55" />
            </div>
          ))}
        </div>

        <div
          ref={viewportRef}
          className="min-h-0 min-w-0 overflow-auto bg-[#0e0d0c]"
          onWheel={(event) => {
            if (!event.ctrlKey && !event.metaKey) return;
            event.preventDefault();
            setZoom((value) => Math.max(1, Math.min(12, value * (event.deltaY > 0 ? 0.9 : 1.1))));
          }}
        >
          <div className="relative min-h-full min-w-full" style={{ width: `${contentWidth}%` }}>
            <div
              className="sticky top-0 z-20 h-7 cursor-ew-resize border-b border-catty-border-subtle bg-[#12110f]"
              onPointerDown={startScrub}
            >
              {ticks.map((tick) => (
                <div
                  className="absolute bottom-0 top-0 border-l border-catty-border-subtle"
                  key={tick}
                  style={{ left: `${(tick / duration) * 100}%` }}
                >
                  <span className="absolute left-1 top-1 text-[7px] tabular-nums text-catty-muted-2">
                    {formatClock(tick).slice(0, 5)}
                  </span>
                  <span className="absolute bottom-0 left-0 h-1.5 border-l border-catty-muted-2/60" />
                </div>
              ))}
            </div>

            {tracks.map((track, index) => (
              <div
                className="relative h-[46px] border-b border-catty-border-subtle"
                key={track.name}
                onPointerDown={startScrub}
              >
                {ticks.map((tick) => (
                  <div
                    key={tick}
                    className="pointer-events-none absolute inset-y-0 border-l border-catty-border-subtle/40"
                    style={{ left: `${(tick / duration) * 100}%` }}
                  />
                ))}
                {episode && index === 0 && (
                  <div
                    className={`absolute inset-y-[4px] left-[3px] right-[3px] overflow-hidden rounded-[3px] border ${track.tone}`}
                  >
                    <div className="flex h-full items-center px-2 text-[8px] font-medium text-[#e9ddd4]">
                      <span className="max-w-[70%] truncate">{episode.name}</span>
                      <span className="ml-auto text-[7px] text-white/45">
                        {formatClock(duration)}
                      </span>
                    </div>
                  </div>
                )}
                {episode && index === 1 && (
                  <div
                    className={`absolute inset-y-[4px] left-[3px] right-[3px] overflow-hidden rounded-[3px] border ${track.tone}`}
                  >
                    <div className="flex h-full items-center gap-[2px] px-1 opacity-65">
                      {Array.from({ length: 140 }).map((_, bar) => (
                        <span
                          key={bar}
                          className="min-w-px flex-1 bg-[#8eb89c]"
                          style={{ height: `${15 + ((bar * 29) % 75)}%` }}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {episode && (
              <div
                className={`pointer-events-none absolute bottom-0 top-0 z-40 w-px ${draggingPlayhead ? "bg-[#ffb16f]" : "bg-catty-accent"}`}
                style={{ left: playheadLeft }}
              >
                <div className="absolute -left-[5px] top-0 h-3 w-[11px] rounded-b-[3px] bg-catty-accent" />
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
