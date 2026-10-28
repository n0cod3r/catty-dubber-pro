export type {
  DubSegment,
  DubStatus,
  EdgeVoice,
  TtsGenerateParams,
  TtsGenerationMode,
  TtsPreviewParams,
  TtsProgress,
  VoiceEngine,
  VoiceProfile,
} from "./tts";
import type {
  DubSegment,
  EdgeVoice,
  TtsGenerateParams,
  TtsPreviewParams,
  VoiceProfile,
} from "./tts";

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
export type PersistedTranslation = {
  language: string;
  text: string;
  status: "pending" | "translated" | "edited" | "failed";
  provider: string | null;
  model: string | null;
  manually_edited: boolean;
  updated_at: string;
};
export type PersistedDialogueSegment = {
  id: string;
  start: number;
  end: number;
  speaker_id: string | null;
  source_language: string;
  source_text: string;
  confidence: number | null;
  translation: PersistedTranslation | null;
  created_at: string;
  updated_at: string;
};
export type EpisodeSpeaker = {
  id: string;
  name: string;
  character_id: string | null;
  segment_ids: string[];
};
export type EpisodeProcessingState = {
  transcription: string;
  speakers: string;
  translation: string;
  speaker_error?: string | null;
  [key: string]: string | null | undefined;
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
  dub_segments: DubSegment[];
  processing: EpisodeProcessingState;
  created_at: string;
  updated_at: string;
};
export type GlossaryEntry = {
  source: string;
  target: string;
  note: string | null;
};
export type ProjectTranslationSettings = {
  source_language: string;
  target_language: string;
  style: string;
  glossary: GlossaryEntry[];
  custom_instructions: string | null;
};
export type PersistedProject = {
  schema_version: number;
  id: string;
  name: string;
  episodes: PersistedEpisode[];
  characters: unknown[];
  voice_profiles: VoiceProfile[];
  settings: {
    translation?: ProjectTranslationSettings;
    [key: string]: unknown;
  };
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
  speaker_error?: string | null;
};
export type SpeechTranscribeParams = {
  operation_id?: string;
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

export type TranslationProviderId = string;
export type TranslationMode = "missing" | "all" | "selected";
export type TranslationProviderInfo = Record<string, unknown>;
export type TranslationModel = Record<string, unknown>;
export type ConnectionTestResult = Record<string, unknown>;
export type ModelStatus = Record<string, unknown>;
export type AppSettings = Record<string, unknown>;
export type SettingsSnapshot = Record<string, unknown>;
export type TranslationProgress = {
  operation_id: string;
  project_directory: string;
  episode_id: string;
  phase: string;
  completed: number;
  total: number;
  episode?: PersistedEpisode | null;
  [key: string]: unknown;
};

export type EngineMethods = {
  health: { params: Record<string, never>; result: EngineStatus };
  "media.probe": { params: { path: string }; result: MediaInfo };
  "project.create": { params: { project_directory: string; name: string }; result: PersistedProject };
  "project.open": { params: { project_directory: string }; result: PersistedProject };
  "project.prepare_episode": { params: { project_directory: string; episode_id: string }; result: PersistedEpisode };
  "project.rebuild_proxy": { params: { project_directory: string; episode_id: string }; result: PersistedEpisode };
  "project.import_episode": { params: { project_directory: string; project_name: string; source: string }; result: PersistedEpisode };
  "project.dialogue_restore": { params: { project_directory: string; episode_id: string; expected_segments: PersistedDialogueSegment[]; dialogue_segments: PersistedDialogueSegment[]; speakers: EpisodeSpeaker[]; dub_segments: DubSegment[] }; result: PersistedEpisode };
  "project.dialogue_assign_speaker": { params: DialogueEditParams & { speaker_id: string | null; expected_speaker_id: string | null; create_new?: boolean }; result: PersistedEpisode };
  "project.dialogue_update_text": { params: DialogueEditParams & { text: string; expected_text: string }; result: PersistedEpisode };
  "project.dialogue_update_translation": { params: DialogueEditParams & { text: string; expected_text: string | null }; result: PersistedEpisode };
  "project.dialogue_split": { params: DialogueSplitParams; result: PersistedEpisode };
  "project.dialogue_merge_next": { params: DialogueEditParams; result: PersistedEpisode };
  "speech.transcribe": { params: SpeechTranscribeParams; result: TranscriptionResult };
  "settings.get": { params: Record<string, never>; result: SettingsSnapshot };
  "settings.update": { params: { settings: AppSettings; credentials?: Record<string, string | null> }; result: SettingsSnapshot };
  "settings.credential_add": { params: { provider: TranslationProviderId; secret: string }; result: SettingsSnapshot };
  "settings.credential_remove": { params: { provider: TranslationProviderId; credential_id: string }; result: SettingsSnapshot };
  "translation.providers": { params: Record<string, never>; result: TranslationProviderInfo[] };
  "translation.models": { params: { provider: TranslationProviderId; credential?: string | null }; result: TranslationModel[] };
  "translation.test_connection": { params: { provider: TranslationProviderId; credential?: string | null }; result: ConnectionTestResult };
  "translation.translate_episode": { params: { project_directory: string; episode_id: string; mode?: TranslationMode; operation_id?: string; segment_ids?: string[]; overwrite_manual?: boolean; batch_size?: number }; result: PersistedEpisode };
  "models.list": { params: Record<string, never>; result: TranslationModel[] };
  "models.install": { params: { model_id: string }; result: TranslationModel };
  "models.install_status": { params: { model_id?: string | null }; result: ModelStatus[] };
  "models.remove": { params: { model_id: string }; result: TranslationModel };
  "tts.voices": { params: Record<string, never>; result: EdgeVoice[] };
  "tts.ensure_voice": { params: { project_directory: string; voice_id: string; name?: string | null }; result: VoiceProfile };
  "tts.preview": { params: TtsPreviewParams; result: { path: string } };
  "tts.generate": { params: TtsGenerateParams; result: PersistedEpisode };
};
