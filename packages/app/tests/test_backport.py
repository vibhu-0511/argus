"""P8-T10: the backport bot, with real git on local bare repositories and the stateful fake GitHub. No network, no model.

Every git call of the bot goes through a spy runner that records the argument lists, so the tests can say what the bot
never ran (a force, a delete, a reset, a PR-head fetch). The real GitHub and a real installation token were not used
(docs/notes/p8-t10.md).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from flow.github_write import GitHubWriteError, HttpGitHubClient
from flow.states import branch_name
from test_pr import REPO, FakeGitHubApi

from argus_app.backport import (
    COMMAND_FIELDS,
    BackportConfig,
    ConflictCommandRefused,
    Refused,
    backport_branch,
    backport_merged_pr,
    check_args,
    git_env,
)

TICKET, PR_NUMBER = "acme/shop#7", 12
TOKEN = "installation-token-not-real"
BACKPORT = backport_branch(PR_NUMBER, "release")
FORBIDDEN_WORDS = {"--force", "-f", "--force-with-lease", "--delete", "-d", "-D", "--mirror", "--prune", "reset", "clean", "rebase", "fetch", "pull", "branch"}


def _env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "Path", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "COMSPEC", "PATHEXT")}
    env.update(HOME=str(home), USERPROFILE=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    return env


class Repos:
    """A bare `origin.git` with `main` and `release`, and a working clone to add commits from."""

    def __init__(self, root: Path) -> None:
        self.root, self.home = root, root / "home"
        self.home.mkdir()
        self.origin, self.seed = root / "origin.git", root / "seed"
        self.git(root, "init", "--bare", "-b", "main", str(self.origin))
        self.git(root, "clone", str(self.origin), str(self.seed))
        self.write("a.txt", "one\ntwo\nthree\n")
        self.commit("base")
        self.git(self.seed, "branch", "-M", "main")
        self.git(self.seed, "push", "origin", "main")
        self.git(self.seed, "branch", "release")
        self.git(self.seed, "push", "origin", "release")

    def git(self, cwd: Path, *args: str) -> str:
        done = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.test", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
            cwd=cwd, env=_env(self.home), capture_output=True, text=True, check=True,
        )
        return done.stdout.strip()

    def write(self, name: str, text: str) -> None:
        (self.seed / name).write_text(text, encoding="utf-8", newline="\n")

    def commit(self, message: str) -> str:
        self.git(self.seed, "add", "-A")
        self.git(self.seed, "commit", "-m", message)
        return self.git(self.seed, "rev-parse", "HEAD")

    def on(self, branch: str) -> None:
        self.git(self.seed, "checkout", branch)

    def push(self, *branches: str) -> None:
        self.git(self.seed, "push", "origin", *branches)

    def fix_on_main(self) -> str:
        """A squash-style merged fix: one commit on main that changes line two."""
        self.on("main")
        self.write("a.txt", "one\nTWO\nthree\n")
        sha = self.commit("fix: TWO")
        self.push("main")
        return sha

    def refs(self) -> dict[str, str]:
        out = self.git(self.origin, "for-each-ref", "--format=%(refname) %(objectname)")
        return dict(line.split(" ") for line in out.splitlines())

    def file(self, ref: str, name: str) -> str:
        return self.git(self.origin, "show", f"{ref}:{name}")


class Spy:
    """Records the argument list of every git call; can make one subcommand fail without running it."""

    def __init__(self, fail_on: dict[str, str] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on or {}
        self.dirs: list[Path] = []

    @staticmethod
    def sub(argv: list[str]) -> str:
        rest = argv[1:]
        while rest[0] == "-c":
            rest = rest[2:]
        return rest[0]

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.dirs.append(Path(kwargs["cwd"]))
        assert isinstance(argv, list) and "shell" not in kwargs  # an argument list, never a shell string
        sub = self.sub(argv)
        if sub in self.fail_on:
            return subprocess.CompletedProcess(argv, 1, "", self.fail_on[sub])
        return subprocess.run(argv, **kwargs)

    def subs(self) -> list[str]:
        return [self.sub(c) for c in self.calls]

    def args_of(self, sub: str) -> list[list[str]]:
        return [c for c in self.calls if self.sub(c) == sub]

    def assert_not_destructive(self) -> None:
        for argv in self.calls:
            assert not (set(argv) & FORBIDDEN_WORDS), argv
            assert not any(a.startswith(("+", ":")) for a in argv[1:]), argv
            assert not any("refs/pull" in a for a in argv), argv


def event(sha: str, *, number: int = PR_NUMBER, ticket: str = TICKET, base: str = "main", merged: bool = True, action: str = "closed", title: str | None = None) -> dict:
    return {
        "action": action,
        "repository": {"full_name": REPO},
        "pull_request": {
            "number": number,
            "merged": merged,
            "merge_commit_sha": sha,
            "title": title or f"Argus fix for {ticket}",
            "base": {"ref": base},
            "head": {"ref": branch_name(ticket), "sha": "f" * 40},
        },
    }


@pytest.fixture
def repos(tmp_path):
    return Repos(tmp_path)


@pytest.fixture
def api():
    return FakeGitHubApi()


@pytest.fixture
def github(api):
    return HttpGitHubClient("app-token-not-real", REPO, transport=api.transport())


def run(repos, github, sha, spy=None, *, token=None, **event_args):
    spy = spy or Spy()
    result = backport_merged_pr(
        event(sha, **event_args), BackportConfig("release"), github, clone_url=str(repos.origin), token=token, runner=spy
    )
    spy.assert_not_destructive()
    return result, spy


# -- a merged fix is backported --------------------------------------------------------------------------------


def test_a_merged_fix_opens_a_backport_pr_to_the_configured_branch(repos, api, github):
    sha = repos.fix_on_main()
    result, spy = run(repos, github, sha)
    assert result.outcome == "opened" and result.pr is not None
    assert repos.file(f"refs/heads/{BACKPORT}", "a.txt") == "one\nTWO\nthree"  # the fix is on the new branch
    assert repos.file("refs/heads/release", "a.txt") == "one\ntwo\nthree"  # the release branch itself is not touched
    assert repos.git(repos.origin, "log", "-1", "--format=%B", BACKPORT).count(f"(cherry picked from commit {sha})") == 1
    pr = api.pulls[0]
    assert (pr["head"]["ref"], pr["base"], pr["draft"], pr["title"]) == (BACKPORT, "release", True, "Backport #12 to release")
    assert any("Backport to `release` opened" in c["body"] for c in api.comments)
    assert spy.args_of("push") and all(len(c) for c in spy.calls)


def test_a_merge_commit_is_picked_with_the_first_parent(repos, api, github):
    repos.on("main")
    repos.git(repos.seed, "checkout", "-b", "feat")
    repos.write("c.txt", "new file\n")
    repos.commit("feat: c")
    repos.on("main")
    repos.write("a.txt", "one\ntwo\nthree\nfour\n")  # main moves on, so the merge is a real merge commit
    repos.commit("main moves")
    repos.git(repos.seed, "merge", "--no-ff", "-m", "Merge feat", "feat")
    repos.push("main")
    merge = repos.git(repos.seed, "rev-parse", "HEAD")
    result, spy = run(repos, github, merge)
    assert result.outcome == "opened"
    assert ["-m", "1"] == spy.args_of("cherry-pick")[0][-3:-1]
    assert repos.file(f"refs/heads/{BACKPORT}", "c.txt") == "new file"
    assert repos.file(f"refs/heads/{BACKPORT}", "a.txt") == "one\ntwo\nthree"  # only the feature's change, not the main commit


def test_a_second_run_finds_the_existing_pr_and_runs_no_git(repos, api, github):
    sha = repos.fix_on_main()
    run(repos, github, sha)
    refs, comments = repos.refs(), len(api.comments)
    result, spy = run(repos, github, sha)
    assert result.outcome == "exists" and result.pr.number == 1
    assert spy.calls == [] and len(api.pulls) == 1 and repos.refs() == refs and len(api.comments) == comments


def test_the_temporary_clone_is_removed(repos, github):
    sha = repos.fix_on_main()
    _, spy = run(repos, github, sha)
    assert not spy.dirs[0].exists()


# -- a conflict is reported and nothing else happens -----------------------------------------------------------


def make_conflict(repos) -> str:
    repos.on("release")
    repos.write("a.txt", "one\nzwei\nthree\n")
    repos.commit("release: zwei")
    repos.push("release")
    return repos.fix_on_main()


def test_a_conflict_is_commented_and_nothing_is_changed(repos, api, github):
    sha = make_conflict(repos)
    before = repos.refs()
    result, spy = run(repos, github, sha)
    assert result.outcome == "conflict" and result.detail == "a.txt"
    assert ["cherry-pick", "--abort"] in [c[-2:] for c in spy.args_of("cherry-pick")]
    assert "push" not in spy.subs()
    assert repos.refs() == before  # not one ref moved, none created, none deleted
    assert api.pulls == [] and api.count("POST /repos/acme/shop/pulls") == 0
    assert len(api.comments) == 1
    body = api.comments[0]["body"]
    assert "`release`" in body and "`a.txt`" in body and sha[:12] in body and "Nothing was pushed" in body


def test_a_conflict_is_commented_once_across_runs(repos, api, github):
    sha = make_conflict(repos)
    before = repos.refs()
    for _ in range(3):
        result, spy = run(repos, github, sha)
        assert result.outcome == "conflict" and "push" not in spy.subs()
    assert len(api.comments) == 1 and api.pulls == [] and repos.refs() == before


def test_a_conflict_in_a_file_name_with_backticks_stays_inside_the_comment(repos, api, github):
    repos.on("release")
    repos.write("we`ird.txt", "release\n")
    repos.commit("release adds file")
    repos.push("release")
    repos.on("main")
    repos.write("we`ird.txt", "main\n")
    sha = repos.commit("main adds file")
    repos.push("main")
    result, _ = run(repos, github, sha)
    assert result.outcome == "conflict"
    assert "`we'ird.txt`" in api.comments[0]["body"]


# -- failures that must not turn into a second attempt from a stale branch ------------------------------------------


def test_a_failed_push_creates_no_pr(repos, api, github):
    sha = repos.fix_on_main()
    before = repos.refs()
    result, spy = run(repos, github, sha, Spy(fail_on={"push": f"rejected, token {TOKEN}"}), token=TOKEN)
    assert result.outcome == "push-failed" and TOKEN not in result.detail
    assert api.pulls == [] and api.count("POST /repos/acme/shop/pulls") == 0 and repos.refs() == before
    assert len(spy.args_of("push")) == 1  # no retry


def test_a_stale_branch_on_the_remote_is_left_alone(repos, api, github):
    sha = repos.fix_on_main()
    repos.git(repos.seed, "checkout", "-b", BACKPORT, "release")
    repos.write("other.txt", "someone else's work\n")
    repos.commit("unrelated")
    repos.push(BACKPORT)
    before = repos.refs()
    result, spy = run(repos, github, sha)
    assert result.outcome == "stale-branch"
    assert "push" not in spy.subs() and api.pulls == [] and repos.refs() == before


def test_a_pr_that_failed_after_the_push_is_opened_from_the_same_branch_without_a_second_push(repos, api, github):
    sha = repos.fix_on_main()
    api.fail[("POST", f"/repos/{REPO}/pulls")] = 500
    spy = Spy()
    with pytest.raises(GitHubWriteError):
        run(repos, github, sha, spy)
    assert f"refs/heads/{BACKPORT}" in repos.refs() and api.pulls == []
    del api.fail[("POST", f"/repos/{REPO}/pulls")]
    result, _ = run(repos, github, sha, spy)
    assert result.outcome == "opened" and len(api.pulls) == 1
    assert len(spy.args_of("push")) == 1  # the branch from the first run was reused, not pushed again


def test_a_lookup_error_runs_no_git_and_creates_nothing(repos, api, github):
    sha = repos.fix_on_main()
    api.fail[("GET", f"/repos/{REPO}/pulls")] = 502
    spy = Spy()
    with pytest.raises(GitHubWriteError):
        run(repos, github, sha, spy)
    assert spy.calls == [] and api.pulls == []


# -- what it refuses ---------------------------------------------------------------------------------------------


def test_a_commit_that_is_not_in_the_base_history_is_refused(repos, api, github):
    """A PR head (a branch that was never merged, or a fork's commit) is not backported."""
    repos.git(repos.seed, "checkout", "-b", "pr-head", "main")
    repos.write("evil.txt", "from a PR head\n")
    head = repos.commit("pr head")
    repos.push("pr-head")
    before = repos.refs()
    for sha in (head, "a" * 40):  # on the remote but not on main; not in the repo at all
        spy = Spy()
        with pytest.raises(Refused, match="never a PR head"):
            run(repos, github, sha, spy)
        assert "cherry-pick" not in spy.subs() and "push" not in spy.subs()
    assert repos.refs() == before and api.pulls == [] and api.comments == []


@pytest.mark.parametrize(
    "argv",
    [
        ["fetch", "origin", "refs/pull/12/head"],
        ["checkout", "refs/pull/12/head"],
        ["push", "--force", "origin", "x"],
        ["push", "-f", "origin", "x"],
        ["push", "--force-with-lease", "origin", "x"],
        ["push", "origin", "+x"],
        ["push", "origin", ":x"],
        ["push", "--delete", "origin", "x"],
        ["branch", "-D", "x"],
        ["reset", "--hard", "HEAD"],
        ["clean", "-fd"],
        ["rebase", "main"],
        [],
    ],
)
def test_check_args_refuses_destructive_and_pr_head_commands(argv):
    with pytest.raises(Refused):
        check_args(argv)


def test_the_head_ref_and_head_sha_of_the_pr_are_kept_away_from_git():
    head_sha, head_ref = "f" * 40, "feature/their-fork-branch"
    for arg in (head_sha, head_ref):
        with pytest.raises(Refused, match="never fetched or checked out"):
            check_args(["checkout", arg], [head_sha, head_ref])
    check_args(["checkout", "-b", BACKPORT], [head_sha, head_ref])  # the bot's own branch is fine


@pytest.mark.parametrize("field", sorted(COMMAND_FIELDS))
def test_a_conflict_command_from_the_tenant_is_refused(field, tmp_path, monkeypatch):
    def started(*a, **k):
        raise AssertionError("a process was started")

    monkeypatch.setattr(subprocess, "run", started)
    monkeypatch.setattr(subprocess, "Popen", started)
    with pytest.raises(ConflictCommandRefused, match="never runs a command"):
        BackportConfig.from_mapping({"target_branch": "release", field: "touch " + str(tmp_path / "ran")})
    assert not (tmp_path / "ran").exists() and issubclass(ConflictCommandRefused, Refused)


def test_the_config_is_exactly_a_target_branch():
    assert BackportConfig.from_mapping({"target_branch": "release/1.x"}).target_branch == "release/1.x"
    for bad in ({}, {"target_branch": "release", "extra": 1}, {"target_branch": 3}):
        with pytest.raises(ValueError):
            BackportConfig.from_mapping(bad)


@pytest.mark.parametrize("name", ["", "-x", "--upload-pack=x", "a..b", "a b", "x/", "x.lock", "a@{b}", "a;b", "$(x)", "a\nb"])
def test_a_branch_name_that_could_be_an_option_or_a_ref_trick_is_refused(name):
    with pytest.raises(ValueError):
        BackportConfig(name)


@pytest.mark.parametrize(
    "changes",
    [{"action": "opened"}, {"merged": False}, {"title": "Fix the bug"}, {"base": "release"}, {"ticket": "acme/shop#8", "title": "Argus fix for acme/shop#7"}],
)
def test_events_that_are_not_a_merged_argus_fix_start_nothing(repos, api, github, changes):
    sha = repos.fix_on_main()
    result, spy = run(repos, github, sha, **changes)
    assert result.outcome == "skipped" and spy.calls == [] and api.log == []


# -- the token ----------------------------------------------------------------------------------------------------


def test_the_token_is_in_the_environment_for_https_only_and_never_in_an_argument(repos, api, github, tmp_path):
    env = git_env(tmp_path, "https://github.com/acme/shop.git", TOKEN)
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader" and env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    assert "GIT_CONFIG_COUNT" not in git_env(tmp_path, str(repos.origin), TOKEN)  # a local path gets no header
    sha = repos.fix_on_main()
    _, spy = run(repos, github, sha, token=TOKEN)
    assert TOKEN not in json.dumps(spy.calls)


def test_git_gets_a_short_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_MODEL_API_KEY", "model-key-not-real")
    monkeypatch.setenv("GITHUB_WRITE_TOKEN", "write-token-not-real")
    env = git_env(tmp_path, "https://github.com/acme/shop.git", None)
    assert "model-key-not-real" not in json.dumps(env) and "write-token-not-real" not in json.dumps(env)
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["GIT_CONFIG_NOSYSTEM"] == "1"


def test_a_failed_clone_is_reported_and_scrubbed(repos, github):
    sha = repos.fix_on_main()
    import base64

    b64 = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
    result, _ = run(repos, github, sha, Spy(fail_on={"clone": f"fatal: {TOKEN} {b64}"}), token=TOKEN)
    assert result.outcome == "failed" and TOKEN not in result.detail and b64 not in result.detail


def test_no_shell_and_no_force_in_the_source():
    text = (Path(__file__).resolve().parents[1] / "src" / "argus_app" / "backport.py").read_text(encoding="utf-8")
    for needle in ("shell=", "os.system", "os.popen", "eval(", "exec("):
        assert needle not in text
