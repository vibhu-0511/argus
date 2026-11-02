"""P5.5-T07: the selection ticket set is well formed and the scorer counts hits. No model, no network."""

import json

from skills.selection import ANSWERS, PACKAGE, prompt, real_catalog, score, tickets

REAL = {p.name for p in (PACKAGE / "skills").iterdir() if p.is_dir()}


def test_ten_tickets_cover_the_five_skills_and_two_no_match():
    rows = tickets()
    assert len(rows) == 10 and len({r["id"] for r in rows}) == 10
    assert {r["expected"] for r in rows if r["expected"]} == REAL
    assert sum(r["expected"] is None for r in rows) == 2
    for r in rows:
        assert r["expected"] is None or r["expected"] in r["fits"]
        assert set(r["fits"]) - {None} <= REAL


def test_the_two_same_ticket_pairs_have_identical_text_and_different_skills():
    by_id = {r["id"]: r for r in tickets()}
    for a, b in (("s01", "s02"), ("s03", "s04")):
        assert by_id[a]["text"] == by_id[b]["text"] and by_id[a]["expected"] != by_id[b]["expected"]


def test_prompt_holds_the_real_catalog_and_the_ticket_only():
    row = tickets()[0]
    text = prompt(row, real_catalog())
    assert row["text"] in text and all(f"- {name}: " in text for name in REAL)
    assert "SKILL.md" not in text and "Ticket form" not in text  # no skill body leaks into level 1


def test_score_counts_strict_and_fits():
    rows = [{"id": "a", "expected": "x", "fits": ["x", "y"]}, {"id": "b", "expected": None, "fits": [None]}, {"id": "c", "expected": "x", "fits": ["x"]}]
    out = score(rows, {"a": {"first_skill": "y"}, "b": {"first_skill": None}, "c": {"first_skill": "z"}})
    assert [(r["strict"], r["fits"]) for r in out] == [(False, True), (True, True), (False, False)]


def test_stored_answers_cover_every_ticket():
    answers = json.loads(ANSWERS.read_text(encoding="utf-8"))["answers"]
    assert set(answers) == {r["id"] for r in tickets()}
