"""P7-T20 real-run script, tested against a mock GitHub (no network, no App, no key). The real answer is NOT shown here."""

from __future__ import annotations

import json

import httpx
import pytest
from flow.app_push_check import run_check

REPO, OTHER, TOKEN = "acme/scratch", "acme/private-other", "ghs_FAKE_0000000000_fake-token-not-a-secret"


def mock_github(protect_status: int | None, installed=(REPO,)):
    """protect_status: 403 or 422 when the default branch is protected, None when it is not."""
    state = {"main": "c0", "refs": set(), "moved": False}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        path, method = request.url.path, request.method
        body = json.loads(request.content) if request.content else {}
        if path == "/installation/repositories":
            return httpx.Response(200, json={"repositories": [{"full_name": n} for n in installed]})
        if path.startswith(f"/repos/{OTHER}"):
            return httpx.Response(404, json={"message": "Not Found"})
        if path == f"/repos/{REPO}/git/ref/heads/main":
            return httpx.Response(200, json={"object": {"sha": state["main"]}})
        if path == f"/repos/{REPO}/git/commits/c0":
            return httpx.Response(200, json={"tree": {"sha": "t0"}})
        if path == f"/repos/{REPO}/git/commits" and method == "POST":
            assert body["parents"] == ["c0"] and body["tree"] == "t0"
            return httpx.Response(201, json={"sha": "c1"})
        if path == f"/repos/{REPO}/git/refs/heads/main" and method == "PATCH":
            assert body["force"] is False  # never a force update
            if protect_status:
                return httpx.Response(protect_status, json={"message": "Protected branch update failed for refs/heads/main."})
            state["main"], state["moved"] = body["sha"], True
            return httpx.Response(200, json={})
        if path == f"/repos/{REPO}/git/refs" and method == "POST":
            state["refs"].add(body["ref"])
            return httpx.Response(201, json={})
        if path.startswith(f"/repos/{REPO}/git/refs/heads/argus-p7-t20-probe-") and method == "DELETE":
            state["refs"].discard("refs/heads/" + path.rsplit("/", 1)[1])
            return httpx.Response(204)
        return httpx.Response(500, json={"message": f"unmodelled {method} {path}"})

    return httpx.MockTransport(handler), state


@pytest.mark.parametrize("status", [403, 422])
def test_protected_default_branch_is_refused_and_the_probe_branch_is_cleaned_up(status):
    transport, state = mock_github(status)
    result = run_check(TOKEN, REPO, OTHER, "main", transport=transport)
    assert result["verdict"].startswith("as expected")
    steps = {s["step"]: s for s in result["steps"]}
    assert steps["move the default branch (non-force)"]["status"] == status
    assert steps["write on another repository"]["status"] == 404
    assert steps["control: create a probe branch"]["status"] == 201 and steps["control: delete the probe branch"]["status"] == 204
    assert state["main"] == "c0" and not state["refs"]  # main did not move and the probe branch is gone
    assert TOKEN not in json.dumps(result)


def test_an_unprotected_default_branch_is_reported_loudly():
    transport, state = mock_github(None)
    result = run_check(TOKEN, REPO, OTHER, "main", transport=transport)
    assert result["verdict"].startswith("NOT PROTECTED") and state["moved"]


def test_more_than_one_visible_repository_is_flagged():
    transport, _ = mock_github(403, installed=(REPO, "acme/other-installed"))
    result = run_check(TOKEN, REPO, OTHER, "main", transport=transport)
    assert result["steps"][0]["as_expected"] is False and result["steps"][0]["repositories"] == [REPO, "acme/other-installed"]


def test_a_token_that_reaches_the_other_repository_is_not_called_as_expected():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith(f"/repos/{OTHER}"):
            return httpx.Response(422, json={"message": "Object does not exist"})  # the write got through to validation
        return mock_github(403)[0].handle_request(request)

    result = run_check(TOKEN, REPO, OTHER, "main", transport=httpx.MockTransport(handler))
    assert result["verdict"] == "unexpected: read the steps"
    assert not {s["step"]: s for s in result["steps"]}["write on another repository"]["as_expected"]


def test_it_stops_when_the_branch_cannot_be_read():
    transport = httpx.MockTransport(lambda r: httpx.Response(404, json={"message": "Not Found"}) if "/git/ref/" in r.url.path
                                    else httpx.Response(200, json={"repositories": [{"full_name": REPO}]}))
    result = run_check(TOKEN, REPO, OTHER, "main", transport=transport)
    assert result["verdict"].startswith("stopped") and len(result["steps"]) == 2


def test_the_script_refuses_to_write_without_the_throwaway_confirmation(capsys):
    from flow.app_push_check import main

    with pytest.raises(SystemExit) as seen:
        main(["--repo", REPO, "--other-repo", OTHER])
    assert seen.value.code == 2 and "--throwaway-repo" in capsys.readouterr().err
