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
export type TimelineDocument = {
  layers: Layer[];
  clips: TimelineClip[];
  initialized: boolean;
};
export type TimelineHistory = {
  past: TimelineDocument[];
  present: TimelineDocument;
  future: TimelineDocument[];
};
