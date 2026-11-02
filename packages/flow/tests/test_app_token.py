"""The GitHub App token (P7-T04) against a mock GitHub. No network, no real App, no committed key.

The fake follows the GitHub behaviour the docs describe (docs.github.com/en/rest/apps/apps, create an
installation access token): a JWT signed with the App key, `permissions` and `repositories` narrow the token,
a permission or repository the installation lacks is refused with 422, the token is only good for the repos it
was made for, and a missing permission gives 403 "Resource not accessible by integration". The protected branch
answer (403 or 422) and the 404 for another repo are modelled the same way. This is a model: the real GitHub was
not called, so what it does is not shown here.

Every key and token is made at run time: a throwaway RSA key per test session, a random token of the
`ghs_<APPID>_<JWT>` shape.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import time

import httpx
import jwt
import pytest
from argus_core.redact import redact
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from github_api_fake import NEW_FILES, PATCH, FakeGitHubApi

from flow import app_token
from flow.agent_job import scrub
from flow.app_token import MINIMUM, PROFILES, AppTokenError, AppTokenMinter, PolicyError, app_jwt, check_policy
from flow.github_read import HttpGitHubReader
from flow.github_write import GitHubWriteError, HttpGitHubClient

APP_ID = "123456"
INSTALLATION = "987654"
OWNER, REPO_NAME = "acme", "shop"
REPO = f"{OWNER}/{REPO_NAME}"
APP_GRANT = {"metadata": "read", "contents": "write", "pull_requests": "write", "issues": "write", "actions": "write", "administration": "write", "workflows": "write"}


@pytest.fixture(scope="module")
def keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return private, public


# (method, path pattern) -> the permission GitHub's docs list for the call, and the level it needs
NEEDS = [
    ("POST", r"/repos/[^/]+/[^/]+/git/(refs|trees|commits)", "contents", "write"),
    ("PATCH", r"/repos/[^/]+/[^/]+/git/refs/.+", "contents", "write"),
    ("GET", r"/repos/[^/]+/[^/]+/(git|contents)/.+", "contents", "read"),
    ("POST", r"/repos/[^/]+/[^/]+/pulls", "pull_requests", "write"),
    ("PATCH", r"/repos/[^/]+/[^/]+/pulls/\d+", "pull_requests", "write"),
    ("GET", r"/repos/[^/]+/[^/]+/pulls", "pull_requests", "read"),
    ("POST", r"/repos/[^/]+/[^/]+/issues/\d+/(comments|labels)", "issues", "write"),
    ("DELETE", r"/repos/[^/]+/[^/]+/issues/\d+/labels/.+", "issues", "write"),
    ("GET", r"/repos/[^/]+/[^/]+/issues.*", "issues", "read"),
    ("POST", r"/repos/[^/]+/[^/]+/actions/workflows/.+/dispatches", "actions", "write"),
    ("GET", r"/repos/[^/]+/[^/]+/actions/.+", "actions", "read"),
    ("GET", r"/repos/[^/]+/[^/]+", "metadata", "read"),
]
LEVEL = {"read": 1, "write": 2}


class AppGitHub(FakeGitHubApi):
    """The repo `acme/shop` from `github_api_fake`, plus the App endpoint, token scoping and branch protection."""

    def __init__(self, public_key: str, *, installed=(REPO_NAME,), extra_grant: dict[str, str] | None = None, app_grant: dict[str, str] | None = None) -> None:
        super().__init__()
        self.public_key, self.installed, self.extra_grant, self.app_grant = public_key, installed, extra_grant or {}, app_grant or APP_GRANT
        self.tokens: dict[str, dict] = {}  # token -> {"permissions": ..., "repositories": [...]}
        self.protected_status = {"main": 422}  # branch -> the status a write to its ref gets
        self.mint_bodies: list[dict] = []
        self.calls = 0  # every request that reached the server

    def handle(self, req: httpx.Request) -> httpx.Response:
        self.calls += 1
        auth = req.headers.get("authorization", "")
        bearer = auth.removeprefix("Bearer ")
        if req.url.path == f"/app/installations/{INSTALLATION}/access_tokens":
            return self._mint(req, bearer)
        grant = self.tokens.get(bearer)
        if grant is None:
            return self._json({"message": f"Bad credentials {auth}"}, 401)  # adversarial: echoes the header
        repo_path = re.match(r"/repos/([^/]+/[^/]+)", req.url.path)
        if repo_path and repo_path[1].split("/")[1] not in grant["repositories"]:
            return self._json({"message": "Not Found"}, 404)  # GitHub answers 404 for a repo the token cannot see
        for method, pattern, name, level in NEEDS:
            if req.method == method and re.fullmatch(pattern, req.url.path):
                if LEVEL.get(grant["permissions"].get(name, ""), 0) < LEVEL[level]:
                    return self._json({"message": "Resource not accessible by integration"}, 403)
                break
        branch = re.fullmatch(r"/repos/[^/]+/[^/]+/git/refs/heads/(.+)", req.url.path)
        if req.method == "PATCH" and branch and branch[1] in self.protected_status:
            return self._json({"message": f"Protected branch update failed for refs/heads/{branch[1]}."}, self.protected_status[branch[1]])
        return super().handle(req)

    def _mint(self, req: httpx.Request, signed: str) -> httpx.Response:
        try:
            claims = jwt.decode(signed, self.public_key, algorithms=["RS256"], options={"require": ["exp", "iat", "iss"]})
        except jwt.PyJWTError:
            return self._json({"message": f"A JSON web token could not be decoded {signed}"}, 401)
        assert claims["iss"] == APP_ID
        assert claims["exp"] - claims["iat"] <= 600 + 60  # GitHub: exp at most 10 minutes ahead; iat 60 s back
        body = json.loads(req.content)
        self.mint_bodies.append(body)
        wanted = body.get("permissions") or self.app_grant  # no map: everything the App has (the docs)
        repos = body.get("repositories") or list(self.installed)
        if any(r not in self.installed for r in repos):
            return self._json({"message": "Validation Failed"}, 422)
        if any(n not in self.app_grant or LEVEL[lv] > LEVEL[self.app_grant[n]] for n, lv in wanted.items()):
            return self._json({"message": "The permissions requested are not granted to this installation."}, 422)
        token = f"ghs_{APP_ID}_" + secrets.token_urlsafe(48) + "." + secrets.token_urlsafe(30)  # the new stateless shape
        permissions = {**wanted, **self.extra_grant}
        self.tokens[token] = {"permissions": permissions, "repositories": repos}
        return self._json(
            {"token": token, "expires_at": "2099-01-01T00:00:00Z", "permissions": permissions, "repository_selection": "selected", "repositories": [{"name": r} for r in repos]},
            201,
        )


@pytest.fixture
def api(keys):
    return AppGitHub(keys[1])


@pytest.fixture
def minter(keys, api):
    return AppTokenMinter(APP_ID, keys[0], INSTALLATION, REPO, transport=api.transport())


def client_with(token: str, api: AppGitHub, repo: str = REPO) -> HttpGitHubClient:
    return HttpGitHubClient(token, repo, transport=api.transport())


# -- the committed minimum --------------------------------------------------------------------------


def test_the_minimum_is_the_five_permissions_the_code_needs():
    assert MINIMUM == {"metadata": "read", "contents": "write", "pull_requests": "write", "issues": "write", "actions": "write"}
    assert PROFILES["dispatch"] == {"metadata": "read", "actions": "write"}
    for name in PROFILES.values():
        check_policy(name, ["shop"])  # every profile passes its own policy


@pytest.mark.parametrize("name", ["read", "write", "dispatch"])
def test_a_profile_token_is_made_for_one_repo_with_the_explicit_map(minter, api, name):
    token = minter.mint(name)
    assert api.mint_bodies == [{"permissions": PROFILES[name], "repositories": [REPO_NAME]}]
    assert token.permissions == PROFILES[name]
    assert token.token.startswith(f"ghs_{APP_ID}_")


def test_the_jwt_is_rs256_signed_and_short(keys):
    signed = app_jwt(APP_ID, keys[0], now=1_000_000)
    assert jwt.get_unverified_header(signed)["alg"] == "RS256"
    claims = jwt.decode(signed, keys[1], algorithms=["RS256"], options={"verify_exp": False, "verify_iat": False})
    assert (claims["iss"], claims["iat"], claims["exp"]) == (APP_ID, 1_000_000 - 60, 1_000_000 + 540)


def test_the_key_may_come_with_escaped_newlines(keys):
    one_line = keys[0].strip().replace("\n", "\\n")
    assert jwt.get_unverified_header(app_jwt(APP_ID, one_line, now=1_000_000))["alg"] == "RS256"


# -- an over-broad request is refused before any HTTP call -------------------------------------------


@pytest.mark.parametrize(
    "asked",
    [
        {"administration": "write"},
        {"workflows": "write"},
        {"secrets": "write"},
        {"members": "read"},  # an organization permission
        {"contents": "admin"},
        {"actions": "write", "contents": "write", "issues": "write", "pull_requests": "write", "metadata": "read", "environments": "write"},
        {"issues": "owner"},
        {},
    ],
)
def test_a_broader_permission_map_is_refused_before_any_call(minter, api, asked):
    with pytest.raises(PolicyError):
        minter.mint(asked)
    assert api.calls == 0


def test_a_narrower_custom_map_is_fine(minter, api):
    minter.mint({"metadata": "read", "contents": "read"})
    assert api.mint_bodies[0]["permissions"] == {"metadata": "read", "contents": "read"}


@pytest.mark.parametrize("repositories", [[], ["shop", "other"], [f"{OWNER}/{REPO_NAME}"], [""]])
def test_more_or_other_than_one_bare_repository_is_refused(repositories):
    with pytest.raises(PolicyError):
        check_policy(PROFILES["write"], repositories)


def test_an_unknown_profile_is_refused(minter, api):
    with pytest.raises(PolicyError):
        minter.mint("admin")
    assert api.calls == 0


def test_the_mock_would_have_given_a_broader_token_if_the_policy_were_not_there(keys, api):
    """The check is ours: with no `permissions` map the (modelled) GitHub gives the token all the App has."""
    signed = app_jwt(APP_ID, keys[0], now=time.time())
    response = httpx.Client(transport=api.transport(), base_url="https://api.github.com").post(
        f"/app/installations/{INSTALLATION}/access_tokens", json={}, headers={"Authorization": f"Bearer {signed}"}
    )
    assert response.json()["permissions"]["administration"] == "write"


# -- what GitHub refuses ---------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [403, 422])
def test_a_push_to_the_protected_default_branch_is_refused(minter, api, status):
    api.protected_status["main"] = status
    client = client_with(minter.mint("write").token, api)
    with pytest.raises(GitHubWriteError, match=str(status)):
        client.push_branch("main", PATCH, "argus:acme/shop#7:push-branch:1")
    assert api.refs["main"] == "c0"  # the default branch did not move


def test_the_same_token_pushes_to_the_one_draft_pr_branch(minter, api):
    client = client_with(minter.mint("write").token, api)
    client.push_branch("argus/acme-shop-7", PATCH, "argus:acme/shop#7:push-branch:1")
    assert api.files_at("argus/acme-shop-7") == NEW_FILES
    pr = client.create_draft_pr("argus/acme-shop-7", "Argus patch", "body")
    assert pr.draft is True


def test_a_call_on_another_repository_is_refused(minter, api):
    client = client_with(minter.mint("write").token, api, repo=f"{OWNER}/other")
    with pytest.raises(GitHubWriteError, match="404"):
        client.push_branch("argus/x", PATCH, "k")
    reader = HttpGitHubReader(minter.mint("read").token, transport=api.transport())
    with pytest.raises(Exception, match="404"):
        reader.read_github_state(f"{OWNER}/other#1")


def test_a_token_cannot_be_made_for_a_repository_the_installation_lacks(keys, api):
    stranger = AppTokenMinter(APP_ID, keys[0], INSTALLATION, f"{OWNER}/other", transport=api.transport())
    with pytest.raises(AppTokenError, match="422"):
        stranger.mint("read")


def test_a_permission_the_app_was_not_given_is_refused_by_github_too(keys):
    narrow = AppGitHub(keys[1], app_grant={"metadata": "read", "issues": "read"})
    with pytest.raises(AppTokenError, match="422"):
        AppTokenMinter(APP_ID, keys[0], INSTALLATION, REPO, transport=narrow.transport()).mint("write")


def test_a_token_only_does_what_its_profile_allows(minter, api):
    dispatch = client_with(minter.mint("dispatch").token, api)
    with pytest.raises(GitHubWriteError, match="403"):
        dispatch.push_branch("argus/x", PATCH, "k")
    read = client_with(minter.mint("read").token, api)
    with pytest.raises(GitHubWriteError, match="403"):
        read.post_comment(f"{REPO}#7", "k", "hi")


def test_a_token_that_is_broader_than_asked_is_dropped(keys):
    greedy = AppGitHub(keys[1], extra_grant={"administration": "write"})
    minter = AppTokenMinter(APP_ID, keys[0], INSTALLATION, REPO, transport=greedy.transport())
    with pytest.raises(AppTokenError, match="broader than asked") as seen:
        minter.mint("write")
    assert all(token not in str(seen.value) for token in greedy.tokens)


# -- no secret in a log, an error or a repr ----------------------------------------------------------------


def test_the_key_the_jwt_and_the_token_stay_out_of_logs_errors_and_reprs(keys, minter, api, caplog):
    caplog.set_level(logging.DEBUG)
    token = minter.mint("write")
    text = [repr(minter), repr(token), str(token)]
    client = client_with(token.token, api)
    api.leak = token.token
    api.fail[("GET", f"/repos/{REPO}")] = 500  # GitHub echoes the token in the message
    with pytest.raises(GitHubWriteError) as write_error:
        client.push_branch("argus/x", PATCH, "k")
    text.append(str(write_error.value))
    # a bad key: the signature is refused and GitHub's 401 message echoes the Authorization header
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong = other.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    with pytest.raises(AppTokenError) as bad:
        AppTokenMinter(APP_ID, wrong, INSTALLATION, REPO, transport=api.transport()).mint("write")
    text.append(str(bad.value))
    with pytest.raises(AppTokenError) as garbage:  # not a key at all
        AppTokenMinter(APP_ID, "not a pem", INSTALLATION, REPO, transport=api.transport()).mint("write")
    text.append(str(garbage.value))
    body = keys[0].split("-----")[2].strip().replace("\n", "")
    everything = "\n".join(text + [r.getMessage() for r in caplog.records])
    assert token.token not in everything and body[:40] not in everything and "eyJ" not in everything
    assert "401" in str(bad.value) and "not a pem" not in str(garbage.value)


def test_the_transport_error_is_reported_by_class_name_only(keys):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect {request.headers['authorization']}")

    minter = AppTokenMinter(APP_ID, keys[0], INSTALLATION, REPO, transport=httpx.MockTransport(boom))
    with pytest.raises(AppTokenError) as seen:
        minter.mint("read")
    assert str(seen.value).endswith("ConnectError") and seen.value.__context__ is None and "Bearer" not in str(seen.value)


def test_the_redactor_and_the_job_scrub_both_mask_the_installation_token_shape(minter):
    token = minter.mint("write").token
    assert "_" in token.split("_", 2)[2] or "." in token  # the shape the old scrub regex missed: ghs_<APPID>_<JWT with . and ->
    for text in (f"push failed for {token}", f"Authorization: token {token} end"):
        assert token not in redact(text, {})
        assert token not in scrub(text, {})
    assert scrub("ordinary text", {}) == "ordinary text"


def test_the_private_key_in_the_environment_is_masked_by_the_job_scrub(keys):
    line = keys[0].strip().split("\n")[1]
    assert scrub(f"oops {line}", {app_token.KEY_ENV: line}) == "oops ***"


def test_from_env_names_what_is_missing_and_never_the_value(monkeypatch, keys):
    for name in (app_token.APP_ID_ENV, app_token.INSTALLATION_ID_ENV, app_token.KEY_ENV):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match=app_token.KEY_ENV):
        AppTokenMinter.from_env(REPO)
    monkeypatch.setenv(app_token.APP_ID_ENV, APP_ID)
    monkeypatch.setenv(app_token.INSTALLATION_ID_ENV, INSTALLATION)
    monkeypatch.setenv(app_token.KEY_ENV, keys[0])
    assert "BEGIN" not in repr(AppTokenMinter.from_env(REPO))
