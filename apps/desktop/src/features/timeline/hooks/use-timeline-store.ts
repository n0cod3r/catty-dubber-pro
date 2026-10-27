import { useContext } from "react";

import { useStore } from "zustand";

import { TimelineStoreContext } from "../contexts/timeline-store-context";
import type { TimelineState } from "../stores/timeline-store";

export function useTimelineStore<T>(selector: (state: TimelineState) => T): T {
  const store = useContext(TimelineStoreContext);
  if (!store) throw new Error("useTimelineStore requires a TimelineProvider");
  return useStore(store, selector);
}
