from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from argus_bench.flake import flake_all

DELAY = "transition-delay: random;"


def test_random_transition_delay_is_quarantined_then_removed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    fixture = tmp_path / "anim-probe"
    fixture.mkdir()
    css = fixture / "route.css"
    css.write_text(f".route {{\n  {DELAY}\n}}\n", encoding="utf-8")
    buggy = tmp_path / "buggy"
    golden = tmp_path / "golden"
    buggy.mkdir()
    golden.mkdir()
    step = 0

    def score(task: Path, tree: Path) -> int:
        nonlocal step
        text = (Path(task) / "route.css").read_text(encoding="utf-8")
        if DELAY in text:
            code = step % 2
            step += 1
            return code
        return 1 if Path(tree) == buggy else 0

    quarantine = tmp_path / "quarantine"
    code = flake_all(
        score,
        tasks=[fixture],
        buggy=buggy,
        golden=golden,
        quarantine=quarantine,
    )
    assert code == 1
    assert capsys.readouterr().out == "anim-probe\n"
    assert (quarantine / "anim-probe").is_dir()
    assert not fixture.exists()

    shutil.move(quarantine / "anim-probe", fixture)
    text = css.read_text(encoding="utf-8")
    css.write_text(
        "".join(line for line in text.splitlines(keepends=True) if DELAY not in line),
        encoding="utf-8",
    )
    fresh = tmp_path / "quarantine-fixed"
    code = flake_all(
        score,
        tasks=[fixture],
        buggy=buggy,
        golden=golden,
        quarantine=fresh,
    )
    assert code == 0
    assert fixture.is_dir()
    assert not fresh.exists()
    assert capsys.readouterr().out == ""
