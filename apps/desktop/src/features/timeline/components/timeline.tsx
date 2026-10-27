import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Flag, Plus } from "lucide-react";
import { useShallow } from "zustand/react/shallow";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { EpisodeMedia } from "@/features/timeline/deps/episodes";
import { cn } from "@/lib/utils";
import { clampFinite as clamp } from "@/shared/utils/math";
import { formatTime } from "@/shared/utils/time";

import { TIMELINE } from "../constants";
import { useClipDrag } from "../hooks/use-clip-drag";
import { useMediaVisuals } from "../hooks/use-media-visuals";
import { useTimelineScrub } from "../hooks/use-timeline-scrub";
import { useTimelineStore } from "../hooks/use-timeline-store";
import { useTimelineViewport } from "../hooks/use-timeline-viewport";
import { clipEditGroup, splitCandidates } from "../stores/timeline-edits";
import type { Layer, TimelineClip, TrackKind } from "../types";
import { dialogueSplitTarget } from "../utils/dialogue-split";
import { snapTime, visibleTicks } from "../utils/geometry";
import { clipRenderWindow, thumbnailTiles } from "../utils/render-window";
import { trackStyles } from "../utils/tracks";
import { TimelineToolbar } from "./timeline-toolbar";
import { TimelineTrack } from "./timeline-track";

type TimelineProps = {
  episode: EpisodeMedia | null;
  currentTime: number;
  onSeek: (time: number) => void;
  muted: boolean;
  onMuteChange: (muted: boolean) => void;
  followPlayhead: boolean;
  duration: number;
  dialogueEditing: {
    busy: boolean;
    historyCounts: { undo: number; redo: number };
    split: (id: string, time: number) => Promise<boolean | undefined>;
    restore: (redo: boolean) => Promise<boolean | undefined>;
  };
};

export function Timeline({
  episode,
  currentTime,
  onSeek,
  muted,
  onMuteChange,
  followPlayhead,
  duration: projectDuration,
  dialogueEditing,
}: TimelineProps) {
  const history = useTimelineStore((state) => state.history);
  const actions = useTimelineStore(
    useShallow((state) => ({
      addLayer: state.addLayer,
      addClip: state.addClip,
      moveClip: state.moveClip,
      removeClip: state.removeClip,
      updateText: state.updateText,
      split: state.split,
      undo: state.undo,
      redo: state.redo,
    })),
  );
  const visuals = useMediaVisuals(episode);
  const mediaDuration = episode?.durationSeconds ?? 0;
  const duration = Math.max(projectDuration, 30);
  // A loaded short video fits its actual duration; empty media has a 30s ruler.
  const timelineDuration = projectDuration > 0 ? projectDuration : duration;
  const viewport = useTimelineViewport(timelineDuration, currentTime, followPlayhead);
  const committedDocument = history.present;
  const playheadRef = useRef(currentTime);
  useEffect(() => {
    playheadRef.current = currentTime;
  }, [currentTime]);
  const [snap, setSnap] = useState(true);
  const [markers, setMarkers] = useState<number[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const enabled = projectDuration > 0;
  const clipDrag = useClipDrag(
    committedDocument,
    viewport.viewportRef,
    viewport.width / timelineDuration,
    snap,
    [0, currentTime, ...markers],
    setSelected,
    actions.moveClip,
  );
  const document = clipDrag.draft?.document ?? committedDocument;
  const ticks = useMemo(
    () =>
      visibleTicks(timelineDuration, viewport.width, viewport.scrollLeft, viewport.viewportWidth),
    [timelineDuration, viewport.width, viewport.scrollLeft, viewport.viewportWidth],
  );
  const clipsByLayer = useMemo(
    () =>
      new Map(
        document.layers.map((layer) => [
          layer.id,
          document.clips.filter((clip) => clip.trackId === layer.id),
        ]),
      ),
    [document.layers, document.clips],
  );
  const canEdit = !document.layers.some((layer) => layer.locked);
  const dialogueSegment = dialogueSplitTarget(
    episode?.id,
    episode?.dialogueSegments ?? [],
    selected,
    currentTime,
  );
  const dialogueContext =
    !!selected?.startsWith(`dialogue:${episode?.id}:`) ||
    (!selected &&
      (!!dialogueSegment ||
        dialogueEditing.historyCounts.undo > 0 ||
        dialogueEditing.historyCounts.redo > 0));
  const canSplit =
    !dialogueEditing.busy &&
    (dialogueContext
      ? !!dialogueSegment &&
        !document.layers.find((layer) => layer.id === "dialogue-subtitles")?.locked
      : splitCandidates(document, currentTime, selected).length > 0);
  function split() {
    if (!canSplit) return;
    if (dialogueSegment) void dialogueEditing.split(dialogueSegment.id, currentTime);
    else actions.split({ time: currentTime, selectedId: selected });
  }
  const undo = () => (dialogueContext ? void dialogueEditing.restore(false) : actions.undo());
  const redo = () => (dialogueContext ? void dialogueEditing.restore(true) : actions.redo());
  const addLayer = (kind: TrackKind) => {
    const count = document.layers.filter((layer) => layer.kind === kind).length + 1;
    actions.addLayer({
      layer: {
        id: crypto.randomUUID(),
        kind,
        name: `${trackStyles[kind].label} ${count}`,
        locked: false,
        muted: false,
        hidden: false,
      },
    });
  };
  const addClip = useCallback(
    (layer: Layer) => {
      if (!episode || mediaDuration <= 0) return;
      const overlay = layer.kind === "subtitle" || layer.kind === "graphic";
      const start = overlay ? Math.min(playheadRef.current, Math.max(0, mediaDuration - 0.1)) : 0;
      const clip: TimelineClip = {
        id: crypto.randomUUID(),
        trackId: layer.id,
        kind: layer.kind,
        start,
        sourceStart: 0,
        duration: overlay ? Math.min(5, mediaDuration - start) : mediaDuration,
        sourceId: overlay ? undefined : episode.id,
        name: overlay
          ? layer.kind === "subtitle"
            ? "New subtitle"
            : "Title graphic"
          : episode.name,
        text: overlay
          ? layer.kind === "subtitle"
            ? "Your subtitle here"
            : "Your title here"
          : undefined,
        color: "#c084fc",
      };
      actions.addClip({ clip });
      setSelected(clip.id);
    },
    [actions, episode, mediaDuration],
  );
  const frameTimes = useMemo(() => {
    const times = document.clips
      .filter((clip) => clip.kind === "video")
      .flatMap((clip) => {
        const window = clipRenderWindow(
          clip.start,
          clip.duration,
          viewport.width / timelineDuration,
          viewport.scrollLeft,
          viewport.viewportWidth,
        );
        return thumbnailTiles(
          clip.sourceStart,
          window.left,
          window.width,
          viewport.width / timelineDuration,
          mediaDuration,
        ).map((tile) => tile.time);
      });
    return [...new Set(times)];
  }, [
    document.clips,
    viewport.width,
    viewport.scrollLeft,
    viewport.viewportWidth,
    timelineDuration,
    mediaDuration,
  ]);
  const { available, requestFrames } = visuals;
  useEffect(() => {
    if (!available) return;
    const timer = setTimeout(() => requestFrames(frameTimes), 60);
    return () => clearTimeout(timer);
  }, [frameTimes, available, requestFrames]);
  const canEditClip = useCallback(
    (id: string) => clipEditGroup(committedDocument, id).length > 0,
    [committedDocument],
  );
  const selectedClip = document.clips.find((clip) => clip.id === selected);
  const canDelete = !!selected && clipEditGroup(committedDocument, selected).length > 0;
  function removeSelected() {
    if (selected && canDelete) {
      actions.removeClip({ id: selected });
      setSelected(null);
    }
  }

  function addMarker() {
    if (enabled)
      setMarkers((values) =>
        values.some((value) => Math.abs(value - currentTime) < 0.01)
          ? values
          : [...values, currentTime].sort((a, b) => a - b).slice(0, 100),
      );
  }
  function seekFromPointer(clientX: number, bypassSnap: boolean) {
    let time = viewport.timeAt(clientX);
    if (snap && !bypassSnap)
      time = snapTime(
        time,
        [
          0,
          mediaDuration,
          ...document.clips.flatMap((clip) => [clip.start, clip.start + clip.duration]),
          ...markers,
        ],
        viewport.width / timelineDuration,
      );
    onSeek(clamp(time, 0, projectDuration));
  }
  const scrubHandlers = useTimelineScrub(
    viewport.viewportRef,
    enabled,
    seekFromPointer,
    viewport.setScrubbing,
  );

  return (
    <section
      className="flex h-full min-h-0 flex-col bg-background select-none"
      aria-label="Timeline editor"
      onKeyDown={(event) => {
        if (
          (event.target as HTMLElement).closest("input, textarea, select, [contenteditable=true]")
        )
          return;
        if (event.key === "Escape") {
          clipDrag.cancel();
          return;
        }
        if (clipDrag.draft) return;
        if (event.key === "Delete" || event.key === "Backspace") {
          event.preventDefault();
          removeSelected();
          return;
        }
        const command = event.metaKey || event.ctrlKey;
        if (command && event.key.toLowerCase() === "z") {
          event.preventDefault();
          if (canEdit) {
            if (event.shiftKey) redo();
            else undo();
          }
        } else if (!command && !event.altKey) {
          if (event.key.toLowerCase() === "s") {
            event.preventDefault();
            split();
          }
          if (event.key.toLowerCase() === "n") {
            event.preventDefault();
            setSnap((value) => !value);
          }
          if (event.key.toLowerCase() === "m") {
            event.preventDefault();
            addMarker();
          }
        }
      }}
    >
      <TimelineToolbar
        currentTime={currentTime}
        duration={projectDuration}
        zoom={viewport.zoom}
        snap={snap}
        enabled={enabled}
        canSplit={canSplit}
        canUndo={
          !dialogueEditing.busy &&
          (dialogueContext ? dialogueEditing.historyCounts.undo > 0 : history.past.length > 0) &&
          canEdit
        }
        canRedo={
          !dialogueEditing.busy &&
          (dialogueContext ? dialogueEditing.historyCounts.redo > 0 : history.future.length > 0) &&
          canEdit
        }
        canDelete={canDelete}
        onDelete={removeSelected}
        onSplit={split}
        onUndo={undo}
        onRedo={redo}
        onSnap={() => setSnap((value) => !value)}
        onMarker={addMarker}
        onZoom={viewport.changeZoom}
        onFit={viewport.fit}
        layerControl={
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="outline" size="xs" aria-label="Add layer" />}
            >
              <Plus />
              Layer
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-40">
              {(["video", "audio", "subtitle", "graphic"] as TrackKind[]).map((kind) => (
                <DropdownMenuItem key={kind} onClick={() => addLayer(kind)}>
                  Add {trackStyles[kind].label.toLowerCase()} layer
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        }
      />
      <div
        ref={viewport.viewportRef}
        tabIndex={0}
        aria-label="Timeline tracks. Drag to scrub; S to split, M for marker, N for snapping."
        className="relative min-h-0 flex-1 overflow-auto outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring"
        onScroll={(event) => viewport.setScrollLeft(event.currentTarget.scrollLeft)}
        onPointerDown={(event) => {
          if (!clipDrag.begin(event)) scrubHandlers.onPointerDown(event);
        }}
        onPointerMove={(event) => {
          clipDrag.move(event);
          scrubHandlers.onPointerMove(event);
        }}
        onPointerUp={(event) => {
          clipDrag.finish(event, true);
          scrubHandlers.onPointerUp(event);
        }}
        onPointerCancel={(event) => {
          clipDrag.finish(event, false);
          scrubHandlers.onPointerCancel(event);
        }}
        onLostPointerCapture={(event) => {
          clipDrag.finish(event, false);
          scrubHandlers.onLostPointerCapture(event);
        }}
      >
        <div
          className="relative grid min-h-full"
          style={{
            gridTemplateColumns: `${TIMELINE.headerWidth}px ${viewport.width}px`,
            width: TIMELINE.headerWidth + viewport.width,
            gridTemplateRows: `${TIMELINE.rulerHeight}px repeat(${document.layers.length}, ${TIMELINE.trackHeight}px) minmax(24px, 1fr)`,
          }}
        >
          <div className="sticky top-0 left-0 z-40 flex items-center border-r border-b bg-card px-3 text-[9px] font-medium tracking-widest text-muted-foreground">
            TRACKS{" "}
            <span className="ml-auto rounded border px-1 text-[9px]">{document.layers.length}</span>
          </div>
          <div
            data-timeline-surface
            className="sticky top-0 z-20 touch-none overflow-hidden border-b bg-card"
            aria-label="Timeline ruler"
          >
            {ticks.map((tick) => (
              <div
                key={tick}
                className="pointer-events-none absolute inset-y-0 border-l border-border/70"
                style={{ left: (tick / timelineDuration) * viewport.width }}
              >
                <span className="absolute top-1 left-1 whitespace-nowrap font-mono text-[9px] tabular-nums text-muted-foreground">
                  {formatTime(tick, !Number.isInteger(tick))}
                </span>
                <span className="absolute bottom-0 h-1.5 border-l border-muted-foreground/70" />
              </div>
            ))}
            {markers.map((time, index) => (
              <button
                key={time}
                className="absolute bottom-0 text-amber-400"
                style={{ left: (time / timelineDuration) * viewport.width - 5 }}
                aria-label={`Marker ${index + 1} at ${formatTime(time, true)}`}
                title="Click to seek; double-click to remove marker"
                onPointerDown={(event) => event.stopPropagation()}
                onClick={() => onSeek(time)}
                onDoubleClick={() =>
                  setMarkers((values) => values.filter((value) => value !== time))
                }
              >
                <Flag className="size-3" fill="currentColor" />
              </button>
            ))}
          </div>
          {document.layers.map((layer) => (
            <TimelineTrack
              key={layer.id}
              layer={layer}
              clips={clipsByLayer.get(layer.id) ?? []}
              sourceDuration={mediaDuration}
              timelineDuration={timelineDuration}
              width={viewport.width}
              viewportWidth={viewport.viewportWidth}
              scrollLeft={viewport.scrollLeft}
              ticks={ticks}
              selected={selected}
              muted={muted}
              visuals={visuals}
              canEditClip={canEditClip}
              onMuteChange={onMuteChange}
              onSelect={setSelected}
              onSeek={onSeek}
              onAddClip={addClip}
            />
          ))}
          <div className="sticky left-0 z-30 border-r bg-card" />
          <div className="bg-muted/5" />
          {enabled && (
            <div
              className={cn(
                "pointer-events-none absolute top-0 bottom-0 z-20 w-px bg-primary",
                viewport.scrubbing && "shadow-[0_0_6px_var(--primary)]",
              )}
              style={{
                left:
                  TIMELINE.headerWidth +
                  (clamp(currentTime, 0, timelineDuration) / timelineDuration) * viewport.width,
              }}
            >
              <div className="absolute top-0 -left-1 h-3 w-[9px] rounded-b-sm bg-primary" />
            </div>
          )}
        </div>
      </div>
      {selectedClip && (selectedClip.kind === "subtitle" || selectedClip.kind === "graphic") && (
        <div className="flex h-8 shrink-0 items-center gap-2 border-t bg-card px-3 text-[10px]">
          <label htmlFor="clip-text">Layer text</label>
          <input
            key={selectedClip.id + selectedClip.text}
            id="clip-text"
            aria-label="Layer text"
            className="min-w-0 flex-1 rounded border bg-background px-2 py-0.5"
            defaultValue={selectedClip.text}
            disabled={document.layers.find((layer) => layer.id === selectedClip.trackId)?.locked}
            onBlur={(event) =>
              actions.updateText({ id: selectedClip.id, text: event.currentTarget.value })
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
            }}
          />
          <span className="text-muted-foreground">Enter to apply</span>
        </div>
      )}
      <footer className="flex h-6 shrink-0 items-center gap-4 border-t bg-card px-3 text-[9px] text-muted-foreground">
        <span>
          {enabled
            ? `${document.layers.length} layers · ${document.clips.length} clips`
            : "No media"}
        </span>
        <span>{markers.length} markers</span>
        {clipDrag.draft && (
          <span
            role="status"
            className={clipDrag.draft.valid ? "text-primary" : "text-destructive"}
          >
            {clipDrag.draft.valid
              ? `Move to ${formatTime(clipDrag.draft.start, true)}`
              : "Cannot drop: locked, incompatible, or occupied layer"}{" "}
            · Esc to cancel
          </span>
        )}
        <span className="ml-auto">
          {Math.round(viewport.zoom * 100)}%{" "}
          <span className="ml-3 hidden md:inline">
            Ctrl / ⌘ + scroll to zoom · Shift to bypass snap
          </span>
        </span>
      </footer>
    </section>
  );
}
