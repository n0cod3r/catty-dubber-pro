import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { initializeLogs } from "@/features/logs";
import { initializeCompactRuntime } from "@/features/voice-runtime";

import { App } from "./app/App";

import "@/styles/global.css";

initializeLogs();
initializeCompactRuntime();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
