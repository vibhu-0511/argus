"""A small in-memory GitHub for the PR screen (P10-T08): an httpx MockTransport behind the real `HttpGitHubClient`.

    mock = mock_for(root)                          # one per run-store root, alive as long as the process
    client = HttpGitHubClient("mock-token-not-real", MOCK_REPO, transport=mock.transport())

It answers only the calls `flow.github_write` makes to push a branch and to find, create and edit a pull request
(refs, commits, trees, contents, pulls), the same way GitHub does where the client relies on it: 404 for a missing
ref or file, 422 for a second PR with the same head, a fast-forward-only ref update. Nothing leaves the process:
there is no socket, and the URL it hands out ends in `.invalid`, a name that cannot exist.

The base branch is a stand-in. `seed_from_patch` puts the pre-image of every file the patch touches on `main`
(lines the patch does not show are filler), so the patch always applies. That proves the wiring and the
find-before-act rules, not that the patch fits a real repository.

`log` holds "METHOD /path" for every request, so a test can check which calls the mock saw.

ponytail: in-memory per process; a restart forgets the branches and PRs (the run folders keep pr.json).
ponytail: only the routes above exist; any other call answers 404 "the mock has no route", which surfaces as a GitHubWriteError.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from argus_workbench import store

MOCK_OWNER, MOCK_NAME = "mock-owner", "mock-repo"
MOCK_REPO = f"{MOCK_OWNER}/{MOCK_NAME}"
PR_URL = "https://mock-github.invalid/" + MOCK_REPO + "/pull/{number}"
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
_FILLER = "(not shown by the patch)"


def preimages(patch: str) -> dict[str, str]:
    """Path -> text of the file before the patch, rebuilt from the hunks (context and removed lines at their old line numbers)."""
    out: dict[str, list[str]] = {}
    lines = patch.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].startswith("--- a/") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            path = lines[i][6:].split("\t")[0].strip()
            old: list[str] = []
            i += 2
            while i < len(lines) and not lines[i].startswith(("--- ", "diff --git")):
                m = _HUNK.match(lines[i])
                i += 1
                if not m:
                    continue
                start, count = int(m[1]), int(m[2] if m[2] is not None else 1)
                old += [_FILLER] * (start - 1 - len(old))
                taken = 0
                while taken < count and i < len(lines) and not lines[i].startswith("@@"):
                    kind = lines[i][:1] or " "
                    if kind in (" ", "-"):
                        old.append(lines[i][1:])
                        taken += 1
                    i += 1
            out[path] = old
        else:
            i += 1
    return {path: "\n".join(old) + "\n" for path, old in out.items() if old}


class MockGitHub:
    def __init__(self) -> None:
        self.log: list[str] = []
        self.requests: list[httpx.Request] = []
        self.trees: dict[str, dict[str, str]] = {"t0": {}}
        self.commits: dict[str, dict[str, Any]] = {"c0": {"message": "mock base", "tree": {"sha": "t0"}, "parents": []}}
        self.refs: dict[str, str] = {"main": "c0"}
        self.pulls: list[dict[str, Any]] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def count(self, method: str, suffix: str) -> int:
        """How many requests with this method ended in `suffix` (for example ("POST", "/pulls"))."""
        return sum(1 for r in self.requests if r.method == method and r.url.path.endswith(suffix))

    def seed_from_patch(self, patch: str) -> None:
        base = self.trees[self.commits[self.refs["main"]]["tree"]["sha"]]
        for path, text in preimages(patch).items():
            base.setdefault(path, text)

    # -- the server ------------------------------------------------------------------------

    def handle(self, req: httpx.Request) -> httpx.Response:
        method, path = req.method, req.url.path
        self.log.append(f"{method} {path}")
        self.requests.append(req)
        body = json.loads(req.content) if req.content and method != "GET" else {}
        base = f"/repos/{MOCK_REPO}"
        if (method, path) == ("GET", base):
            return self._json({"default_branch": "main"})
        if m := re.fullmatch(base + r"/git/ref/heads/(.+)", path):
            sha = self.refs.get(m[1])
            return self._json({"object": {"sha": sha}}) if sha else self._json({"message": "Not Found"}, 404)
        if m := re.fullmatch(base + r"/git/commits/(\w+)", path):
            return self._json(self.commits[m[1]]) if m[1] in self.commits else self._json({"message": "Not Found"}, 404)
        if m := re.fullmatch(base + r"/contents/(.+)", path):
            tree = self.trees[self.commits[req.url.params["ref"]]["tree"]["sha"]]
            text = tree.get(m[1])
            return httpx.Response(200, content=text.encode()) if text is not None else self._json({"message": "Not Found"}, 404)
        if (method, path) == ("POST", base + "/git/trees"):
            tree = dict(self.trees[body["base_tree"]])
            for entry in body["tree"]:
                if entry.get("sha", 1) is None:
                    tree.pop(entry["path"], None)
                else:
                    tree[entry["path"]] = entry["content"]
            sha = f"t{len(self.trees)}"
            self.trees[sha] = tree
            return self._json({"sha": sha}, 201)
        if (method, path) == ("POST", base + "/git/commits"):
            sha = f"c{len(self.commits)}"
            self.commits[sha] = {"message": body["message"], "tree": {"sha": body["tree"]}, "parents": body["parents"]}
            return self._json({"sha": sha}, 201)
        if (method, path) == ("POST", base + "/git/refs"):
            branch = body["ref"].removeprefix("refs/heads/")
            if branch in self.refs:
                return self._json({"message": "Reference already exists"}, 422)
            self.refs[branch] = body["sha"]
            return self._json({}, 201)
        if method == "PATCH" and path.startswith(base + "/git/refs/heads/"):
            branch = path.removeprefix(base + "/git/refs/heads/")
            if body.get("force") or branch not in self.refs or self.commits[body["sha"]]["parents"] != [self.refs[branch]]:
                return self._json({"message": "Update is not a fast forward"}, 422)
            self.refs[branch] = body["sha"]
            return self._json({})
        if (method, path) == ("GET", base + "/pulls"):
            head = req.url.params["head"].removeprefix(MOCK_OWNER + ":")
            return self._json([p for p in self.pulls if p["head"]["ref"] == head])
        if (method, path) == ("POST", base + "/pulls"):
            if any(p["head"]["ref"] == body["head"] for p in self.pulls):
                return self._json({"message": "Validation Failed"}, 422)
            number = len(self.pulls) + 1
            pr = {"number": number, "html_url": PR_URL.format(number=number), "node_id": f"PR_{number}", "draft": body["draft"],
                  "state": "open", "head": {"ref": body["head"]}, "title": body["title"], "body": body["body"], "base": body["base"]}
            self.pulls.append(pr)
            return self._json(pr, 201)
        if m := re.fullmatch(base + r"/pulls/(\d+)", path):
            pr = self.pulls[int(m[1]) - 1]
            pr.update({k: body[k] for k in ("state", "title", "body") if k in body})
            return self._json(pr)
        return self._json({"message": f"the mock has no route for {method} {path}"}, 404)

    @staticmethod
    def _json(data: Any, status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=data)


_MOCKS: dict[str, MockGitHub] = {}


def mock_for(root: Path | str | None = None) -> MockGitHub:
    """The one mock GitHub of this run store. Two stores (two tests) never share branches or PRs."""
    key = str(store.store_root(root).resolve())
    return _MOCKS.setdefault(key, MockGitHub())
