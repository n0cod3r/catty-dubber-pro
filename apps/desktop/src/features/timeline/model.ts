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
  | { type: "update-text"; id: string; text: string }
  | { type: "split"; time: number; selectedId: string | null }
  | { type: "undo" }
  | { type: "redo" };

export function createTimeline(): TimelineHistory {
  return {
    past: [],
    future: [],
    present: {
      initialized: false,
      clips: [],
      layers: [
        {
          id: "video",
          kind: "video",
          name: "Video 1",
          source: true,
          locked: false,
          muted: false,
          hidden: false,
        },
        {
          id: "audio",
          kind: "audio",
          name: "Original audio",
          source: true,
          locked: false,
          muted: false,
          hidden: false,
        },
        { id: "dub", kind: "audio", name: "Khmer dub", locked: false, muted: false, hidden: false },
      ],
    },
  };
}

export function splitCandidates(
  document: TimelineDocument,
  time: number,
  selectedId: string | null,
) {
  if (!Number.isFinite(time)) return [];
  const selected = document.clips.find((clip) => clip.id === selectedId);
  const candidates = document.clips.filter(
    (clip) =>
      time > clip.start + 0.001 &&
      time < clip.start + clip.duration - 0.001 &&
      (selected
        ? clip.id === selected.id || (!!selected.linkId && clip.linkId === selected.linkId)
        : !!clip.linkId),
  );
  return candidates.some(
    (clip) => document.layers.find((layer) => layer.id === clip.trackId)?.locked,
  )
    ? []
    : candidates;
}

function change(
  document: TimelineDocument,
  action: Exclude<TimelineAction, { type: "undo" | "redo" }>,
): TimelineDocument {
  if (action.type === "initialize") {
    if (document.initialized || !Number.isFinite(action.duration) || action.duration <= 0)
      return document;
    return {
      ...document,
      initialized: true,
      clips: ["video", "audio"].map((kind) => ({
        id: `${kind}:source`,
        trackId: kind,
        kind: kind as "video" | "audio",
        sourceId: action.sourceId,
        sourceStart: 0,
        start: 0,
        duration: action.duration,
        name: action.name,
        linkId: "source",
      })),
    };
  }
  if (action.type === "add-layer") {
    if (document.layers.some((layer) => layer.id === action.layer.id)) return document;
    return { ...document, layers: [action.layer, ...document.layers] };
  }
  const layer = "id" in action ? document.layers.find((item) => item.id === action.id) : undefined;
  if (action.type === "remove-layer") {
    if (
      !layer ||
      layer.source ||
      layer.locked ||
      document.clips.some((clip) => clip.trackId === layer.id)
    )
      return document;
    return { ...document, layers: document.layers.filter((item) => item.id !== action.id) };
  }
  if (action.type === "toggle-layer") {
    if (!layer || (layer.locked && action.property !== "locked")) return document;
    return {
      ...document,
      layers: document.layers.map((item) =>
        item.id === action.id ? { ...item, [action.property]: !item[action.property] } : item,
      ),
    };
  }
  if (action.type === "move-layer") {
    const index = document.layers.findIndex((item) => item.id === action.id);
    const next = index + action.direction;
    if (!layer || layer.locked || next < 0 || next >= document.layers.length) return document;
    const layers = [...document.layers];
    layers.splice(index, 1);
    layers.splice(next, 0, layer);
    return { ...document, layers };
  }
  if (action.type === "add-clip") {
    const target = document.layers.find((item) => item.id === action.clip.trackId);
    if (
      !target ||
      target.locked ||
      target.kind !== action.clip.kind ||
      document.clips.some((clip) => clip.id === action.clip.id) ||
      !Number.isFinite(action.clip.duration) ||
      action.clip.duration <= 0 ||
      !Number.isFinite(action.clip.start) ||
      action.clip.start < 0 ||
      !Number.isFinite(action.clip.sourceStart) ||
      action.clip.sourceStart < 0
    )
      return document;
    return { ...document, clips: [...document.clips, action.clip] };
  }
  if (action.type === "update-text") {
    const clip = document.clips.find((item) => item.id === action.id);
    if (
      !clip ||
      document.layers.find((item) => item.id === clip.trackId)?.locked ||
      clip.text === action.text
    )
      return document;
    return {
      ...document,
      clips: document.clips.map((item) =>
        item.id === action.id
          ? { ...item, text: action.text, name: action.text || item.kind }
          : item,
      ),
    };
  }
  const candidates = splitCandidates(document, action.time, action.selectedId);
  if (!candidates.length) return document;
  const ids = new Set(candidates.map((clip) => clip.id));
  return {
    ...document,
    clips: document.clips.flatMap((clip) => {
      if (!ids.has(clip.id)) return [clip];
      const offset = action.time - clip.start;
      return [
        { ...clip, duration: offset },
        {
          ...clip,
          id: `${clip.id}@${action.time}`,
          start: action.time,
          sourceStart: clip.sourceStart + offset,
          duration: clip.duration - offset,
        },
      ];
    }),
  };
}

export function timelineReducer(state: TimelineHistory, action: TimelineAction): TimelineHistory {
  if (action.type === "undo") {
    const previous = state.past.at(-1);
    return previous
      ? {
          past: state.past.slice(0, -1),
          present: previous,
          future: [state.present, ...state.future],
        }
      : state;
  }
  if (action.type === "redo") {
    const next = state.future[0];
    return next
      ? { past: [...state.past, state.present], present: next, future: state.future.slice(1) }
      : state;
  }
  const next = change(state.present, action);
  if (next === state.present) return state;
  // Media metadata is initialization, never an undoable edit.
  return action.type === "initialize"
    ? {
        past: state.past.map((document) => change(document, action)),
        present: next,
        future: state.future.map((document) => change(document, action)),
      }
    : { past: [...state.past.slice(-99), state.present], present: next, future: [] };
}
