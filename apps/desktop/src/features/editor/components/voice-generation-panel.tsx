import { useEffect, useMemo, useRef, useState } from "react";

import type { DubStatus } from "@catty/contracts";
import { convertFileSrc } from "@tauri-apps/api/core";
import {
  ChevronRight,
  LoaderCircle,
  Mic,
  Play,
  RotateCcw,
  Settings2,
  Square,
  Users,
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
import { cn } from "@/lib/utils";

import type { TranslationEditing } from "../hooks/use-translation";
import type { TtsEditing, TtsTuning } from "../hooks/use-tts";
import type { VoiceAssignments } from "../hooks/use-voice-assignments";
import {
  DEFAULT_TTS_TUNING,
  EDGE_VOICE_PRESETS,
  matchingVoicePreset,
} from "../utils/voice-presets";

type RowStatus = DubStatus | "missing";

const STATUS_STYLE: Record<RowStatus, string> = {
  ready: "bg-primary/10 text-primary",
  generating: "bg-primary/10 text-primary",
  pending: "text-muted-foreground",
  outdated: "text-amber-500",
  failed: "text-destructive",
  missing: "text-muted-foreground",
};

export function VoiceGenerationPanel({
  episode,
  translation,
  tts,
  speakerVoices,
}: {
  episode: EpisodeMedia | null;
  translation: TranslationEditing;
  tts: TtsEditing;
  speakerVoices: VoiceAssignments;
}) {
  const rows = useMemo(
    () =>
      episode?.dialogueSegments?.filter((row) =>
        row.translation?.text?.trim(),
      ) ?? [],
    [episode?.dialogueSegments],
  );
  const speakerNames = useMemo(
    () => new Map((episode?.speakers ?? []).map((s) => [s.id, s.name])),
    [episode?.speakers],
  );
  const voice = tts.voices.find((item) => item.id === tts.voiceId);
  const [tuning, setTuning] = useState<TtsTuning>(DEFAULT_TTS_TUNING);
  const savedProfile = voice?.id.startsWith("library:") ?? false;
  const displayedTuning = voice?.tuning ?? tuning;
  const [preferredPreset, setPreferredPreset] = useState("normal");
  const presetId = matchingVoicePreset(
    displayedTuning,
    voice?.gender,
    preferredPreset,
  );
  const voiceItems = tts.voices.map((item) => ({
    label: `${item.name} · ${item.gender}`,
    value: item.id,
  }));
  const presetItems = [
    ...EDGE_VOICE_PRESETS.map((preset) => ({
      label: `${preset.label} · ${preset.pitch > 0 ? "+" : ""}${preset.pitch} Hz · 1.25×`,
      value: preset.id,
    })),
    { label: "Custom", value: "custom" },
  ];
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(
    null,
  );
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    setTuning(DEFAULT_TTS_TUNING);
    setPreferredPreset("normal");
    setPreviewingId(null);
    setEditing(null);
  }, [episode?.id]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, []);

  const readyCount = rows.filter(
    (row) => tts.dubByDialogue.get(row.id)?.status === "ready",
  ).length;

  const preview = async (segmentId: string, voiceId: string | null) => {
    if (tts.previewing) return;
    setPreviewingId(segmentId);
    try {
      const path = await tts.preview(segmentId, tuning, voiceId);
      if (!path || !mounted.current) return;
      audioRef.current?.pause();
      const audio = new Audio(convertFileSrc(path));
      audioRef.current = audio;
      void audio.play();
    } finally {
      setPreviewingId(null);
    }
  };

  const beginEdit = (segmentId: string, text: string) => {
    if (tts.generating || translation.busy) return;
    setEditing({ id: segmentId, text });
  };

  const saveEdit = async () => {
    if (!editing) return;
    const current = rows.find((row) => row.id === editing.id);
    const saved = await translation.updateText(
      editing.id,
      editing.text,
      current?.translation?.text ?? null,
    );
    if (saved) setEditing(null);
  };

  if (!episode) return null;
  return (
    <section
      className="flex min-h-0 flex-1 flex-col"
      aria-label="Voice generation"
    >
      <details className="group shrink-0 border-b">
        <summary className="flex h-8 cursor-pointer list-none items-center gap-1.5 px-2 text-[10px] outline-none select-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
          <Settings2 className="size-3 shrink-0 text-muted-foreground" />
          <span className="shrink-0 font-medium">Voice</span>
          <span
            className="min-w-0 flex-1 truncate text-muted-foreground"
            title={voice?.name}
          >
            {voice?.name ?? "No voice selected"}
          </span>
          <span className="shrink-0 text-[8px] tabular-nums text-muted-foreground">
            {displayedTuning.speed.toFixed(2)}× · p{displayedTuning.pitch} · v
            {displayedTuning.volume}
          </span>
          <ChevronRight className="size-3 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
        </summary>
        <div className="space-y-1.5 border-t px-2 py-2">
          <Select
            value={tts.voiceId}
            items={voiceItems}
            onValueChange={(value) => tts.setVoiceId(value || null)}
            disabled={tts.generating}
          >
            <SelectTrigger
              size="sm"
              aria-label="Khmer voice"
              className="w-full text-[10px]"
            >
              <SelectValue placeholder="Select a voice" />
            </SelectTrigger>
            <SelectContent align="start" className="min-w-72">
              <SelectGroup>
                {voiceItems.map((item) => (
                  <SelectItem
                    key={item.value}
                    value={item.value}
                    className="text-[11px]"
                  >
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          {savedProfile && (
            <p className="text-[9px] text-muted-foreground">
              Saved voice tuning is managed in Settings → Voices &amp; TTS.
            </p>
          )}
          {voice?.engine === "voxcpm2" && (
            <p className="text-[9px] text-muted-foreground">
              VoxCPM2 uses the saved reference and style. Edge tuning does not
              apply.
            </p>
          )}
          <Select
            value={presetId}
            items={presetItems}
            disabled={tts.generating || savedProfile}
            onValueChange={(id) => {
              const preset = EDGE_VOICE_PRESETS.find((item) => item.id === id);
              if (!preset) return;
              if (
                preset.gender &&
                voice?.gender.toLowerCase() !== preset.gender
              ) {
                const matchingVoice = tts.voices.find(
                  (item) => item.gender.toLowerCase() === preset.gender,
                );
                if (!matchingVoice) return;
                tts.setVoiceId(matchingVoice.id);
              }
              setPreferredPreset(preset.id);
              setTuning({ ...DEFAULT_TTS_TUNING, pitch: preset.pitch });
            }}
          >
            <SelectTrigger
              size="sm"
              aria-label="Edge voice preset"
              className="w-full text-[10px]"
            >
              <SelectValue placeholder="Voice preset">
                {EDGE_VOICE_PRESETS.find((preset) => preset.id === presetId)
                  ?.label ?? "Custom"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent align="start">
              <SelectGroup>
                {EDGE_VOICE_PRESETS.map((preset) => (
                  <SelectItem
                    key={preset.id}
                    value={preset.id}
                    disabled={
                      !!preset.gender &&
                      !tts.voices.some(
                        (item) => item.gender.toLowerCase() === preset.gender,
                      )
                    }
                    className="text-[11px]"
                  >
                    {preset.label} · {preset.pitch > 0 ? "+" : ""}
                    {preset.pitch} Hz · 1.25×
                  </SelectItem>
                ))}
                <SelectItem value="custom" disabled className="text-[11px]">
                  Custom
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1">
            <NumberControl
              label="Speed"
              value={displayedTuning.speed}
              min={0.5}
              max={2}
              step={0.05}
              disabled={tts.generating || savedProfile}
              onChange={(speed) => setTuning((value) => ({ ...value, speed }))}
            />
            <NumberControl
              label="Pitch"
              value={displayedTuning.pitch}
              min={-100}
              max={100}
              step={1}
              disabled={tts.generating || savedProfile}
              onChange={(pitch) => setTuning((value) => ({ ...value, pitch }))}
            />
            <NumberControl
              label="Volume"
              value={displayedTuning.volume}
              min={-100}
              max={100}
              step={1}
              disabled={tts.generating || savedProfile}
              onChange={(volume) =>
                setTuning((value) => ({ ...value, volume }))
              }
            />
          </div>
        </div>
      </details>

      {!!episode.speakers?.length && (
        <details className="group shrink-0 border-b">
          <summary className="flex h-8 cursor-pointer list-none items-center gap-1.5 px-2 text-[10px] outline-none select-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
            <Users className="size-3 shrink-0 text-muted-foreground" />
            <span className="shrink-0 font-medium">Speakers</span>
            <span className="min-w-0 flex-1 truncate text-muted-foreground">
              Default voice per speaker
            </span>
            <ChevronRight className="size-3 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
          </summary>
          <div className="space-y-1 border-t px-2 py-2">
            {episode.speakers.map((speaker) => {
              const assigning = tts.assigningSpeakerId === speaker.id;
              return (
                <div key={speaker.id} className="flex items-center gap-1.5">
                  <span
                    className="min-w-0 flex-1 truncate text-[10px]"
                    title={speaker.name}
                  >
                    {speaker.name}
                  </span>
                  {assigning && (
                    <LoaderCircle className="size-3 shrink-0 animate-spin text-primary motion-reduce:animate-none" />
                  )}
                  <Select
                    value={speakerVoices.voiceBySpeaker[speaker.id] ?? null}
                    items={voiceItems}
                    disabled={
                      tts.generating ||
                      !!tts.assigningSpeakerId ||
                      !!tts.assigningSegmentId
                    }
                    onValueChange={(voiceId) => {
                      if (voiceId)
                        void speakerVoices.assignSpeaker(speaker.id, voiceId);
                    }}
                  >
                    <SelectTrigger
                      size="sm"
                      aria-label={`Default voice for ${speaker.name}`}
                      className="w-36 text-[9px]"
                    >
                      <SelectValue placeholder="Speaker default" />
                    </SelectTrigger>
                    <SelectContent align="end" className="min-w-56">
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
                </div>
              );
            })}
            <p className="text-[8px] leading-snug text-muted-foreground">
              Lines with their own voice override keep it when the speaker
              default changes.
            </p>
          </div>
        </details>
      )}

      <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b px-2 py-1.5">
        <Button
          size="xs"
          variant="outline"
          className="h-6 shrink-0 text-[9px]"
          disabled={
            !tts.voiceId ||
            tts.generating ||
            translation.busy ||
            !!editing ||
            rows.length === 0
          }
          onClick={() => void tts.generate("missing", [], tuning)}
        >
          <Mic /> Generate missing
        </Button>
        {tts.generating ? (
          <>
            <LoaderCircle className="size-3 shrink-0 animate-spin text-primary motion-reduce:animate-none" />
            <span className="shrink-0 text-[9px] tabular-nums text-muted-foreground">
              {tts.progress?.completed ?? 0}/
              {tts.progress?.total ?? rows.length}
            </span>
            <progress
              aria-label="Voice generation progress"
              className="h-1.5 min-w-6 flex-1 accent-primary"
              max={Math.max(1, tts.progress?.total ?? rows.length)}
              value={tts.progress?.completed ?? 0}
            />
            <Button
              size="xs"
              variant="destructive"
              className="h-6 shrink-0 text-[9px]"
              onClick={() => void tts.cancel()}
            >
              <Square /> Cancel
            </Button>
          </>
        ) : (
          <span className="ml-auto shrink-0 text-[9px] tabular-nums text-muted-foreground">
            {readyCount}/{rows.length} ready
          </span>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        {rows.length === 0 && (
          <p className="p-3 text-[10px] text-muted-foreground">
            Translate dialogue to Khmer first — voice generation uses translated
            lines.
          </p>
        )}
        {rows.map((row, index) => {
          const dub = tts.dubByDialogue.get(row.id);
          const pending = tts.pendingSegmentIds.includes(row.id);
          const status: RowStatus = pending
            ? "generating"
            : tts.failedSegmentId === row.id
              ? "failed"
              : (dub?.status ?? "missing");
          const speaker = row.speakerId
            ? (speakerNames.get(row.speakerId) ?? "Speaker")
            : null;
          const lineVoice =
            speakerVoices.voiceBySegment[row.id] ??
            (row.speakerId
              ? speakerVoices.voiceBySpeaker[row.speakerId]
              : undefined) ??
            tts.voiceId;
          const lineVoiceName = tts.voices.find(
            (item) => item.id === lineVoice,
          )?.name;
          const isEditing = editing?.id === row.id;
          const canEdit = !tts.generating && !translation.busy;
          return (
            <div
              key={row.id}
              className={cn(
                "border-b border-l-2 border-l-transparent px-2 py-1.5 last:border-b-0",
                dub?.status === "ready" && "border-l-primary/40",
                isEditing && "border-l-primary bg-primary/5",
                !isEditing && "hover:bg-muted/40",
              )}
            >
              <div className="flex items-center gap-1">
                <span className="w-4 shrink-0 text-[8px] tabular-nums text-muted-foreground">
                  {index + 1}
                </span>
                {speaker && (
                  <span
                    className="max-w-20 shrink-0 truncate rounded border px-1 text-[8px] text-muted-foreground"
                    title={speaker}
                  >
                    {speaker}
                  </span>
                )}
                <span
                  className={cn(
                    "flex shrink-0 items-center gap-0.5 rounded px-1 text-[8px]",
                    STATUS_STYLE[status],
                  )}
                >
                  {status === "generating" && (
                    <LoaderCircle className="size-2.5 animate-spin motion-reduce:animate-none" />
                  )}
                  {status}
                </span>
                <span className="ml-auto flex shrink-0 items-center gap-0.5">
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={`Preview line ${index + 1}`}
                    title={`Preview line ${index + 1}${lineVoiceName ? ` with ${lineVoiceName}` : ""}`}
                    disabled={
                      !lineVoice ||
                      tts.generating ||
                      tts.previewing ||
                      translation.busy ||
                      !!editing
                    }
                    onClick={() => void preview(row.id, lineVoice ?? null)}
                  >
                    {previewingId === row.id ? (
                      <LoaderCircle className="animate-spin motion-reduce:animate-none" />
                    ) : (
                      <Play />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={`${dub ? "Regenerate" : "Generate"} line ${index + 1}`}
                    title={
                      dub
                        ? `Regenerate line ${index + 1}`
                        : `Generate line ${index + 1}`
                    }
                    disabled={
                      !tts.voiceId ||
                      tts.generating ||
                      translation.busy ||
                      pending ||
                      !!editing
                    }
                    onClick={() =>
                      void tts.generate("selected", [row.id], tuning)
                    }
                  >
                    {pending ? (
                      <LoaderCircle className="animate-spin motion-reduce:animate-none" />
                    ) : dub ? (
                      <RotateCcw />
                    ) : (
                      <Mic />
                    )}
                  </Button>
                </span>
              </div>
              {isEditing ? (
                <div className="mt-1 space-y-1">
                  <textarea
                    autoFocus
                    lang="km"
                    rows={2}
                    value={editing.text}
                    maxLength={100000}
                    disabled={translation.busy}
                    aria-label={`Edit Khmer line ${index + 1}`}
                    className="w-full resize-y rounded-md border bg-background px-1.5 py-1 text-[10px] leading-snug outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    onChange={(event) => {
                      const text = event.currentTarget.value;
                      setEditing((value) =>
                        value ? { ...value, text } : value,
                      );
                    }}
                    onKeyDown={(event) => {
                      if (event.nativeEvent.isComposing) return;
                      if (event.key === "Escape" && !translation.busy) {
                        event.preventDefault();
                        setEditing(null);
                      }
                      if (
                        (event.metaKey || event.ctrlKey) &&
                        event.key === "Enter"
                      ) {
                        event.preventDefault();
                        void saveEdit();
                      }
                    }}
                  />
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[8px] text-muted-foreground">
                      ⌘ / Ctrl + Enter to save · Esc to cancel
                    </span>
                    <div className="flex shrink-0 gap-1">
                      <Button
                        size="xs"
                        variant="ghost"
                        className="h-6 text-[9px]"
                        disabled={translation.busy}
                        onClick={() => setEditing(null)}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="xs"
                        className="h-6 text-[9px]"
                        disabled={
                          translation.busy ||
                          !editing.text.trim() ||
                          editing.text.trim() === (row.translation?.text ?? "")
                        }
                        onClick={() => void saveEdit()}
                      >
                        {translation.busy ? "Saving…" : "Save"}
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  className="mt-0.5 block w-full text-left text-[10px] leading-snug outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-default"
                  title={canEdit ? "Click to edit Khmer text" : undefined}
                  disabled={!canEdit}
                  onClick={() => beginEdit(row.id, row.translation?.text ?? "")}
                >
                  <span className="line-clamp-2">{row.translation?.text}</span>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {(tts.error || translation.error) && (
        <div className="shrink-0 space-y-1 border-t px-2 py-1.5">
          {tts.error && (
            <p role="alert" className="text-[9px] text-destructive">
              {tts.error}
            </p>
          )}
          {translation.error && (
            <p role="alert" className="text-[9px] text-destructive">
              {translation.error}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function NumberControl({
  label,
  value,
  min,
  max,
  step,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <label
      className="flex h-7 shrink-0 items-center gap-1 rounded-[min(var(--radius-md),10px)] border border-input pl-1.5 pr-1 text-[8px] text-muted-foreground transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 has-[:disabled]:opacity-50"
      title={label}
    >
      {label}
      <input
        className="h-5 w-6 min-w-0 appearance-none rounded bg-transparent text-right text-[10px] text-foreground outline-none [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        type="number"
        aria-label={label}
        disabled={disabled}
        value={draft ?? String(value)}
        min={min}
        max={max}
        step={step}
        onChange={(event) => {
          const text = event.target.value;
          setDraft(text);
          const next = Number(text);
          if (text.trim() === "" || !Number.isFinite(next)) return;
          onChange(Math.min(max, Math.max(min, next)));
        }}
        onBlur={() => setDraft(null)}
      />
    </label>
  );
}
