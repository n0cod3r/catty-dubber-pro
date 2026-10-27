import { useCallback, useEffect, useRef, useState } from "react";
import type { PersistedProject } from "@catty/contracts";
import { isTauri } from "@tauri-apps/api/core";
import { requestEngine } from "@/features/engine/client";
import { pickEpisodePath } from "@/features/episodes/import-episode";
import type { EpisodeMedia } from "@/features/episodes/types";

function basename(path: string) { return path.split(/[\\/]/).pop() ?? path; }
function toEpisodeMedia(episode: import("@catty/contracts").PersistedEpisode): EpisodeMedia {
  const path = episode.media.source_path;
  const name = basename(path);
  const extension = name.includes(".") ? (name.split(".").pop()?.toLowerCase() ?? "") : "";
  return { id: episode.id, path, playbackPath: episode.playback_proxy_path, name, extension, durationSeconds: episode.media.duration, width: episode.media.width, height: episode.media.height, fps: episode.media.fps, videoCodec: episode.media.video_codec, audioCodec: episode.media.audio_codec, sampleRate: episode.media.sample_rate, channels: episode.media.channels };
}

export function useEpisode(projectDirectory: string | null, project: PersistedProject | null) {
  const [episode, setEpisode] = useState<EpisodeMedia | null>(() => project?.episodes[0] ? toEpisodeMedia(project.episodes[0]) : null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const importLock = useRef(false);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { setEpisode(project?.episodes[0] ? toEpisodeMedia(project.episodes[0]) : null); }, [project]);
  useEffect(() => { const path = episode?.path; return () => { if (path?.startsWith("blob:")) URL.revokeObjectURL(path); }; }, [episode?.path]);
  const openEpisode = useCallback(async () => {
    if (importLock.current || !projectDirectory || !project) return;
    if (!isTauri()) { fileInputRef.current?.click(); return; }
    importLock.current = true; setImporting(true); setError(null);
    try {
      const selected = await pickEpisodePath(); if (!selected) return;
      const persisted = await requestEngine("project.import_episode", { project_directory: projectDirectory, project_name: project.name, source: selected });
      if (mounted.current) setEpisode(toEpisodeMedia(persisted));
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : "មិនអាច import episode នេះបានទេ។");
    } finally { importLock.current = false; if (mounted.current) setImporting(false); }
  }, [projectDirectory, project]);
  const importFile = useCallback((file: File) => {
    if (!/\.(mp4|mov|mkv|webm|m4v|avi)$/i.test(file.name)) { setError("សូមជ្រើស MP4, MOV, MKV, WebM, M4V ឬ AVI។"); return; }
    setError("Web preview មិនអាចរក្សាទុក episode ទៅ Project បានទេ។ សូមប្រើ Catty desktop app។");
  }, []);
  const updateMetadata = useCallback((id: string, metadata: Pick<EpisodeMedia, "durationSeconds" | "width" | "height">) => { setEpisode((current) => current?.id === id ? { ...current, ...metadata } : current); }, []);
  return { episode, importing, error, dismissError: () => setError(null), openEpisode, importFile, fileInputRef, updateMetadata };
}
