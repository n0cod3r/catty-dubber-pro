import { useEffect, useMemo, useState } from "react";

import { convertFileSrc } from "@tauri-apps/api/core";
import {
  LoaderCircle,
  Play,
  RotateCcw,
  Square,
  Volume2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";
import { cn } from "@/lib/utils";

import type { TtsEditing, TtsTuning } from "../hooks/use-tts";

const DEFAULT_TUNING: TtsTuning = { speed: 1, pitch: 0, volume: 0 };

export function VoiceGenerationPanel({
  episode,
  tts,
}: {
  episode: EpisodeMedia | null;
  tts: TtsEditing;
}) {
  const rows = useMemo(
    () =>
      episode?.dialogueSegments?.filter((row) => row.translation?.text?.trim()) ??
      [],
    [episode?.dialogueSegments],
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected =
    rows.find((row) => row.id === selectedId) ?? rows[0] ?? null;
  const existing = selected
    ? tts.dubByDialogue.get(selected.id)
    : undefined;
  const [tuning, setTuning] = useState<TtsTuning>(DEFAULT_TUNING);

  useEffect(() => {
    if (!selected) return;
    const dub = tts.dubByDialogue.get(selected.id);
    setTuning(
      dub
        ? { speed: dub.speed, pitch: dub.pitch, volume: dub.volume }
        : DEFAULT_TUNING,
    );
  }, [selected, tts.dubByDialogue]);

  const preview = async () => {
    if (!selected) return;
    const path = await tts.preview(selected.id, tuning);
    if (path) void new Audio(convertFileSrc(path)).play();
  };

  if (!episode) return null;
  return (
    <section
      className="shrink-0 border-b bg-card"
      aria-label="Voice generation"
    >
      <div className="flex h-8 items-center gap-2 border-b px-2">
        <Volume2 className="size-3 text-primary" />
        <span className="text-[10px] font-medium">Voice Generation</span>
        <span className="ml-auto text-[9px] text-muted-foreground">
          {episode.dubbingStatus ?? "idle"}
        </span>
      </div>
      <div className="space-y-2 p-2">
        <label className="block text-[9px] text-muted-foreground">
          Khmer voice
        </label>
        <select
          className="h-7 w-full rounded-md border bg-background px-2 text-[10px]"
          value={tts.voiceId ?? ""}
          disabled={tts.generating}
          onChange={(event) => tts.setVoiceId(event.target.value || null)}
        >
          {tts.voices.map((voice) => (
            <option key={voice.id} value={voice.id}>
              {voice.name} · {voice.gender}
            </option>
          ))}
        </select>

        <div className="grid grid-cols-3 gap-1.5">
          <NumberControl
            label="Speed"
            value={tuning.speed}
            min={0.5}
            max={2}
            step={0.05}
            onChange={(speed) => setTuning((value) => ({ ...value, speed }))}
          />
          <NumberControl
            label="Pitch"
            value={tuning.pitch}
            min={-100}
            max={100}
            step={1}
            onChange={(pitch) => setTuning((value) => ({ ...value, pitch }))}
          />
          <NumberControl
            label="Volume"
            value={tuning.volume}
            min={-100}
            max={100}
            step={1}
            onChange={(volume) => setTuning((value) => ({ ...value, volume }))}
          />
        </div>

        <div className="max-h-24 overflow-auto rounded-md border">
          {rows.map((row, index) => {
            const dub = tts.dubByDialogue.get(row.id);
            const active = row.id === selected?.id;
            return (
              <button
                key={row.id}
                type="button"
                className={cn(
                  "flex w-full items-center gap-2 border-b px-2 py-1 text-left text-[9px] last:border-b-0 hover:bg-muted/40",
                  active && "bg-primary/10",
                )}
                onClick={() => setSelectedId(row.id)}
              >
                <span className="w-5 text-muted-foreground">{index + 1}</span>
                <span className="min-w-0 flex-1 truncate">
                  {row.translation?.text}
                </span>
                <span
                  className={cn(
                    "rounded px-1 text-[8px]",
                    dub?.status === "ready"
                      ? "bg-primary/10 text-primary"
                      : dub?.status === "failed"
                        ? "text-destructive"
                        : "text-muted-foreground",
                  )}
                >
                  {dub?.status ?? "missing"}
                </span>
              </button>
            );
          })}
        </div>

        {tts.generating && tts.progress && (
          <div className="flex items-center gap-2 text-[9px] text-muted-foreground">
            <LoaderCircle className="size-3 animate-spin text-primary" />
            <span>
              {tts.progress.completed}/{tts.progress.total}
            </span>
            <progress
              className="h-1.5 flex-1 accent-primary"
              max={Math.max(1, tts.progress.total)}
              value={tts.progress.completed}
            />
          </div>
        )}

        <div className="flex flex-wrap gap-1">
          <Button
            size="xs"
            variant="outline"
            className="h-6 text-[9px]"
            disabled={!selected || tts.previewing || tts.generating}
            onClick={() => void preview()}
          >
            {tts.previewing ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Play />
            )}
            Preview selected
          </Button>
          <Button
            size="xs"
            variant="outline"
            className="h-6 text-[9px]"
            disabled={!selected || tts.generating}
            onClick={() =>
              selected && void tts.generate("selected", [selected.id], tuning)
            }
          >
            <RotateCcw /> Regenerate selected
          </Button>
          <Button
            size="xs"
            variant="outline"
            className="h-6 text-[9px]"
            disabled={tts.generating || rows.length === 0}
            onClick={() => void tts.generate("missing", [], tuning)}
          >
            Generate missing
          </Button>
          <Button
            size="xs"
            className="h-6 text-[9px]"
            disabled={tts.generating || rows.length === 0}
            onClick={() => void tts.generate("all", [], tuning)}
          >
            Regenerate all
          </Button>
          {tts.generating && (
            <Button
              size="xs"
              variant="destructive"
              className="h-6 text-[9px]"
              onClick={() => void tts.cancel()}
            >
              <Square /> Cancel
            </Button>
          )}
        </div>
        {existing && (
          <p className="text-[8px] text-muted-foreground">
            Selected: {existing.status} · {existing.speed.toFixed(2)}× · pitch{" "}
            {existing.pitch} · volume {existing.volume}
          </p>
        )}
        {tts.error && (
          <p role="alert" className="text-[9px] text-destructive">
            {tts.error}
          </p>
        )}
      </div>
    </section>
  );
}

function NumberControl({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="text-[8px] text-muted-foreground">
      {label}
      <input
        className="mt-0.5 h-6 w-full rounded border bg-background px-1 text-[9px] text-foreground"
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) =>
          onChange(Math.min(max, Math.max(min, Number(event.target.value))))
        }
      />
    </label>
  );
}
