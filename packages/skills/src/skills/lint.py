"""P5.5-T12 skill lint for CI. No model call, no network.

    uv run --package skills python -m skills.lint [--skills DIR] [--lock FILE]    # exit 1 on any problem

Checks every `<skills>/<name>/SKILL.md`:

- frontmatter and body size: the loader's own checks (`fix_loop.skills._parse`, `MAX_BODY_CHARS`), so the rules live in
  one place. That covers a missing or unclosed frontmatter, an unknown field, a repeated key, a bad `name` or
  `metadata`, and a body over 8,000 characters.
- the directory holds `SKILL.md` and nothing else (v1 has no scripts or resource files; spec notes section 2).
- the lock file (`skills.lock.json`, spec notes section 4): each skill has an entry whose `sha256` is 64 lowercase hex
  characters and equals the hash of the file (CRLF to LF, then SHA-256), and no entry names a skill that is gone.

Each line printed names the skill and one of the loader's typed reasons (`fix_loop.skills.Reason`).

ponytail: the hash and lock checks are the lint's own, because `fix_loop.skills.trust_refusal` is empty until P5.5-T10.
When T10 lands, call its lock reader and hash function here instead of `_hash` and `_lock_problems`, and add the
review-flag checks the spec lists for the lint (`argus-status` against the lock's `reviewed`, `argus-archetype` when
reviewed, `argus-sources` against the held-out ids). Not checked today: those three.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from fix_loop.skills import MAX_BODY_CHARS, Reason, Refusal, _parse

PACKAGE = Path(__file__).resolve().parents[2]
SKILLS = PACKAGE / "skills"
LOCK = PACKAGE / "skills.lock.json"
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def lint(skills: Path, lock: Path) -> list[str]:
    """Every problem found, one line each as `<skill>: <reason>: <detail>`. Empty means clean."""
    folders = sorted(p for p in skills.iterdir() if p.is_dir() and not p.name.startswith(".")) if skills.is_dir() else []
    problems: list[str] = []
    entries, lock_note = _read_lock(lock) if folders or lock.is_file() else ({}, None)
    if lock_note:
        problems.append(f"skills.lock.json: {Reason.not_pinned.value}: {lock_note}")
    for folder in folders:
        problems += [f"{folder.name}: {reason.value}: {detail}" for reason, detail in _skill_problems(folder, entries)]
    problems += [
        f"{name}: {Reason.not_pinned.value}: the lock has an entry but no skill directory"
        for name in sorted(set(entries) - {f.name for f in folders})
    ]
    return problems


def _read_lock(lock: Path) -> tuple[dict, str | None]:
    try:
        doc = json.loads(lock.read_text(encoding="utf-8"))
        entries = doc["skills"]
        if not isinstance(entries, dict):
            raise TypeError
    except FileNotFoundError:
        return {}, "the lock file is missing"
    except (ValueError, KeyError, TypeError):
        return {}, 'the lock file is not JSON of the form {"version": 1, "skills": {...}}'
    return entries, None


def _skill_problems(folder: Path, entries: dict) -> list[tuple[Reason, str]]:
    found: list[tuple[Reason, str]] = []
    extra = sorted(p.name for p in folder.iterdir() if p.name != "SKILL.md")
    if extra:
        found.append((Reason.bad_frontmatter, "files other than SKILL.md: " + ", ".join(extra)))
    file = folder / "SKILL.md"
    if not file.is_file():
        return [*found, (Reason.bad_frontmatter, "no SKILL.md")]
    raw = file.read_bytes()
    parsed = _parse(folder.name, raw)
    if isinstance(parsed, Refusal):
        found.append((parsed.reason, parsed.detail))
    elif len(parsed[1]) > MAX_BODY_CHARS:
        found.append((Reason.too_large, f"body is {len(parsed[1])} characters, the limit is {MAX_BODY_CHARS}"))
    entry = entries.get(folder.name)
    pin = entry.get("sha256") if isinstance(entry, dict) else None
    if entry is None:
        found.append((Reason.not_pinned, "no entry in the lock file"))
    elif not isinstance(pin, str) or not _SHA256.fullmatch(pin):
        found.append((Reason.not_pinned, "the lock entry has no sha256 of 64 lowercase hex characters"))
    elif pin != _hash(raw):
        found.append((Reason.hash_mismatch, f"SKILL.md hashes to {_hash(raw)}, the lock has {pin}"))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skills.lint")
    parser.add_argument("--skills", type=Path, default=SKILLS)
    parser.add_argument("--lock", type=Path, default=LOCK)
    args = parser.parse_args(argv)
    problems = lint(args.skills, args.lock)
    for line in problems:
        print(line, file=sys.stderr)
    count = len(list(args.skills.iterdir())) if args.skills.is_dir() else 0
    print(f"{len(problems)} problem(s)" if problems else f"skills clean ({count} checked)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
