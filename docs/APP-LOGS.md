# App logs

The timeline footer's **Logs** button opens a modal for the current app session.
Search messages, filter Frontend/Rust/Python or severity, copy the visible entries,
clear the current view, or disable Follow to inspect older output. Escape closes
it. Logs are held in memory, not in project.json or persisted across app restarts.
Both native and frontend buffers retain at most 2,000 entries, each capped at 8,192
characters. Native logs accumulate even with the dialog closed.
A cursor-based command fetches new entries every 750 ms while the dialog is open;
it does not acquire the engine request mutex, so long-running inference does not
block log viewing. Clear removes collected entries without resetting the native cursor.

Python uses the standard logging API under the `catty_engine` namespace. The
`logged_request` decorator correlates request IDs and logs success/failure.
`logged_process` logs phase starts, elapsed duration, and exception traces without
serializing call arguments, model inputs, dialogue text or credential settings.
Use `logging.getLogger(__name__).info(...)` for additional progress inside a phase.
Translation logs batch progress, provider error categories and retry attempts;
media, model loading, ASR, speaker inference and project mutations log phase boundaries.
Logs go to stderr as NDJSON tagged with `catty_log`, keeping stdout exclusively IPC.
Existing third-party stderr, including FunASR diagnostics, is also captured by Rust.
Unstructured third-party lines have INFO severity; structured Python logs retain levels.

Rust collects startup, request lifecycle, transport errors and Python diagnostics.
Frontend initialization captures console output, uncaught errors and unhandled
promise rejections; caught engine errors also enter the frontend log store.
Common credential patterns (Bearer tokens, API keys, secrets and passwords) are
redacted before display/copy, and native storage redacts its input too. Avoid
logging credentials or request bodies even with these filters in place.

Restart the desktop development app after updating native/Python code. The browser
preview can show frontend logs only. Existing log output from before this feature
started cannot be reconstructed. No external logging/telemetry service is used.
