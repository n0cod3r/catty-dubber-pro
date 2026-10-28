import { useEffect, useState } from "react";

import {
  AudioLines,
  LoaderCircle,
  Scissors,
  Volume2,
  VolumeX,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";
import type { MixDubClip } from "@/features/editor/deps/preview";
import { cn } from "@/lib/utils";

import type { SeparationEditing } from "../hooks/use-separation";
import {
  separationNeedsModel,
  separationPhase,
  type SeparationPhase,
} from "../utils/separation";

const PHASE_LABEL: Record<SeparationPhase, string> = {
  idle: "Not separated",
  interrupted: "Interrupted",
  ready: "Ready",
  failed: "Failed",
};
const PHASE_STYLE: Record<SeparationPhase, string> = {
  idle: "text-muted-foreground",
  interrupted: "text-amber-500",
  ready: "bg-primary/10 text-primary",
  failed: "text-destructive",
};

export function MixPanel({
  episode,
  separation,
  mixClips,
  mixEnabled,
  onMixChange,
  onOpenModels,
}: {
  episode: EpisodeMedia | null;
  separation: SeparationEditing;
  mixClips: MixDubClip[];
  mixEnabled: boolean;
  onMixChange: (enabled: boolean) => void;
  onOpenModels: () => void;
}) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!separation.separating) {
      setElapsed(0);
      return;
    }
    const started = separation.startedAt ?? Date.now();
    const tick = () => setElapsed(Math.floor((Date.now() - started) / 1000));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [separation.separating, separation.startedAt]);

  if (!episode) return null;
  const phase = separationPhase(
    episode.separationStatus,
    !!separation.background,
  );
  const translated = (episode.dialogueSegments ?? []).filter((row) =>
    row.translation?.text?.trim(),
  ).length;
  const silent = Math.max(0, translated - mixClips.length);
  const background = separation.background;

  return (
    <section className="flex min-h-0 flex-1 flex-col" aria-label="Dub mix">
      <div className="shrink-0 space-y-2 border-b p-3">
        <div className="flex items-center gap-1.5">
          <Scissors className="size-3.5 shrink-0 text-muted-foreground" />
          <p className="text-[10px] font-medium">Dialogue removal</p>
          <span
            className={cn(
              "ml-auto flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[8px]",
              PHASE_STYLE[phase],
            )}
          >
            {separation.separating && (
              <LoaderCircle className="size-2.5 animate-spin motion-reduce:animate-none" />
            )}
            {separation.separating ? "Separating…" : PHASE_LABEL[phase]}
          </span>
        </div>
        <p className="text-[9px] leading-relaxed text-muted-foreground">
          Removes the original voices and keeps music and effects. Runs locally
          with the UVR dialogue-removal model.
        </p>
        <div className="flex items-center gap-1.5">
          <Button
            size="xs"
            variant="outline"
            className="h-6 shrink-0 text-[9px]"
            disabled={separation.separating}
            aria-busy={separation.separating}
            onClick={() => void separation.separate()}
          >
            {separation.separating ? (
              <LoaderCircle className="animate-spin motion-reduce:animate-none" />
            ) : (
              <Scissors />
            )}
            {separation.separating
              ? "Separating…"
              : phase === "ready"
                ? "Re-separate"
                : "Separate audio"}
          </Button>
          {separation.separating && (
            <span className="text-[9px] tabular-nums text-muted-foreground">
              {elapsed}s · local CPU
            </span>
          )}
          {!separation.separating && background && (
            <span className="truncate text-[9px] text-muted-foreground">
              {Math.round(background.sample_rate / 1000)} kHz ·{" "}
              {background.channels === 1 ? "mono" : "stereo"}
            </span>
          )}
        </div>
        {phase === "interrupted" && !separation.separating && (
          <p className="text-[9px] text-amber-500">
            The previous run was interrupted. Run separation again.
          </p>
        )}
        {separation.error && (
          <div className="space-y-1">
            <p role="alert" className="text-[9px] text-destructive">
              {separation.error}
            </p>
            {separationNeedsModel(separation.error) && (
              <Button
                size="xs"
                variant="outline"
                className="h-6 text-[9px]"
                onClick={onOpenModels}
              >
                Open Models settings
              </Button>
            )}
          </div>
        )}
      </div>

      <div className="shrink-0 space-y-2 border-b p-3">
        <div className="flex items-center gap-1.5">
          <AudioLines className="size-3.5 shrink-0 text-muted-foreground" />
          <p className="text-[10px] font-medium">Preview mix</p>
          {mixEnabled && background && (
            <span className="ml-auto rounded bg-emerald-500/10 px-1.5 py-0.5 text-[8px] text-emerald-400">
              Playing
            </span>
          )}
        </div>
        <Button
          size="xs"
          variant={mixEnabled && background ? "secondary" : "outline"}
          className="h-6 text-[9px]"
          aria-pressed={mixEnabled && !!background}
          disabled={!background}
          onClick={() => onMixChange(!mixEnabled)}
        >
          {mixEnabled && background ? <Volume2 /> : <VolumeX />}
          {mixEnabled && background ? "Turn off mix" : "Hear the dub mix"}
        </Button>
        <p className="text-[9px] leading-relaxed text-muted-foreground">
          {background
            ? "Plays the background stem under the video and lays generated Khmer lines on top."
            : "Separate the audio first to hear Khmer lines over the background."}
        </p>
        <div className="flex items-center justify-between gap-2 text-[9px] tabular-nums">
          <span className="text-muted-foreground">
            {mixClips.length}/{translated || 0} Khmer lines in mix
          </span>
          {silent > 0 && (
            <span className="text-amber-500">
              {silent} line{silent === 1 ? "" : "s"} silent
            </span>
          )}
        </div>
        {translated === 0 && (
          <p className="text-[9px] text-muted-foreground">
            Translate and generate Khmer voice lines to place them in the mix.
          </p>
        )}
        <p className="text-[8px] leading-snug text-muted-foreground">
          The source voices are muted while the mix plays. Use the preview mute
          button to silence everything.
        </p>
      </div>
    </section>
  );
}
