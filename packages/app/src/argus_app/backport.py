"""Backport bot: copy a merged Argus fix to a configured branch, and stop safely on a conflict (P8-T10).

    result = backport_merged_pr(pull_request_event, BackportConfig("release-1.x"), github, clone_url=..., token=...)

Input is the `pull_request` webhook payload (action `closed`, `merged` true). Only an Argus fix PR counts
(`flow.review_comment.ticket_of_pr`: title and head branch agree). What happens, in this order:

1. The backport branch is `argus/backport-<pr number>-to-<hash of target>`: one stable name per PR and target. The PR
   of that head is looked up first (any state). Found: `exists`, and not one git command runs. A lookup error
   raises; nothing was cloned, pushed or created.
2. A temporary clone of the repo, on the target branch, with an empty home, no system config, no hooks and no prompts.
   Only the merge commit of the PR is used, and only if it is an ancestor of `origin/<PR base>`: it is a commit that is
   already in the repo's own history. The PR head (a fork, or a branch that was never merged) is never fetched or
   checked out, under the installation token or without it: `Git.run` refuses `refs/pull/...`, the head ref and the
   head sha as arguments.
3. `git cherry-pick -x <sha>` on a new branch (`-m 1` when the commit is a merge commit).
4. Conflict: `git cherry-pick --abort`, then one comment on the merged PR naming the target, the commit and the
   conflicted files (written once; the comment carries a key marker, `flow.github_write.post_comment`). Nothing is
   pushed, no PR is made, no branch is deleted or reset. `conflict`.
5. Clean: push the branch (plain push of a new branch, never forced, no `+` refspec). A failed push stops there:
   `push-failed`, no PR is created, because the branch on the remote is not the one this run made. If the branch is
   already on the remote (an earlier run pushed and then failed to open the PR) and its tree equals this run's, the
   push is skipped and the PR is opened from it; if the trees differ it is stale: `stale-branch`, nothing is done.
6. Open the PR (draft, base = the target branch) and comment on the merged PR with its link. `opened`.

Safety rules, each with a test in `tests/test_backport.py`:

- Every git call is an argument list to `subprocess.run`; there is no shell and no string is built into a command.
- No git subcommand outside `ALLOWED`; no `--force`, `-f`, `--delete`, `-d`, `-D`, `--mirror`, `--prune`, no refspec that
  starts with `+` or `:`; so nothing the bot does can force-push, delete or reset a branch.
- The installation token goes to git only as `http.extraHeader` through the `GIT_CONFIG_*` environment variables, so
  it is in no argument list, no file and (the output is scrubbed) no message. It is used only for `https://` URLs.
- A tenant cannot make the bot run a command on a conflict: `BackportConfig.from_mapping` refuses `conflict_command`
  and the other names for it with `ConflictCommandRefused`, and nothing in this module runs a command the tenant wrote.
  Branch names are checked (`valid_branch`) so a name cannot be read as an option.
- The git environment is a short allow-list (path, temp dir): no secret variable of the service reaches git.

ADR-027 (written separately) says the backport head is a branch the tenant's own workflow may test; this module only
creates that branch and PR.

ponytail: a rebase-merge of several commits has a `merge_commit_sha` that is only the last of them, so only that
commit is picked; a squash or a merge commit is exact. One target branch per call. The PR is always a draft and the
module is not called from the webhook yet (`flow.webhook` has no `pull_request` closed hook); it needs `git` on the
host that runs it, which the Render image does not promise.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from argus_core.redact import redact
from flow.review_comment import ticket_of_pr
from flow.workflow import PullRequest

TARGET_ENV = "ARGUS_BACKPORT_BRANCH"
ALLOWED = frozenset({"clone", "checkout", "cherry-pick", "rev-list", "rev-parse", "merge-base", "cat-file", "diff", "push"})
FORBIDDEN = frozenset({"--force", "-f", "--force-with-lease", "--delete", "-d", "-D", "--mirror", "--prune", "--all"})
COMMAND_FIELDS = frozenset({"conflict_command", "on_conflict", "conflict_cmd", "resolve_command", "command", "script", "hook"})
BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}")
SHA = re.compile(r"[0-9a-f]{40}")
_ENV_KEEP = ("PATH", "Path", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT")
GIT_TIMEOUT = 120
OUTPUT_LIMIT = 300
IDENTITY = ("user.name=argus-app[bot]", "user.email=argus-app[bot]@users.noreply.github.com")


class Refused(RuntimeError):
    """The bot will not do this. Nothing was changed."""


class ConflictCommandRefused(Refused):
    """A tenant tried to give the bot a command to run on a conflict."""


def valid_branch(name: str) -> bool:
    return bool(BRANCH.fullmatch(name)) and ".." not in name and "//" not in name and not name.endswith(("/", ".", ".lock")) and "@{" not in name


@dataclass(frozen=True)
class BackportConfig:
    target_branch: str

    def __post_init__(self) -> None:
        if not valid_branch(self.target_branch):
            raise ValueError("target_branch is not a plain branch name")

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> BackportConfig:
        """Only `target_branch`. A command field is refused by name, any other unknown field by a plain error."""
        commands = sorted(COMMAND_FIELDS & set(data))
        if commands:
            raise ConflictCommandRefused(f"{commands[0]!r} is refused: the bot never runs a command written by a tenant")
        if set(data) != {"target_branch"} or not isinstance(data["target_branch"], str):
            raise ValueError("the backport config is exactly {'target_branch': <branch>}")
        return cls(data["target_branch"])

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> BackportConfig:
        value = (os.environ if env is None else env).get(TARGET_ENV, "")
        if not value:
            raise RuntimeError(f"{TARGET_ENV} is not set")
        return cls(value)


class BackportClient(Protocol):
    def find_pr(self, branch: str) -> PullRequest | None: ...
    def create_draft_pr(self, branch: str, title: str, body: str, base: str | None = None) -> PullRequest: ...
    def post_comment(self, ticket_id: str, key: str, body: str) -> None: ...


@dataclass(frozen=True)
class BackportResult:
    outcome: str  # opened, exists, conflict, push-failed, stale-branch, skipped, failed
    detail: str = ""
    pr: PullRequest | None = None


def backport_branch(pr_number: int, target: str) -> str:
    return f"argus/backport-{pr_number}-to-{hashlib.sha1(target.encode()).hexdigest()[:8]}"


# -- git, as argument lists --------------------------------------------------------------------------------------


def git_env(home: Path, url: str, token: str | None) -> dict[str, str]:
    env = {k: os.environ[k] for k in _ENV_KEEP if k in os.environ}
    env.update(HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    if token and url.startswith("https://"):  # in the environment, not in an argument list
        header = "Authorization: Basic " + base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader", GIT_CONFIG_VALUE_0=header)
    return env


def check_args(args: Sequence[str], keep_away: Sequence[str] = ()) -> None:
    """Raise `Refused` for anything that could force, delete, reset, or touch a PR head."""
    if not args or args[0] not in ALLOWED:
        raise Refused(f"git {args[0] if args else ''!r} is not one of the commands the bot may run")
    for arg in args[1:]:
        if arg in FORBIDDEN or arg.startswith(("+", ":")):
            raise Refused(f"git argument {arg!r} is refused: the bot never forces, deletes or resets")
        if "refs/pull" in arg or arg in keep_away:
            raise Refused(f"git argument {arg!r} is refused: a pull request head is never fetched or checked out")


class Git:
    def __init__(self, exe: str, cwd: Path, env: dict[str, str], hooks: Path, secrets: Sequence[str], keep_away: Sequence[str], runner: Callable) -> None:
        self.exe, self.cwd, self.env, self.hooks, self.keep_away, self.runner = exe, cwd, env, hooks, tuple(keep_away), runner
        self.secrets = tuple(s for s in secrets if s)

    def run(self, *args: str) -> tuple[int, str]:
        """(exit code, scrubbed output). `args` are checked first; the command is an argument list, never a shell string."""
        check_args(args, self.keep_away)
        options = [x for pair in (("-c", v) for v in (*IDENTITY, f"core.hooksPath={self.hooks}", "advice.detachedHead=false", "commit.gpgsign=false")) for x in pair]
        try:
            done = self.runner([self.exe, *options, *args], cwd=self.cwd, env=self.env, capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            return 124, "git timed out"
        return done.returncode, self.clean((done.stdout or "") + (done.stderr or ""))

    def clean(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "***")
        return redact(text).strip()[:OUTPUT_LIMIT]


# -- the bot --------------------------------------------------------------------------------------------------


def _plain(text: str) -> str:
    return " ".join(text.replace("`", "'").split())[:200]


def backport_merged_pr(
    event: Mapping,
    config: BackportConfig,
    github: BackportClient,
    *,
    clone_url: str,
    token: str | None = None,
    git_exe: str = "git",
    runner: Callable = subprocess.run,
) -> BackportResult:
    pr, repo = event.get("pull_request") or {}, (event.get("repository") or {}).get("full_name")
    number, sha = pr.get("number"), pr.get("merge_commit_sha")
    base, head = (pr.get("base") or {}).get("ref"), pr.get("head") or {}
    target = config.target_branch
    if event.get("action") != "closed" or pr.get("merged") is not True:
        return BackportResult("skipped", "not a merged pull request")
    if not (repo and isinstance(number, int) and ticket_of_pr(pr)):
        return BackportResult("skipped", "not an Argus fix PR")
    if not (isinstance(sha, str) and SHA.fullmatch(sha) and isinstance(base, str) and valid_branch(base)):
        return BackportResult("skipped", "the PR has no merge commit on a plain base branch")
    if base == target:
        return BackportResult("skipped", "the PR already targets the backport branch")
    branch = backport_branch(number, target)
    existing = github.find_pr(branch)  # a lookup error raises here: nothing is cloned, pushed or created
    if existing is not None:
        return BackportResult("exists", f"backport PR #{existing.number}", existing)
    key = hashlib.sha1(target.encode()).hexdigest()[:8]
    ticket = f"{repo}#{number}"
    with tempfile.TemporaryDirectory(prefix="argus-backport-", ignore_cleanup_errors=True) as tmp_name:
        tmp = Path(tmp_name)
        (tmp / "home").mkdir()
        (tmp / "hooks").mkdir()  # empty: no hook of the repo can run
        git = Git(git_exe, tmp, git_env(tmp / "home", clone_url, token), tmp / "hooks", [token or "", base64.b64encode(f"x-access-token:{token}".encode()).decode() if token else ""], [head.get("ref") or "", head.get("sha") or ""], runner)
        work = tmp / "work"
        code, out = git.run("clone", "--branch", target, "--", clone_url, str(work))
        if code:
            return BackportResult("failed", f"clone failed: {out}")
        git.cwd = work
        if git.run("cat-file", "-e", f"{sha}^{{commit}}")[0] or git.run("merge-base", "--is-ancestor", sha, f"origin/{base}")[0]:
            raise Refused(f"{sha[:12]} is not in the history of {base}: only a merged commit is backported, never a PR head")
        on_remote = git.run("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}")[0] == 0
        git.run("checkout", "-b", branch)
        merge = len(git.run("rev-list", "--parents", "-n", "1", sha)[1].split()) > 2
        code, out = git.run("cherry-pick", "-x", *(["-m", "1"] if merge else []), sha)
        if code:
            files = [f for f in git.run("diff", "--name-only", "--diff-filter=U")[1].splitlines() if f]
            git.run("cherry-pick", "--abort")
            if not files:
                return BackportResult("failed", f"cherry-pick failed without a conflict: {out}")
            listed = "\n".join(f"- `{_plain(f)}`" for f in files[:20])
            github.post_comment(
                ticket,
                f"argus:{ticket}:backport-conflict-{key}",
                f"Argus could not backport this fix to `{target}`: cherry-picking `{sha[:12]}` conflicts in:\n\n{listed}\n\n"
                f"Nothing was pushed and no branch was changed. To do it by hand: check out `{target}`, run `git cherry-pick -x {sha[:12]}`, and resolve the files above.",
            )
            return BackportResult("conflict", ", ".join(files))
        if on_remote:
            if git.run("diff", "--quiet", f"refs/remotes/origin/{branch}", "HEAD")[0]:
                return BackportResult("stale-branch", f"{branch} is already on the remote with other content; nothing was changed")
        else:
            code, out = git.run("push", "origin", branch)
            if code:
                return BackportResult("push-failed", f"push failed, no PR was created: {out}")
    opened = github.create_draft_pr(
        branch,
        f"Backport #{number} to {target}",
        f"Backport of #{number} (`{sha[:12]}`) to `{target}`, made with `git cherry-pick -x`. Draft: review it like any change to `{target}`.\n",
        base=target,
    )
    github.post_comment(ticket, f"argus:{ticket}:backport-opened-{key}", f"Backport to `{target}` opened: {opened.url}")
    return BackportResult("opened", opened.url, opened)
