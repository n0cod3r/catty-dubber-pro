export type SeparationPhase = "idle" | "interrupted" | "ready" | "failed";

export function separationPhase(
  status: string | null | undefined,
  hasBackground: boolean,
): SeparationPhase {
  if (hasBackground) return "ready";
  if (status === "failed") return "failed";
  // A persisted PROCESSING status without a running request means a previous
  // run was interrupted (app closed or engine restarted).
  if (status === "processing" || status === "queued") return "interrupted";
  return "idle";
}

export function separationNeedsModel(error: string | null): boolean {
  return !!error && /not installed|separation_model_missing/i.test(error);
}
