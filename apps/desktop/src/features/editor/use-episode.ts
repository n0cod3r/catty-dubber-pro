import { useCallback, useEffect, useRef, useState } from "react";

import { isTauri } from "@tauri-apps/api/core";

import { requestEngine } from "@/features/engine/client";
import { importEpisode } from "@/features/episodes/import-episode";
import type { EpisodeMedia } from "@/features/episodes/types";

export function useEpisode() {
  const [episode, setEpisode] = useState<EpisodeMedia | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const importLock = useRef(false);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const path = episode?.path;
    return () => {
      if (path?.startsWith("blob:")) URL.revokeObjectURL(path);
    };
  }, [episode?.path]);

  const openEpisode = useCallback(async () => {
    if (importLock.current) return;
    if (!isTauri()) {
      fileInputRef.current?.click();
      return;
    }
    importLock.current = true;
    setImporting(true);
    setError(null);
    try {
      const selected = await importEpisode();
      if (mounted.current && selected) {
        setEpisode(selected);
        try {
          const media = await requestEngine("media.probe", { path: selected.path });
          if (mounted.current)
            setEpisode((current) =>
              current?.id === selected.id
                ? {
                    ...current,
                    durationSeconds: current.durationSeconds ?? media.duration,
                    width: current.width ?? media.width,
                    height: current.height ?? media.height,
                    fps: media.fps,
                    videoCodec: media.video_codec,
                    audioCodec: media.audio_codec,
                    sampleRate: media.sample_rate,
                    channels: media.channels,
                  }
                : current,
            );
        } catch (cause) {
          if (mounted.current)
            setError(
              `Video imported, but engine metadata could not be read: ${cause instanceof Error ? cause.message : "Engine unavailable"}`,
            );
        }
      }
    } catch (cause) {
      if (mounted.current)
        setError(
          cause instanceof Error ? cause.message : "Could not open this episode. Please try again.",
        );
    } finally {
      importLock.current = false;
      if (mounted.current) setImporting(false);
    }
  }, []);

  const importFile = useCallback((file: File) => {
    if (!/\.(mp4|mov|mkv|webm|m4v|avi)$/i.test(file.name)) {
      setError("Choose an MP4, MOV, MKV, WebM, M4V, or AVI video.");
      return;
    }
    setError(null);
    setEpisode({
      id: crypto.randomUUID(),
      path: URL.createObjectURL(file),
      name: file.name,
      extension: file.name.split(".").pop()?.toLowerCase() ?? "",
      durationSeconds: null,
      width: null,
      height: null,
    });
  }, []);

  const updateMetadata = useCallback(
    (id: string, metadata: Pick<EpisodeMedia, "durationSeconds" | "width" | "height">) => {
      setEpisode((current) => (current?.id === id ? { ...current, ...metadata } : current));
    },
    [],
  );

  return {
    episode,
    importing,
    error,
    dismissError: () => setError(null),
    openEpisode,
    importFile,
    fileInputRef,
    updateMetadata,
  };
}
