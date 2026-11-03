"""`guard` command line. Sub-commands are added by the P7 tasks (verify-log, escape)."""
import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["verify-log"]:
        from guard.auditlog import verify_log_main

        return verify_log_main(args[1:])
    if args[:1] == ["escape"]:
        from guard.escape import main as escape_main

        return escape_main(args[1:])
    if args[:1] == ["redteam"]:
        from guard.redteam import main as redteam_main

        return redteam_main(args[1:])
    if args[:1] == ["sandbox-run"]:
        from guard.sandbox_run import main as sandbox_run_main

        return sandbox_run_main(args[1:])
    if args[:1] == ["firecracker-run"]:
        from guard.firecracker_run import main as firecracker_run_main

        return firecracker_run_main(args[1:])
    print("guard: no sub-command yet" if not args else f"guard: unknown sub-command {args[0]!r}")
    return 2
