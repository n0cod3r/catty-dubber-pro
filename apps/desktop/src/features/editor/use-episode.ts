import { useCallback, useEffect, useRef, useState } from "react";

import { isTauri } from "@tauri-apps/api/core";

import { requestEngine } from "@/features/engine/client";
import { pickEpisodePath } from "@/features/episodes/import-episode";
import type { EpisodeMedia } from "@/features/episodes/types";

const DEFAULT_PROJECT_NAME = "Default Project";

function basename(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

function defaultProjectDirectory(sourcePath: string) {
  const separator = sourcePath.includes("\\") ? "\\" : "/";
  const parts = sourcePath.split(/[\\/]/);
  parts.pop();
  const parent = parts.join(separator) || ".";
  return `${parent}${separator}.catty-dubber-pro`;
}

function toEpisodeMedia(episode: import("@catty/contracts").PersistedEpisode): EpisodeMedia {
  const path = episode.media.source_path;
  const name = basename(path);
  const extension = name.includes(".") ? (name.split(".").pop()?.toLowerCase() ?? "") : "";

  return {
    id: episode.id,
    path,
    name,
    extension,
    durationSeconds: episode.media.duration,
    width: episode.media.width,
    height: episode.media.height,
    fps: episode.media.fps,
    videoCodec: episode.media.video_codec,
    audioCodec: episode.media.audio_codec,
    sampleRate: episode.media.sample_rate,
    channels: episode.media.channels,
  };
}

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
      const selected = await pickEpisodePath();
      if (!selected) return;

      const persisted = await requestEngine("project.import_episode", {
        project_directory: defaultProjectDirectory(selected),
        project_name: DEFAULT_PROJECT_NAME,
        source: selected,
      });

      if (mounted.current) setEpisode(toEpisodeMedia(persisted));
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
