from __future__ import annotations


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Catty media and AI engine")
    parser.add_argument(
        "--rpc", action="store_true", help="Handle one JSON request on stdin"
    )
    args = parser.parse_args()
    if args.rpc:
        from catty_engine.ipc import run_rpc

        run_rpc()
    else:
        print("Catty Engine ready")


__all__ = ["main"]
