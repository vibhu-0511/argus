"""P5.5-T07 skill selection test: does the catalog (names and descriptions only) make a model pick the right skill.

    python -m skills.selection prompts OUT_DIR         write one prompt per ticket: the real catalog text and the ticket, nothing else
    python -m skills.selection score [ANSWERS_JSON]    table of hits and misses from the stored answers

The catalog is `fix_loop.skills.catalog` over the loadable skills in `packages/skills/skills`, the same text the loop puts
in the system message. A model (a fresh Claude Haiku subagent per ticket) answers `{"first_skill", "reason"}` from that text
alone. `strict` counts a hit only for the ticket's `expected` skill; `fits` also counts any skill the ticket text cannot
rule out (the same-ticket pairs and the other plain CSS-value tickets).

ponytail: one answer per ticket, so a hit rate is a count out of 10, not a rate with an interval.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fix_loop.skills import catalog, load_skills

PACKAGE = Path(__file__).resolve().parents[2]
TICKETS = PACKAGE / "selection" / "tickets.json"
ANSWERS = PACKAGE / "selection" / "answers.json"

FRAME = """You are the model in a bug-fixing loop. Below are the skills part of your system message and the ticket.

--- system message (skills part) ---
{catalog}
--- ticket ---
{text}
--- end ---

Answer from this text only. Do not use any tool, do not read any file. Decide which skill, if any, you would load with load_skill before you edit anything.
Reply with one JSON object and nothing else: {{"first_skill": "<the skill name you would load first, or null if none>", "reason": "<one sentence>"}}"""


def tickets(path: Path = TICKETS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["tickets"]


def real_catalog() -> str:
    loaded, refused = load_skills(PACKAGE / "skills")
    if refused:
        raise SystemExit(f"skills refused: {[r.name for r in refused]}")
    return catalog(loaded)


def prompt(ticket: dict, catalog_text: str) -> str:
    return FRAME.format(catalog=catalog_text, text=ticket["text"])


def score(rows: list[dict], answers: dict) -> list[dict]:
    """One result per ticket: the chosen skill (None when the answer is missing or says none) and both verdicts."""
    out = []
    for row in rows:
        chosen = answers.get(row["id"], {}).get("first_skill")
        out.append({"id": row["id"], "expected": row["expected"], "chosen": chosen, "strict": chosen == row["expected"], "fits": chosen in row["fits"]})
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    rows = tickets()
    if len(args) == 2 and args[0] == "prompts":
        out = Path(args[1])
        out.mkdir(parents=True, exist_ok=True)
        text = real_catalog()
        for row in rows:
            (out / f"{row['id']}.txt").write_text(prompt(row, text), encoding="utf-8", newline="\n")
        print(f"wrote {len(rows)} prompts to {out}")
        return 0
    if args and args[0] == "score":
        answers = json.loads(Path(args[1] if len(args) > 1 else ANSWERS).read_text(encoding="utf-8"))["answers"]
        results = score(rows, answers)
        print("| id | expected | chosen | strict | fits |\n|---|---|---|---|---|")
        for r in results:
            print(f"| {r['id']} | {r['expected']} | {r['chosen']} | {'hit' if r['strict'] else 'MISS'} | {'hit' if r['fits'] else 'MISS'} |")
        print(f"strict {sum(r['strict'] for r in results)}/{len(results)}, fits {sum(r['fits'] for r in results)}/{len(results)}")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
