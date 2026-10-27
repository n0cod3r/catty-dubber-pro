import { createStore } from "zustand/vanilla";

import type { TimelineDocument, TimelineHistory } from "../types";
import {
  addClipEdit,
  addLayerEdit,
  createTimeline,
  initializeEdit,
  moveClipEdit,
  moveLayerEdit,
  removeClipEdit,
  removeLayerEdit,
  splitEdit,
  toggleLayerEdit,
  updateTextEdit,
} from "./timeline-edits.ts";

type DialogueTimelineSegment = { id: string; start: number; end: number; text: string };

export type TimelineActions = {
  initialize: (input: Parameters<typeof initializeEdit>[1]) => void;
  syncDialogue: (input: { sourceId: string; segments: DialogueTimelineSegment[] }) => void;
  addLayer: (input: Parameters<typeof addLayerEdit>[1]) => void;
  removeLayer: (input: Parameters<typeof removeLayerEdit>[1]) => void;
  toggleLayer: (input: Parameters<typeof toggleLayerEdit>[1]) => void;
  moveLayer: (input: Parameters<typeof moveLayerEdit>[1]) => void;
  addClip: (input: Parameters<typeof addClipEdit>[1]) => void;
  moveClip: (input: Parameters<typeof moveClipEdit>[1]) => void;
  removeClip: (input: Parameters<typeof removeClipEdit>[1]) => void;
  updateText: (input: Parameters<typeof updateTextEdit>[1]) => void;
  split: (input: Parameters<typeof splitEdit>[1]) => void;
  undo: () => void;
  redo: () => void;
};
export type TimelineState = { history: TimelineHistory } & TimelineActions;

export function createTimelineStore(initialHistory: TimelineHistory = createTimeline()) {
  return createStore<TimelineState>()((set) => {
    const commit = (edit: (document: TimelineDocument) => TimelineDocument, initialize = false) =>
      set((state) => {
        const history = state.history;
        const next = edit(history.present);
        if (next === history.present) return state;
        return {
          history: initialize
            ? { past: history.past.map(edit), present: next, future: history.future.map(edit) }
            : { past: [...history.past.slice(-99), history.present], present: next, future: [] },
        };
      });
    return {
      history: initialHistory,
      initialize: (input) => commit((document) => initializeEdit(document, input), true),
      syncDialogue: ({ sourceId, segments }) =>
        commit((document) => {
          const subtitleLayer = document.layers.find((layer) => layer.id === "dialogue-subtitles");
          const layers = subtitleLayer
            ? document.layers
            : [
                ...document.layers.slice(0, 1),
                {
                  id: "dialogue-subtitles",
                  kind: "subtitle" as const,
                  name: "Dialogue subtitles",
                  locked: false,
                  muted: false,
                  hidden: false,
                },
                ...document.layers.slice(1),
              ];
          const retained = document.clips.filter(
            (clip) => !(clip.trackId === "dialogue-subtitles" && clip.sourceId === sourceId),
          );
          const subtitles = segments
            .filter((segment) => Number.isFinite(segment.start) && Number.isFinite(segment.end) && segment.end > segment.start)
            .map((segment, index) => ({
              id: `dialogue:${sourceId}:${segment.id || index}`,
              trackId: "dialogue-subtitles",
              kind: "subtitle" as const,
              sourceId,
              sourceStart: segment.start,
              start: segment.start,
              duration: segment.end - segment.start,
              name: segment.text,
              text: segment.text,
            }));
          return { ...document, layers, clips: [...retained, ...subtitles] };
        }, true),
      addLayer: (input) => commit((document) => addLayerEdit(document, input), false),
      removeLayer: (input) => commit((document) => removeLayerEdit(document, input), false),
      toggleLayer: (input) => commit((document) => toggleLayerEdit(document, input), false),
      moveLayer: (input) => commit((document) => moveLayerEdit(document, input), false),
      addClip: (input) => commit((document) => addClipEdit(document, input), false),
      moveClip: (input) => commit((document) => moveClipEdit(document, input), false),
      removeClip: (input) => commit((document) => removeClipEdit(document, input), false),
      updateText: (input) => commit((document) => updateTextEdit(document, input), false),
      split: (input) => commit((document) => splitEdit(document, input), false),
      undo: () =>
        set((state) => {
          const { past, present, future } = state.history;
          const previous = past.at(-1);
          return previous
            ? { history: { past: past.slice(0, -1), present: previous, future: [present, ...future] } }
            : state;
        }),
      redo: () =>
        set((state) => {
          const { past, present, future } = state.history;
          const next = future[0];
          return next
            ? { history: { past: [...past, present], present: next, future: future.slice(1) } }
            : state;
        }),
    };
  });
}
