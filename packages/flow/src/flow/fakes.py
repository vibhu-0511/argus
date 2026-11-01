"""In-memory runners and GitHub client for the workflow tests (P6-T03). No network, no LLM.

They model the rule the real ones must keep: an effect is made once per key, and a repeat call
finds it. `calls` counts every invocation, `runs` / `branches` / `prs` count what really happened,
so a test can tell "the step ran again" from "the effect happened again".
"""

from __future__ import annotations

from flow.workflow import Outcome, PullRequest


class FakeRunner:
    def __init__(self, outcome: Outcome = Outcome(True, "ok")) -> None:
        self.outcome = outcome
        self.calls: list[str] = []  # run_key of every call
        self.runs: dict[str, Outcome] = {}  # run_key -> the one run that was started

    def run(self, ticket_id: str, run_key: str, upstream: str) -> Outcome:
        self.calls.append(run_key)
        return self.runs.setdefault(run_key, self.outcome)


class FakeGitHub:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.branches: dict[str, set[str]] = {}  # branch -> push keys applied
        self.prs: dict[str, PullRequest] = {}  # branch -> PR
        self.bodies: dict[str, tuple[str, str]] = {}  # branch -> (title, body) of the PR
        self.comments: dict[str, str] = {}  # key -> body
        self.labels: dict[str, str] = {}  # ticket -> current argus label state
        self.lookup_error: Exception | None = None

    def push_branch(self, branch: str, patch: str, key: str) -> None:
        self.calls.append("push_branch")
        self.branches.setdefault(branch, set()).add(key)

    def find_pr(self, branch: str) -> PullRequest | None:
        self.calls.append("find_pr")
        if self.lookup_error is not None:
            raise self.lookup_error
        return self.prs.get(branch)

    def create_draft_pr(self, branch: str, title: str, body: str) -> PullRequest:
        self.calls.append("create_draft_pr")
        if branch in self.prs:
            raise RuntimeError("a PR for this head already exists")  # GitHub answers 422
        self.bodies[branch] = (title, body)
        self.prs[branch] = PullRequest(len(self.prs) + 1, f"https://example.test/pr/{branch}", True)
        return self.prs[branch]

    def post_comment(self, ticket_id: str, key: str, body: str) -> None:
        self.calls.append("post_comment")
        self.comments.setdefault(key, body)

    def set_label(self, ticket_id: str, state: str) -> None:
        self.calls.append("set_label")
        self.labels[ticket_id] = state
