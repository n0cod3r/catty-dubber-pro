# Engine ↔ UI connection

The desktop transport is now connected for engine health and media probing:

```text
React: requestEngine("media.probe", { path })
  → Tauri: invoke("engine_request", { method, params })
  → Rust: engine/.venv/bin/python -m catty_engine --rpc
  → Python: MediaProbeService → FFprobe
  → versioned JSON result/error → typed React result
```

The engine runs locally; no HTTP server or port is required. Requests are passed
as JSON on stdin, never interpolated into shell commands. Rust runs the process
on a blocking worker so the UI remains responsive, checks the response ID and
protocol version, and kills requests after 35 seconds. FFprobe has a 30-second
timeout. The process exits after each short request.

## Run in development

Install Python 3.13, uv, and FFmpeg/FFprobe, then run from the repository root:

```sh
cd engine
uv sync
cd ..
pnpm install
pnpm dev
```

You do **not** need to run `uv run catty-engine` separately. Tauri starts the
engine automatically when an operation is requested. The header shows **Engine
online** after a successful health check; click the status to retry. Missing
Python dependencies or FFprobe produce an actionable error.

On desktop video import, the engine supplies frame rate, codecs, sample rate,
and channel count to the media inspector. Source frame rate drives arrow-key
frame stepping. Browser video dimensions/duration are retained once available
because the WebView accounts for display rotation. If probing fails, the video
still loads and an error is shown. `pnpm dev:web` keeps its file-picker fallback;
a browser cannot invoke local Python and displays **Engine · desktop only**.

Paths default to this checkout's `engine/` directory and its `.venv`. Set absolute
`CATTY_ENGINE_DIR` and `CATTY_ENGINE_PYTHON` paths before starting the desktop host
if using a different engine checkout or Python environment.

## Contract and available operations

`packages/contracts/src/index.ts` is the shared TypeScript contract, consumed as
`@catty/contracts`. `engine/src/catty_engine/ipc.py` validates incoming requests
with Pydantic and dispatches the implemented operations:

- `health`: engine version, supported operations, FFprobe availability.
- `media.probe`: source metadata from `MediaProbeService`.

Example protocol request:

```json
{
  "version": 1,
  "id": "probe-1",
  "method": "media.probe",
  "params": { "path": "/absolute/video.mp4" }
}
```

An engine error is `{ "code": "MEDIA_PROBE_FAILED", "message": "..." }`.
Stdout is reserved for one JSON response; engine diagnostics belong on stderr.

## What to connect next

`ProjectService` and `ProjectStore` are implemented in Python, but project UI and
project IPC operations are not connected yet. Add explicit request/result types,
validated parameter models, and narrow Tauri method allowlisting for create,
open, save, and episode operations before exposing them in the UI.

Speech, translation, TTS, separation, and workers currently have no implemented
operations. When they are added, expose them as background jobs with job IDs,
progress events, cancellation, and structured results. Use a persistent engine
worker for model-heavy work so models are not reloaded per request. The current
one-request process transport is for short health/probe calls.

Release packaging is a separate step: ship a Python engine executable as a Tauri
sidecar and include/configure FFprobe. This development bridge relies on the
checkout and virtual environment; it does not make an installed release
self-contained.

## Checks

```sh
uv run --directory engine pytest -q
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --lib engine::tests
pnpm typecheck
pnpm lint
pnpm build:web
```

The Rust tests execute the actual Python engine, including probing a generated
WAV through FFprobe. They require the engine environment and FFprobe installed.
