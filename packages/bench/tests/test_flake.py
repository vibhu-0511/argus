from __future__ import annotations

from pathlib import Path

import pytest

from argus_bench.flake import flake_all


def _layout(tmp_path: Path, name: str) -> tuple[Path, Path, Path, Path]:
    task = tmp_path / name
    task.mkdir()
    return task, tmp_path / "buggy", tmp_path / "golden", tmp_path / "quarantine"


def _score(codes: list[int], calls: list[Path]):
    pending = iter(codes)

    def score(task: Path, tree: Path) -> int:
        calls.append(tree)
        return next(pending)

    return score


def test_stable_pattern_stays(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    task, buggy, golden, quarantine = _layout(tmp_path, "seed-stable")
    calls: list[Path] = []
    code = flake_all(
        _score([1, 1, 1, 1, 1, 0, 0, 0, 0, 0], calls),
        tasks=[task],
        buggy=buggy,
        golden=golden,
        quarantine=quarantine,
    )
    assert code == 0
    assert task.is_dir()
    assert not quarantine.exists()
    assert calls == [buggy] * 5 + [golden] * 5
    assert capsys.readouterr().out == ""


def test_mixed_results_are_quarantined(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    task, buggy, golden, quarantine = _layout(tmp_path, "seed-mix")
    calls: list[Path] = []
    code = flake_all(
        _score([1, 1, 1, 1, 0, 0, 0, 0, 0, 0], calls),
        tasks=[task],
        buggy=buggy,
        golden=golden,
        quarantine=quarantine,
    )
    assert code == 1
    assert not task.exists()
    assert (quarantine / "seed-mix").is_dir()
    assert calls == [buggy] * 5 + [golden] * 5
    assert capsys.readouterr().out == "seed-mix\n"


def test_five_infra_exits_are_quarantined(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    task, buggy, golden, quarantine = _layout(tmp_path, "seed-infra")
    calls: list[Path] = []
    code = flake_all(
        _score([2] * 10, calls),
        tasks=[task],
        buggy=buggy,
        golden=golden,
        quarantine=quarantine,
    )
    assert code == 1
    assert not task.exists()
    assert (quarantine / "seed-infra").is_dir()
    assert calls == [buggy] * 5 + [golden] * 5
    assert capsys.readouterr().out == "seed-infra\n"
