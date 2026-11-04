"""The workflow's GitHub write client over the REST API (P6, replaces `UnwiredGitHub`).

`HttpGitHubClient` implements `flow.workflow.GitHubClient`. The token comes from the environment
variable `GITHUB_WRITE_TOKEN` (see `from_env`), goes only into the `Authorization` header, and is never
in a repr, a log line or an error text (`GitHubWriteError` carries the method, path, status and
GitHub's `message` with the token scrubbed). The httpx transport is injectable, so tests use
`httpx.MockTransport` and touch no network. Needs a fine-grained token on the one repository with
Contents, Pull requests and Issues read and write.

Every method finds before it acts, so DBOS repeating a step changes nothing (the T02 effect table):

- `push_branch`: GET the branch ref; its head commit carries `Argus-Key: <key>`: done. Otherwise read
  the touched files at the base (the branch head, or the default branch when the branch is missing),
  apply the diff in memory (`flow.diff_apply`), then tree, commit and ref through the git data API.
  The ref is created or fast-forwarded, never forced.
- `find_pr` / `create_draft_pr`: the PR is found by head `<owner>:<branch>` with `state=all`. A lookup
  error raises, so nothing is created. A 422 on create (the PR appeared between find and create) is
  answered by looking the PR up again and returning it.
- `update_pr` (P8-T09): PATCH title and body of an open PR, skipped when they are unchanged or the PR is closed.
- `ready_pr` / `close_pr`: skipped when the PR is already ready / closed. REST cannot mark a draft
  ready, so `ready_pr` uses the GraphQL mutation `markPullRequestReadyForReview`.
- `post_comment`: lists the issue comments and skips when the hidden marker of the key is there.
- `set_label`: adds `argus:<state>` unless present, then removes other `argus:*` labels (404 ignored).

No text anywhere links a PR to an issue with a closing keyword.

ponytail: one patch is limited by `flow.diff_apply` (text files, no renames) and by the contents API
(files up to 100 MB raw, fine for source). A repeat push finds only a head commit that carries the
key: if someone commits on top of the branch afterwards, a repeat adds the patch again (and fails on
context if it no longer matches). Comments and labels are read from the first 10 pages of 100.
Commits are authored by the token's user.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

from flow.diff_apply import FileChange, PatchError, apply_unified
from flow.states import comment_marker
from flow.workflow import PullRequest

TOKEN_ENV = "GITHUB_WRITE_TOKEN"
API_URL = "https://api.github.com"
LABEL_PREFIX = "argus:"
_MAX_PAGES = 10
_READY = "mutation($id: ID!) { markPullRequestReadyForReview(input: {pullRequestId: $id}) { pullRequest { isDraft } } }"


class GitHubWriteError(RuntimeError):
    """A GitHub call failed or answered something unusable. Never contains the token."""


class HttpGitHubClient:
    def __init__(self, token: str, repo: str, *, transport: httpx.BaseTransport | None = None, base_url: str = API_URL, timeout: float = 30.0) -> None:
        if not token:
            raise ValueError("a GitHub token is required")
        if repo.count("/") != 1 or not all(repo.split("/")):
            raise ValueError("repo must be 'owner/name'")
        self._token, self._repo, self._owner = token, repo, repo.split("/")[0]
        self._base: str | None = None  # the default branch, read on first use
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def __repr__(self) -> str:  # the client holds the token
        return f"HttpGitHubClient(repo={self._repo!r}, token=<set>)"

    @classmethod
    def from_env(cls, repo: str, **kwargs: Any) -> HttpGitHubClient:
        token = os.environ.get(TOKEN_ENV, "")
        if not token:
            raise RuntimeError(f"{TOKEN_ENV} is not set")
        return cls(token, repo, **kwargs)

    # -- plumbing ---------------------------------------------------------------------------

    def _scrub(self, text: str) -> str:
        return text.replace(self._token, "<token>")

    def _call(self, method: str, path: str, *, ok: tuple[int, ...] = (200,), **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as e:  # an HTTP library may echo request headers: the class name only
            raise GitHubWriteError(f"{method} {path} failed: {type(e).__name__}") from None
        if response.status_code not in ok:
            try:
                detail = str(response.json().get("message", ""))[:200]
            except (ValueError, AttributeError):
                detail = ""
            raise GitHubWriteError(self._scrub(f"{method} {path} -> {response.status_code} {detail}".strip()))
        return response

    def _json(self, method: str, path: str, *, ok: tuple[int, ...] = (200,), **kwargs: Any) -> Any:
        return self._call(method, path, ok=ok, **kwargs).json()

    def _repo_path(self, tail: str) -> str:
        return f"/repos/{self._repo}{tail}"

    def _default_branch(self) -> str:
        if self._base is None:
            self._base = self._json("GET", self._repo_path(""))["default_branch"]
        return self._base

    def _issue(self, ticket_id: str) -> str:
        repo, _, number = ticket_id.rpartition("#")
        if repo != self._repo or not number.isdigit():
            raise ValueError(f"ticket id {ticket_id!r} is not {self._repo}#number")
        return self._repo_path(f"/issues/{number}")

    def _ref(self, branch: str) -> str | None:
        response = self._call("GET", self._repo_path(f"/git/ref/heads/{branch}"), ok=(200, 404))
        return response.json()["object"]["sha"] if response.status_code == 200 else None

    def _paged(self, path: str) -> list[Any]:
        items: list[Any] = []
        for page in range(1, _MAX_PAGES + 1):
            got = self._json("GET", path, params={"per_page": 100, "page": page})
            items += got
            if len(got) < 100:
                break
        return items

    # -- branch ----------------------------------------------------------------------------

    def push_branch(self, branch: str, patch: str, key: str) -> None:
        trailer = f"Argus-Key: {key}"
        head = self._ref(branch)
        if head is not None and trailer in self._commit(head)["message"].splitlines():
            return
        base = head or self._ref(self._default_branch())
        if base is None:
            raise GitHubWriteError(f"the default branch {self._default_branch()} has no ref")
        try:
            changes = apply_unified(patch, lambda path: self._read_file(path, base))
        except PatchError as e:
            raise GitHubWriteError(f"cannot apply the patch of {key}: {e}") from None
        tree = self._json(
            "POST",
            self._repo_path("/git/trees"),
            ok=(201,),
            json={"base_tree": self._commit(base)["tree"]["sha"], "tree": [_entry(c) for c in changes]},
        )["sha"]
        commit = self._json(
            "POST",
            self._repo_path("/git/commits"),
            ok=(201,),
            json={"message": f"Argus patch\n\n{trailer}", "tree": tree, "parents": [base]},
        )["sha"]
        if head is None:
            self._call("POST", self._repo_path("/git/refs"), ok=(201,), json={"ref": f"refs/heads/{branch}", "sha": commit})
        else:
            self._call("PATCH", self._repo_path(f"/git/refs/heads/{branch}"), json={"sha": commit, "force": False})

    def _commit(self, sha: str) -> dict[str, Any]:
        return self._json("GET", self._repo_path(f"/git/commits/{sha}"))

    def _read_file(self, path: str, sha: str) -> str | None:
        response = self._call(
            "GET",
            self._repo_path(f"/contents/{quote(path)}"),
            ok=(200, 404),
            params={"ref": sha},
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if response.status_code == 404:
            return None
        try:
            return response.content.decode("utf-8")
        except UnicodeDecodeError:
            raise PatchError(f"{path} is not UTF-8 text") from None

    # -- pull request ----------------------------------------------------------------------

    def _pr_json(self, branch: str) -> dict[str, Any] | None:
        pulls = self._json("GET", self._repo_path("/pulls"), params={"head": f"{self._owner}:{branch}", "state": "all", "per_page": 2})
        return next((p for p in pulls if p["head"]["ref"] == branch), None)

    def find_pr(self, branch: str) -> PullRequest | None:
        pr = self._pr_json(branch)
        return _pr(pr) if pr else None

    def create_draft_pr(self, branch: str, title: str, body: str) -> PullRequest:
        response = self._call(
            "POST",
            self._repo_path("/pulls"),
            ok=(201, 422),
            json={"title": title, "head": branch, "base": self._default_branch(), "body": body, "draft": True},
        )
        if response.status_code == 201:
            return _pr(response.json())
        found = self.find_pr(branch)  # 422: a PR for this head already exists (a racing worker made it)
        if found is None:
            raise GitHubWriteError(self._scrub(f"POST /pulls -> 422 and no PR for {branch}: {response.text[:200]}"))
        return found

    def update_pr(self, branch: str, title: str, body: str) -> PullRequest:
        """Set title and body of the PR of `branch` (P8-T09). Only an open PR is edited: a closed or merged one is left as it is.

        Title and body travel as JSON fields. A PR that already has this title and body is not written again.
        """
        pr = self._need_pr(branch)
        if pr["state"] == "open" and (pr.get("title"), pr.get("body")) != (title, body):
            pr = self._json("PATCH", self._repo_path(f"/pulls/{pr['number']}"), json={"title": title, "body": body})
        return _pr(pr)

    def ready_pr(self, branch: str) -> None:
        pr = self._need_pr(branch)
        if not pr["draft"]:
            return
        result = self._json("POST", "/graphql", json={"query": _READY, "variables": {"id": pr["node_id"]}})
        if result.get("errors"):  # GraphQL answers 200 with an errors list
            raise GitHubWriteError(self._scrub("markPullRequestReadyForReview failed: " + "; ".join(str(e.get("message", "")) for e in result["errors"])[:200]))

    def close_pr(self, branch: str) -> None:
        pr = self._need_pr(branch)
        if pr["state"] != "closed":
            self._call("PATCH", self._repo_path(f"/pulls/{pr['number']}"), json={"state": "closed"})

    def _need_pr(self, branch: str) -> dict[str, Any]:
        pr = self._pr_json(branch)
        if pr is None:
            raise GitHubWriteError(f"no PR for branch {branch}")
        return pr

    # -- issue -----------------------------------------------------------------------------

    def post_comment(self, ticket_id: str, key: str, body: str) -> None:
        issue = self._issue(ticket_id)
        marker = comment_marker(key)
        if any(marker in (c.get("body") or "") for c in self._paged(f"{issue}/comments")):
            return
        self._call("POST", f"{issue}/comments", ok=(201,), json={"body": f"{body}\n\n{marker}"})

    def set_label(self, ticket_id: str, state: str) -> None:
        issue = self._issue(ticket_id)
        want = f"{LABEL_PREFIX}{state}"
        have = {label["name"] for label in self._paged(f"{issue}/labels")}
        if want not in have:
            self._call("POST", f"{issue}/labels", json={"labels": [want]})
        for name in sorted(n for n in have if n.startswith(LABEL_PREFIX) and n != want):
            self._call("DELETE", f"{issue}/labels/{quote(name, safe='')}", ok=(200, 404))


def _pr(p: dict[str, Any]) -> PullRequest:
    return PullRequest(p["number"], p["html_url"], bool(p.get("draft")))


def _entry(c: FileChange) -> dict[str, Any]:
    entry: dict[str, Any] = {"path": c.path, "mode": c.mode, "type": "blob"}
    if c.content is None:
        entry["sha"] = None  # a null sha removes the path from the tree
    else:
        entry["content"] = c.content  # the API makes the blob
    return entry
