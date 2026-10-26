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
export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
  confidence: number | null;
};
export type TranscriptionResult = {
  backend: string;
  model: string;
  language: string;
  segments: TranscriptSegment[];
};
export type SpeechTranscribeParams = {
  project_directory: string;
  episode_id: string;
  source: string;
  source_start: number;
  duration: number;
  language?: string;
  asr_backend: string;
  asr_config: Record<string, unknown>;
  vad_backend: string;
  vad_config: Record<string, unknown>;
  existing_asset?: AudioAsset | null;
};
export type EngineMethods = {
  health: { params: Record<string, never>; result: EngineStatus };
  "media.probe": { params: { path: string }; result: MediaInfo };
  "speech.transcribe": { params: SpeechTranscribeParams; result: TranscriptionResult };
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
