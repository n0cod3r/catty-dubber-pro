import type { TtsProgress } from "@catty/contracts";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export function listenTtsProgress(
  listener: (progress: TtsProgress) => void,
): Promise<UnlistenFn> {
  return listen<TtsProgress>("catty:tts-progress", (event) => {
    listener(event.payload);
  });
}
