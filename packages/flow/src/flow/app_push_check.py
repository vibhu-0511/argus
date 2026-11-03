"""P7-T20, the real run: try to move the default branch with a least-privilege App token, and record GitHub's own answer.

The owner runs this once, against a THROWAWAY repository the App is installed on, after turning on branch protection
for its default branch (`docs/notes/p7-t20-owner-steps.md`). It needs no model. Nothing here has been run against GitHub;
`packages/flow/tests/test_app_push_check.py` runs it against a mock.

What it does, in order (the token is minted with the committed minimum, for that one repository):

1. lists the repositories the token can see (expected: exactly the throwaway repo);
2. creates an empty commit object on top of the default branch (a commit object is not a ref update, so protection does
   not stop it);
3. tries to move the default branch to that commit with a normal (non-force) ref update. EXPECTED: 403 or 422 with a
   protection message. If it returns 200 the branch is NOT protected and the default branch now has one extra empty
   commit: that is why the repository must be a throwaway;
4. control: creates a probe branch with the same commit (expected 201), then deletes it (expected 204). This shows the
   token works, so the refusal in step 3 is about the branch and not about a bad token;
5. tries a write on another repository the App is not installed on (a ref create with a made-up sha, which creates
   nothing). EXPECTED: 403 or 404. A 422 would mean the token reached the other repository.

The token is never printed or written; messages go through `argus_core.redact`. The result file holds status codes and
GitHub's messages only.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from argus_core.redact import redact

from flow.app_token import API_URL, AppTokenMinter

API_VERSION = "2022-11-28"
FAKE_SHA = "0" * 39 + "1"  # a sha that cannot exist: a write that gets through to validation answers 422 and creates nothing


def _msg(response: httpx.Response) -> str:
    try:
        return redact(str(response.json().get("message", "")))[:300]
    except (ValueError, AttributeError):
        return redact(response.text)[:300]


def run_check(token: str, repo: str, other_repo: str, default_branch: str, *, transport: httpx.BaseTransport | None = None,
              base_url: str = API_URL, clock=lambda: datetime.now(timezone.utc)) -> dict:
    """Run the five steps with `token`. Returns the result dict; raises nothing for an unexpected status (it is recorded)."""
    steps: list[dict] = []

    with httpx.Client(base_url=base_url, transport=transport, timeout=30.0,
                      headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION}) as client:
        def call(name: str, method: str, path: str, expect: tuple[int, ...], **kw: Any) -> httpx.Response:
            response = client.request(method, path, **kw)
            steps.append({"step": name, "request": f"{method} {path}", "status": response.status_code, "message": _msg(response),
                          "as_expected": response.status_code in expect, "expected": list(expect)})
            return response

        listed = call("installation repositories", "GET", "/installation/repositories", (200,))
        names = [r.get("full_name") for r in listed.json().get("repositories", [])] if listed.status_code == 200 else None
        steps[-1]["repositories"] = names
        steps[-1]["as_expected"] = names == [repo]

        head = call("read default branch", "GET", f"/repos/{repo}/git/ref/heads/{default_branch}", (200,))
        if head.status_code != 200:
            return _finish(steps, repo, other_repo, default_branch, clock, "stopped: could not read the default branch")
        sha = head.json()["object"]["sha"]
        tree = call("read head commit", "GET", f"/repos/{repo}/git/commits/{sha}", (200,))
        if tree.status_code != 200:
            return _finish(steps, repo, other_repo, default_branch, clock, "stopped: could not read the head commit")
        commit = call("create an empty commit object", "POST", f"/repos/{repo}/git/commits", (201,),
                      json={"message": "Argus P7-T20 probe: empty commit, never merged", "tree": tree.json()["tree"]["sha"], "parents": [sha]})
        if commit.status_code != 201:
            return _finish(steps, repo, other_repo, default_branch, clock, "stopped: could not create a commit object")
        new_sha = commit.json()["sha"]

        moved = call("move the default branch (non-force)", "PATCH", f"/repos/{repo}/git/refs/heads/{default_branch}", (403, 422),
                     json={"sha": new_sha, "force": False})

        probe = f"argus-p7-t20-probe-{secrets.token_hex(3)}"
        created = call("control: create a probe branch", "POST", f"/repos/{repo}/git/refs", (201,), json={"ref": f"refs/heads/{probe}", "sha": new_sha})
        if created.status_code == 201:
            call("control: delete the probe branch", "DELETE", f"/repos/{repo}/git/refs/heads/{probe}", (204,))

        other = call("write on another repository", "POST", f"/repos/{other_repo}/git/refs", (403, 404),
                     json={"ref": f"refs/heads/argus-p7-t20-other-{secrets.token_hex(3)}", "sha": FAKE_SHA})

    if moved.status_code == 200:
        verdict = "NOT PROTECTED: the default branch moved (one extra empty commit on a throwaway repository)"
    elif moved.status_code in (403, 422) and created.status_code == 201 and other.status_code in (403, 404):
        verdict = "as expected: default branch refused, probe branch allowed, other repository refused"
    else:
        verdict = "unexpected: read the steps"
    return _finish(steps, repo, other_repo, default_branch, clock, verdict)


def _finish(steps: list[dict], repo: str, other_repo: str, default_branch: str, clock, verdict: str) -> dict:
    return {"task": "P7-T20", "ran_at": clock().isoformat(timespec="seconds"), "repo": repo, "other_repo": other_repo,
            "default_branch": default_branch, "verdict": verdict, "steps": steps}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m flow.app_push_check", description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True, help="owner/name of the THROWAWAY repository the App is installed on")
    ap.add_argument("--other-repo", required=True, help="owner/name of a repository the App is NOT installed on")
    ap.add_argument("--default-branch", default="main")
    ap.add_argument("--throwaway-repo", action="store_true", help="I confirm --repo is a throwaway: if protection is off, its default branch gets one empty commit")
    ap.add_argument("--out", help="write the result JSON here")
    args = ap.parse_args(argv)
    if not args.throwaway_repo:
        ap.error("pass --throwaway-repo to confirm the repository can be written to")
    if args.repo == args.other_repo:
        ap.error("--other-repo must be a different repository")

    token = AppTokenMinter.from_env(args.repo).mint("write").token  # the environment variables are named in flow.app_token
    result = run_check(token, args.repo, args.other_repo, args.default_branch)
    text = json.dumps(result, indent=2)
    assert token not in text
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if result["verdict"].startswith("as expected") else 1


if __name__ == "__main__":
    sys.exit(main())
