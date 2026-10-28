# Engine ↔ UI connection

The desktop transport is connected for engine health, media probing, project and episode import, persistent dialogue editing, speaker correction, and Smart Transcribe:

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
protocol version, limits short requests to 35 seconds, and allows long media and
speech requests up to one hour. FFprobe has a 30-second timeout. The Python process
is persistent: model-heavy operations reuse the loaded FunASR stack instead of
restarting the engine per request.

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

`ProjectService` and `ProjectStore` are connected to the editor through
`project.*` operations. `speech.transcribe` runs Smart Transcribe and persists
dialogue, speakers, and processing state. `speaker_error` is returned to the UI and
persisted as `processing.speaker_error` when only speaker annotation fails.

Translation, TTS, separation, and annotate-only speaker retry are not implemented.
When they are added, expose them as cancellable jobs with structured progress.
`audio.prepare` already uses the dedicated cancellable Tauri command; Transcribe is
a long-running synchronous request and does not yet expose progress or cancel.

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

### Live translation updates

Translation requests may include an `operation_id`. Python emits structured
`catty_progress: translation` messages on stderr; Rust relays these through the
`catty:translation-progress` Tauri event without waiting for the final RPC reply.
Stdout remains reserved for the response. The frontend subscribes before invoking
translation and accepts updates only for the active operation, project and episode.
Listeners and queued callbacks are invalidated on completion or scope changes.

Local translation saves and publishes each completed dialogue line. Cloud
translation retains batches (currently 12 lines by default) and publishes each
completed batch. Progress includes active segment IDs, the operation's saved/total
counts, and an episode snapshot only after it has been saved to project.json.
The Inspector immediately displays these saved translations, highlights active
rows, and shows a progress bar with elapsed time. This is completed-line/batch
streaming, not token streaming or a guessed percentage during model loading.
Manual edits remain protected. If later work fails, earlier saved results remain
visible and persistent; the frontend refreshes saved state after an RPC error.

Restart the desktop process after updating Rust/Python to enable the event bridge.
