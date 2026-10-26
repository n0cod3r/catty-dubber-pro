export type EpisodeMedia = {
  id: string;
  path: string;
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
};
