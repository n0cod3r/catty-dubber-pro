import { AudioLines, Film, Layers, Subtitles } from "lucide-react";

import type { TrackKind } from "./model";

export const trackStyles = {
  video: {
    icon: Film,
    color: "border-amber-700/70 bg-amber-950/70 text-amber-100",
    dot: "bg-amber-400",
    label: "Video",
  },
  audio: {
    icon: AudioLines,
    color: "border-emerald-700/70 bg-emerald-950/70 text-emerald-100",
    dot: "bg-emerald-400",
    label: "Audio",
  },
  subtitle: {
    icon: Subtitles,
    color: "border-blue-700/70 bg-blue-950/70 text-blue-100",
    dot: "bg-blue-400",
    label: "Subtitle",
  },
  graphic: {
    icon: Layers,
    color: "border-purple-700/70 bg-purple-950/70 text-purple-100",
    dot: "bg-purple-400",
    label: "Graphic",
  },
} satisfies Record<TrackKind, unknown>;
