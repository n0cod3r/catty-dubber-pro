export type EpisodeMedia = {
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
    sourceLanguage: string;
    sourceText: string;
    confidence: number | null;
  }>;
};
