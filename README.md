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

## TypeScript, linting, and formatting

```bash
pnpm typecheck     # Browser code and Vite configuration
pnpm lint         # ESLint, TypeScript, React Hooks, and Fast Refresh rules
pnpm lint:fix     # Apply automatic lint fixes
pnpm format       # Prettier formatting and import sorting
pnpm check        # Typecheck, lint, and formatting checks
pnpm build:web    # Typecheck and build the web UI
```

In VS Code or Cursor, install the workspace's recommended ESLint and Prettier
extensions. Saving formats files and sorts imports with Prettier; ESLint also
applies automatic fixes. Imports are grouped by Node built-ins, React, other
packages, `@/` aliases, and relative paths. Side-effect imports (including CSS)
keep their execution order.

The browser TypeScript configuration includes `vite/client` for CSS and asset
imports. Vite's configuration is checked separately with Node types. Reference
`*.test.ts` and `*.test.tsx` files are excluded from the browser build; Freecut
tests using `vite-plus/test` need a Catty test runner and fixture migration before
they can run here.

## Run the Python engine shell

```bash
cd engine
uv sync
uv run catty-engine
```

The initial milestone intentionally contains only a runnable shell and clean boundaries. Movox functionality will be migrated module-by-module after this foundation is stable.
