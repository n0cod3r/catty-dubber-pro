export type VoiceEngine = "edge" | "voxcpm2";
export type DubStatus =
  "pending" | "generating" | "ready" | "outdated" | "failed";
export type TtsGenerationMode = "missing" | "all" | "selected";

export type VoiceProfile = {
  id: string;
  name: string;
  engine: VoiceEngine;
  language: string;
  engine_voice_id: string | null;
  reference_audio_path: string | null;
  reference_text?: string | null;
  style_prompt?: string;
  library_voice_id?: string | null;
  speed?: number | null;
  pitch?: number | null;
  volume?: number | null;
  created_at: string;
};

export type EdgeVoice = {
  id: string;
  name: string;
  locale: string;
  gender: string;
  engine?: VoiceEngine;
  tuning?: { speed: number; pitch: number; volume: number };
};

export type VoiceDraft = {
  name: string;
  engine: VoiceEngine;
  gender?: string;
  engine_voice_id?: string | null;
  speed?: number;
  pitch?: number;
  volume?: number;
  reference_audio_path?: string | null;
  reference_text?: string | null;
  style_prompt?: string;
  base_voice_id?: string | null;
};
export type LibraryVoice = VoiceDraft & {
  id: string;
  origin: "builtin" | "user";
};

export type DubSegment = {
  id: string;
  dialogue_segment_id: string;
  voice_profile_id: string;
  audio_path: string | null;
  status: DubStatus;
  target_duration: number;
  generated_duration: number | null;
  speed: number;
  pitch: number;
  volume: number;
  generated_at: string | null;
};

export type TtsProgress = {
  operation_id: string;
  project_directory: string;
  episode_id: string;
  phase:
    "started" | "generating" | "saved" | "completed" | "cancelled" | "failed";
  completed: number;
  total: number;
  segment_id: string | null;
  segment: DubSegment | null;
  episode: import("./index").PersistedEpisode | null;
};

export type TtsGenerateParams = {
  operation_id?: string;
  project_directory: string;
  episode_id: string;
  voice_profile_id: string;
  mode?: TtsGenerationMode;
  segment_ids?: string[];
  speed?: number;
  pitch?: number;
  volume?: number;
  cancel_file?: string | null;
  assign_speaker_id?: string | null;
  assign_only?: boolean;
};

export type TtsPreviewParams = {
  project_directory: string;
  text: string;
  voice_id: string;
  speed?: number;
  pitch?: number;
  volume?: number;
};
