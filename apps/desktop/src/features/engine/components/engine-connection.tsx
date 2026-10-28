import { useCallback, useEffect, useState } from "react";

import { isTauri } from "@tauri-apps/api/core";
import { Circle, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { requestEngine } from "../services/client";

export function EngineConnection() {
  const [state, setState] = useState<
    | "checking"
    | "ready"
    | "missing-ffprobe"
    | "missing-ffmpeg"
    | "offline"
    | "web"
  >("checking");
  const [message, setMessage] = useState("");
  const check = useCallback(async (active: () => boolean = () => true) => {
    if (!isTauri()) {
      setState("web");
      return;
    }
    setState("checking");
    try {
      const status = await requestEngine("health", {});
      if (!active()) return;
      setState(
        !status.ffprobe_available
          ? "missing-ffprobe"
          : !status.ffmpeg_available
            ? "missing-ffmpeg"
            : "ready",
      );
      setMessage(
        status.ffprobe_available && status.ffmpeg_available
          ? `${status.name} ${status.version}`
          : "Engine is running, but FFmpeg or FFprobe is missing from PATH. Install FFmpeg and restart Catty.",
      );
    } catch (cause) {
      if (active()) {
        setState("offline");
        setMessage(
          cause instanceof Error ? cause.message : "Engine unavailable",
        );
      }
    }
  }, []);
  useEffect(() => {
    let active = true;
    void check(() => active);
    return () => {
      active = false;
    };
  }, [check]);
  return (
    <Button
      size="xs"
      variant="ghost"
      disabled={state === "checking" || state === "web"}
      onClick={() => {
        void check();
      }}
      title={
        message ||
        "The Python engine is available in the desktop app. Click to check again."
      }
      aria-label="Check engine connection"
    >
      {state === "checking" ? (
        <LoaderCircle className="size-3 animate-spin" />
      ) : (
        <Circle
          className={cn(
            "size-2 fill-current",
            state === "ready"
              ? "text-emerald-400"
              : state === "offline"
                ? "text-destructive"
                : "text-amber-400",
          )}
        />
      )}
      {state === "checking"
        ? "Connecting engine…"
        : state === "ready"
          ? "Engine online"
          : state === "offline"
            ? "Engine offline · retry"
            : state === "web"
              ? "Engine · desktop only"
              : state === "missing-ffmpeg"
                ? "FFmpeg missing · retry"
                : "FFprobe missing · retry"}
    </Button>
  );
}
