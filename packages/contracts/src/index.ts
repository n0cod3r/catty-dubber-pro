export type EngineError = { code: string; message: string };
export type EngineStatus = {
  name: string;
  version: string;
  capabilities: string[];
  ffprobe_available: boolean;
  ffmpeg_available: boolean;
};
export type MediaInfo = {
  source_path: string;
  duration: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  video_codec: string | null;
  audio_codec: string | null;
  sample_rate: number | null;
  channels: number | null;
};
export type EngineMethods = {
  health: { params: Record<string, never>; result: EngineStatus };
  "media.probe": { params: { path: string }; result: MediaInfo };
};

export type AudioAsset = {
  path: string;
  kind: "speech" | "master" | "background" | "dialogue" | "dub";
  sample_rate: number;
  channels: number;
  source_fingerprint: string;
  created_at: string;
};
export type AudioPrepareParams = {
  source: string;
  episode_id: string;
  project_directory: string;
  existing_asset?: AudioAsset | null;
};
