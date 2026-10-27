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
export type AudioAsset = {
  path: string;
  kind: "speech" | "master" | "background" | "dialogue" | "dub";
  sample_rate: number;
  channels: number;
  source_fingerprint: string;
  created_at: string;
};
export type PersistedDialogueSegment = {
  id: string;
  start: number;
  end: number;
  speaker_id: string | null;
  source_language: string;
  source_text: string;
  confidence: number | null;
  translation: unknown | null;
  created_at: string;
  updated_at: string;
};
export type EpisodeSpeaker = {
  id: string;
  name: string;
  character_id: string | null;
  segment_ids: string[];
};
export type PersistedEpisode = {
  id: string;
  name: string;
  order: number;
  media: MediaInfo;
  playback_proxy_path: string | null;
  audio_assets: AudioAsset[];
  speakers: EpisodeSpeaker[];
  dialogue_segments: PersistedDialogueSegment[];
  dub_segments: unknown[];
  processing: Record<string, string>;
  created_at: string;
  updated_at: string;
};
export type PersistedProject = {
  schema_version: number;
  id: string;
  name: string;
  episodes: PersistedEpisode[];
  characters: unknown[];
  voice_profiles: unknown[];
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
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
export type DialogueEditParams = {
  project_directory: string;
  episode_id: string;
  segment_id: string;
};
export type DialogueSplitParams = DialogueEditParams & { split_at: number };
export type AudioPrepareParams = {
  source: string;
  episode_id: string;
  project_directory: string;
  existing_asset?: AudioAsset | null;
};
export type EngineMethods = {
  health: { params: Record<string, never>; result: EngineStatus };
  "media.probe": { params: { path: string }; result: MediaInfo };
  "project.create": {
    params: { project_directory: string; name: string };
    result: PersistedProject;
  };
  "project.open": { params: { project_directory: string }; result: PersistedProject };
  "project.prepare_episode": {
    params: { project_directory: string; episode_id: string };
    result: PersistedEpisode;
  };
  "project.rebuild_proxy": {
    params: { project_directory: string; episode_id: string };
    result: PersistedEpisode;
  };
  "project.import_episode": {
    params: { project_directory: string; project_name: string; source: string };
    result: PersistedEpisode;
  };
  "project.dialogue_restore": {
    params: {
      project_directory: string;
      episode_id: string;
      expected_segments: PersistedDialogueSegment[];
      dialogue_segments: PersistedDialogueSegment[];
      speakers: EpisodeSpeaker[];
      dub_segments: unknown[];
    };
    result: PersistedEpisode;
  };
  "project.dialogue_assign_speaker": {
    params: DialogueEditParams & {
      speaker_id: string | null;
      expected_speaker_id: string | null;
      create_new?: boolean;
    };
    result: PersistedEpisode;
  };
  "project.dialogue_update_text": {
    params: DialogueEditParams & { text: string; expected_text: string };
    result: PersistedEpisode;
  };
  "project.dialogue_split": { params: DialogueSplitParams; result: PersistedEpisode };
  "project.dialogue_merge_next": { params: DialogueEditParams; result: PersistedEpisode };
  "speech.transcribe": { params: SpeechTranscribeParams; result: TranscriptionResult };
};
