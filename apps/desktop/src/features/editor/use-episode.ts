import { useCallback, useEffect, useRef, useState } from "react";
import type { PersistedEpisode, PersistedProject } from "@catty/contracts";
import { isTauri } from "@tauri-apps/api/core";
import { requestEngine } from "@/features/engine/client";
import { pickEpisodePath } from "@/features/episodes/import-episode";
import type { EpisodeMedia } from "@/features/episodes/types";

function basename(path: string) { return path.split(/[\\/]/).pop() ?? path; }
function toEpisodeMedia(episode: PersistedEpisode): EpisodeMedia {
  const path = episode.media.source_path;
  const name = basename(path);
  const extension = name.includes(".") ? (name.split(".").pop()?.toLowerCase() ?? "") : "";
  return { id: episode.id, path, playbackPath: episode.playback_proxy_path, name, extension, durationSeconds: episode.media.duration, width: episode.media.width, height: episode.media.height, fps: episode.media.fps, videoCodec: episode.media.video_codec, audioCodec: episode.media.audio_codec, sampleRate: episode.media.sample_rate, channels: episode.media.channels };
}

export function useEpisode(projectDirectory: string | null, project: PersistedProject | null) {
  const [episode, setEpisode] = useState<EpisodeMedia | null>(() => project?.episodes[0] ? toEpisodeMedia(project.episodes[0]) : null);
  const [importing, setImporting] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const importLock = useRef(false);
  const preparationKey = useRef<string | null>(null);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    const first = project?.episodes[0];
    setEpisode(first ? toEpisodeMedia(first) : null);
    if (!first || !projectDirectory || !isTauri() || first.playback_proxy_path) {
      setPreparing(false);
      setStatus(null);
      return;
    }
    const key = `${projectDirectory}:${first.id}`;
    if (preparationKey.current === key) return;
    preparationKey.current = key;
    setPreparing(true);
    setStatus("កំពុងរៀបចំ preview video និង audio សម្រាប់ playback រលូន…");
    void requestEngine("project.prepare_episode", { project_directory: projectDirectory, episode_id: first.id })
      .then((prepared) => {
        if (!mounted.current) return;
        setEpisode(toEpisodeMedia(prepared));
        setStatus("Preview រួចរាល់");
        window.setTimeout(() => { if (mounted.current) setStatus(null); }, 1800);
      })
      .catch((cause: unknown) => {
        if (!mounted.current) return;
        preparationKey.current = null;
        setError(cause instanceof Error ? cause.message : "មិនអាចរៀបចំ preview បានទេ។");
        setStatus(null);
      })
      .finally(() => { if (mounted.current) setPreparing(false); });
  }, [project, projectDirectory]);
  useEffect(() => { const path = episode?.path; return () => { if (path?.startsWith("blob:")) URL.revokeObjectURL(path); }; }, [episode?.path]);
  const openEpisode = useCallback(async () => {
    if (importLock.current || !projectDirectory || !project) return;
    if (!isTauri()) { fileInputRef.current?.click(); return; }
    importLock.current = true; setImporting(true); setStatus("កំពុង import និងរៀបចំ media…"); setError(null);
    try {
      const selected = await pickEpisodePath(); if (!selected) return;
      setStatus("កំពុងបង្កើត preview video និង audio…");
      const persisted = await requestEngine("project.import_episode", { project_directory: projectDirectory, project_name: project.name, source: selected });
      if (mounted.current) { setEpisode(toEpisodeMedia(persisted)); setStatus("Episode រួចរាល់"); window.setTimeout(() => { if (mounted.current) setStatus(null); }, 1800); }
    } catch (cause) {
      if (mounted.current) { setError(cause instanceof Error ? cause.message : "មិនអាច import episode នេះបានទេ។"); setStatus(null); }
    } finally { importLock.current = false; if (mounted.current) setImporting(false); }
  }, [projectDirectory, project]);
  const importFile = useCallback((file: File) => {
    if (!/\.(mp4|mov|mkv|webm|m4v|avi)$/i.test(file.name)) { setError("សូមជ្រើស MP4, MOV, MKV, WebM, M4V ឬ AVI។"); return; }
    setError("Web preview មិនអាចរក្សាទុក episode ទៅ Project បានទេ។ សូមប្រើ Catty desktop app។");
  }, []);
  const updateMetadata = useCallback((id: string, metadata: Pick<EpisodeMedia, "durationSeconds" | "width" | "height">) => { setEpisode((current) => current?.id === id ? { ...current, ...metadata } : current); }, []);
  return { episode, importing, preparing, status, error, dismissError: () => setError(null), openEpisode, importFile, fileInputRef, updateMetadata };
}
