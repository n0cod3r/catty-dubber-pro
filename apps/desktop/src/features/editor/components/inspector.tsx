import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { TranscriptSegment } from "@catty/contracts";
import {
  AlertTriangle,
  Film,
  Languages,
  LoaderCircle,
  MessageSquareText,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";
import { cn } from "@/lib/utils";
import { formatTime } from "@/shared/utils/time";

import type { DialogueEditing } from "../hooks/use-dialogue-editing";
import { activeDialogueId, dialogueScrollDelta } from "../utils/dialogue-follow";
import { isMergeDialogueShortcut } from "../utils/dialogue-shortcuts";
import { DialogueTextEditor } from "./dialogue-text-editor";

const tabs = [
  { id: "source", label: "Dialogue", icon: MessageSquareText },
  { id: "translation", label: "Khmer", icon: Languages },
  { id: "properties", label: "Media", icon: Film },
] as const;
const transcriptionEngines = [
  { id: "paraformer", label: "Paraformer" },
  { id: "sense-small", label: "SenseSmall" },
] as const;
type TranscriptionEngine = (typeof transcriptionEngines)[number]["id"];
type DialogueRow = TranscriptSegment & { id: string; speakerId: string | null };
const TRANSCRIPTION_ENGINE_KEY = "catty.transcription-engine.v1";

function readTranscriptionEngine(): TranscriptionEngine {
  if (typeof window === "undefined") return "paraformer";
  return window.localStorage.getItem(TRANSCRIPTION_ENGINE_KEY) === "sense-small"
    ? "sense-small"
    : "paraformer";
}
function persistedSegments(segments: EpisodeMedia["dialogueSegments"]): DialogueRow[] {
  return (segments ?? []).map((segment) => ({
    id: segment.id,
    start: segment.start,
    end: segment.end,
    speakerId: segment.speakerId ?? null,
    text: segment.sourceText,
    confidence: segment.confidence,
  }));
}

export function Inspector({
  episode,
  currentTime,
  followTimeline,
  onSeek,
  dialogue,
}: {
  episode: EpisodeMedia | null;
  currentTime: number;
  followTimeline: boolean;
  onSeek: (time: number) => void;
  dialogue: DialogueEditing;
}) {
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("source");
  const [engine, setEngine] = useState<TranscriptionEngine>(readTranscriptionEngine);
  const { busy, transcribing, error, historyCounts } = dialogue;
  const speakerWarning = dialogue.speakerWarning ?? episode?.speakerError ?? null;
  const [segments, setSegments] = useState<DialogueRow[]>(() =>
    persistedSegments(episode?.dialogueSegments),
  );
  const listRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef(new Map<string, HTMLButtonElement>());
  const activeId = activeDialogueId(segments, currentTime);
  const [textEditorId, setTextEditorId] = useState<string | null>(null);
  const textEditorSegment = segments.find((segment) => segment.id === textEditorId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedIndex = useMemo(
    () => segments.findIndex((segment) => segment.id === selectedId),
    [segments, selectedId],
  );
  const selected = selectedIndex >= 0 ? segments[selectedIndex] : null;
  const canSplit =
    !!selected && currentTime > selected.start + 0.05 && currentTime < selected.end - 0.05;
  const canMergeNext = selectedIndex >= 0 && selectedIndex < segments.length - 1;

  useEffect(() => {
    if (!followTimeline || tab !== "source" || !activeId) return;
    const list = listRef.current;
    const row = rowRefs.current.get(activeId);
    if (!list || !row) return;
    const bounds = list.getBoundingClientRect();
    const rowBounds = row.getBoundingClientRect();
    list.scrollTop += dialogueScrollDelta(
      rowBounds.top,
      rowBounds.bottom,
      bounds.top,
      bounds.bottom,
    );
  }, [activeId, followTimeline, tab]);

  useEffect(() => window.localStorage.setItem(TRANSCRIPTION_ENGINE_KEY, engine), [engine]);
  useEffect(() => {
    const restored = persistedSegments(episode?.dialogueSegments);
    setSegments(restored);
    setSelectedId(null);
    setTextEditorId(null);
  }, [episode?.id, episode?.dialogueSegments]);

  const splitSelected = () =>
    selected && canSplit ? dialogue.split(selected.id, currentTime) : undefined;
  const mergeNext = useCallback(
    () => (selected && canMergeNext ? dialogue.merge(selected.id) : undefined),
    [selected, canMergeNext, dialogue],
  );
  const transcribe = () => dialogue.transcribe(engine);
  const restoreDialogue = (redo: boolean) => dialogue.restore(redo);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (!isMergeDialogueShortcut(event) || tab !== "source" || !canMergeNext || busy) return;
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        target.closest(
          "input, textarea, select, [contenteditable]:not([contenteditable=false]), [role=textbox]",
        )
      )
        return;
      event.preventDefault();
      void mergeNext();
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [tab, canMergeNext, busy, mergeNext]);

  return (
    <section
      className="flex min-h-0 min-w-0 flex-1 flex-col bg-card"
      aria-label="Dialogue and media inspector"
      onKeyDown={(event) => {
        if (
          event.defaultPrevented ||
          event.repeat ||
          event.nativeEvent.isComposing ||
          event.altKey ||
          !(event.metaKey || event.ctrlKey) ||
          event.key.toLowerCase() !== "z"
        )
          return;
        if (
          (event.target as HTMLElement).closest(
            "input, textarea, select, [contenteditable]:not([contenteditable=false])",
          )
        )
          return;
        event.preventDefault();
        event.stopPropagation();
        void restoreDialogue(event.shiftKey);
      }}
    >
      <div className="flex h-9 shrink-0 items-center justify-between border-b px-3 text-[11px] font-medium">
        Inspector
        <span className="rounded border px-1.5 py-0.5 text-[9px] font-normal text-muted-foreground">
          {tab === "properties" ? "Source" : `${segments.length} lines`}
        </span>
      </div>
      <div role="tablist" aria-label="Inspector panels" className="flex h-9 shrink-0 border-b">
        {tabs.map(({ id, label, icon: Icon }, index) => (
          <button
            key={id}
            id={`inspector-tab-${id}`}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`inspector-panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 border-b-2 border-transparent text-[10px] text-muted-foreground outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring",
              tab === id && "border-primary bg-background/40 text-foreground",
            )}
            onClick={() => setTab(id)}
            onKeyDown={(event) => {
              const next =
                event.key === "ArrowRight"
                  ? (index + 1) % tabs.length
                  : event.key === "ArrowLeft"
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? tabs.length - 1
                        : null;
              const nextTab = next === null ? undefined : tabs[next];
              if (nextTab) {
                event.preventDefault();
                setTab(nextTab.id);
                document.getElementById(`inspector-tab-${nextTab.id}`)?.focus();
              }
            }}
          >
            <Icon className="size-3" />
            {label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`inspector-panel-${tab}`}
        aria-labelledby={`inspector-tab-${tab}`}
        tabIndex={0}
        className="flex min-h-0 flex-1 flex-col overflow-auto outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring"
      >
        {tab === "properties" && episode ? (
          <dl className="space-y-4 p-4 text-[11px]">
            {[
              ["File", episode.name],
              ["Container", episode.extension.toUpperCase()],
              ["Duration", formatTime(episode.durationSeconds ?? 0, true)],
              [
                "Resolution",
                episode.width && episode.height
                  ? `${episode.width} × ${episode.height}`
                  : "Reading…",
              ],
              ["Target language", "Khmer"],
              ...(episode.fps ? [["Frame rate", `${episode.fps.toFixed(3)} fps`]] : []),
              ...(episode.videoCodec ? [["Video codec", episode.videoCodec]] : []),
              ...(episode.audioCodec ? [["Audio codec", episode.audioCodec]] : []),
              ...(episode.sampleRate ? [["Audio sample rate", `${episode.sampleRate} Hz`]] : []),
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="mb-1 text-[10px] text-muted-foreground">{label}</dt>
                <dd className="break-words">{value}</dd>
              </div>
            ))}
          </dl>
        ) : tab === "source" ? (
          segments.length > 0 ? (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex min-h-9 shrink-0 items-center justify-between gap-2 border-b px-2 py-1">
                <div className="flex items-center gap-1">
                  <div
                    className="flex items-center rounded-md border bg-muted/30 p-0.5"
                    role="group"
                    aria-label="Transcription engine"
                  >
                    {transcriptionEngines.map((item) => (
                      <Button
                        key={item.id}
                        type="button"
                        size="xs"
                        variant={engine === item.id ? "secondary" : "ghost"}
                        aria-pressed={engine === item.id}
                        className="h-5 px-1.5 text-[9px]"
                        disabled={busy}
                        onClick={() => setEngine(item.id)}
                      >
                        {item.label}
                      </Button>
                    ))}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      size="xs"
                      variant="ghost"
                      className="h-5 px-1.5 text-[9px]"
                      disabled={busy || !historyCounts.undo}
                      title="Undo dialogue edit · Ctrl / ⌘ + Z"
                      onClick={() => void restoreDialogue(false)}
                    >
                      Undo
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      className="h-5 px-1.5 text-[9px]"
                      disabled={busy || !historyCounts.redo}
                      title="Redo dialogue edit · Ctrl / ⌘ + Shift + Z"
                      onClick={() => void restoreDialogue(true)}
                    >
                      Redo
                    </Button>
                  </div>
                  {selected && (
                    <Button
                      size="xs"
                      variant="ghost"
                      className="h-5 px-1.5 text-[9px]"
                      disabled={busy || !!textEditorId}
                      onClick={() => setTextEditorId(selected.id)}
                    >
                      Edit text
                    </Button>
                  )}
                  {selected && (
                    <div className="flex items-center gap-1 border-l pl-1">
                      <Button
                        size="xs"
                        variant="ghost"
                        className="h-5 px-1.5 text-[9px]"
                        disabled={!canSplit || busy}
                        title={
                          canSplit
                            ? `Split at ${formatTime(currentTime, true)}. Text is divided proportionally; audio is not re-transcribed.`
                            : "Move the playhead inside the selected segment"
                        }
                        onClick={() => void splitSelected()}
                      >
                        Split
                      </Button>
                      <Button
                        size="xs"
                        variant="ghost"
                        className="h-5 px-1.5 text-[9px]"
                        disabled={!canMergeNext || busy}
                        title="Merge selected dialogue with next · Ctrl / ⌘ + Shift + M"
                        aria-keyshortcuts="Control+Shift+M Meta+Shift+M"
                        onClick={() => void mergeNext()}
                      >
                        Merge next
                      </Button>
                    </div>
                  )}
                </div>
                <Button
                  size="xs"
                  variant="outline"
                  className="h-6 text-[9px]"
                  disabled={busy}
                  onClick={() => void transcribe()}
                >
                  {transcribing && <LoaderCircle className="animate-spin" />}Re-transcribe
                </Button>
              </div>
              <div className="grid h-7 shrink-0 grid-cols-[28px_92px_minmax(0,1fr)] items-center border-b bg-muted/20 px-2 text-[9px] font-medium text-muted-foreground">
                <span>#</span>
                <span>Time</span>
                <span>Dialogue</span>
              </div>
              {speakerWarning && (
                <p
                  role="status"
                  title={speakerWarning}
                  className="flex shrink-0 items-start gap-1.5 border-b border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[10px] leading-snug text-amber-700 dark:text-amber-300"
                >
                  <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                  <span>
                    ការបម្លែងសំឡេងទៅជាអត្ថបទបានជោគជ័យ ប៉ុន្តែការសម្គាល់អ្នកនិយាយបរាជ័យ។ Dialogue
                    ត្រូវបានរក្សាទុក ហើយអ្នកអាចកែ Speaker ដោយដៃ។
                  </span>
                </p>
              )}
              <div
                ref={listRef}
                className="min-h-0 flex-1 overflow-auto"
                aria-label="Dialogue segments"
              >
                {segments.map((segment, index) => (
                  <button
                    key={segment.id}
                    type="button"
                    ref={(row) => {
                      if (row) rowRefs.current.set(segment.id, row);
                      else rowRefs.current.delete(segment.id);
                    }}
                    aria-current={activeId === segment.id ? "true" : undefined}
                    data-active={activeId === segment.id || undefined}
                    aria-pressed={selectedId === segment.id}
                    className={cn(
                      "grid w-full grid-cols-[28px_92px_minmax(0,1fr)] items-start border-b border-l-2 border-l-transparent px-2 py-1.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                      activeId === segment.id && "border-l-primary bg-primary/15",
                      selectedId === segment.id
                        ? "bg-primary/20 ring-1 ring-inset ring-primary/50"
                        : activeId !== segment.id && "hover:bg-muted/40",
                    )}
                    onClick={() => {
                      setSelectedId(segment.id);
                      onSeek(segment.start);
                    }}
                  >
                    <span className="pt-0.5 text-[9px] tabular-nums text-muted-foreground">
                      {index + 1}
                    </span>
                    <span className="pt-0.5 text-[9px] tabular-nums text-muted-foreground">
                      {formatTime(segment.start, true)}
                      <span className="block opacity-60">→ {formatTime(segment.end, true)}</span>
                    </span>
                    <span className="min-w-0 text-[11px] leading-[1.45]">
                      {segment.speakerId && (
                        <span
                          title="Detected speaker · select row to correct"
                          className="mr-1 inline-block rounded border border-primary/25 bg-primary/10 px-1 text-[9px] text-primary"
                        >
                          {episode?.speakers?.find((speaker) => speaker.id === segment.speakerId)
                            ?.name ?? "?"}
                        </span>
                      )}
                      {segment.text}
                    </span>
                  </button>
                ))}
              </div>
              {selected && (
                <label className="flex shrink-0 items-center gap-2 border-t px-2 py-1 text-[10px] text-muted-foreground">
                  Speaker
                  <select
                    aria-label="Correct dialogue speaker"
                    className="min-w-0 rounded border bg-background px-1 py-0.5 text-foreground"
                    disabled={busy}
                    value={selected.speakerId ?? ""}
                    onChange={(event) => {
                      const value = event.target.value;
                      if (value !== (selected.speakerId ?? ""))
                        void dialogue.assignSpeaker(
                          selected.id,
                          value === "__new" ? null : value || null,
                          selected.speakerId,
                          value === "__new",
                        );
                    }}
                  >
                    <option value="">Unassigned</option>
                    {episode?.speakers?.map((speaker) => (
                      <option key={speaker.id} value={speaker.id}>
                        {speaker.name}
                      </option>
                    ))}
                    <option value="__new">New speaker…</option>
                  </select>
                </label>
              )}
              {textEditorSegment && (
                <DialogueTextEditor
                  key={textEditorSegment.id}
                  text={textEditorSegment.text}
                  busy={busy}
                  onSave={(text) =>
                    dialogue.updateText(textEditorSegment.id, text, textEditorSegment.text)
                  }
                  onCancel={() => setTextEditorId(null)}
                />
              )}
              {selected && (
                <div className="flex h-7 shrink-0 items-center justify-between border-t px-2 text-[9px] text-muted-foreground">
                  <span>
                    Selected #{selectedIndex + 1} ·{" "}
                    {formatTime(selected.end - selected.start, true)}
                  </span>
                  <span>
                    {canSplit
                      ? `Split @ ${formatTime(currentTime, true)}`
                      : "Move playhead inside to split"}
                  </span>
                </div>
              )}
              {error && (
                <p role="alert" className="border-t px-2 py-1.5 text-[10px] text-destructive">
                  {error}
                </p>
              )}
            </div>
          ) : (
            <div className="m-auto flex w-full max-w-[270px] flex-col items-center p-4 text-center">
              <MessageSquareText
                className="mb-3 size-7 text-muted-foreground/50"
                strokeWidth={1.3}
              />
              <p className="text-xs font-medium">
                {episode ? "No dialogue yet" : "No media selected"}
              </p>
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                {episode
                  ? "ជ្រើស engine ហើយចុច Transcribe។ Catty នឹងបង្កើត Dialogue និង Subtitle timeline ដោយស្វ័យប្រវត្តិ។"
                  : "Import an episode to start transcription and dubbing."}
              </p>
              {episode && (
                <div
                  className="mt-3 flex items-center rounded-md border bg-muted/30 p-0.5"
                  role="group"
                  aria-label="Transcription engine"
                >
                  {transcriptionEngines.map((item) => (
                    <Button
                      key={item.id}
                      type="button"
                      size="xs"
                      variant={engine === item.id ? "secondary" : "ghost"}
                      aria-pressed={engine === item.id}
                      className="h-6 px-2 text-[10px]"
                      disabled={busy}
                      onClick={() => setEngine(item.id)}
                    >
                      {item.label}
                    </Button>
                  ))}
                </div>
              )}
              <Button
                size="xs"
                className="mt-2"
                disabled={!episode?.durationSeconds || busy}
                onClick={() => void transcribe()}
              >
                {transcribing ? <LoaderCircle className="animate-spin" /> : <Sparkles />}
                {transcribing ? "កំពុង Transcribe…" : "Transcribe"}
              </Button>
              {episode && (
                <p className="mt-2 text-[9px] text-muted-foreground/70">
                  Chinese · {engine === "paraformer" ? "Paraformer" : "SenseSmall"} · Auto VAD
                </p>
              )}
              {error && (
                <p role="alert" className="mt-2 text-[10px] text-destructive">
                  {error}
                </p>
              )}
            </div>
          )
        ) : (
          <div className="m-auto p-4 text-center">
            <Languages className="mx-auto mb-3 size-7 text-muted-foreground/50" strokeWidth={1.3} />
            <p className="text-xs font-medium">
              {episode ? "No Khmer translation yet" : "No media selected"}
            </p>
            <p className="mt-2 max-w-[230px] text-[11px] leading-relaxed text-muted-foreground">
              {episode
                ? "Translate dialogue after transcription. Translation will stay linked to its source timing and speaker."
                : "Import and transcribe an episode before translating it."}
            </p>
          </div>
        )}
      </div>
      <div className="flex h-7 shrink-0 items-center justify-between border-t px-3 text-[9px] text-muted-foreground">
        <span>Source → Khmer</span>
        <span>{episode ? "AI dubbing" : "Inspector"}</span>
      </div>
    </section>
  );
}
