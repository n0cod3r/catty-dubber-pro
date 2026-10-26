import { Fit, Minus, Plus, Scissors } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import type { EpisodeMedia } from "../../features/episodes/types";
import { Badge } from "../ui/badge";
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
  if (visible <= 15) return 1;
  if (visible <= 40) return 5;
  if (visible <= 120) return 10;
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
  const duration = Math.max(episode?.durationSeconds ?? 0, 1);
  const contentWidth = Math.max(100, zoom * 100);
  const step = rulerStep(duration, zoom);

  const ticks = useMemo(() => {
    const values: number[] = [];
    for (let value = 0; value <= duration; value += step) values.push(value);
    if (values.at(-1) !== duration) values.push(duration);
    return values;
  }, [duration, step]);

  function seekFromPointer(clientX: number) {
    const viewport = viewportRef.current;
    if (!viewport || !episode) return;
    const rect = viewport.getBoundingClientRect();
    const x = clientX - rect.left + viewport.scrollLeft;
    const totalWidth = viewport.scrollWidth;
    onSeek(Math.max(0, Math.min(duration, (x / totalWidth) * duration)));
  }

  const playheadLeft = `${(currentTime / duration) * 100}%`;

  return (
    <section className="flex min-h-[190px] flex-col border-t border-catty-border bg-[#11100e]">
      <div className="flex h-9 shrink-0 items-center justify-between border-b border-catty-border px-2.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-semibold text-catty-text-soft">Timeline</span>
          <Badge tone="accent">{formatClock(currentTime)}</Badge>
          {episode && <span className="text-[8px] text-catty-muted-2">{formatClock(duration)}</span>}
        </div>
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon" aria-label="Split"><Scissors size={11} /></Button>
          <span className="mx-1 h-3.5 w-px bg-catty-border" />
          <Button variant="ghost" size="icon" aria-label="Zoom out" onClick={() => setZoom((value) => Math.max(1, value / 1.35))}><Minus size={11} /></Button>
          <span className="w-9 text-center text-[8px] tabular-nums text-catty-muted">{Math.round(zoom * 100)}%</span>
          <Button variant="ghost" size="icon" aria-label="Zoom in" onClick={() => setZoom((value) => Math.min(12, value * 1.35))}><Plus size={11} /></Button>
          <Button variant="ghost" size="icon" aria-label="Fit timeline" onClick={() => setZoom(1)}><Fit size={11} /></Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[108px_minmax(0,1fr)]">
        <div className="border-r border-catty-border-subtle bg-catty-panel/45">
          <div className="h-6 border-b border-catty-border-subtle" />
          {tracks.map((track) => (
            <div className="flex h-[42px] flex-col justify-center border-b border-catty-border-subtle px-2" key={track.name}>
              <span className="text-[8px] font-semibold tracking-wide text-catty-text-soft">{track.name}</span>
              <span className="mt-0.5 text-[7px] text-catty-muted-2">{track.label}</span>
            </div>
          ))}
        </div>

        <div ref={viewportRef} className="min-w-0 overflow-x-auto overflow-y-hidden" onWheel={(event) => {
          if (!event.ctrlKey && !event.metaKey) return;
          event.preventDefault();
          setZoom((value) => Math.max(1, Math.min(12, value * (event.deltaY > 0 ? 0.9 : 1.1))));
        }}>
          <div className="relative min-w-full" style={{ width: `${contentWidth}%` }}>
            <div className="relative h-6 cursor-pointer border-b border-catty-border-subtle bg-[#0f0e0d]" onPointerDown={(event) => seekFromPointer(event.clientX)}>
              {ticks.map((tick) => (
                <div className="absolute inset-y-0 border-l border-catty-border-subtle" key={tick} style={{ left: `${(tick / duration) * 100}%` }}>
                  <span className="absolute left-1 top-1 text-[7px] tabular-nums text-catty-muted-2">{formatClock(tick).slice(0, 5)}</span>
                </div>
              ))}
            </div>

            {tracks.map((track, index) => (
              <div className="relative h-[42px] border-b border-catty-border-subtle px-1 py-1" key={track.name} onPointerDown={(event) => seekFromPointer(event.clientX)}>
                {ticks.map((tick) => <div key={tick} className="pointer-events-none absolute inset-y-0 border-l border-catty-border-subtle/55" style={{ left: `${(tick / duration) * 100}%` }} />)}
                {episode && index === 0 && (
                  <div className={`absolute inset-y-1 left-1 right-1 overflow-hidden rounded-[4px] border ${track.tone}`}>
                    <div className="flex h-full items-center px-2 text-[8px] font-medium text-[#e9ddd4]">
                      <span className="max-w-[60%] truncate">{episode.name}</span>
                      <span className="ml-auto text-[7px] text-white/45">{formatClock(duration)}</span>
                    </div>
                  </div>
                )}
                {episode && index === 1 && (
                  <div className={`absolute inset-y-1 left-1 right-1 overflow-hidden rounded-[4px] border ${track.tone}`}>
                    <div className="flex h-full items-center gap-[3px] px-1 opacity-55">
                      {Array.from({ length: 90 }).map((_, bar) => <span key={bar} className="w-px bg-[#8eb89c]" style={{ height: `${20 + ((bar * 17) % 70)}%` }} />)}
                    </div>
                  </div>
                )}
              </div>
            ))}

            <div className="pointer-events-none absolute bottom-0 top-0 z-20 w-px bg-catty-accent" style={{ left: playheadLeft }}>
              <div className="absolute -left-[4px] top-0 size-[9px] rotate-45 rounded-[2px] bg-catty-accent" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
