import type { EpisodeSpeaker } from "@catty/contracts";

export type EpisodeMedia = {
  speakers?: EpisodeSpeaker[];
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
    sourceLanguage: string;
    sourceText: string;
    confidence: number | null;
  }>;
};
