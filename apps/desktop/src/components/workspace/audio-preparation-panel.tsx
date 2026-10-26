import { useEffect, useRef, useState } from "react";

import type { AudioAsset } from "@catty/contracts";
import { isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { AudioLines, Check, FolderOpen, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cancelAudio, prepareAudio } from "@/features/engine/client";
import type { EpisodeMedia } from "@/features/episodes/types";

function errorMessage(error: unknown) {
  return typeof error === "object" && error !== null && "message" in error
    ? String(error.message)
    : String(error);
}
function cancelled(error: unknown) {
  return (
    typeof error === "object" && error !== null && "code" in error && error.code === "CANCELLED"
  );
}

export function AudioPreparationPanel({ episode }: { episode: EpisodeMedia }) {
  const [asset, setAsset] = useState<AudioAsset | null>(null);
  const [directory, setDirectory] = useState<string | null>(null);
  const [state, setState] = useState<
    "idle" | "choosing" | "running" | "cancelling" | "ready" | "cancelled" | "error"
  >("idle");
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);
  const busyRef = useRef(false);
  const jobRef = useRef<string | null>(null);
  const desktop = isTauri() && !episode.path.startsWith("blob:");
  const busy = state === "choosing" || state === "running" || state === "cancelling";

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (jobRef.current) void cancelAudio(jobRef.current).catch(() => {});
    };
  }, []);

  async function prepare() {
    if (!desktop || busyRef.current) return;
    busyRef.current = true;
    setError(null);
    try {
      let destination = directory;
      if (!destination) {
        setState("choosing");
        const selected = await open({
          directory: true,
          multiple: false,
          title: "Choose the folder for prepared episode audio",
        });
        if (!mounted.current) return;
        if (!selected || Array.isArray(selected)) {
          setState(asset ? "ready" : "idle");
          return;
        }
        destination = selected;
        setDirectory(destination);
      }
      const job = crypto.randomUUID();
      jobRef.current = job;
      setState("running");
      const result = await prepareAudio(job, {
        source: episode.path,
        episode_id: episode.id,
        project_directory: destination,
        existing_asset: asset,
      });
      if (mounted.current && jobRef.current === job) {
        setAsset(result);
        setState("ready");
      }
    } catch (cause) {
      if (mounted.current) {
        setState(cancelled(cause) ? "cancelled" : "error");
        if (!cancelled(cause)) setError(errorMessage(cause));
      }
    } finally {
      jobRef.current = null;
      busyRef.current = false;
    }
  }
  async function cancel() {
    const job = jobRef.current;
    if (!job) return;
    setState("cancelling");
    try {
      await cancelAudio(job);
    } catch (cause) {
      if (mounted.current) {
        setState("running");
        setError(`Could not cancel: ${errorMessage(cause)}`);
      }
    }
  }

  return (
    <section
      aria-label="Audio preparation"
      className="mt-5 space-y-3 rounded-lg border bg-background/40 p-3 text-[11px]"
      aria-busy={busy}
    >
      <h3 className="flex items-center gap-2 font-medium">
        <AudioLines className="size-3.5 text-primary" />
        Audio preparation
      </h3>
      <p className="leading-relaxed text-muted-foreground">
        Extract a 16 kHz mono WAV for speech recognition. The original media stays unchanged.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          size="xs"
          variant="outline"
          disabled={!desktop || busy}
          onClick={() => {
            void prepare();
          }}
        >
          {busy ? <LoaderCircle className="animate-spin" /> : asset ? <Check /> : <AudioLines />}
          {state === "choosing"
            ? "Choose folder…"
            : busy
              ? "Preparing…"
              : asset
                ? "Check / reuse speech audio"
                : "Prepare speech audio"}
        </Button>
        {(state === "running" || state === "cancelling") && (
          <Button
            size="xs"
            variant="ghost"
            disabled={state === "cancelling"}
            onClick={() => {
              void cancel();
            }}
          >
            {state === "cancelling" ? "Cancelling…" : "Cancel"}
          </Button>
        )}
        {directory && !busy && (
          <Button
            size="xs"
            variant="ghost"
            onClick={() => {
              setDirectory(null);
              setAsset(null);
              setState("idle");
            }}
          >
            <FolderOpen />
            Change folder
          </Button>
        )}
      </div>
      {!desktop && (
        <p className="text-muted-foreground">Available for videos imported in the desktop app.</p>
      )}
      {busy && (
        <p role="status" className="flex items-center gap-2 text-muted-foreground">
          <LoaderCircle className="size-3 animate-spin" />
          {state === "choosing"
            ? "Choose an output folder."
            : state === "cancelling"
              ? "Stopping FFmpeg…"
              : "Preparing source audio in the background…"}
        </p>
      )}
      {state === "cancelled" && (
        <p role="status" className="text-muted-foreground">
          Audio preparation cancelled. You can retry.
        </p>
      )}
      {error && (
        <p role="alert" className="break-words text-destructive">
          {error}
        </p>
      )}
      {asset && (
        <div className="space-y-1 border-t pt-2">
          <p role="status" className="text-emerald-400">
            {state === "ready" ? "Speech audio ready" : "Previous speech audio"} ·{" "}
            {asset.sample_rate.toLocaleString()} Hz ·{" "}
            {asset.channels === 1 ? "Mono" : `${asset.channels} channels`}
          </p>
          <p className="font-mono text-[9px] break-all text-muted-foreground" title={asset.path}>
            {asset.path}
          </p>
        </div>
      )}
    </section>
  );
}
