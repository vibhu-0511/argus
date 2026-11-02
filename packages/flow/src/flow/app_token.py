"""Short-lived, least-privilege GitHub App installation tokens (P7-T04).

The owner creates the App later (`docs/notes/p7-t04-app-permissions.md`). Nothing here needs it to exist:
`AppTokenMinter` takes an injectable httpx transport, and the tests run it against a mock GitHub.

How a token is made, per use, never kept:

1. `app_jwt` signs a JWT (RS256) with the App's private key. `iat` is 60 s in the past (clock drift), `exp` 9
   minutes ahead (GitHub allows 10).
2. `AppTokenMinter.mint` posts it to `POST /app/installations/{id}/access_tokens` with an explicit `permissions`
   map and a `repositories` list of exactly one name. GitHub fixes the token life at one hour; this class keeps
   no token, so the caller mints again when it needs one.
3. `check_policy` runs before any HTTP call and refuses a permission that is not in `PROFILES` (the committed
   minimum), a higher level than the minimum, an empty map (GitHub reads a missing map as "everything the App
   has") and anything but one repository. The answer is checked too: a token that is broader than the request is
   dropped, not returned.

The private key comes from the environment variable `ARGUS_GITHUB_APP_PRIVATE_KEY` (PEM, `\\n` escapes allowed).
It is never in a repr, a log line or an error: errors carry the HTTP status and GitHub's message, run through
`argus_core.redact` with the JWT and the key replaced first.

ponytail: the clients (`github_write`, `github_read`, `actions`) still take a token string from their own env
variable; wiring the minter into the Render service (mint at the start of a workflow step) is not done here, and
nothing shows how the real GitHub answers. The profiles are derived from the code and the GitHub docs, not from a
run against GitHub.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from argus_core.redact import redact

APP_ID_ENV = "ARGUS_GITHUB_APP_ID"
INSTALLATION_ID_ENV = "ARGUS_GITHUB_APP_INSTALLATION_ID"
KEY_ENV = "ARGUS_GITHUB_APP_PRIVATE_KEY"
API_URL = "https://api.github.com"
_JWT_SHAPE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.?[A-Za-z0-9_-]*")  # header.payload.signature, also when cut short
JWT_BACK = 60  # seconds `iat` is set in the past
JWT_LIFETIME = 540  # seconds from now to `exp`; GitHub's limit is 600

# GitHub's permission names. Three uses of the pipeline, each with the least it needs; see
# docs/notes/p7-t04-app-permissions.md for the call behind every line.
PROFILES: dict[str, dict[str, str]] = {
    # flow.github_read: the poller. Only GETs.
    "read": {"metadata": "read", "issues": "read", "pull_requests": "read", "contents": "read", "actions": "read"},
    # flow.github_write: branch, commit, draft PR, comment, label.
    "write": {"metadata": "read", "contents": "write", "pull_requests": "write", "issues": "write"},
    # flow.actions: dispatch the workflow, read its runs and artifacts (write includes read).
    "dispatch": {"metadata": "read", "actions": "write"},
}
LEVELS = {"read": 1, "write": 2}  # "admin" is not a level this module will ever ask for
MINIMUM: dict[str, str] = {}
for _profile in PROFILES.values():
    for _name, _level in _profile.items():
        if LEVELS[_level] > LEVELS.get(MINIMUM.get(_name, ""), 0):
            MINIMUM[_name] = _level


class PolicyError(ValueError):
    """A token request broader than the committed minimum. Raised before any HTTP call."""


class AppTokenError(RuntimeError):
    """The token could not be made or what came back was not acceptable. Never contains the key, the JWT or a token."""


def check_policy(permissions: Mapping[str, str], repositories: Sequence[str]) -> None:
    """Raise `PolicyError` unless `permissions` is within `MINIMUM` and `repositories` is exactly one bare repo name."""
    if len(repositories) != 1 or not repositories[0] or "/" in repositories[0]:
        raise PolicyError("a token is for exactly one repository, given as a bare name (not owner/name)")
    if not permissions:  # an empty or missing map would give the token every permission the App has
        raise PolicyError("an explicit, non-empty permissions map is required")
    for name, level in permissions.items():
        if name not in MINIMUM:
            raise PolicyError(f"permission {name!r} is not in the committed minimum")
        if level not in LEVELS or LEVELS[level] > LEVELS[MINIMUM[name]]:
            raise PolicyError(f"permission {name!r} at level {level!r} is above the committed minimum {MINIMUM[name]!r}")


def _pem(private_key: str) -> str:
    return private_key.replace("\\n", "\n")  # an env var often carries the PEM on one line


def app_jwt(app_id: str, private_key: str, now: float) -> str:
    payload = {"iat": int(now) - JWT_BACK, "exp": int(now) + JWT_LIFETIME, "iss": str(app_id)}
    try:
        return jwt.encode(payload, _pem(private_key), algorithm="RS256")
    except Exception as e:  # the library's message can quote key material: the class name only
        raise AppTokenError(f"cannot sign the App JWT: {type(e).__name__}") from None


@dataclass(frozen=True)
class InstallationToken:
    token: str = field(repr=False)
    expires_at: str
    permissions: Mapping[str, str]

    def __str__(self) -> str:
        return repr(self)


class AppTokenMinter:
    def __init__(
        self,
        app_id: str,
        private_key: str,
        installation_id: str,
        repo: str,
        *,
        transport: httpx.BaseTransport | None = None,
        base_url: str = API_URL,
        timeout: float = 15.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not (app_id and private_key and installation_id):
            raise ValueError("app id, private key and installation id are required")
        if repo.count("/") != 1 or not all(repo.split("/")):
            raise ValueError("repo must be 'owner/name'")
        self._app_id, self._key, self._installation = str(app_id), private_key, str(installation_id)
        self._repo_name = repo.split("/")[1]
        self._clock = clock
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def __repr__(self) -> str:  # the minter holds the private key
        return f"AppTokenMinter(app_id={self._app_id!r}, repo={self._repo_name!r}, key=<set>)"

    @classmethod
    def from_env(cls, repo: str, **kwargs: Any) -> AppTokenMinter:
        values = {name: os.environ.get(name, "") for name in (APP_ID_ENV, INSTALLATION_ID_ENV, KEY_ENV)}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"not set: {', '.join(missing)}")
        return cls(values[APP_ID_ENV], values[KEY_ENV], values[INSTALLATION_ID_ENV], repo, **kwargs)

    def mint(self, profile: str | Mapping[str, str] = "write") -> InstallationToken:
        """A new one-hour token for one repository. `profile` is a name in `PROFILES` or an explicit map."""
        if isinstance(profile, str):
            if profile not in PROFILES:
                raise PolicyError(f"unknown profile {profile!r}, expected one of {sorted(PROFILES)}")
            permissions = dict(PROFILES[profile])
        else:
            permissions = dict(profile)
        repositories = [self._repo_name]
        check_policy(permissions, repositories)  # before the key is touched and before any HTTP call
        signed = app_jwt(self._app_id, self._key, self._clock())
        path = f"/app/installations/{self._installation}/access_tokens"
        failure = ""
        try:
            response = self._client.post(
                path,
                json={"permissions": permissions, "repositories": repositories},
                headers={"Authorization": f"Bearer {signed}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            )
        except httpx.HTTPError as e:
            failure = type(e).__name__
        if failure:  # raised outside the except block so no __context__ keeps the original message
            raise AppTokenError(f"POST {path} failed: {failure}")
        if response.status_code != 201:
            raise AppTokenError(self._clean(f"POST {path} -> {response.status_code} {_message(response)}", signed))
        return self._accept(response, permissions, signed)

    def _accept(self, response: httpx.Response, asked: Mapping[str, str], signed: str) -> InstallationToken:
        try:
            data = response.json()
            token, expires_at = data["token"], data["expires_at"]
            granted = data.get("permissions") or {}
            names = [r["name"] for r in data.get("repositories", [])]
            selection = data.get("repository_selection")
        except (ValueError, KeyError, TypeError, AttributeError):
            raise AppTokenError("the answer is not an installation token") from None
        if not isinstance(token, str) or not token or not isinstance(expires_at, str):
            raise AppTokenError("the answer is not an installation token")
        too_broad = [n for n, level in granted.items() if n not in asked or LEVELS.get(level, 99) > LEVELS[asked[n]]]
        if too_broad or selection != "selected" or names != [self._repo_name]:  # the token is dropped here, unused
            raise AppTokenError(self._clean(f"the token is broader than asked (permissions {too_broad}, selection {selection!r}, repositories {names})", signed))
        return InstallationToken(token, expires_at, dict(granted))

    def _clean(self, text: str, signed: str) -> str:
        text = _JWT_SHAPE.sub("***", text.replace(signed, "***").replace(self._key, "***"))
        return redact(text)[:300]  # cleaned whole, then cut: a cut JWT would not match


def _message(response: httpx.Response) -> str:
    try:
        return str(response.json().get("message", ""))
    except (ValueError, AttributeError):
        return ""
