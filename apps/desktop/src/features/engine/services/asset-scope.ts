import { invoke, isTauri } from "@tauri-apps/api/core";

import { addLog } from "../deps/logs";

/**
 * Tauri's asset protocol only serves configured roots by default. Projects may
 * live on an external drive or another Windows volume, so grant the exact path
 * the user picked before the preview tries to load it.
 */
export async function allowAssetPath(path: string): Promise<void> {
  if (!isTauri() || !path) return;
  try {
    await invoke("allow_asset_path", { path });
  } catch (cause) {
    addLog(
      "frontend",
      "WARN",
      `Asset scope could not allow ${path}: ${
        cause instanceof Error ? cause.message : String(cause)
      }`,
    );
  }
}
