"""P10-T02: `serve` binds 127.0.0.1 and there is no way to ask for another host. uvicorn.run is replaced; nothing listens."""

import pytest

from argus_workbench import cli, server


@pytest.fixture
def run_calls(monkeypatch):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.append((app, kw)))
    return calls


def test_serve_passes_host_127_0_0_1_to_uvicorn(run_calls):
    assert cli.main(["serve"]) == 0
    (app, kw), = run_calls
    assert kw["host"] == "127.0.0.1" and kw["port"] == cli.DEFAULT_PORT
    assert app.title == "argus-workbench"


def test_serve_port_is_passed_and_host_stays_loopback(run_calls):
    cli.main(["serve", "--port", "9123"])
    assert run_calls[0][1]["host"] == "127.0.0.1" and run_calls[0][1]["port"] == 9123


@pytest.mark.parametrize("argv", [
    ["serve", "--host", "0.0.0.0"], ["serve", "--host=0.0.0.0"], ["serve", "--host", "127.0.0.1"], ["--host", "0.0.0.0", "serve"],
    ["serve", "--bind", "0.0.0.0"], ["serve", "--bind=0.0.0.0:8000"], ["serve", "-H", "0.0.0.0"],
])
def test_host_option_is_rejected(run_calls, argv, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2 and run_calls == []
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize("port", ["-1", "65536", "abc", "", "1.5"])
def test_bad_port_is_rejected(run_calls, port):
    with pytest.raises(SystemExit) as exc:
        cli.main(["serve", "--port", port])
    assert exc.value.code == 2 and run_calls == []


def test_no_option_anywhere_can_set_a_host():
    options = {opt for action in cli.build_parser()._subparsers._group_actions[0].choices["serve"]._actions for opt in action.option_strings}
    assert options == {"-h", "--help", "--port"}


def test_abbreviated_host_option_is_not_accepted(run_calls):
    with pytest.raises(SystemExit):
        cli.main(["serve", "--ho", "0.0.0.0"])
    assert run_calls == []


def test_only_the_masked_token_is_printed(run_calls, monkeypatch, capsys):
    real = server.create_app
    monkeypatch.setattr(server, "create_app", lambda **kw: real(token="test-token-not-secret", **kw))
    cli.main(["serve"])
    out = capsys.readouterr().out
    assert "test..." in out and "test-token-not-secret" not in out and "http://127.0.0.1:" in out
