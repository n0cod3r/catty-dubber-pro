import { memo } from "react";

import {
  ArrowDown,
  ArrowUp,
  Eye,
  EyeOff,
  LockKeyhole,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Trash2,
  UnlockKeyhole,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useShallow } from "zustand/react/shallow";

import { Button } from "@/components/ui/button";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { formatTime } from "@/shared/utils/time";

import { TIMELINE } from "../constants";
import type { MediaVisuals } from "../hooks/use-media-visuals";
import { useTimelineStore } from "../hooks/use-timeline-store";
import type { Layer, TimelineClip } from "../types";
import { trackStyles } from "../utils/tracks";
import { ClipMediaCanvas } from "./clip-media-canvas";

type Props = {
  layer: Layer;
  clips: TimelineClip[];
  sourceDuration: number;
  timelineDuration: number;
  width: number;
  viewportWidth: number;
  scrollLeft: number;
  ticks: number[];
  selected: string | null;
  muted: boolean;
  visuals: MediaVisuals;
  canEditClip: (id: string) => boolean;
  onMuteChange: (value: boolean) => void;
  onSelect: (id: string) => void;
  onSeek: (time: number) => void;
  onAddClip: (layer: Layer) => void;
};

export const TimelineTrack = memo(function TimelineTrack({
  layer,
  clips,
  sourceDuration,
  timelineDuration,
  width,
  viewportWidth,
  scrollLeft,
  ticks,
  selected,
  muted,
  visuals,
  canEditClip,
  onMuteChange,
  onSelect,
  onSeek,
  onAddClip,
}: Props) {
  const actions = useTimelineStore(
    useShallow((state) => ({
      moveLayer: state.moveLayer,
      removeLayer: state.removeLayer,
      toggleLayer: state.toggleLayer,
      removeClip: state.removeClip,
    })),
  );
  const style = trackStyles[layer.kind];
  const Icon = style.icon;
  const isMuted = layer.muted || (layer.source && muted);
  const wave = visuals.waveform.current;
  return (
    <>
      <div
        className="sticky left-0 z-30 flex flex-col justify-center gap-1 border-r border-b bg-card px-2"
        data-layer-id={layer.id}
      >
        <div className="flex items-center gap-1.5">
          <span className={cn("h-4 w-0.5 rounded", style.dot)} />
          <Icon className="size-3 text-muted-foreground" />
          <span
            className="min-w-0 flex-1 truncate text-[10px] font-medium"
            title={layer.name}
          >
            {layer.name}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label={`Options for ${layer.name}`}
                />
              }
            >
              <MoreHorizontal />
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-44">
              <DropdownMenuItem
                disabled={layer.locked}
                onClick={() =>
                  actions.moveLayer({ id: layer.id, direction: -1 })
                }
              >
                <ArrowUp />
                Move layer up
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={layer.locked}
                onClick={() =>
                  actions.moveLayer({ id: layer.id, direction: 1 })
                }
              >
                <ArrowDown />
                Move layer down
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={layer.locked || !!layer.source || clips.length > 0}
                onClick={() => actions.removeLayer({ id: layer.id })}
              >
                <Trash2 />
                Remove empty layer
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="flex items-center gap-1 pl-2">
          <span className="mr-auto text-[8px] text-muted-foreground">
            {clips.length} clip{clips.length === 1 ? "" : "s"}
          </span>
          {layer.kind === "audio" ? (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={`${isMuted ? "Unmute" : "Mute"} ${layer.name}`}
              aria-pressed={!!isMuted}
              disabled={layer.locked}
              onClick={() =>
                layer.source
                  ? onMuteChange(!muted)
                  : actions.toggleLayer({ id: layer.id, property: "muted" })
              }
            >
              {isMuted ? <VolumeX className="text-primary" /> : <Volume2 />}
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={`${layer.hidden ? "Show" : "Hide"} ${layer.name}`}
              aria-pressed={layer.hidden}
              disabled={layer.locked}
              onClick={() =>
                actions.toggleLayer({ id: layer.id, property: "hidden" })
              }
            >
              {layer.hidden ? <EyeOff className="text-primary" /> : <Eye />}
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={`${layer.locked ? "Unlock" : "Lock"} ${layer.name} track`}
            aria-pressed={layer.locked}
            onClick={() =>
              actions.toggleLayer({ id: layer.id, property: "locked" })
            }
          >
            {layer.locked ? (
              <LockKeyhole className="text-primary" />
            ) : (
              <UnlockKeyhole className="opacity-40" />
            )}
          </Button>
        </div>
      </div>
      <div
        data-timeline-surface
        data-track-drop={layer.id}
        className="relative touch-none overflow-hidden border-b bg-muted/10"
        style={{ height: TIMELINE.trackHeight }}
      >
        {ticks.map((tick) => (
          <span
            key={tick}
            className="pointer-events-none absolute inset-y-0 border-l border-border/30"
            style={{ left: (tick / timelineDuration) * width }}
          />
        ))}
        {clips.map((clip) => {
          const clipLeft = (clip.start / timelineDuration) * width;
          const clipWidth = Math.max(
            1,
            (clip.duration / timelineDuration) * width,
          );
          if (
            clipLeft + clipWidth < scrollLeft - 96 ||
            clipLeft > scrollLeft + viewportWidth + 96
          )
            return null;
          const visualMessage =
            clip.kind === "audio"
              ? !wave
                ? "Decoding audio…"
                : wave.status === "loading"
                  ? `Waveform ${Math.round(wave.progress * 100)}%`
                  : wave.status === "absent"
                    ? "No audio stream"
                    : wave.status === "error"
                      ? "Waveform unavailable"
                      : null
              : clip.kind === "video"
                ? visuals.videoError
                  ? "Thumbnails unavailable"
                  : visuals.frames.current.size === 0
                    ? "Decoding frames…"
                    : null
                : null;
          const mediaClip = clip.kind === "video" || clip.kind === "audio";
          return (
            <ContextMenu key={clip.id}>
              <ContextMenuTrigger
                render={<button type="button" disabled={layer.locked} />}
                onContextMenu={() => onSelect(clip.id)}
                data-clip-id={clip.id}
                aria-disabled={layer.locked}
                data-clip-start={clip.start}
                data-source-start={clip.sourceStart}
                aria-label={`${layer.name}: ${clip.name}, ${formatTime(clip.start, true)} to ${formatTime(clip.start + clip.duration, true)}`}
                aria-pressed={selected === clip.id}
                title="Drag to move. Right-click for clip actions."
                className={cn(
                  "absolute inset-y-1 cursor-grab touch-none overflow-hidden rounded border text-left text-[10px] active:cursor-grabbing outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  style.color,
                  selected === clip.id && "ring-1 ring-primary",
                  (isMuted || layer.hidden) && "opacity-35",
                  layer.locked && "opacity-60",
                )}
                style={{ left: clipLeft, width: clipWidth }}
                onPointerDown={() => onSelect(clip.id)}
                onClick={(event) => {
                  if (event.detail === 0) {
                    onSelect(clip.id);
                    onSeek(clip.start);
                  }
                }}
              >
                <span className="absolute inset-x-0 top-0 z-10 flex h-5 items-center gap-1 bg-black/30 px-1.5">
                  <Icon className="size-2.5 shrink-0" />
                  <span className="truncate">{clip.name}</span>
                  <span className="ml-auto shrink-0 text-[8px] opacity-60">
                    {formatTime(clip.duration)}
                  </span>
                </span>
                {mediaClip && (
                  <ClipMediaCanvas
                    clip={clip}
                    pixelsPerSecond={width / timelineDuration}
                    scrollLeft={scrollLeft}
                    viewportWidth={viewportWidth}
                    sourceDuration={sourceDuration}
                    visuals={visuals}
                  />
                )}
                {(clip.kind === "subtitle" || clip.kind === "graphic") && (
                  <span className="absolute inset-x-0 top-6 truncate px-2 text-xs">
                    {clip.text}
                  </span>
                )}
                {visualMessage && (
                  <span
                    className="absolute right-1 bottom-0.5 rounded bg-black/60 px-1 text-[8px]"
                    title={wave?.error ?? visuals.videoError ?? undefined}
                  >
                    {visualMessage}
                  </span>
                )}
              </ContextMenuTrigger>
              <ContextMenuContent className="w-48">
                {mediaClip && (
                  <>
                    <ContextMenuItem
                      onClick={() =>
                        window.dispatchEvent(new Event("catty:rebuild-proxy"))
                      }
                    >
                      <RefreshCw />
                      Rebuild playback proxy
                    </ContextMenuItem>
                    <ContextMenuSeparator />
                  </>
                )}
                <ContextMenuItem
                  disabled={!canEditClip(clip.id)}
                  variant="destructive"
                  onClick={() => actions.removeClip({ id: clip.id })}
                >
                  <Trash2 />
                  Remove clip
                </ContextMenuItem>
              </ContextMenuContent>
            </ContextMenu>
          );
        })}
        {!clips.length && (
          <button
            className="absolute inset-y-0 left-3 flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground disabled:opacity-40"
            style={{ transform: `translateX(${scrollLeft}px)` }}
            disabled={layer.locked || sourceDuration <= 0}
            onPointerDown={(event) => event.stopPropagation()}
            onClick={() => onAddClip(layer)}
          >
            <Plus className="size-3" />
            {layer.kind === "subtitle"
              ? "Add subtitle at playhead"
              : layer.kind === "graphic"
                ? "Add title graphic at playhead"
                : "Add source clip"}
          </button>
        )}
      </div>
    </>
  );
});
