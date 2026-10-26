import type { EngineMethods } from "@catty/contracts";
import { invoke } from "@tauri-apps/api/core";

export async function requestEngine<M extends keyof EngineMethods>(
  method: M,
  params: EngineMethods[M]["params"],
): Promise<EngineMethods[M]["result"]> {
  try {
    return await invoke<EngineMethods[M]["result"]>("engine_request", { method, params });
  } catch (cause) {
    const message =
      typeof cause === "object" &&
      cause !== null &&
      "message" in cause &&
      typeof cause.message === "string"
        ? cause.message
        : typeof cause === "string"
          ? cause
          : "The engine request failed.";
    throw new Error(message, { cause });
  }
}
