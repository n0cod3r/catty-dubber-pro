# Catty Dubber Pro Architecture

## Boundary

Catty Dubber Pro is split into two primary runtimes:

```text
React UI
  ↓
Tauri desktop host
  ↓
Typed job/IPC boundary
  ↓
Python engine
  ↓
FFmpeg / ASR / diarization / translation / TTS / separation
```

The desktop layer owns presentation, user interaction and native desktop integration. The Python engine owns AI and media processing. Long-running engine operations must be modeled as jobs with progress, cancellation and structured errors rather than blocking UI calls.

## Migration rule

The old PySide6 presentation layer is not migrated. Existing Movox engine behavior may be ported module-by-module only after its responsibility and interface are defined. The first milestone is a runnable desktop shell with clean boundaries, not feature parity.

## Initial modules

The engine is divided into `media`, `speech`, `speakers`, `translation`, `tts`, `separation`, `project`, and `workers`. The desktop application should organize UI by feature as those features are migrated.

## Desktop feature ownership

The desktop source groups UI and behavior by feature:

```text
src/
  app/                    Application composition and project routing
  components/ui/          Shared UI primitives
  features/
    editor/               Workspace layout, sidebar, header, inspector
    timeline/             Timeline UI, editing state, interactions, media visuals
      components/
      deps/
      hooks/
      services/
      stores/
      types/
      utils/
      workers/
      constants.ts
      types.ts
      index.ts
    preview/              Video composition, audio sync, aspect ratio and sizing
    playback/             Playback clock and controls
    episodes/             Source import and episode lifecycle
    projects/             Project home and persistence
    engine/               Engine connection, requests and desktop shutdown
    audio-preparation/    Audio preparation UI
  shared/                 Feature-independent types and utilities
```

Each feature exposes its supported interface through `index.ts`. Cross-feature
imports go through the importing feature's `deps/` adapters, which re-export only
what it needs from another feature's public entry. Internal files use relative
imports. Application composition imports public entries directly. Shared code
must not depend on features or the application.

Timeline owns waveform and thumbnail generation, including its worker lifecycle.
Editor composes timeline, playback and preview without managing visual decoding.
Folders are created when they have an implementation, rather than adding empty
placeholders for future features.

Run `pnpm check:boundaries` to enforce the import rules and keep feature UI out of
root components. This check also runs as part of `pnpm check`.

### Editor loading and timeline sessions

The public editor workspace is a lazy component with a visible Suspense fallback.
Project home can render before the workspace chunk is loaded. The existing editor
error boundary handles loading and render failures.

Each mounted workspace creates a vanilla Zustand store through `TimelineProvider`.
`useTimelineStore(selector)` reads that session through context. The store exposes named editing actions and commits each edit atomically,
preserving editing constraints and undo/redo. It is
not a global singleton and does not persist transient history. The existing
workspace key resets the session when the episode or playback media revision
changes; closing a project unmounts the provider. Future timeline consumers can
subscribe directly through the provider without extending workspace prop chains.

## Product workflow

Catty follows **automation first, correction second**. The five primary actions
are Import, Transcribe, Translate to Khmer, Generate Dubbing and Export. Internal
analysis and setup must not become mandatory manual workflow steps.

The next milestone is **Smart Speaker Detection**, integrated into Transcribe.
Speaker assignment and renaming are optional corrections, followed by the
**Smart Khmer Translation** milestone. Voice mapping likewise defaults to ready
to run when generating dubbing. See [Smart Dubbing Pipeline](SMART-DUBBING-PIPELINE.md)
for planned behavior, acceptance criteria and the distinction from current support.
