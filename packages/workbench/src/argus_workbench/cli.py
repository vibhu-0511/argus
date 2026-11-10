"""`argus-workbench serve [--port N]`. Binds 127.0.0.1 and nothing else: there is no --host option on purpose."""

from __future__ import annotations

import argparse
import sys

HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _port(text: str) -> int:
    port = int(text)
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be 0 to 65535")
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="argus-workbench",
        description="Local Argus workbench: five screens over scripted and replayed runs. No model is called. "
        "Serves 127.0.0.1 only.",
    )
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="start the local server on 127.0.0.1")
    serve.add_argument("--port", type=_port, default=DEFAULT_PORT, help=f"port to listen on (default {DEFAULT_PORT})")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command != "serve":
        parser.print_help()
        return 2
    import uvicorn  # imported here so `--help` stays fast

    from argus_workbench.security import mask
    from argus_workbench.server import create_app

    app = create_app()
    print(f"argus-workbench: http://{HOST}:{args.port}/  (token {mask(app.state.token)} goes to the page, never in a URL)")
    uvicorn.run(app, host=HOST, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
