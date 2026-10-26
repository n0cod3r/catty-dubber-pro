# Engine ↔ UI connection

The desktop transport is now connected for engine health, media probing, and speech-audio preparation:

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
protocol version, and limits short requests to 35 seconds. FFprobe has a 30-second
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

- `health`: engine version, supported operations, FFmpeg/FFprobe availability.
- `media.probe`: source metadata from `MediaProbeService`.
- `audio.prepare`: 16 kHz mono speech WAV from `AudioPreparationService`, invoked
  through the dedicated cancellable Tauri `prepare_audio` command.

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
one-request transport handles health/probe calls and bounded audio extraction;
model-heavy AI work should still use a persistent worker.

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

## Audio Preparation in the UI

1. Import a video in the desktop app.
2. Open **Inspector → Audio** (selected automatically after import).
3. Click **Prepare speech audio** and choose an output folder.
4. The UI shows an indeterminate running indicator and a Cancel button; no
   estimated percentage is fabricated. On completion it shows the WAV path,
   sample rate, and channels.

The file is written under
`<chosen folder>/assets/episodes/<episode UUID>/audio/speech-16k-mono.wav`.
This prepares the full source episode, independently of timeline edits. Original
source video/audio are not replaced. Repeating preparation in the same session
passes the existing AudioAsset to the engine for fingerprint/cache validation.
Changing tabs keeps the job and result alive; replacing the episode cancels its
active job. Project manifest persistence of the asset is not wired yet.

Audio extraction runs off the UI thread with its own job ID and a one-hour
limit. `cancel_audio` signals a private cancellation file, which the engine
checks while FFmpeg runs. Cancellation stops the FFmpeg child and removes its
staged output. Successful extraction atomically publishes a complete WAV, so
failed/cancelled retries preserve any previous valid cached file.

The engine reports CANCELLED, FFMPEG_NOT_FOUND, AUDIO_PREPARATION_FAILED, and
validation errors as structured errors. Browser-only imports cannot prepare
audio through the desktop bridge and show an explanatory disabled control.

Tests include real Rust → Python → FFmpeg extraction, probing the resulting
16 kHz mono WAV, cache reuse, cancellation, and failure cleanup.

## Closing the desktop window

Closing the main Catty window or choosing Quit now shuts down the application
instead of leaving a hidden macOS app and its engine work running. The native
host rejects new requests, cancels active audio preparation, and terminates
active metadata/probe processes. Engine requests run in isolated process groups
on Unix; forced cancellation and timeout terminate Python and descendants such
as FFprobe/FFmpeg together. Windows uses process-tree termination.

The UI shows **Closing Catty…** while playback, decoder workers, and preparation
controls unmount. Audio extraction first gets a cooperative cancellation signal
so FFmpeg can stop and remove staged output. The host force-stops an unresponsive
request after two seconds and drains tracked jobs before exiting. Shutdown tests
cover cancellation, rejection of late work, and descendant-process termination.
