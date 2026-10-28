import type { UnlistenFn } from "@tauri-apps/api/event";
import { listen } from "@tauri-apps/api/event";

export type TtsProgressPhase =
  | "started"
  | "generating"
  | "saved"
  | "completed"
  | "cancelled"
  | "failed";

export type TtsProgress = {
  operation_id: string;
  project_directory: string;
  episode_id: string;
  phase: TtsProgressPhase;
  completed: number;
  total: number;
  segment_id: string | null;
  segment: unknown | null;
  episode: unknown | null;
};

export function listenTtsProgress(
  listener: (progress: TtsProgress) => void,
): Promise<UnlistenFn> {
  return listen<TtsProgress>("catty:tts-progress", (event) => {
    listener(event.payload);
  });
}
