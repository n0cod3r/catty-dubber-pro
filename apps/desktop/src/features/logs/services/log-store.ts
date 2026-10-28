import { invoke, isTauri } from "@tauri-apps/api/core";

export type LogEntry = {
  id: string;
  timestamp: number;
  source: string;
  level: string;
  message: string;
};
const LIMIT = 2000;
let entries: LogEntry[] = [];
let cursor = 0;
let sequence = 0;
const subscribers = new Set<() => void>();
const notify = () => subscribers.forEach((listener) => listener());
export const subscribeLogs = (listener: () => void) => {
  subscribers.add(listener);
  return () => {
    subscribers.delete(listener);
  };
};
export const getLogs = () => entries;
export function addLog(source: string, level: string, message: string) {
  entries = [
    ...entries,
    {
      id: `web-${++sequence}`,
      timestamp: Date.now(),
      source,
      level,
      message: redact(message).slice(0, 8192),
    },
  ].slice(-LIMIT);
  notify();
}
function redact(message: string) {
  return message
    .replace(/(bearer\s+)[^\s"']+/gi, "$1[REDACTED]")
    .replace(
      /((?:api[_-]?key|access[_-]?token|authorization|password|secret)["']?\s*[:=]\s*["']?)[^\s,"'}]+/gi,
      "$1[REDACTED]",
    );
}
export async function pollNativeLogs() {
  if (!isTauri()) return;
  const batch = await invoke<Array<Omit<LogEntry, "id"> & { id: number }>>("app_logs", {
    after: cursor,
  });
  const fresh = batch.filter((entry) => entry.id > cursor);
  if (!fresh.length) return;
  cursor = fresh[fresh.length - 1]!.id;
  entries = [
    ...entries,
    ...fresh.map((entry) => ({
      ...entry,
      id: `native-${entry.id}`,
      message: redact(entry.message),
    })),
  ]
    .sort((a, b) => a.timestamp - b.timestamp)
    .slice(-LIMIT);
  notify();
}
export function clearLogs() {
  entries = [];
  notify();
}
let initialized = false;
export function initializeLogs() {
  if (initialized) return;
  initialized = true;
  for (const level of ["debug", "info", "log", "warn", "error"] as const) {
    const original = console[level].bind(console);
    console[level] = (...values: unknown[]) => {
      original(...values);
      addLog(
        "frontend",
        level === "log" ? "INFO" : level.toUpperCase(),
        values
          .map((value) => {
            if (value instanceof Error) return value.stack ?? value.message;
            if (typeof value === "string") return value;
            try {
              return JSON.stringify(value);
            } catch {
              return String(value);
            }
          })
          .join(" "),
      );
    };
  }
  window.addEventListener("error", (event) =>
    addLog("frontend", "ERROR", event.error?.stack ?? event.message),
  );
  window.addEventListener("unhandledrejection", (event) =>
    addLog(
      "frontend",
      "ERROR",
      event.reason instanceof Error
        ? (event.reason.stack ?? event.reason.message)
        : String(event.reason),
    ),
  );
  addLog("frontend", "INFO", "Catty interface started");
}
