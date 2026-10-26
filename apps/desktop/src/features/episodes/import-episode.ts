import { open } from "@tauri-apps/plugin-dialog";

import type { EpisodeMedia } from "./types";

const VIDEO_EXTENSIONS = ["mp4", "mov", "mkv", "webm", "m4v", "avi"];

function basename(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

export async function importEpisode(): Promise<EpisodeMedia | null> {
  const selected = await open({
    multiple: false,
    directory: false,
    title: "Import episode",
    filters: [
      {
        name: "Video",
        extensions: VIDEO_EXTENSIONS,
      },
    ],
  });

  if (!selected || Array.isArray(selected)) return null;

  const name = basename(selected);
  const extension = name.includes(".") ? (name.split(".").pop()?.toLowerCase() ?? "") : "";

  return {
    id: crypto.randomUUID(),
    path: selected,
    name,
    extension,
    durationSeconds: null,
    width: null,
    height: null,
  };
}
