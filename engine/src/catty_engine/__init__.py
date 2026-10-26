from __future__ import annotations


def main() -> None:
    import argparse

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
