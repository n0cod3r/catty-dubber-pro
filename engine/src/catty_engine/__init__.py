from __future__ import annotations

import sys
from typing import TextIO


def _configure_stdio() -> None:
    """Force UTF-8 on the IPC pipes.

    Windows pipes use the ANSI code page by default, so any Unicode path,
    project name or Khmer dialogue would fail to decode on stdin or encode on
    stdout. Rust always reads/writes UTF-8, so both ends must agree.
    """
    streams: tuple[TextIO, ...] = tuple(
        stream for stream in (sys.stdin, sys.stdout) if stream is not None
    )
    for stream in streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="strict")
    if sys.stderr is not None:
        reconfigure = getattr(sys.stderr, "reconfigure", None)
        if reconfigure is not None:
            # Diagnostics must never crash the request loop on odd input.
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main() -> None:
    import argparse

    _configure_stdio()

    parser = argparse.ArgumentParser(description="Catty media and AI engine")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--rpc",
        action="store_true",
        help="Handle one JSON request on stdin",
    )
    mode.add_argument(
        "--server",
        action="store_true",
        help="Run the long-lived NDJSON engine server",
    )
    args = parser.parse_args()

    if args.rpc:
        from catty_engine.ipc import run_rpc

        run_rpc()
    elif args.server:
        from catty_engine.ipc import run_server

        run_server()
    else:
        print("Catty Engine ready")


__all__ = ["main"]
