export type TrackKind = "video" | "audio" | "subtitle" | "graphic";
export type Layer = {
  id: string;
  kind: TrackKind;
  name: string;
  locked: boolean;
  muted: boolean;
  hidden: boolean;
  source?: boolean;
};
export type TimelineClip = {
  id: string;
  trackId: string;
  kind: TrackKind;
  sourceId?: string;
  sourceStart: number;
  start: number;
  duration: number;
  name: string;
  linkId?: string;
  text?: string;
  color?: string;
};
export type TimelineDocument = { layers: Layer[]; clips: TimelineClip[]; initialized: boolean };
export type TimelineHistory = {
  past: TimelineDocument[];
  present: TimelineDocument;
  future: TimelineDocument[];
};
export type TimelineAction =
  | { type: "initialize"; sourceId: string; name: string; duration: number }
  | { type: "add-layer"; layer: Layer }
  | { type: "remove-layer"; id: string }
  | { type: "move-layer"; id: string; direction: -1 | 1 }
  | { type: "toggle-layer"; id: string; property: "locked" | "muted" | "hidden" }
  | { type: "add-clip"; clip: TimelineClip }
  | { type: "move-clip"; id: string; start: number; trackId: string }
  | { type: "remove-clip"; id: string }
  | { type: "update-text"; id: string; text: string }
  | { type: "split"; time: number; selectedId: string | null }
  | { type: "undo" }
  | { type: "redo" };
