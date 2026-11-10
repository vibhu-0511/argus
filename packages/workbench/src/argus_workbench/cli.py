"""`argus-workbench` command line. The `serve` sub-command is added by P10-T02."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="argus-workbench",
        description="Local Argus workbench: five screens over scripted and replayed runs. No model is called.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(sys.argv[1:] if argv is None else argv)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
