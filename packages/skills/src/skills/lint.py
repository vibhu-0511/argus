"""P5.5-T12 skill lint for CI. No model call, no network.

    uv run --package skills python -m skills.lint [--skills DIR] [--lock FILE]    # exit 1 on any problem

Checks every `<skills>/<name>/SKILL.md`:

- frontmatter and body size: the loader's own checks (`fix_loop.skills._parse`, `MAX_BODY_CHARS`), so the rules live in
  one place. That covers a missing or unclosed frontmatter, an unknown field, a repeated key, a bad `name` or
  `metadata`, and a body over 8,000 characters.
- the directory holds `SKILL.md` and nothing else (v1 has no scripts or resource files; spec notes section 2).
- the trust checks, by calling the loader's own `fix_loop.skills.trust_refusal` (lock read by `lock_skills`, hash by
  `content_hash`): `unreviewed`, `not-pinned`, `hash-mismatch` and `tool-not-allowed` mean exactly what they mean at
  load time (ADR-019, `docs/notes/p5.5-t10.md`). They run only on a skill that passes the format checks, as in the loader.
  Extra: no lock entry may name a skill that is gone, and a missing or unusable lock file fails.

A draft (no reviewed lock entry, `argus-status` not `reviewed`) is `unreviewed` at load time but not a lint failure: it
is the normal state between T05 and T06. A skill whose frontmatter says `argus-status: reviewed` and has no reviewed lock
entry is the disagreement the spec notes (section 4) ask the lint to catch, and fails as `unreviewed`.

Each line printed names the skill and one of the loader's typed reasons (`fix_loop.skills.Reason`).

ponytail: not checked yet: `argus-status: unreviewed` on a skill the lock says is reviewed, `argus-archetype` when
reviewed, `argus-sources` against the held-out ids.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fix_loop.skills import MAX_BODY_CHARS, Reason, Refusal, _parse, lock_skills, trust_refusal

PACKAGE = Path(__file__).resolve().parents[2]
SKILLS = PACKAGE / "skills"
LOCK = PACKAGE / "skills.lock.json"


def lint(skills: Path, lock: Path) -> list[str]:
    """Every problem found, one line each as `<skill>: <reason>: <detail>`. Empty means clean."""
    folders = sorted(p for p in skills.iterdir() if p.is_dir() and not p.name.startswith(".")) if skills.is_dir() else []
    problems: list[str] = []
    entries: dict[str, dict] = {}
    if lock.is_file():
        entries, broken = lock_skills(lock)
        if broken:
            problems.append(f"skills.lock.json: {Reason.unreviewed.value}: the lock file {broken}; no skill is trusted")
    elif folders:
        problems.append(f"skills.lock.json: {Reason.unreviewed.value}: the lock file is missing; no skill is trusted")
    for folder in folders:
        problems += [f"{folder.name}: {reason.value}: {detail}" for reason, detail in _skill_problems(folder, entries)]
    problems += [
        f"{name}: {Reason.not_pinned.value}: the lock has an entry but no skill directory"
        for name in sorted(set(entries) - {f.name for f in folders})
    ]
    return problems


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
        return [*found, (parsed.reason, parsed.detail)]
    fields, body = parsed
    if len(body) > MAX_BODY_CHARS:
        found.append((Reason.too_large, f"body is {len(body)} characters, the limit is {MAX_BODY_CHARS}"))
    trust = trust_refusal(folder.name, raw, fields, entries)
    claims_reviewed = (fields.get("metadata") or {}).get("argus-status") == "reviewed"
    if trust is not None and (trust[0] is not Reason.unreviewed or claims_reviewed):
        found.append(trust)
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
