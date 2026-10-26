import { useEffect, useState } from "react";

import { isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export function useDesktopShutdown() {
  const [closing, setClosing] = useState(false);
  useEffect(() => {
    if (!isTauri()) return;
    let active = true;
    const subscription = listen("catty:shutting-down", () => {
      if (active) setClosing(true);
    }).catch(() => undefined);
    // A closing app must not keep video playback, thumbnail workers or UI jobs
    // mounted while the host drains and terminates its engine processes.
    return () => {
      active = false;
      void subscription.then((unlisten) => unlisten?.()).catch(() => {});
    };
  }, []);
  return closing;
}
