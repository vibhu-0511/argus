"""A small stateful stand-in for the GitHub REST calls the write client makes, served by an httpx MockTransport.

It keeps a repo `acme/shop` with a default branch `main` (one commit holding `FILES`), git data
(trees, commits, refs), pull requests, issue comments and labels, and answers like GitHub does where
the client relies on it: 404 for a missing ref or file, 422 for a second PR with the same head, a
null tree sha deleting a path, `draft` flipped only by the GraphQL mutation. Knobs for failure:

- `fail[(method, path)] = status` answers that call with the status (and a message that echoes `leak`);
- `graphql_error = "text"` makes the GraphQL call answer 200 with an `errors` list, as GraphQL does;
- `labels_vanish = True` makes a label DELETE answer 404 (someone else removed it first);
- `stale_pull_lists = n` makes the next n `GET /pulls` answer `[]` as if the PR was not visible yet.

`log` holds `"METHOD /path"` for every request, `count(prefix)` counts them.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

REPO = "acme/shop"
FILES = {"src/a.py": "x = 1\n", "README.md": "# shop\n"}
PATCH = """diff --git a/src/a.py b/src/a.py
index 111..222 100644
--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-x = 1
+x = 2
diff --git a/docs/new.md b/docs/new.md
new file mode 100644
index 0000000..333
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1,2 @@
+hello
+world
"""
NEW_FILES = {"src/a.py": "x = 2\n", "docs/new.md": "hello\nworld\n", "README.md": "# shop\n"}


class FakeGitHubApi:
    def __init__(self, leak: str = "") -> None:
        self.leak = leak
        self.log: list[str] = []
        self.requests: list[httpx.Request] = []
        self.fail: dict[tuple[str, str], int] = {}
        self.stale_pull_lists = 0
        self.graphql_error = ""
        self.labels_vanish = False
        self.trees: dict[str, dict[str, str]] = {"t0": dict(FILES)}
        self.commits: dict[str, dict[str, Any]] = {"c0": {"message": "init", "tree": {"sha": "t0"}, "parents": []}}
        self.refs: dict[str, str] = {"main": "c0"}
        self.pulls: list[dict[str, Any]] = []
        self.comments: list[dict[str, Any]] = []
        self.labels: list[str] = []
        self.modes: dict[str, str] = {}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def count(self, prefix: str) -> int:
        return sum(line.startswith(prefix) for line in self.log)

    def files_at(self, branch: str) -> dict[str, str]:
        return self.trees[self.commits[self.refs[branch]]["tree"]["sha"]]

    def add_pr(self, branch: str, *, draft: bool = True, state: str = "open") -> dict[str, Any]:
        n = len(self.pulls) + 1
        pr = {"number": n, "html_url": f"https://github.test/{REPO}/pull/{n}", "node_id": f"PR_{n}", "draft": draft, "state": state, "head": {"ref": branch}}
        self.pulls.append(pr)
        return pr

    # -- the server ------------------------------------------------------------------------

    def handle(self, req: httpx.Request) -> httpx.Response:
        method, path = req.method, req.url.path
        self.log.append(f"{method} {path}")
        self.requests.append(req)
        if (method, path) in self.fail:
            return self._json({"message": f"boom {self.leak}"}, self.fail[(method, path)])
        body = json.loads(req.content) if req.content and method != "GET" else {}
        base = f"/repos/{REPO}"
        if (method, path) == ("GET", base):
            return self._json({"default_branch": "main"})
        if m := re.fullmatch(base + r"/git/ref/heads/(.+)", path):
            sha = self.refs.get(m[1])
            return self._json({"object": {"sha": sha}}) if sha else self._json({"message": "Not Found"}, 404)
        if m := re.fullmatch(base + r"/git/commits/(\w+)", path):
            return self._json(self.commits[m[1]])
        if m := re.fullmatch(base + r"/contents/(.+)", path):
            tree = self.trees[self.commits[req.url.params["ref"]]["tree"]["sha"]]
            text = tree.get(m[1])
            return httpx.Response(200, content=text.encode()) if text is not None else self._json({"message": "Not Found"}, 404)
        if (method, path) == ("POST", base + "/git/trees"):
            tree = dict(self.trees[body["base_tree"]])
            for e in body["tree"]:
                if e.get("sha", 1) is None:
                    tree.pop(e["path"], None)
                else:
                    tree[e["path"]] = e["content"]
                    self.modes[e["path"]] = e["mode"]
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
        if m := re.fullmatch(base + r"/git/refs/heads/(.+)", path) and method == "PATCH":
            branch = path.removeprefix(base + "/git/refs/heads/")
            if body.get("force") or branch not in self.refs or self.commits[body["sha"]]["parents"] != [self.refs[branch]]:
                return self._json({"message": "Update is not a fast forward"}, 422)
            self.refs[branch] = body["sha"]
            return self._json({})
        if (method, path) == ("GET", base + "/pulls"):
            head = req.url.params["head"]
            assert head.startswith("acme:") and req.url.params["state"] == "all"
            if self.stale_pull_lists:
                self.stale_pull_lists -= 1
                return self._json([])
            return self._json([p for p in self.pulls if p["head"]["ref"] == head.removeprefix("acme:")])
        if (method, path) == ("POST", base + "/pulls"):
            if any(p["head"]["ref"] == body["head"] for p in self.pulls):
                return self._json({"message": "Validation Failed", "errors": [{"message": "A pull request already exists"}]}, 422)
            pr = self.add_pr(body["head"], draft=body["draft"])
            pr.update(title=body["title"], body=body["body"], base=body["base"])
            return self._json(pr, 201)
        if m := re.fullmatch(base + r"/pulls/(\d+)", path):
            pr = self.pulls[int(m[1]) - 1]
            pr["state"] = body["state"]
            return self._json(pr)
        if (method, path) == ("POST", "/graphql"):
            if self.graphql_error:
                return self._json({"errors": [{"message": self.graphql_error}]})
            pr = next(p for p in self.pulls if p["node_id"] == body["variables"]["id"])
            pr["draft"] = False
            return self._json({"data": {"markPullRequestReadyForReview": {"pullRequest": {"isDraft": False}}}})
        if m := re.fullmatch(base + r"/issues/\d+/comments", path):
            if method == "GET":
                return self._page(self.comments, req)
            self.comments.append({"body": body["body"]})
            return self._json({}, 201)
        if m := re.fullmatch(base + r"/issues/\d+/labels", path):
            if method == "GET":
                return self._page([{"name": n} for n in self.labels], req)
            self.labels += [n for n in body["labels"] if n not in self.labels]
            return self._json([{"name": n} for n in self.labels])
        if m := re.fullmatch(base + r"/issues/\d+/labels/(.+)", path) and method == "DELETE":
            name = req.url.raw_path.decode().rsplit("/labels/", 1)[1].replace("%3A", ":")
            if self.labels_vanish or name not in self.labels:
                return self._json({"message": "Label does not exist"}, 404)
            self.labels.remove(name)
            return self._json([])
        raise AssertionError(f"the fake GitHub has no route for {method} {path}")

    @staticmethod
    def _json(data: Any, status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=data)

    def _page(self, items: list[Any], req: httpx.Request) -> httpx.Response:
        page, size = int(req.url.params["page"]), int(req.url.params["per_page"])
        return self._json(items[(page - 1) * size : page * size])
