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

export type TimelineActions = {
  initialize: (input: Parameters<typeof initializeEdit>[1]) => void;
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
    // One transaction per committed edit, including linked audio/video clips.
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
            ? {
                history: {
                  past: past.slice(0, -1),
                  present: previous,
                  future: [present, ...future],
                },
              }
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
