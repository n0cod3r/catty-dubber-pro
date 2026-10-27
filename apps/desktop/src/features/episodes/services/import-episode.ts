import { open } from "@tauri-apps/plugin-dialog";

const VIDEO_EXTENSIONS = ["mp4", "mov", "mkv", "webm", "m4v", "avi"];

export async function pickEpisodePath(): Promise<string | null> {
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
  return selected;
}
