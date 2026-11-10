"""P8-T23 break it: force a cherry-pick conflict in a backport, and attack every other promise of the bot.

Real `git` on local bare repositories (helpers of test_backport.py), the stateful fake GitHub, no network, no model.
Each test names the clause of the T23 row it guards. The write-up, with the output of the tests against bots that were
mutated on purpose (force-push, PR creation after a failed push, PR head allowed, ...), is docs/notes/p8-break-it-t23.md.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest
from flow.github_write import GitHubWriteError, HttpGitHubClient
from flow.states import branch_name
from test_backport import BACKPORT, PR_NUMBER, TICKET, TOKEN, Repos, Spy, event, make_conflict, run
from test_pr import REPO, FakeGitHubApi

from argus_app.backport import COMMAND_FIELDS, BackportConfig, ConflictCommandRefused, Refused, backport_merged_pr, check_args

HEAD_REF = branch_name(TICKET)
POST_PULLS = f"POST /repos/{REPO}/pulls"


@pytest.fixture
def repos(tmp_path):
    return Repos(tmp_path)


@pytest.fixture
def api():
    return FakeGitHubApi()


@pytest.fixture
def github(api):
    return HttpGitHubClient("app-token-not-real", REPO, transport=api.transport())


def reject_pushes(repos: Repos, on: bool = True) -> None:
    """A pre-receive hook on the origin: the remote refuses every push (a real failed push, not a faked exit code)."""
    hook = repos.origin / "hooks" / "pre-receive"
    if on:
        hook.write_text("#!/bin/sh\necho 'rejected by policy' >&2\nexit 1\n", newline="\n")
    else:
        hook.unlink()


def only_git(spy: Spy) -> None:
    assert spy.calls and all(Path(argv[0]).name.lower().removesuffix(".exe") == "git" for argv in spy.calls)


# -- clause: the bot comments the conflict and leaves branches untouched ---------------------------------------


def modify_delete(repos: Repos) -> str:
    repos.on("release")
    repos.git(repos.seed, "rm", "a.txt")
    repos.commit("release deletes a.txt")
    repos.push("release")
    return repos.fix_on_main()


def add_add(repos: Repos) -> str:
    repos.on("release")
    repos.write("b.txt", "release b\n")
    repos.write("c.txt", "release c\n")
    repos.commit("release adds b and c")
    repos.push("release")
    repos.on("main")
    repos.write("b.txt", "main b\n")
    repos.write("c.txt", "main c\n")
    sha = repos.commit("main adds b and c")
    repos.push("main")
    return sha


@pytest.mark.parametrize(
    ("make", "files"),
    [(make_conflict, ["a.txt"]), (modify_delete, ["a.txt"]), (add_add, ["b.txt", "c.txt"])],
    ids=["edit-edit", "modify-delete", "add-add-two-files"],
)
def test_a_conflict_is_commented_and_not_one_ref_moves(repos, api, github, make, files):
    sha = make(repos)
    before = repos.refs()
    result, spy = run(repos, github, sha, token=TOKEN)
    assert result.outcome == "conflict" and result.detail == ", ".join(files)
    assert repos.refs() == before  # no ref moved, none created (no backport branch), none deleted
    assert f"refs/heads/{BACKPORT}" not in repos.refs()
    assert api.pulls == [] and api.count(POST_PULLS) == 0
    assert len(api.comments) == 1 and all(f"`{f}`" in api.comments[0]["body"] for f in files) and sha[:12] in api.comments[0]["body"]
    assert "push" not in spy.subs() and ["cherry-pick", "--abort"] == spy.args_of("cherry-pick")[-1][-2:]
    assert not spy.dirs[0].exists()  # and the temporary clone, with the half-applied pick, is gone
    only_git(spy)


def test_a_fix_that_is_already_on_the_target_changes_nothing(repos, api, github):
    """Someone applied the fix by hand: the pick is empty, which is not a conflict. Nothing is pushed or created."""
    repos.on("release")
    repos.write("a.txt", "one\nTWO\nthree\n")
    repos.commit("release has the fix already")
    repos.push("release")
    sha = repos.fix_on_main()
    before = repos.refs()
    result, spy = run(repos, github, sha)
    assert result.outcome == "failed" and "without a conflict" in result.detail
    assert repos.refs() == before and api.pulls == [] and api.comments == [] and "push" not in spy.subs()


# -- clause: fails on a force-push of the bot branch ---------------------------------------------------------------


def stale_by_a_person(repos: Repos, api, github) -> None:
    repos.git(repos.seed, "checkout", "-b", BACKPORT, "release")
    repos.write("other.txt", "someone else's work\n")
    repos.commit("a person's commit on the bot branch")
    repos.push(BACKPORT)


def stale_by_a_half_done_run(repos: Repos, api, github) -> None:
    """Run 1 pushed the branch and then GitHub refused to create the PR; later the target branch moved on."""
    sha = repos.fix_on_main()
    api.fail[("POST", f"/repos/{REPO}/pulls")] = 500
    with pytest.raises(GitHubWriteError):
        run(repos, github, sha)
    del api.fail[("POST", f"/repos/{REPO}/pulls")]
    repos.on("release")
    repos.write("r.txt", "the release branch moved\n")
    repos.commit("release moves")
    repos.push("release")


@pytest.mark.parametrize("make_stale", [stale_by_a_person, stale_by_a_half_done_run], ids=["person-pushed", "target-moved-after-half-done-run"])
def test_a_bot_branch_that_differs_is_never_overwritten_and_no_pr_is_made_from_it(repos, api, github, make_stale):
    if make_stale is stale_by_a_person:
        sha = repos.fix_on_main()
        make_stale(repos, api, github)
    else:
        make_stale(repos, api, github)
        sha = repos.git(repos.origin, "rev-parse", "main")
    branch_tip = repos.refs()[f"refs/heads/{BACKPORT}"]
    before = repos.refs()
    for _ in range(2):  # and a second run does the same
        result, spy = run(repos, github, sha)
        assert result.outcome == "stale-branch"
        assert "push" not in spy.subs() and repos.refs() == before and repos.refs()[f"refs/heads/{BACKPORT}"] == branch_tip
    assert api.pulls == [] and api.count(POST_PULLS) <= 1  # the only POST is the failed one of the half-done run (none in the other case)


@pytest.mark.parametrize(
    "argv",
    [
        ["push", "-fu", "origin", "x"],
        ["push", "-uf", "origin", "x"],
        ["push", "--forc", "origin", "x"],
        ["push", "--force-with-lease=x:y", "origin", "x"],
        ["push", "--force-if-includes", "origin", "x"],
        ["push", "--del", "origin", "x"],
        ["push", "--mirro", "origin"],
        ["push", "origin", "HEAD:release"],
        ["push", "origin", "refs/heads/x:refs/heads/release"],
        ["checkout", "-B", "x"],
        ["checkout", "-f", "x"],
        ["clone", "--upload-pack=touch pwned", "--", "url", "dir"],
        ["clone", "--config", "core.sshCommand=touch pwned", "--", "url", "dir"],
        ["cherry-pick", "--strategy-option=theirs", "abc"],
    ],
    ids=lambda argv: " ".join(argv),
)
def test_git_options_in_any_spelling_that_force_delete_or_run_a_command_are_refused(argv):
    """Git accepts `-fu` and the prefix `--forc` for a force; the guard allows only the options the bot itself uses."""
    with pytest.raises(Refused):
        check_args(argv)


# -- clause: fails on a failed push that still retries PR creation from a stale branch -------------------------


def test_a_push_the_remote_rejects_creates_no_pr_and_is_not_retried(repos, api, github):
    sha = repos.fix_on_main()
    reject_pushes(repos)
    before = repos.refs()
    result, spy = run(repos, github, sha)
    assert result.outcome == "push-failed" and "rejected by policy" in result.detail
    assert len(spy.args_of("push")) == 1  # one attempt, no retry
    assert api.pulls == [] and api.count(POST_PULLS) == 0 and api.comments == [] and repos.refs() == before


def test_after_rejected_pushes_the_next_run_starts_clean_and_opens_one_pr_from_its_own_branch(repos, api, github):
    sha = repos.fix_on_main()
    reject_pushes(repos)
    for _ in range(2):
        result, spy = run(repos, github, sha)
        assert result.outcome == "push-failed" and api.pulls == [] and len(spy.args_of("push")) == 1
    reject_pushes(repos, on=False)
    result, spy = run(repos, github, sha)
    assert result.outcome == "opened" and len(api.pulls) == 1 and len(spy.args_of("push")) == 1
    assert repos.file(f"refs/heads/{BACKPORT}", "a.txt") == "one\nTWO\nthree"


# -- clause: a second run finds the existing PR or no-ops ---------------------------------------------------------


def test_a_second_run_after_each_outcome_finds_the_pr_or_does_nothing_new(repos, api, github):
    sha = repos.fix_on_main()
    run(repos, github, sha)
    refs, comments, log = repos.refs(), list(api.comments), len(api.log)
    result, spy = run(repos, github, sha)
    assert result.outcome == "exists" and spy.calls == [] and repos.refs() == refs and api.comments == comments and len(api.pulls) == 1
    assert api.log[log:] == [f"GET /repos/{REPO}/pulls"]  # one lookup, nothing written
    api.pulls[0]["state"] = "closed"  # a maintainer declined the backport: the bot does not open it again
    result, spy = run(repos, github, sha)
    assert result.outcome == "exists" and spy.calls == [] and len(api.pulls) == 1


def test_a_conflict_run_three_times_comments_once_and_never_pushes(repos, api, github):
    sha = make_conflict(repos)
    before = repos.refs()
    for _ in range(3):
        result, spy = run(repos, github, sha)
        assert result.outcome == "conflict" and "push" not in spy.subs()
    assert len(api.comments) == 1 and api.pulls == [] and repos.refs() == before


def test_a_pr_that_failed_after_the_push_is_opened_by_the_next_run_without_a_second_push(repos, api, github):
    sha = repos.fix_on_main()
    api.fail[("POST", f"/repos/{REPO}/pulls")] = 500
    spy = Spy()
    with pytest.raises(GitHubWriteError):
        run(repos, github, sha, spy)
    del api.fail[("POST", f"/repos/{REPO}/pulls")]
    result, _ = run(repos, github, sha, spy)
    assert result.outcome == "opened" and len(api.pulls) == 1 and len(spy.args_of("push")) == 1


def test_two_runs_at_the_same_time_make_one_pr_and_destroy_nothing(repos, api, github):
    sha = repos.fix_on_main()
    release = repos.refs()["refs/heads/release"]
    results, spies = [], [Spy(), Spy()]

    def one(spy: Spy) -> None:
        try:
            results.append(run(repos, github, sha, spy)[0].outcome)
        except Exception as e:  # the fake GitHub is not built for two writers; what matters is the invariants below
            results.append(type(e).__name__)

    threads = [threading.Thread(target=one, args=(s,)) for s in spies]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert "opened" in results and set(results) <= {"opened", "exists", "push-failed", "stale-branch"}, results
    assert len(api.pulls) == 1 and f"refs/heads/{BACKPORT}" in repos.refs() and repos.refs()["refs/heads/release"] == release


# -- clause: refuses a tenant conflict command ------------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(COMMAND_FIELDS))
def test_a_tenant_conflict_command_is_refused_and_no_process_starts(field, tmp_path, monkeypatch):
    def started(*a, **k):
        raise AssertionError("a process was started")

    monkeypatch.setattr(subprocess, "run", started)
    monkeypatch.setattr(subprocess, "Popen", started)
    marker = tmp_path / "ran"
    for value in (f"touch {marker}", f"$(touch {marker})", ["touch", str(marker)]):
        with pytest.raises(ConflictCommandRefused, match="never runs a command"):
            BackportConfig.from_mapping({"target_branch": "release", field: value})
    assert not marker.exists()


def test_a_command_written_into_the_tenants_repo_is_never_run_on_a_conflict(repos, api, github, tmp_path):
    """The tenant puts `on_conflict` into `.argus.yml` and a merge driver into `.gitattributes` on the target branch."""
    marker = tmp_path / "pwned"
    repos.on("release")
    repos.write(".argus.yml", f"backport:\n  on_conflict: python -c \"open(r'{marker}','w')\"\n")
    repos.write(".gitattributes", "* merge=pwn\n")
    repos.commit("tenant config")
    repos.push("release")
    repos.on("main")
    repos.git(repos.seed, "merge", "--no-edit", "release")
    repos.push("main")
    sha = make_conflict(repos)
    result, spy = run(repos, github, sha)
    assert result.outcome == "conflict" and not marker.exists()
    only_git(spy)  # every process the bot started was git
    assert "push" not in spy.subs() and api.pulls == []


# -- clause: refuses a checkout of the PR head under the installation token ---------------------------------------------


def pr_head(repos: Repos) -> str:
    repos.git(repos.seed, "checkout", "-b", HEAD_REF, "main")
    repos.write("evil.txt", "from a PR head\n")
    head = repos.commit("pr head")
    repos.push(HEAD_REF)
    repos.git(repos.origin, "update-ref", "refs/pull/12/head", head)  # the ref GitHub keeps for every PR
    return head


@pytest.mark.parametrize("event_head_sha", ["head", "f" * 40], ids=["event-names-the-head", "event-head-is-stale"])
def test_a_pr_head_is_never_checked_out_or_picked_even_with_a_token(repos, api, github, event_head_sha):
    """The event claims `merged` and gives the PR head as the merge commit (a forged or confused payload)."""
    head = pr_head(repos)
    ev = event(head)
    ev["pull_request"]["head"] = {"ref": HEAD_REF, "sha": head if event_head_sha == "head" else event_head_sha}
    before = repos.refs()
    spy = Spy()
    with pytest.raises(Refused):
        backport_merged_pr(ev, BackportConfig("release"), github, clone_url=str(repos.origin), token=TOKEN, runner=spy)
    spy.assert_not_destructive()
    for argv in spy.calls:
        if spy.sub(argv) in {"checkout", "cherry-pick", "push", "fetch", "pull"}:
            assert head not in argv and HEAD_REF not in argv, argv
    assert repos.refs() == before and api.pulls == [] and api.comments == []


def test_the_merge_commit_of_a_merged_pr_is_still_backported_with_a_token(repos, api, github):
    """The other side of the refusal: a commit that is in the base history is fine, and its checkout is only the new branch."""
    pr_head(repos)
    sha = repos.fix_on_main()
    result, spy = run(repos, github, sha, token=TOKEN)
    assert result.outcome == "opened"
    assert [c[-3:] for c in spy.args_of("checkout")] == [["checkout", "-b", BACKPORT]]
