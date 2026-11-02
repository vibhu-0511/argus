"""P5-T05: the phase report from results files. No model call, no network."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.__main__ import main
from eval.report import render
from eval.results import Results

EXAMPLE = Path(__file__).resolve().parents[1] / "schemas" / "results.example.json"
EMPTY = """| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase | — | — | — | — | — |
| This phase | — | — | — | — | — |
| Delta | — | — | — | — | — |
"""


def _write(tmp_path: Path, name: str, **change) -> Path:
    r = Results.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    data = r.model_dump(by_alias=True)
    for key, value in change.items():
        data[key] = value
    path = tmp_path / name
    path.write_text(Results.model_validate(data).to_json(), encoding="utf-8")
    return path


def test_none_prints_the_empty_template(capsys):
    assert main(["report"]) == 0
    assert capsys.readouterr().out == EMPTY


def test_two_files_print_previous_this_and_delta(tmp_path: Path, capsys):
    prev = _write(tmp_path, "prev.json", **{"$_equivalent": 1.0})  # example: 1/2 resolved, 2 scored tasks
    this = _write(
        tmp_path,
        "this.json",
        **{
            "$_equivalent": 1.5,
            "resolve_rate": {"successes": 3, "total": 4, "rate": 0.75, "ci_low": 0.3, "ci_high": 0.95},
            "latency_s": {"p50": 100.0, "p95": 200.0, "n": 4},
        },
    )
    assert main(["report", str(prev), str(this)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[2] == "| Previous phase | 50.0% (1/2) | 163,116 | $0.5000 | 115.0 s | 181.3 s |"
    assert lines[3] == "| This phase | 75.0% (3/4) | 163,116 | $0.3750 | 100.0 s | 200.0 s |"
    assert lines[4] == "| Delta | +25.0 pp | +0 (+0.0%) | -$0.1250 (-25.0%) | -15.0 s | +18.7 s |"


def test_one_file_is_this_phase_and_null_dollars_are_a_dash(tmp_path: Path, capsys):
    this = _write(tmp_path, "this.json")  # example has $_equivalent null
    assert main(["report", str(this)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[2] == "| Previous phase | — | — | — | — | — |"
    assert lines[3] == "| This phase | 50.0% (1/2) | 163,116 | — | 115.0 s | 181.3 s |"
    assert lines[4] == "| Delta | — | — | — | — | — |"


def test_a_null_on_one_side_gives_a_dash_delta_for_that_column(tmp_path: Path):
    prev = Results.model_validate_json(_write(tmp_path, "p.json").read_text(encoding="utf-8"))
    this = Results.model_validate_json(_write(tmp_path, "t.json", **{"$_equivalent": 2.0}).read_text(encoding="utf-8"))
    delta = render(prev, this).splitlines()[4]
    assert delta == "| Delta | +0.0 pp | +0 (+0.0%) | — | +0.0 s | +0.0 s |"
