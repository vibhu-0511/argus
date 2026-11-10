"""P10-T01: `argus-workbench --help` works."""

import subprocess
import sys

import pytest

from argus_workbench import cli


def test_help_exits_zero_and_says_local_only(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "No model is called" in " ".join(capsys.readouterr().out.split())


def test_no_command_prints_help_and_returns_2(capsys):
    assert cli.main([]) == 2
    assert "usage: argus-workbench" in capsys.readouterr().out


def test_module_runs_as_a_process():
    out = subprocess.run([sys.executable, "-m", "argus_workbench.cli", "--help"], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and "argus-workbench" in out.stdout
