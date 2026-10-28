import wasmModuleUrl from "onnxruntime-web/ort-wasm-simd-threaded.asyncify.mjs?url";
import wasmUrl from "onnxruntime-web/ort-wasm-simd-threaded.asyncify.wasm?url";
import * as ort from "onnxruntime-web/webgpu";

import { encodeWave, normalNoise, readMonoWave } from "../services/audio.ts";

// Independently implements the graph contract published with
// Uddom/voxcpm2-khmer-webgpu and the Apache-2.0 OpenBMB VoxCPM2 inference layout.
// React never executes the model loop; KV caches remain in this worker.
ort.env.wasm.numThreads = 1;
ort.env.wasm.proxy = false;
ort.env.wasm.wasmPaths = { wasm: wasmUrl, mjs: wasmModuleUrl };

type Graph = {
  name: string;
  path: string;
  externalData?: { path: string }[];
  outputs?: { name: string }[];
};
type Manifest = {
  version: string;
  files: Graph[];
  config: { hidden: number; baseLayers: number; residualLayers: number };
};
type Job = {
  operation_id: string;
  url: string;
  model_version: string;
  tokens: number[];
  has_reference: boolean;
  reference_text: string | null;
};
type GPUAdapterInfo = { vendor?: string; architecture?: string };
type Adapter = {
  info?: GPUAdapterInfo;
  features: Set<string>;
  limits: { maxBufferSize: number; maxStorageBufferBindingSize: number };
  requestDevice: (options: object) => Promise<{ destroy: () => void }>;
};
const scope = self as unknown as {
  onmessage: (event: MessageEvent<Job | { check: true }>) => void;
  postMessage: (value: unknown, transfer?: Transferable[]) => void;
};
let sessions: Record<string, ort.InferenceSession> = {};
let embeddings: Uint16Array | null = null;
let version = "";
let active = false;

async function checkGPU() {
  const gpu = (
    navigator as unknown as {
      gpu?: { requestAdapter: () => Promise<Adapter | null> };
    }
  ).gpu;
  if (!gpu)
    throw new Error(
      "WebGPU is unavailable in this desktop webview. Select original VoxCPM2 in Settings → Models.",
    );
  const adapter = await gpu.requestAdapter();
  if (!adapter || !adapter.features.has("shader-f16"))
    throw new Error(
      "Compact VoxCPM2 requires a WebGPU GPU with float16 support.",
    );
  if (adapter.limits.maxStorageBufferBindingSize < 134217728)
    throw new Error("GPU buffer limits are too small for compact VoxCPM2.");
  const device = await adapter.requestDevice({
    requiredFeatures: ["shader-f16"],
  });
  device.destroy();
  return {
    available: true,
    adapter: {
      vendor: adapter.info?.vendor ?? "",
      architecture: adapter.info?.architecture ?? "",
    },
  };
}

async function checkInference() {
  const capability = await checkGPU();
  const model = new Uint8Array([
    8, 8, 58, 70, 10, 14, 10, 1, 88, 10, 1, 88, 18, 1, 89, 34, 3, 77, 117, 108,
    18, 18, 99, 111, 109, 112, 97, 99, 116, 45, 102, 112, 49, 54, 45, 112, 114,
    111, 98, 101, 90, 15, 10, 1, 88, 18, 10, 10, 8, 8, 10, 18, 4, 10, 2, 8, 2,
    98, 15, 10, 1, 89, 18, 10, 10, 8, 8, 10, 18, 4, 10, 2, 8, 2, 66, 2, 16, 13,
  ]);
  const probe = await ort.InferenceSession.create(model, {
    executionProviders: ["webgpu"],
  });
  const input = new ort.Tensor(
    "float16",
    new Uint16Array([0x3c00, 0x4000]),
    [2],
  );
  try {
    const result = await probe.run({ X: input });
    try {
      const output = await floats(result.Y!);
      if (output[0] !== 1 || output[1] !== 4)
        throw new Error("WebGPU float16 inference returned incorrect results");
    } finally {
      dispose(result);
    }
  } finally {
    input.dispose();
    await probe.release();
  }
  return capability;
}

async function bytes(url: string) {
  const result = await fetch(url);
  if (!result.ok)
    throw new Error(
      `Cannot read local model asset (${result.status}). Reinstall VoxCPM2 Compact.`,
    );
  return result.arrayBuffer();
}
async function load(job: Job) {
  if (version === job.model_version && embeddings) return;
  await checkGPU();
  for (const session of Object.values(sessions)) await session.release();
  sessions = {};
  embeddings = null;
  version = "";
  const response = await fetch(`${job.url}manifest.json`);
  const manifest: Manifest = await response.json();
  if (manifest.version !== job.model_version)
    throw new Error("Model manifest changed; retry generation.");
  try {
    for (const graph of manifest.files.filter((file) =>
      file.path.endsWith(".onnx"),
    )) {
      scope.postMessage({ phase: "loading", graph: graph.name });
      const model = await bytes(job.url + graph.path);
      const externalData = [];
      for (const data of graph.externalData ?? []) {
        externalData.push({
          path: data.path.split("/").at(-1)!,
          data: await bytes(job.url + data.path),
        });
      }
      const preferredOutputLocation: Record<string, "cpu" | "gpu-buffer"> = {};
      for (const output of graph.outputs ?? [])
        preferredOutputLocation[output.name] = output.name.startsWith(
          "present.",
        )
          ? "gpu-buffer"
          : "cpu";
      sessions[graph.name] = await ort.InferenceSession.create(model, {
        executionProviders: ["webgpu"],
        externalData,
        preferredOutputLocation,
        graphOptimizationLevel: "all",
      });
    }
    embeddings = new Uint16Array(await bytes(`${job.url}embed_tokens.f16.bin`));
    if (embeddings.length !== 73448 * 2048)
      throw new Error("Invalid embedding table size");
    version = manifest.version;
  } catch (cause) {
    for (const session of Object.values(sessions)) await session.release();
    sessions = {};
    embeddings = null;
    throw cause;
  }
}

function tensor(data: Float32Array | Uint16Array, dims: number[]) {
  return data instanceof Uint16Array
    ? new ort.Tensor("float16", data, dims)
    : new ort.Tensor("float32", data, dims);
}
function halfToFloat(value: number) {
  const exponent = (value >>> 10) & 31,
    fraction = value & 1023;
  return (
    (value & 32768 ? -1 : 1) *
    (exponent === 0
      ? fraction * 2 ** -24
      : exponent === 31
        ? fraction
          ? NaN
          : Infinity
        : (1 + fraction / 1024) * 2 ** (exponent - 15))
  );
}
async function floats(value: ort.Tensor): Promise<Float32Array> {
  const data = await value.getData();
  return value.type === "float16" && data instanceof Uint16Array
    ? Float32Array.from(data, halfToFloat)
    : Float32Array.from(data as Float32Array);
}
function dispose(values: Record<string, ort.Tensor>) {
  for (const item of Object.values(values)) item.dispose();
}
class Cache {
  values: Record<string, ort.Tensor> = {};
  constructor(layers: number) {
    for (let i = 0; i < layers; i++)
      for (const kind of ["key", "value"])
        this.values[`past_key_values.${i}.${kind}`] = tensor(
          new Uint16Array(0),
          [1, 2, 0, 128],
        );
  }
  replace(outputs: Record<string, ort.Tensor>) {
    dispose(this.values);
    this.values = {};
    for (const [name, value] of Object.entries(outputs))
      if (name.startsWith("present."))
        this.values[name.replace("present.", "past_key_values.")] = value;
  }
  clear() {
    dispose(this.values);
    this.values = {};
  }
}
function session(name: string) {
  const value = sessions[name];
  if (!value) throw new Error(`Missing graph ${name}`);
  return value;
}
async function feature(data: Float32Array, length: number) {
  const input = tensor(data, [1, length, 4, 64]);
  try {
    return (await session("feat_encoder").run({ feat: input })).feat_embed!;
  } finally {
    input.dispose();
  }
}

async function generate(job: Job) {
  if (
    job.tokens.length < 2 ||
    job.tokens.length > 1024 ||
    job.tokens.some((id) => !Number.isInteger(id) || id < 0 || id >= 73448)
  )
    throw new Error(
      "Dialogue is too long or has invalid tokens. Split it into shorter lines.",
    );
  await load(job);
  let reference = new Float32Array(0);
  if (job.has_reference) {
    const audio = readMonoWave(await bytes(`${job.url}reference.wav`));
    const padded = new Float32Array(Math.ceil(audio.length / 2560) * 2560);
    padded.set(audio, job.reference_text ? padded.length - audio.length : 0);
    const input = tensor(padded, [1, 1, padded.length]);
    try {
      const encoded = await session("vae_encoder").run({ audio: input });
      try {
        const latent = await floats(encoded.latents!);
        const frames = encoded.latents!.dims[2]!;
        if (frames % 4)
          throw new Error("Reference latent length is not a multiple of four");
        reference = new Float32Array(frames * 64);
        for (let frame = 0; frame < frames; frame++)
          for (let channel = 0; channel < 64; channel++)
            reference[frame * 64 + channel] = latent[channel * frames + frame]!;
      } finally {
        dispose(encoded);
      }
    } finally {
      input.dispose();
    }
  }
  const referencePatches = reference.length / 256;
  const continuation = job.has_reference && !!job.reference_text;
  const ids = continuation
    ? [...job.tokens, ...new Array<number>(referencePatches).fill(0)]
    : job.has_reference
      ? [
          103,
          ...new Array<number>(referencePatches).fill(0),
          104,
          ...job.tokens,
        ]
      : job.tokens;
  const features = new Float32Array(ids.length * 256);
  const masks = new Uint16Array(ids.length);
  const offset = continuation ? job.tokens.length : 1;
  if (job.has_reference) {
    features.set(reference, offset * 256);
    masks.fill(0x3c00, offset, offset + referencePatches);
  }
  const textEmbeddings = new Uint16Array(ids.length * 2048);
  for (let index = 0; index < ids.length; index++) {
    if (!masks[index])
      textEmbeddings.set(
        embeddings!.subarray(ids[index]! * 2048, (ids[index]! + 1) * 2048),
        index * 2048,
      );
  }
  const baseCache = new Cache(28),
    residualCache = new Cache(8);
  let hidden: ort.Tensor | undefined, stop: ort.Tensor | undefined;
  async function step(
    text: Uint16Array,
    mask: Uint16Array,
    feat: ort.Tensor,
    length: number,
  ) {
    const textInput = tensor(text, [1, length, 2048]),
      maskInput = tensor(mask, [1, length, 1]);
    let base: Record<string, ort.Tensor> | undefined;
    try {
      base = await session("base_lm").run({
        text_embeds: textInput,
        feat_embeds: feat,
        audio_mask: maskInput,
        ...baseCache.values,
      });
      baseCache.replace(base);
      const residual = await session("residual_lm_step").run({
        base_hidden: base.hidden!,
        feat_embeds: feat,
        audio_mask: maskInput,
        ...residualCache.values,
      });
      residualCache.replace(residual);
      hidden?.dispose();
      stop?.dispose();
      hidden = residual.dit_hidden;
      stop = residual.stop_logits;
    } finally {
      base?.hidden?.dispose();
      textInput.dispose();
      maskInput.dispose();
      feat.dispose();
    }
  }
  const patches: Float32Array[] = [];
  const contextPatches = continuation ? Math.min(3, referencePatches) : 0;
  for (let i = referencePatches - contextPatches; i < referencePatches; i++)
    patches.push(reference.slice(i * 256, (i + 1) * 256));
  let condition: Float32Array = continuation
    ? reference.slice(-256)
    : new Float32Array(256);
  const noise = normalNoise(42);
  let ended = false;
  try {
    // Prefill in bounded chunks so long references don't exceed WebGPU tensor limits.
    for (let start = 0; start < ids.length; start += 128) {
      const count = Math.min(128, ids.length - start);
      const feat = await feature(
        features.slice(start * 256, (start + count) * 256),
        count,
      );
      await step(
        textEmbeddings.slice(start * 2048, (start + count) * 2048),
        masks.slice(start, start + count),
        feat,
        count,
      );
    }
    const limit = Math.min(180, job.tokens.length * 6 + 10);
    for (let patch = 0; patch < limit; patch++) {
      let x: Float32Array = Float32Array.from({ length: 256 }, noise);
      const cond = tensor(condition, [1, 4, 64]);
      try {
        const times = Array.from({ length: 11 }, (_, i) => {
          const t = 1 - i / 10;
          return t + Math.cos((Math.PI / 2) * t) - 1 + t;
        });
        // CFG-Zero-Star skips the initial integration interval.
        for (let i = 1; i < 10; i++) {
          const input = tensor(x, [1, 4, 64]);
          const t = tensor(new Float32Array([times[i]!]), []),
            dt = tensor(new Float32Array([times[i]! - times[i + 1]!]), []),
            cfg = tensor(new Float32Array([2]), []);
          let result: Record<string, ort.Tensor> | undefined;
          try {
            result = await session("locdit_step").run({
              x: input,
              dit_hidden: hidden!,
              cond,
              t,
              dt,
              cfg,
            });
            x = await floats(result.x_next!);
          } finally {
            input.dispose();
            t.dispose();
            dt.dispose();
            cfg.dispose();
            if (result) dispose(result);
          }
        }
      } finally {
        cond.dispose();
      }
      patches.push(x);
      condition = x;
      scope.postMessage({ phase: "generating", patches: patch + 1 });
      const logits = await floats(stop!);
      if (patch > 2 && logits[1]! > logits[0]!) {
        ended = true;
        break;
      }
      const feat = await feature(x, 1);
      await step(new Uint16Array(2048), new Uint16Array([0x3c00]), feat, 1);
    }
    if (!ended)
      throw new Error(
        "Speech exceeded the compact model's 28-second line limit. Split the dialogue and retry.",
      );
    const frames = patches.length * 4;
    const latents = new Float32Array(frames * 64);
    for (let patch = 0; patch < patches.length; patch++)
      for (let frame = 0; frame < 4; frame++)
        for (let channel = 0; channel < 64; channel++)
          latents[channel * frames + patch * 4 + frame] =
            patches[patch]![frame * 64 + channel]!;
    const input = tensor(latents, [1, 64, frames]);
    let decoded: Record<string, ort.Tensor> | undefined;
    try {
      decoded = await session("vae_decoder").run({ latents: input });
      const audio = (await floats(decoded.audio!)).slice(contextPatches * 7680);
      if (!audio.length || audio.some((sample) => !Number.isFinite(sample)))
        throw new Error("Generated speech contains invalid samples");
      return encodeWave(audio, 48000);
    } finally {
      input.dispose();
      if (decoded) dispose(decoded);
    }
  } finally {
    baseCache.clear();
    residualCache.clear();
    hidden?.dispose();
    stop?.dispose();
  }
}

scope.onmessage = async ({ data }) => {
  if (active) {
    scope.postMessage({ error: "Compact worker is busy" });
    return;
  }
  active = true;
  try {
    if ("check" in data) scope.postMessage({ checked: await checkInference() });
    else {
      const audio = await generate(data);
      scope.postMessage({ audio, operation_id: data.operation_id }, [audio]);
    }
  } catch (cause) {
    scope.postMessage({
      error: cause instanceof Error ? cause.message : String(cause),
    });
  } finally {
    active = false;
  }
};
