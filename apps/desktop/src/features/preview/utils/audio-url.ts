import { convertFileSrc } from "@tauri-apps/api/core";

export function assetAudioUrl(path: string, projectDirectory: string) {
  const absolute = /^(\/|[A-Za-z]:[\\/]|\\\\)/.test(path)
    ? path
    : `${projectDirectory}/${path}`;
  return convertFileSrc(absolute);
}
