import type {
  AudioAsset,
  DubSegment,
  EpisodeSpeaker,
  PersistedTranslation,
} from "@catty/contracts";

export type EpisodeMedia = {
  audioAssets?: AudioAsset[];
  separationStatus?: string;
  speakers?: EpisodeSpeaker[];
  speakerError?: string | null;
  translationStatus?: string;
  dubbingStatus?: string;
  dubSegments?: DubSegment[];
  id: string;
  path: string;
  playbackPath?: string | null;
  name: string;
  extension: string;
  durationSeconds: number | null;
  width: number | null;
  height: number | null;
  fps?: number | null;
  videoCodec?: string | null;
  audioCodec?: string | null;
  sampleRate?: number | null;
  channels?: number | null;
  dialogueSegments?: Array<{
    id: string;
    start: number;
    end: number;
    speakerId?: string | null;
    voiceProfileId?: string | null;
    sourceLanguage: string;
    sourceText: string;
    confidence: number | null;
    translation: PersistedTranslation | null;
  }>;
};
