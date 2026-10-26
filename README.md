# Catty Dubber Pro

A clean rebuild of Catty Dubber Pro: a desktop AI dubbing studio with a React + Tauri interface and a Python media/AI engine.

## Current foundation

- `apps/desktop` — Tauri 2 + React + TypeScript desktop shell
- `engine` — Python dubbing engine foundation
- `packages/contracts` — shared IPC contract definitions
- `packages/ui` — shared UI package placeholder
- `docs` — architecture and migration notes

## Run the desktop shell

Prerequisites: Node.js, pnpm, Rust, and the Tauri system prerequisites for your OS.

```bash
pnpm install
pnpm dev
```

To run only the web UI:

```bash
pnpm dev:web
```

## Run the Python engine shell

```bash
cd engine
uv sync
uv run catty-engine
```

The initial milestone intentionally contains only a runnable shell and clean boundaries. Movox functionality will be migrated module-by-module after this foundation is stable.
