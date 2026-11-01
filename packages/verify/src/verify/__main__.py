"""python -m verify ci <pair-dir>"""

from __future__ import annotations

import sys
from pathlib import Path

from verify.ci import check_dir


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "ci":
        return check_dir(Path(args[1]))
    print("usage: python -m verify ci <pair-dir>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
