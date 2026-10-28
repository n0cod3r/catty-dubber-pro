import { createContext } from "react";

import type { createTimelineStore } from "../stores/timeline-store";

export const TimelineStoreContext = createContext<ReturnType<
  typeof createTimelineStore
> | null>(null);
