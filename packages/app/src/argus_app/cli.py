"""`argus-app` command line. Sub-commands are added by the P8 tasks."""
import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print("argus-app: no sub-command yet" if not args else f"argus-app: unknown sub-command {args[0]!r}")
    return 2
