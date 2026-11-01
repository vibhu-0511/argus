"""`fix-loop replay <file>` prints the patch from stored edits. No model call."""

from __future__ import annotations

import sys
from pathlib import Path

from fix_loop.replay import replay


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["replay", *args[1:]] or len(args) != 2:
        print("usage: fix-loop replay <file>", file=sys.stderr)
        return 2
    print(replay(Path(args[1]), Path.cwd()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
