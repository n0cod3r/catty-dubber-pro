import type { TranscriptionProgress } from "@catty/contracts";
import { isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export async function listenTranscriptionProgress(
  onProgress: (progress: TranscriptionProgress) => void,
) {
  if (!isTauri()) return () => {};
  return listen<TranscriptionProgress>("catty:transcription-progress", ({ payload }) =>
    onProgress(payload),
  );
}
