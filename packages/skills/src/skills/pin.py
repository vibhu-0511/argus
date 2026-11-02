"""P5.5-T10 the owner's sign-off: pin a reviewed skill in `packages/skills/skills.lock.json`.

    uv run python -m skills.pin NAME --by YOUR-NAME

Writes `reviewed: true`, who, today's date and the SHA-256 of the SKILL.md as it is now. The loader trusts this entry and
nothing in the SKILL.md itself, so any later edit to the file needs a new pin. The lock is rewritten only if the loader
would then accept the skill; a skill that fails a format or tool check is reported and the lock is left as it was.
Only the owner runs this: it is the act of reviewing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from fix_loop.skills import LOCK_NAME, LOCK_VERSION, content_hash, load_skills, read_lock

SKILLS = Path(__file__).resolve().parents[2] / "skills"
LOCK = SKILLS.parent / LOCK_NAME


def pin(name: str, by: str, skills: Path = SKILLS, lock: Path = LOCK) -> str | None:
    """Pin `name`. Returns None on success, else the refusal text (the lock is not changed)."""
    file = skills / name / "SKILL.md"
    if not file.is_file():
        return f"{file} does not exist"
    before = lock.read_bytes() if lock.exists() else None
    entries = read_lock(lock)
    entries[name] = {"sha256": content_hash(file.read_bytes()), "reviewed": True, "reviewed_by": by, "reviewed_on": date.today().isoformat()}
    lock.write_text(json.dumps({"version": LOCK_VERSION, "skills": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    refusal = next((r for r in load_skills(skills, lock)[1] if r.name == name), None)
    if refusal is not None:
        lock.write_bytes(before) if before is not None else lock.unlink()
        return f"{name} was not pinned: {refusal.reason.value}: {refusal.detail}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skills.pin")
    parser.add_argument("name")
    parser.add_argument("--by", required=True, help="who reviewed it")
    args = parser.parse_args(argv)
    problem = pin(args.name, args.by)
    print(problem or f"pinned {args.name}")
    return 1 if problem else 0


if __name__ == "__main__":
    sys.exit(main())
