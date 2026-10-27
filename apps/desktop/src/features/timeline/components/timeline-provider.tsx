import { useState, type ReactNode } from "react";

import { TimelineStoreContext } from "../contexts/timeline-store-context";
import { createTimelineStore } from "../stores/timeline-store";

export function TimelineProvider({ children }: { children: ReactNode }) {
  const [store] = useState(createTimelineStore);
  return <TimelineStoreContext.Provider value={store}>{children}</TimelineStoreContext.Provider>;
}
