import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { EdgeVoice, TranscriptSegment } from "@catty/contracts";
import {
  AlertTriangle,
  AudioLines,
  Film,
  Languages,
  LoaderCircle,
  MessageSquareText,
  Sparkles,
  Volume2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";
import type { MixDubClip } from "@/features/editor/deps/preview";
import { cn } from "@/lib/utils";
import { formatTime } from "@/shared/utils/time";

import type { DialogueEditing } from "../hooks/use-dialogue-editing";
import type { SeparationEditing } from "../hooks/use-separation";
import type { TranslationEditing } from "../hooks/use-translation";
import type { TtsEditing } from "../hooks/use-tts";
import { useVoiceAssignments } from "../hooks/use-voice-assignments";
import {
  activeDialogueId,
  dialogueScrollDelta,
} from "../utils/dialogue-follow";
import { isMergeDialogueShortcut } from "../utils/dialogue-shortcuts";
import { separationPhase } from "../utils/separation";
import { DialogueTextEditor } from "./dialogue-text-editor";
import { MixPanel } from "./mix-panel";
import { VoiceGenerationPanel } from "./voice-generation-panel";

const tabs = [
  { id: "source", label: "Dialogue", icon: MessageSquareText },
  { id: "translation", label: "Khmer", icon: Languages },
  { id: "voice", label: "Voice", icon: Volume2 },
  { id: "mix", label: "Mix", icon: AudioLines },
  { id: "properties", label: "Media", icon: Film },
] as const;
const transcriptionEngines = [
  { id: "paraformer", label: "Paraformer" },
  { id: "sense-small", label: "SenseSmall" },
] as const;
type TranscriptionEngine = (typeof transcriptionEngines)[number]["id"];
type DialogueRow = TranscriptSegment & { id: string; speakerId: string | null };
const TRANSCRIPTION_ENGINE_KEY = "catty.transcription-engine.v1";
const INHERIT_VOICE = "__inherit__";

function readTranscriptionEngine(): TranscriptionEngine {
  if (typeof window === "undefined") return "paraformer";
  return window.localStorage.getItem(TRANSCRIPTION_ENGINE_KEY) === "sense-small"
    ? "sense-small"
    : "paraformer";
}
function persistedSegments(
  segments: EpisodeMedia["dialogueSegments"],
): DialogueRow[] {
  return (segments ?? []).map((segment) => ({
    id: segment.id,
    start: segment.start,
    end: segment.end,
    speakerId: segment.speakerId ?? null,
    text: segment.sourceText,
    confidence: segment.confidence,
  }));
}
function hasSplittableText(text: string): boolean {
  return (text.match(/[\p{L}\p{N}]/gu) ?? []).length >= 2;
}

export function Inspector({
  episode,
  projectDirectory,
  currentTime,
  followTimeline,
  onSeek,
  dialogue,
  translation,
  tts,
  separation,
  mixClips,
  mixEnabled,
  onMixChange,
  onOpenModels,
}: {
  episode: EpisodeMedia | null;
  projectDirectory: string;
  currentTime: number;
  followTimeline: boolean;
  onSeek: (time: number) => void;
  dialogue: DialogueEditing;
  translation: TranslationEditing;
  tts: TtsEditing;
  separation: SeparationEditing;
  mixClips: MixDubClip[];
  mixEnabled: boolean;
  onMixChange: (enabled: boolean) => void;
  onOpenModels: () => void;
}) {
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("source");
  const [engine, setEngine] = useState<TranscriptionEngine>(
    readTranscriptionEngine,
  );
  const { busy, transcribing, error, historyCounts } = dialogue;
  const mixPhase = separationPhase(
    episode?.separationStatus,
    !!separation.background,
  );
  const speakerWarning =
    dialogue.speakerWarning ?? episode?.speakerError ?? null;
  const [segments, setSegments] = useState<DialogueRow[]>(() =>
    persistedSegments(episode?.dialogueSegments),
  );
  const listRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef(new Map<string, HTMLDivElement>());
  const voiceAssignments = useVoiceAssignments(episode, projectDirectory, tts);
  const activeId = activeDialogueId(segments, currentTime);
  const [textEditorId, setTextEditorId] = useState<string | null>(null);
  const textEditorSegment = segments.find(
    (segment) => segment.id === textEditorId,
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedIndex = useMemo(
    () => segments.findIndex((segment) => segment.id === selectedId),
    [segments, selectedId],
  );
  const selected =
    selectedIndex >= 0 ? (segments[selectedIndex] ?? null) : null;
  const canSplit =
    !!selected &&
    hasSplittableText(selected.text) &&
    currentTime > selected.start + 0.05 &&
    currentTime < selected.end - 0.05;
  const canMergeNext =
    selectedIndex >= 0 && selectedIndex < segments.length - 1;

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
  useEffect(
    () => window.localStorage.setItem(TRANSCRIPTION_ENGINE_KEY, engine),
    [engine],
  );
  useEffect(() => {
    const preview = transcribing
      ? dialogue.progress?.preview_segments
      : undefined;
    setSegments(
      preview?.length
        ? preview.map((segment) => ({ ...segment, speakerId: null }))
        : persistedSegments(episode?.dialogueSegments),
    );
    setSelectedId(null);
    setTextEditorId(null);
  }, [
    episode?.id,
    episode?.dialogueSegments,
    transcribing,
    dialogue.progress?.preview_segments,
  ]);

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
      if (
        !isMergeDialogueShortcut(event) ||
        tab !== "source" ||
        !canMergeNext ||
        busy
      )
        return;
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
          event.key.toLowerCase() !== "z" ||
          tab !== "source"
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
          {tab === "properties"
            ? "Source"
            : tab === "voice"
              ? (episode?.dubbingStatus ?? "idle")
              : tab === "mix"
                ? separation.separating
                  ? "separating"
                  : mixPhase
                : `${segments.length} lines`}
        </span>
      </div>
      <div
        role="tablist"
        aria-label="Inspector panels"
        className="flex h-9 shrink-0 border-b"
      >
        {tabs.map(({ id, label, icon: Icon }, index) => (
          <button
            key={id}
            id={`inspector-tab-${id}`}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`inspector-panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            className={cn(
              "flex min-w-0 flex-1 items-center justify-center gap-1.5 border-b-2 border-transparent px-1 text-[10px] text-muted-foreground outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring",
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
            {id === "voice" && tts.generating ? (
              <LoaderCircle className="size-3 animate-spin motion-reduce:animate-none" />
            ) : id === "mix" && separation.separating ? (
              <LoaderCircle className="size-3 animate-spin motion-reduce:animate-none" />
            ) : (
              <Icon className="size-3 shrink-0" />
            )}
            <span className="truncate">{label}</span>
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`inspector-panel-${tab}`}
        aria-labelledby={`inspector-tab-${tab}`}
        tabIndex={0}
        className={cn(
          "flex min-h-0 flex-1 flex-col outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring",
          tab === "voice" || tab === "mix"
            ? "overflow-hidden"
            : "overflow-auto",
        )}
      >
        {tab === "source" && transcribing && (
          <TranscriptionStatus dialogue={dialogue} />
        )}
        {tab === "voice" ? (
          <VoiceGenerationPanel
            episode={episode}
            translation={translation}
            tts={tts}
            speakerVoices={voiceAssignments}
          />
        ) : tab === "mix" ? (
          <MixPanel
            episode={episode}
            separation={separation}
            mixClips={mixClips}
            mixEnabled={mixEnabled}
            onMixChange={onMixChange}
            onOpenModels={onOpenModels}
          />
        ) : tab === "properties" && episode ? (
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
              ...(episode.fps
                ? [["Frame rate", `${episode.fps.toFixed(3)} fps`]]
                : []),
              ...(episode.videoCodec
                ? [["Video codec", episode.videoCodec]]
                : []),
              ...(episode.audioCodec
                ? [["Audio codec", episode.audioCodec]]
                : []),
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="mb-1 text-[10px] text-muted-foreground">
                  {label}
                </dt>
                <dd className="break-words">{value}</dd>
              </div>
            ))}
          </dl>
        ) : tab === "source" ? (
          <SourcePanel
            episode={episode}
            segments={segments}
            listRef={listRef}
            rowRefs={rowRefs}
            activeId={activeId}
            selectedId={selectedId}
            setSelectedId={setSelectedId}
            selected={selected}
            selectedIndex={selectedIndex}
            canSplit={canSplit}
            canMergeNext={canMergeNext}
            busy={busy}
            transcribing={transcribing}
            engine={engine}
            setEngine={setEngine}
            currentTime={currentTime}
            onSeek={onSeek}
            splitSelected={splitSelected}
            mergeNext={mergeNext}
            transcribe={transcribe}
            restoreDialogue={restoreDialogue}
            historyCounts={historyCounts}
            textEditorId={textEditorId}
            setTextEditorId={setTextEditorId}
            textEditorSegment={textEditorSegment}
            dialogue={dialogue}
            speakerWarning={speakerWarning}
            error={error}
            voices={tts.voices}
            speakerVoiceIds={voiceAssignments.voiceBySpeaker}
            segmentVoiceIds={voiceAssignments.voiceBySegment}
            assigningSegmentId={tts.assigningSegmentId}
            assigningDisabled={
              busy ||
              tts.generating ||
              !!tts.assigningSpeakerId ||
              !!tts.assigningSegmentId
            }
            onAssignSegmentVoice={voiceAssignments.assignSegment}
            voiceError={tts.error}
          />
        ) : (
          <TranslationPanel
            episode={episode}
            currentTime={currentTime}
            onSeek={onSeek}
            translation={translation}
          />
        )}
      </div>
      <div className="flex h-7 shrink-0 items-center justify-between border-t px-3 text-[9px] text-muted-foreground">
        <span>Source → Khmer</span>
        <span>{episode ? "AI dubbing" : "Inspector"}</span>
      </div>
    </section>
  );
}

function TranscriptionStatus({ dialogue }: { dialogue: DialogueEditing }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = dialogue.transcriptionStartedAt ?? Date.now();
    const tick = () => setElapsed(Math.floor((Date.now() - started) / 1000));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [dialogue.transcriptionStartedAt]);
  const progress = dialogue.progress;
  const labels = {
    preparing: "Preparing audio…",
    loading: "Loading speech models…",
    vad: "Detecting speech…",
    asr: "Recognizing dialogue…",
    punctuation: "Punctuation and speakers…",
    alignment: "Aligning dialogue…",
    saving: "Saving dialogue…",
    completed: "Dialogue saved",
    failed: "Transcription failed",
  };
  return (
    <div
      role="status"
      className="shrink-0 border-b bg-primary/5 px-3 py-2 text-[10px]"
    >
      <div className="flex items-center gap-2">
        <LoaderCircle className="size-3 animate-spin text-primary" />
        <span>
          {progress
            ? labels[progress.phase]
            : "Waiting for transcription engine…"}
        </span>
        <span className="ml-auto tabular-nums text-muted-foreground">
          {elapsed}s
        </span>
      </div>
      {progress && progress.total > 0 && (
        <div className="mt-1 flex items-center gap-2 text-muted-foreground">
          <span>
            ASR {progress.completed}/{progress.total} chunks
          </span>
          <progress
            aria-label="ASR chunk progress"
            max={progress.total}
            value={progress.completed}
            className="h-1.5 flex-1 accent-primary"
          />
        </div>
      )}
      {!!progress?.preview_segments.length &&
        progress.phase !== "completed" && (
          <p className="mt-1 text-[9px] text-muted-foreground">
            Live preview · final dialogue is saved when processing completes
          </p>
        )}
    </div>
  );
}

function TranslationPanel({
  episode,
  currentTime,
  onSeek,
  translation,
}: {
  episode: EpisodeMedia | null;
  currentTime: number;
  onSeek: (time: number) => void;
  translation: TranslationEditing;
}) {
  const rows = useMemo(
    () => episode?.dialogueSegments ?? [],
    [episode?.dialogueSegments],
  );
  const translated = rows.filter((row) => row.translation?.text).length;
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!translation.translating) return;
    const started = Date.now();
    setElapsed(0);
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [translation.translating]);
  const progress = translation.progress;
  const activeIds = translation.translating
    ? (progress?.active_segment_ids ?? [])
    : [];
  const [editingId, setEditingId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const editing = rows.find((row) => row.id === editingId);
  const selected = rows.find((row) => row.id === selectedId);
  useEffect(() => {
    if (selectedId && !rows.some((row) => row.id === selectedId))
      setSelectedId(null);
  }, [rows, selectedId]);
  if (!episode || rows.length === 0)
    return (
      <div className="m-auto p-4 text-center">
        <Languages
          className="mx-auto mb-3 size-7 text-muted-foreground/50"
          strokeWidth={1.3}
        />
        <p className="text-xs font-medium">
          {episode ? "Transcribe មុនពេលបកប្រែ" : "No media selected"}
        </p>
      </div>
    );
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-9 shrink-0 items-center justify-between gap-2 border-b px-2 py-1">
        <div>
          <p className="text-[10px] font-medium">Khmer Translation</p>
          <p className="text-[9px] text-muted-foreground">
            {translated}/{rows.length} lines ·{" "}
            {episode.translationStatus ?? "idle"}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1">
          {selected && (
            <Button
              size="xs"
              variant="outline"
              className="h-6 text-[9px]"
              disabled={
                translation.busy ||
                !!editing ||
                selected.translation?.manually_edited
              }
              onClick={() =>
                void translation.translate("selected", [selected.id])
              }
            >
              {translation.translating ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <Sparkles />
              )}
              Re-translate selected
            </Button>
          )}
          <Button
            size="xs"
            variant="outline"
            className="h-6 text-[9px]"
            disabled={
              translation.busy || !!editing || translated === rows.length
            }
            onClick={() => void translation.translate("missing")}
          >
            {translation.translating ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            Translate missing
          </Button>
          <Button
            size="xs"
            className="h-6 text-[9px]"
            disabled={translation.busy || !!editing}
            title="Replace all AI translations. Manual edits stay protected."
            onClick={() => {
              if (
                window.confirm(
                  "Re-translate all dialogue? Existing AI translations will be replaced. Manually edited translations will be preserved.",
                )
              )
                void translation.translate("all");
            }}
          >
            {translation.translating ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            Re-translate all
          </Button>
        </div>
      </div>
      {translation.translating && (
        <div
          role="status"
          className="flex shrink-0 items-center gap-2 border-b bg-primary/5 px-3 py-2 text-[10px]"
        >
          <LoaderCircle className="size-3 animate-spin text-primary" />
          <span>
            {progress
              ? `AI translating · ${progress.completed}/${progress.total} saved`
              : "Waiting for translation engine…"}
          </span>
          {progress && (
            <progress
              aria-label="Translation progress"
              max={Math.max(1, progress.total)}
              value={progress.completed}
              className="h-1.5 min-w-12 flex-1 accent-primary"
            />
          )}
          <span className="ml-auto tabular-nums text-muted-foreground">
            {elapsed}s
          </span>
        </div>
      )}
      <div className="grid h-7 shrink-0 grid-cols-[28px_78px_minmax(0,1fr)] items-center border-b bg-muted/20 px-2 text-[9px] font-medium text-muted-foreground">
        <span>#</span>
        <span>Time</span>
        <span>Chinese → Khmer</span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {rows.map((row, index) => {
          const active = currentTime >= row.start && currentTime < row.end;
          const selected = row.id === selectedId;
          return (
            <button
              key={row.id}
              type="button"
              className={cn(
                "grid w-full grid-cols-[28px_78px_minmax(0,1fr)] items-start border-b border-l-2 border-l-transparent px-2 py-1.5 text-left",
                active && "border-l-primary bg-primary/10",
                selected && "bg-primary/20 ring-1 ring-inset ring-primary/50",
                "hover:bg-muted/40",
              )}
              onClick={() => {
                setSelectedId(row.id);
                onSeek(row.start);
              }}
              onDoubleClick={() => {
                if (!translation.busy) setEditingId(row.id);
              }}
            >
              <span className="text-[9px] text-muted-foreground">
                {index + 1}
              </span>
              <span className="text-[9px] tabular-nums text-muted-foreground">
                {formatTime(row.start, true)}
              </span>
              <span className="min-w-0">
                <span
                  className="block truncate text-[9px] text-muted-foreground"
                  title={row.sourceText}
                >
                  {row.sourceText}
                </span>
                <span
                  className={cn(
                    "mt-0.5 block text-[11px] leading-[1.45]",
                    !row.translation?.text && "italic text-muted-foreground",
                  )}
                >
                  {activeIds.includes(row.id) && (
                    <span className="mr-1 inline-flex items-center gap-1 text-[9px] text-primary">
                      <LoaderCircle className="size-2.5 animate-spin" />
                      Translating…
                    </span>
                  )}
                  {row.translation?.text ?? "មិនទាន់បកប្រែ"}
                </span>
                {row.translation?.manually_edited && (
                  <span className="mt-0.5 inline-block rounded border px-1 text-[8px] text-muted-foreground">
                    Edited
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
      {editing && (
        <DialogueTextEditor
          key={`${editing.id}:${editing.translation?.updated_at ?? "new"}`}
          text={editing.translation?.text ?? ""}
          busy={translation.busy}
          onSave={(text) =>
            translation.updateText(
              editing.id,
              text,
              editing.translation?.text ?? null,
            )
          }
          onCancel={() => setEditingId(null)}
        />
      )}
      <div className="flex h-7 shrink-0 items-center justify-between border-t px-2 text-[9px] text-muted-foreground">
        <span>
          {selected
            ? "Selected line · Re-translate selected affects only this row"
            : "Select a line to re-translate"}
        </span>
        <span>Manual edits are protected</span>
      </div>
      {translation.error && (
        <p
          role="alert"
          className="border-t px-2 py-1.5 text-[10px] text-destructive"
        >
          {translation.error}
        </p>
      )}
    </div>
  );
}

function SourcePanel(props: {
  episode: EpisodeMedia | null;
  segments: DialogueRow[];
  listRef: React.RefObject<HTMLDivElement | null>;
  rowRefs: React.RefObject<Map<string, HTMLDivElement>>;
  activeId: string | null;
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  selected: DialogueRow | null;
  selectedIndex: number;
  canSplit: boolean;
  canMergeNext: boolean;
  busy: boolean;
  transcribing: boolean;
  engine: TranscriptionEngine;
  setEngine: (e: TranscriptionEngine) => void;
  currentTime: number;
  onSeek: (t: number) => void;
  splitSelected: () => unknown;
  mergeNext: () => unknown;
  transcribe: () => unknown;
  restoreDialogue: (redo: boolean) => unknown;
  historyCounts: { undo: number; redo: number };
  textEditorId: string | null;
  setTextEditorId: (id: string | null) => void;
  textEditorSegment: DialogueRow | undefined;
  dialogue: DialogueEditing;
  speakerWarning: string | null;
  error: string | null;
  voices: EdgeVoice[];
  speakerVoiceIds: Record<string, string>;
  segmentVoiceIds: Record<string, string>;
  assigningSegmentId: string | null;
  assigningDisabled: boolean;
  onAssignSegmentVoice: (segmentId: string, voiceId: string | null) => unknown;
  voiceError: string | null;
}) {
  const {
    episode,
    segments,
    listRef,
    rowRefs,
    activeId,
    selectedId,
    setSelectedId,
    canSplit,
    canMergeNext,
    busy,
    transcribing,
    engine,
    setEngine,
    onSeek,
    splitSelected,
    mergeNext,
    transcribe,
    restoreDialogue,
    historyCounts,
    textEditorId,
    setTextEditorId,
    textEditorSegment,
    dialogue,
    speakerWarning,
    error,
    voices,
    speakerVoiceIds,
    segmentVoiceIds,
    assigningSegmentId,
    assigningDisabled,
    onAssignSegmentVoice,
    voiceError,
  } = props;
  if (!segments.length)
    return (
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
            ? "ជ្រើស engine ហើយចុច Transcribe។ Catty នឹងបង្កើត Dialogue និង Speaker ដោយស្វ័យប្រវត្តិ។"
            : "Import an episode to start."}
        </p>
        {episode && (
          <div className="mt-3 flex items-center rounded-md border bg-muted/30 p-0.5">
            {transcriptionEngines.map((item) => (
              <Button
                key={item.id}
                size="xs"
                variant={engine === item.id ? "default" : "ghost"}
                className="h-6 px-2 text-[9px]"
                disabled={busy}
                onClick={() => setEngine(item.id)}
              >
                {item.label}
              </Button>
            ))}
          </div>
        )}
        {episode && (
          <Button
            size="sm"
            className="mt-3 h-7 text-[10px]"
            disabled={busy}
            onClick={() => void transcribe()}
          >
            {transcribing ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            {transcribing ? "Transcribing…" : "Transcribe"}
          </Button>
        )}
      </div>
    );
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-9 shrink-0 items-center gap-1 border-b px-2 py-1">
        <div className="flex items-center rounded-md border bg-muted/30 p-0.5">
          {transcriptionEngines.map((item) => (
            <Button
              key={item.id}
              size="xs"
              variant={engine === item.id ? "default" : "ghost"}
              className="h-6 px-2 text-[9px]"
              disabled={busy}
              onClick={() => setEngine(item.id)}
            >
              {item.label}
            </Button>
          ))}
        </div>
        <Button
          size="xs"
          className="ml-auto h-6 text-[9px]"
          disabled={!episode || busy}
          onClick={() => void transcribe()}
        >
          {transcribing ? (
            <LoaderCircle className="animate-spin" />
          ) : (
            <Sparkles />
          )}
          {transcribing ? "Transcribing…" : "Transcribe"}
        </Button>
      </div>
      {speakerWarning && (
        <div className="flex items-start gap-1.5 border-b bg-amber-500/5 px-2 py-1.5 text-[9px] text-amber-600">
          <AlertTriangle className="mt-0.5 size-3 shrink-0" />
          <span>
            Speaker detection failed; transcript is preserved. {speakerWarning}
          </span>
        </div>
      )}
      <div ref={listRef} className="min-h-0 flex-1 overflow-auto">
        {segments.map((segment, index) => {
          const active = segment.id === activeId;
          const selectedRow = segment.id === selectedId;
          const speaker = (episode?.speakers ?? []).find(
            (item) => item.id === segment.speakerId,
          );
          const speakerId = segment.speakerId;
          const assigning = assigningSegmentId === segment.id;
          const overrideVoiceId = segmentVoiceIds[segment.id];
          const overrideVoice = overrideVoiceId
            ? voices.find((voice) => voice.id === overrideVoiceId)
            : undefined;
          const inheritedVoiceId = speakerId
            ? speakerVoiceIds[speakerId]
            : undefined;
          const inheritedVoice = inheritedVoiceId
            ? voices.find((voice) => voice.id === inheritedVoiceId)
            : undefined;
          const inheritLabel = speaker
            ? inheritedVoice
              ? `${speaker.name} default · ${inheritedVoice.name}`
              : `${speaker.name} default (unset)`
            : "Global default";
          const voiceItems = [
            { label: inheritLabel, value: INHERIT_VOICE },
            ...voices.map((voice) => ({
              label: `${voice.name} · ${voice.gender}`,
              value: voice.id,
            })),
          ];
          return (
            <div
              key={segment.id}
              ref={(node) => {
                if (node) rowRefs.current.set(segment.id, node);
                else rowRefs.current.delete(segment.id);
              }}
              className={cn(
                "flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-l-2 border-l-transparent px-2 py-1.5",
                active && "border-l-primary bg-primary/10",
                selectedRow &&
                  "bg-primary/20 ring-1 ring-inset ring-primary/50",
                "hover:bg-muted/40",
              )}
            >
              <button
                type="button"
                className="grid min-w-48 flex-1 grid-cols-[28px_74px_42px_minmax(0,1fr)] items-start gap-x-3 text-left"
                onClick={() => {
                  setSelectedId(segment.id);
                  onSeek(segment.start);
                }}
                onDoubleClick={() => setTextEditorId(segment.id)}
              >
                <span className="text-[9px] text-muted-foreground">
                  {index + 1}
                </span>
                <span className="text-[9px] tabular-nums text-muted-foreground">
                  {formatTime(segment.start, true)}
                </span>
                <span className="rounded bg-primary/10 px-1 py-0.5 text-center text-[8px] font-medium text-primary">
                  {speaker?.name ?? "—"}
                </span>
                <span className="min-w-0 text-[11px] leading-[1.45]">
                  {segment.text}
                </span>
              </button>
              <div className="flex shrink-0 items-center gap-1">
                <Volume2
                  className={cn(
                    "size-2.5 shrink-0",
                    overrideVoiceId ? "text-primary" : "text-muted-foreground",
                  )}
                />
                <Select
                  value={overrideVoiceId ?? INHERIT_VOICE}
                  items={voiceItems}
                  disabled={assigningDisabled}
                  onValueChange={(voiceId) => {
                    if (!voiceId) return;
                    void onAssignSegmentVoice(
                      segment.id,
                      voiceId === INHERIT_VOICE ? null : voiceId,
                    );
                  }}
                >
                  <SelectTrigger
                    size="sm"
                    aria-label={`Voice override for line ${index + 1}`}
                    title={
                      overrideVoice
                        ? `Line override: ${overrideVoice.name} · ${overrideVoice.gender}. Existing audio is kept and marked outdated until regenerated.`
                        : `Uses ${speaker ? `${speaker.name}'s default` : "the global default"} voice. Pick a voice to override this line only.`
                    }
                    className="w-36 pr-1 pl-1.5 text-[8px]"
                  >
                    <SelectValue placeholder="Default" />
                  </SelectTrigger>
                  <SelectContent align="start" className="min-w-64">
                    <SelectGroup>
                      {voiceItems.map((item) => (
                        <SelectItem
                          key={item.value}
                          value={item.value}
                          className="text-[10px]"
                        >
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                {assigning && (
                  <LoaderCircle className="size-3 shrink-0 animate-spin text-primary motion-reduce:animate-none" />
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex min-h-8 shrink-0 items-center gap-1 border-t px-2">
        <Button
          size="xs"
          variant="outline"
          className="h-6 text-[9px]"
          disabled={!canSplit || busy}
          onClick={() => void splitSelected()}
        >
          Split
        </Button>
        <Button
          size="xs"
          variant="outline"
          className="h-6 text-[9px]"
          disabled={!canMergeNext || busy}
          onClick={() => void mergeNext()}
        >
          Merge next
        </Button>
        <Button
          size="xs"
          variant="ghost"
          className="ml-auto h-6 text-[9px]"
          disabled={!historyCounts.undo || busy}
          onClick={() => void restoreDialogue(false)}
        >
          Undo {historyCounts.undo || ""}
        </Button>
        <Button
          size="xs"
          variant="ghost"
          className="h-6 text-[9px]"
          disabled={!historyCounts.redo || busy}
          onClick={() => void restoreDialogue(true)}
        >
          Redo {historyCounts.redo || ""}
        </Button>
      </div>
      {textEditorId && textEditorSegment && (
        <DialogueTextEditor
          key={`${textEditorSegment.id}:${textEditorSegment.text}`}
          text={textEditorSegment.text}
          busy={busy}
          onSave={(text) =>
            dialogue.updateText(
              textEditorSegment.id,
              text,
              textEditorSegment.text,
            )
          }
          onCancel={() => setTextEditorId(null)}
        />
      )}{" "}
      {error && (
        <p
          role="alert"
          className="border-t px-2 py-1.5 text-[10px] text-destructive"
        >
          {error}
        </p>
      )}
      {voiceError && (
        <p
          role="alert"
          className="border-t px-2 py-1.5 text-[10px] text-destructive"
        >
          {voiceError}
        </p>
      )}
    </div>
  );
}
