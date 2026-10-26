import type { ReactNode } from "react";

import {
  Flag,
  Magnet,
  Minus,
  MousePointer2,
  Plus,
  Redo2,
  Scan,
  Scissors,
  Undo2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatTime, TIMELINE } from "@/features/timeline/geometry";

type TimelineToolbarProps = {
  layerControl?: ReactNode;
  currentTime: number;
  duration: number;
  zoom: number;
  snap: boolean;
  canSplit: boolean;
  canUndo: boolean;
  canRedo: boolean;
  enabled: boolean;
  onSplit: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onSnap: () => void;
  onMarker: () => void;
  onZoom: (zoom: number) => void;
  onFit: () => void;
};

export function TimelineToolbar(props: TimelineToolbarProps) {
  return (
    <div className="flex h-10 shrink-0 items-center gap-1 overflow-x-auto border-b bg-card px-2">
      <span className="mr-2 flex items-center gap-2 px-1 text-[11px] font-medium">
        <MousePointer2 className="size-3.5 text-primary" />
        Timeline
      </span>
      {props.layerControl}
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Undo timeline edit"
        title="Undo timeline edit"
        disabled={!props.canUndo}
        onClick={props.onUndo}
      >
        <Undo2 />
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Redo timeline edit"
        title="Redo timeline edit"
        disabled={!props.canRedo}
        onClick={props.onRedo}
      >
        <Redo2 />
      </Button>
      <span className="mx-1 h-4 w-px shrink-0 bg-border" />
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Split at playhead"
        title="Split selected clip or linked source at playhead (S)"
        disabled={!props.canSplit}
        onClick={props.onSplit}
      >
        <Scissors />
      </Button>
      <Button
        variant={props.snap ? "secondary" : "ghost"}
        size="icon-sm"
        aria-label="Toggle snapping"
        title="Snap to cuts and markers (N)"
        aria-pressed={props.snap}
        onClick={props.onSnap}
      >
        <Magnet className={props.snap ? "text-primary" : ""} />
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Add marker"
        title="Add marker at playhead (M)"
        disabled={!props.enabled}
        onClick={props.onMarker}
      >
        <Flag />
      </Button>
      <span className="mx-2 hidden whitespace-nowrap font-mono text-[10px] tabular-nums text-primary xl:block">
        {formatTime(props.currentTime, true)}
        <span className="ml-2 text-muted-foreground">/ {formatTime(props.duration)}</span>
      </span>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom out"
          disabled={props.zoom <= TIMELINE.minZoom}
          onClick={() => props.onZoom(props.zoom / 1.3)}
        >
          <Minus />
        </Button>
        <input
          className="h-1 w-20 accent-primary"
          type="range"
          min={1}
          max={TIMELINE.maxZoom}
          step={0.1}
          value={props.zoom}
          aria-label="Timeline zoom"
          onChange={(event) => props.onZoom(Number(event.target.value))}
        />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom in"
          disabled={props.zoom >= TIMELINE.maxZoom}
          onClick={() => props.onZoom(props.zoom * 1.3)}
        >
          <Plus />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Fit timeline"
          title="Fit timeline to viewport"
          onClick={props.onFit}
        >
          <Scan />
        </Button>
      </div>
    </div>
  );
}
