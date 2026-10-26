import { Languages, MessageSquareText, Search, SlidersHorizontal } from "lucide-react";

import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

export function DialoguePanel() {
  return (
    <section className="flex min-h-0 flex-col bg-catty-panel">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-catty-border px-2.5">
        <div className="flex items-center gap-1.5">
          <MessageSquareText size={12} className="text-catty-accent" />
          <span className="text-[9px] font-medium text-catty-text-soft">Dialogue</span>
          <Badge>0 lines</Badge>
        </div>
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon" aria-label="Search">
            <Search size={12} />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Filters">
            <SlidersHorizontal size={12} />
          </Button>
        </div>
      </div>

      <div className="grid h-8 shrink-0 grid-cols-2 border-b border-catty-border text-[8px]">
        <button className="flex items-center justify-center gap-1 border-r border-catty-border bg-catty-surface text-catty-text-soft">
          <MessageSquareText size={10} /> Source
        </button>
        <button className="flex items-center justify-center gap-1 text-catty-muted">
          <Languages size={10} /> Khmer translation
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-5 text-center">
        <MessageSquareText size={22} strokeWidth={1.4} className="mb-2 text-catty-muted-2" />
        <p className="text-[10px] font-medium text-catty-text-soft">No dialogue yet</p>
        <p className="mt-1 max-w-[250px] text-[9px] leading-4 text-catty-muted-2">
          Transcribed dialogue and Khmer translations will appear here with timestamps and speaker
          assignments.
        </p>
      </div>

      <div className="flex h-8 shrink-0 items-center justify-between border-t border-catty-border px-2.5 text-[8px] text-catty-muted-2">
        <span>0 selected</span>
        <span>Source → Khmer</span>
      </div>
    </section>
  );
}
