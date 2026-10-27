import type { TimelineAction, TimelineDocument, TimelineHistory } from "../types";

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

export function clipEditGroup(document: TimelineDocument, id: string) {
  const selected = document.clips.find((clip) => clip.id === id);
  if (!selected) return [];
  const clips = document.clips.filter(
    (clip) =>
      clip.id === id ||
      (selected.linkId &&
        clip.linkId === selected.linkId &&
        Math.abs(clip.start - selected.start) < 0.000001 &&
        Math.abs(clip.duration - selected.duration) < 0.000001 &&
        Math.abs(clip.sourceStart - selected.sourceStart) < 0.000001),
  );
  return clips.some((clip) => document.layers.find((layer) => layer.id === clip.trackId)?.locked)
    ? []
    : clips;
}

export function moveClip(
  document: TimelineDocument,
  id: string,
  start: number,
  trackId: string,
): TimelineDocument | null {
  const clip = document.clips.find((item) => item.id === id);
  const target = document.layers.find((layer) => layer.id === trackId);
  const group = clipEditGroup(document, id);
  if (
    !clip ||
    !target ||
    target.locked ||
    target.kind !== clip.kind ||
    !group.length ||
    !Number.isFinite(start) ||
    start < 0
  )
    return null;
  const delta = start - clip.start;
  const ids = new Set(group.map((item) => item.id));
  const moved = group.map((item) => ({
    ...item,
    start: item.start + delta,
    trackId: item.id === id ? trackId : item.trackId,
  }));
  if (
    moved.some(
      (item) =>
        item.start < 0 ||
        document.clips.some(
          (other) =>
            !ids.has(other.id) &&
            other.trackId === item.trackId &&
            item.start < other.start + other.duration - 0.000001 &&
            item.start + item.duration > other.start + 0.000001,
        ),
    )
  )
    return null;
  if (Math.abs(delta) < 0.000001 && trackId === clip.trackId) return document;
  return {
    ...document,
    clips: document.clips.map(
      (item) => moved.find((candidate) => candidate.id === item.id) ?? item,
    ),
  };
}

// Magnetic snapping is optional; solid clip boundaries are not. A pointer that
// crosses an occupied edge should stop at contact instead of losing the move.
export function resolveClipDrag(
  document: TimelineDocument,
  id: string,
  start: number,
  trackId: string,
) {
  const direct = moveClip(document, id, start, trackId);
  if (direct) return { document: direct, start };
  const clip = document.clips.find((item) => item.id === id);
  const target = document.layers.find((item) => item.id === trackId);
  const group = clipEditGroup(document, id);
  if (
    !clip ||
    !target ||
    target.locked ||
    target.kind !== clip.kind ||
    !group.length ||
    !Number.isFinite(start) ||
    start < 0
  )
    return null;
  const ids = new Set(group.map((item) => item.id));
  const boundaries = new Set<number>([0]);
  for (const item of group) {
    const destination = item.id === id ? trackId : item.trackId;
    const offset = item.start - clip.start;
    for (const other of document.clips) {
      if (ids.has(other.id) || other.trackId !== destination) continue;
      boundaries.add(other.start + other.duration - offset);
      boundaries.add(other.start - item.duration - offset);
    }
  }
  const ordered = [...boundaries]
    .filter((value) => value >= 0)
    .sort((a, b) => Math.abs(a - start) - Math.abs(b - start));
  for (const boundary of ordered) {
    const next = moveClip(document, id, boundary, trackId);
    if (next) return { document: next, start: boundary };
  }
  return null;
}

export function documentDuration(document: TimelineDocument) {
  return document.clips.reduce((end, clip) => Math.max(end, clip.start + clip.duration), 0);
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
  if (action.type === "move-clip")
    return moveClip(document, action.id, action.start, action.trackId) ?? document;
  if (action.type === "remove-clip") {
    const ids = new Set(clipEditGroup(document, action.id).map((clip) => clip.id));
    return ids.size
      ? { ...document, clips: document.clips.filter((clip) => !ids.has(clip.id)) }
      : document;
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
