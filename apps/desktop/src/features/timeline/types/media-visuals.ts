export type VisualRequest =
  | { type: "open"; url: string; duration: number }
  | { type: "thumbnails"; times: number[] };
export type VisualResponse =
  | { type: "audio-init"; bins: number; rate: number }
  | {
      type: "audio-chunk";
      start: number;
      min: Float32Array;
      max: Float32Array;
      progress: number;
      peak: number;
    }
  | { type: "audio-done" }
  | { type: "audio-absent" }
  | { type: "audio-error" | "video-error"; message: string }
  | { type: "thumbnail"; time: number; bitmap: ImageBitmap };
export type Waveform = {
  min: Float32Array;
  max: Float32Array;
  rate: number;
  peak: number;
  progress: number;
  status: "loading" | "ready" | "absent" | "error";
  error?: string;
};
