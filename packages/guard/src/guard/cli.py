"""`guard` command line. Sub-commands are added by the P7 tasks (verify-log, escape)."""
import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print("guard: no sub-command yet" if not args else f"guard: unknown sub-command {args[0]!r}")
    return 2
