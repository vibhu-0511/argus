"""P7-T20 break it: use the App installation token to push to the default branch. MOCK ONLY.

No GitHub App and no repository exist yet, so this runs against the mock GitHub of `test_app_token.py`, which models
branch protection as a 403 or a 422 on the ref update. The real refusal (GitHub's own answer, with protection on) is
NOT shown here. Run with `-s` to see the requests and answers.
"""

from __future__ import annotations

import httpx
import pytest
from flow.app_token import MINIMUM, PROFILES, PolicyError
from flow.github_write import GitHubWriteError
from github_api_fake import PATCH
from test_app_token import REPO_NAME, client_with, keys, minter, api  # noqa: F401  (fixtures)

FORBIDDEN = {"administration", "workflows", "secrets", "environments", "members"}


def _attempt(token: str, api, method: str, path: str, **kw) -> httpx.Response:
    """A raw call with the token, as an attacker who holds it would make."""
    with httpx.Client(transport=api.transport(), base_url="https://api.github.com") as client:
        response = client.request(method, path, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, **kw)
    print(f"  {method} {path} -> {response.status_code} {response.json().get('message', '')}")
    return response


def test_the_token_is_requested_with_the_minimum_list(minter, api):
    token = minter.mint("write")
    body = api.mint_bodies[-1]
    print(f"\nPOST /app/installations/<id>/access_tokens body: {body}")
    print(f"token permissions (as answered): {dict(token.permissions)}")
    assert body == {"permissions": PROFILES["write"], "repositories": [REPO_NAME]}
    assert not FORBIDDEN & set(body["permissions"]) and set(body["permissions"]) <= set(MINIMUM)
    assert body["permissions"]["contents"] == "write"  # the push permission is there; protection, not the token, must stop main


@pytest.mark.parametrize("status", [403, 422])
def test_a_push_to_the_default_branch_is_refused_by_protection(minter, api, status):
    api.protected_status["main"] = status
    token = minter.mint("write").token
    print(f"\n[protection modelled as {status}] the real client, branch=main:")
    with pytest.raises(GitHubWriteError) as seen:
        client_with(token, api).push_branch("main", PATCH, "argus:acme/shop#7:push-branch:1")
    print(f"  GitHubWriteError: {seen.value}")
    assert str(status) in str(seen.value) and "Protected branch update failed" in str(seen.value)
    assert api.refs["main"] == "c0"  # the default branch did not move
    assert token not in str(seen.value)
    print("  raw ref update with the same token, then the control branch:")
    commit = "c1"  # the commit the client created before the refused ref update
    refused = _attempt(token, api, "PATCH", "/repos/acme/shop/git/refs/heads/main", json={"sha": commit, "force": False})
    assert refused.status_code == status and api.refs["main"] == "c0"
    api.refs["argus/acme-shop-7"] = "c0"  # a draft-PR branch exists; the same call on it works
    allowed = _attempt(token, api, "PATCH", "/repos/acme/shop/git/refs/heads/argus/acme-shop-7", json={"sha": commit, "force": False})
    assert allowed.status_code == 200 and api.refs["argus/acme-shop-7"] == commit


def test_control_without_protection_the_same_token_moves_main(minter, api):
    """What the token itself allows. Contents: write covers every branch, so only protection stops this."""
    api.protected_status.clear()
    token = minter.mint("write").token
    print("\n[control: protection off]")
    client_with(token, api).push_branch("main", PATCH, "argus:acme/shop#7:push-branch:1")
    print(f"  main moved: c0 -> {api.refs['main']}")
    assert api.refs["main"] != "c0"


def test_an_over_broad_request_is_refused_before_http(minter, api):
    print()
    for asked in ({"administration": "write"}, {**PROFILES["write"], "workflows": "write"}, {"contents": "admin"}):
        with pytest.raises(PolicyError) as seen:
            minter.mint(asked)
        print(f"  {asked} -> PolicyError: {seen.value}")
    assert api.calls == 0 and api.mint_bodies == []
