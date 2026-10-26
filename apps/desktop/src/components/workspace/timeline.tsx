import { Minus, Plus, Scissors, ZoomIn } from "lucide-react";

import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

const tracks = [
  { name: "VIDEO", label: "Video" },
  { name: "DIALOGUE", label: "Dialogue" },
  { name: "KHMER DUB", label: "Khmer dub" },
];

export function Timeline() {
  return (
    <section className="min-h-0 border-t border-catty-border bg-[#12110f]">
      <div className="flex h-8 items-center justify-between border-b border-catty-border px-2.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-medium text-catty-text-soft">Timeline</span>
          <Badge tone="accent">00:00:00.000</Badge>
        </div>
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon" aria-label="Split"><Scissors size={11} /></Button>
          <span className="mx-1 h-3.5 w-px bg-catty-border" />
          <Button variant="ghost" size="icon" aria-label="Zoom out"><Minus size={11} /></Button>
          <ZoomIn size={11} className="text-catty-muted-2" />
          <Button variant="ghost" size="icon" aria-label="Zoom in"><Plus size={11} /></Button>
        </div>
      </div>

      <div className="grid h-5 grid-cols-[92px_1fr] border-b border-catty-border-subtle text-[7px] text-catty-muted-2">
        <div className="border-r border-catty-border-subtle" />
        <div className="relative flex items-center justify-between px-2">
          <span>00:00</span><span>00:15</span><span>00:30</span><span>00:45</span><span>01:00</span>
        </div>
      </div>

      {tracks.map((track) => (
        <div className="grid min-h-[42px] grid-cols-[92px_1fr] border-b border-catty-border-subtle" key={track.name}>
          <div className="flex flex-col justify-center border-r border-catty-border-subtle px-2">
            <span className="text-[8px] font-semibold tracking-wide text-catty-text-soft">{track.name}</span>
            <span className="mt-0.5 text-[7px] text-catty-muted-2">{track.label}</span>
          </div>
          <div className="relative m-1.5 overflow-hidden rounded-catty border border-dashed border-catty-border-subtle bg-catty-panel/25">
            <div className="absolute inset-y-0 left-0 w-px bg-catty-accent/70" />
          </div>
        </div>
      ))}
    </section>
  );
}
