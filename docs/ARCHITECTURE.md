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
