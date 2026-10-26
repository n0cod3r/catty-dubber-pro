import { Maximize2, Pause, Play, SkipBack, SkipForward, Volume2 } from "lucide-react";

import { Button } from "../ui/button";

export function VideoPreview() {
  return (
    <section className="flex min-h-0 flex-col border-r border-catty-border bg-[#0d0c0b]">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-catty-border px-2.5">
        <span className="text-[9px] font-medium text-catty-text-soft">Preview</span>
        <span className="text-[8px] text-catty-muted-2">No media loaded</span>
      </div>

      <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-black/40 p-4">
        <div className="flex aspect-video w-full max-w-[720px] items-center justify-center rounded-catty-lg border border-catty-border-subtle bg-[#080807] shadow-2xl">
          <div className="text-center">
            <div className="mx-auto mb-2 grid size-9 place-items-center rounded-full border border-catty-border bg-catty-panel text-catty-muted">
              <Play size={15} fill="currentColor" />
            </div>
            <p className="text-[10px] text-catty-muted">Import an episode to preview video</p>
          </div>
        </div>
      </div>

      <div className="flex h-10 shrink-0 items-center gap-1.5 border-t border-catty-border px-2.5">
        <Button variant="ghost" size="icon" aria-label="Previous"><SkipBack size={13} /></Button>
        <Button variant="ghost" size="icon" aria-label="Play"><Play size={13} /></Button>
        <Button variant="ghost" size="icon" aria-label="Pause"><Pause size={13} /></Button>
        <Button variant="ghost" size="icon" aria-label="Next"><SkipForward size={13} /></Button>
        <span className="ml-1 font-mono text-[9px] text-catty-text-soft">00:00:00.000</span>
        <span className="text-[9px] text-catty-muted-2">/ 00:00:00.000</span>
        <div className="mx-2 h-1 flex-1 overflow-hidden rounded-full bg-catty-surface">
          <div className="h-full w-0 bg-catty-accent" />
        </div>
        <Volume2 size={13} className="text-catty-muted" />
        <Button variant="ghost" size="icon" aria-label="Fullscreen"><Maximize2 size={13} /></Button>
      </div>
    </section>
  );
}
