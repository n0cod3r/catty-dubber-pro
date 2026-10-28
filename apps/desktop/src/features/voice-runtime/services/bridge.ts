import { isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { addLog } from "../deps/logs";

type Job = {
  operation_id: string;
  url: string;
  model_version: string;
  tokens: number[];
  has_reference: boolean;
  reference_text: string | null;
};
let initialized = false;
let disposed = false;
const subscriptions: Array<() => void> = [];
let worker: Worker | null = null;
let running: Job | null = null;

function validateJob(job: Job) {
  const url = new URL(job.url);
  if (
    url.protocol !== "http:" ||
    url.hostname !== "127.0.0.1" ||
    !/^\/[A-Za-z0-9_-]{40,64}\/$/.test(url.pathname) ||
    url.pathname !== `/${job.operation_id}/`
  )
    throw new Error("Invalid local compact inference endpoint");
}
async function reportError(job: Job, error: string) {
  addLog("frontend", "ERROR", `Compact VoxCPM2: ${error}`);
  try {
    await fetch(`${job.url}error`, {
      method: "POST",
      body: error.slice(0, 8000),
    });
  } catch {
    /* Engine or app is already closing. */
  }
}

export function initializeCompactRuntime() {
  if (initialized || !isTauri()) return;
  initialized = true;
  void listen<Job>("catty:compact-inference", ({ payload }) => {
    try {
      validateJob(payload);
    } catch {
      return;
    }
    if (running) {
      void fetch(`${payload.url}accepted`, { method: "POST" })
        .then(() =>
          reportError(
            payload,
            "The compact worker is busy; retry this operation.",
          ),
        )
        .catch(() => {});
      return;
    }
    running = payload;
    void (async () => {
      try {
        const accepted = await fetch(`${payload.url}accepted`, {
          method: "POST",
        });
        if (!accepted.ok) throw new Error("Engine rejected compact job");
        worker ??= new Worker(
          new URL("../workers/compact.worker.ts", import.meta.url),
          { type: "module" },
        );
        worker.onerror = () => {
          void reportError(
            payload,
            "WebGPU worker failed. Select original VoxCPM2 in Settings → Models if this device cannot run the compact model.",
          );
          worker?.terminate();
          worker = null;
          running = null;
        };
        worker.onmessage = ({
          data,
        }: MessageEvent<{
          audio?: ArrayBuffer;
          error?: string;
          phase?: string;
          graph?: string;
          patches?: number;
        }>) => {
          if (data.phase) {
            if (data.phase === "loading")
              addLog(
                "frontend",
                "INFO",
                `Compact VoxCPM2: loading ${data.graph}`,
              );
            else if (data.patches && data.patches % 25 === 0)
              addLog(
                "frontend",
                "INFO",
                `Compact VoxCPM2: generated ${data.patches} audio patches`,
              );
            return;
          }
          void (async () => {
            try {
              if (data.error) await reportError(payload, data.error);
              else if (data.audio) {
                const saved = await fetch(`${payload.url}result`, {
                  method: "POST",
                  body: data.audio,
                  headers: { "Content-Type": "audio/wav" },
                });
                if (!saved.ok)
                  throw new Error("Engine rejected generated audio");
              }
            } catch (cause) {
              await reportError(payload, String(cause));
            } finally {
              running = null;
            }
          })();
        };
        worker.postMessage(payload);
      } catch (cause) {
        await reportError(payload, String(cause));
        running = null;
      }
    })();
  })
    .then((stop) => {
      if (disposed) stop();
      else subscriptions.push(stop);
    })
    .catch((cause: unknown) =>
      addLog(
        "frontend",
        "ERROR",
        `Compact worker subscription failed: ${String(cause)}`,
      ),
    );
  void listen("catty:shutting-down", stopCompactRuntime).then((stop) => {
    if (disposed) stop();
    else subscriptions.push(stop);
  });
}

function stopCompactRuntime() {
  disposed = true;
  worker?.terminate();
  worker = null;
  running = null;
  subscriptions.splice(0).forEach((stop) => stop());
}
if (import.meta.hot) import.meta.hot.dispose(stopCompactRuntime);

export function checkCompactRuntime(): Promise<{
  available: boolean;
  adapter?: object;
}> {
  return new Promise((resolve, reject) => {
    const probe = new Worker(
      new URL("../workers/compact.worker.ts", import.meta.url),
      { type: "module" },
    );
    const timer = window.setTimeout(() => {
      probe.terminate();
      reject(new Error("GPU check timed out"));
    }, 20000);
    const stop = () => {
      window.clearTimeout(timer);
      probe.terminate();
    };
    probe.onmessage = ({
      data,
    }: MessageEvent<{
      checked?: { available: boolean; adapter?: object };
      error?: string;
    }>) => {
      stop();
      if (data.checked) resolve(data.checked);
      else reject(new Error(data.error ?? "Compact inference is unavailable"));
    };
    probe.onerror = () => {
      stop();
      reject(new Error("Compact runtime could not load"));
    };
    probe.postMessage({ check: true });
  });
}
