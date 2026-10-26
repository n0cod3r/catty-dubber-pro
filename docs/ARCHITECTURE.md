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
