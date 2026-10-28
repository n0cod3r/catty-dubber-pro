import type { TranslationProgress } from "@catty/contracts";
import { isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export async function listenTranslationProgress(
  onProgress: (progress: TranslationProgress) => void,
) {
  if (!isTauri()) return () => {};
  return listen<TranslationProgress>(
    "catty:translation-progress",
    ({ payload }) => onProgress(payload),
  );
}
