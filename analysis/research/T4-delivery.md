# T4 delivery — GitHub intake, durable steps, backport conflicts

Track T4. Plan review only. No application code, no plan edits. Clones were read at the pinned SHAs. Competitor code was not installed or run.

`gh search` rejects `--state all` (legal values are `open` and `closed`). Searches below omit the state flag, so open and closed both come back. Comment counts are the `commentsCount` field. Reaction totals were not in the JSON, so a "reactions" rank is GitHub's reactions sort, not a number I counted. The search API rate limit was hit once; the dbos and remaining sorenlouv queries were repeated after the reset.

Hours: every change folds into an existing task or ADR. Net hours 0. No new task. Nothing moves on the cut list. The workflow state machine stays [ME].

## Entries

### T4-01 SWE-agent has no label or webhook intake
- Topic: label triggers
- Their approach: At `3ea751c087f32b16e039a2233dd6eefecef325d5`, `.github/workflows` is `pytest.yaml`, `build-docs.yaml`, `check-links-pr.yaml`, and `check-links-periodic.yaml`. Triggers are push, pull_request, workflow_dispatch, and a monthly schedule. A search of `sweagent/` and those workflows for a webhook receiver or an `issues` / `labeled` trigger found none. **not in this tree.** A run starts from the CLI. `docs/usage/cl_tutorial.md` tells the operator to pass a flag after the run:

```270:271:analysis/_repos/SWE-agent__SWE-agent/docs/usage/cl_tutorial.md
* Alternatively, when running on a GitHub issue, you can have the agent automatically open a PR if the issue has been solved by supplying the `--actions.open_pr` flag.
  Please use this feature responsibly (on your own repositories or after careful consideration).
```

  Permalink: https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/docs/usage/cl_tutorial.md#L270-L271 and https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/.github/workflows/pytest.yaml#L5-L16
- Argus plan: `phases/P08-argus-app.md`, P8-T08. "Adding the label starts exactly one workflow; a label added by a user without write access is ignored." There is no SWE-agent workflow to copy. Hours delta: 0.
- Evidence: [CODE] the four workflow `on:` blocks. [DOCS] the CLI flag.
- Licence: MIT
- Affected: P8-T08, P6-T05, P6-T06

### T4-02 SWE-agent opens a new PR on a random branch
- Topic: idempotent PR creation
- Their approach: `open_pr` builds a branch with a random suffix and calls `pulls.create` with no lookup of an existing PR.

```39:39:analysis/_repos/SWE-agent__SWE-agent/sweagent/run/hooks/open_pr.py
    branch_name = f"swe-agent-fix-#{issue.number}-" + str(random.random())[2:10]
```

```109:112:analysis/_repos/SWE-agent__SWE-agent/sweagent/run/hooks/open_pr.py
            draft=True,
        )
        logger.debug(f"Creating PR with args: {args}")
        pr_info = api.pulls.create(**args)  # type: ignore
```

  Permalink: https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/run/hooks/open_pr.py#L39-L112
- Argus plan: `PROJECT.md`, P6. "opening a pull request is find-or-create, keyed by ticket id." `phases/P08-argus-app.md`, P8-T09. "re-running updates the same PR." The branch name has to be stable for that lookup. A random suffix makes the second call a second PR. P8-T09 also does not say the PR is a draft until QA accepts it. SWE-agent's only open path is `draft=True`. Hours delta: 0. Add the stable branch name and the draft-until-QA assertion to P8-T09 and P6-T21.
- Evidence: [CODE]
- Licence: MIT
- Affected: P6-T21, P8-T09, ADR-023

### T4-03 The skip check looks for "closes #N" in a commit, not for an open PR
- Topic: idempotent PR creation
- Their approach: `should_open_pr` returns false when an issue event of type `referenced` has a commit whose message contains `fixes #N` or `closes #N`. The default `skip_if_commits_reference_issue` is true. There is no search for an open pull request.

```117:124:analysis/_repos/SWE-agent__SWE-agent/sweagent/utils/github.py
    for event in events:
        if event.event != "referenced":
            continue
        if not event.commit_id:
            continue
        commit = api.repos.get_commit(org, repo, event.commit_id)  # type: ignore
        message = commit.commit.message
        if f"fixes #{issue_number}" in message.lower() or f"closes #{issue_number}" in message.lower():
```

  Permalink: https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/utils/github.py#L110-L126 and https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/run/hooks/open_pr.py#L174-L179
- Argus plan: `phases/P06-argus-flow.md`, break-it for P6-T21. "make open PR a find-or-create keyed by the ticket id." The acceptance test should find the PR when no commit message contains `closes #N`. A heuristic on commit text misses a draft that was opened and not yet referenced that way, and it fires on an unrelated commit that happens to say `closes #N`. Hours delta: 0.
- Evidence: [CODE]
- Licence: MIT
- Affected: P6-T21, P8-T09, P6-T02

### T4-04 The fork remote URL contains the token
- Topic: token scopes
- Their approach: when pushing to a fork, the token is interpolated into the HTTPS remote.

```73:76:analysis/_repos/SWE-agent__SWE-agent/sweagent/run/hooks/open_pr.py
        token_prefix = ""
        if token:
            token_prefix = f"{token}@"
        fork_url = f"https://{token_prefix}github.com/{forker}/{repo}.git"
```

  The same function's push error tells the operator to "check your token and permissions" after `git push` fails. There is no scope check before the push. Permalink: https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/run/hooks/open_pr.py#L73-L90
- Argus plan: `phases/P07-argus-guard.md`, P7-T03. "a test plants a fake secret and shows it is redacted from a trajectory and a trace." ADR-026 asks "What lifetimes and permissions does each credential get?" The plan does not say the git remote must not contain the token. Hours delta: 0. P7-T03 and ADR-026 should forbid a token in a remote URL, and P7-T04 should state the scopes before the first push.
- Evidence: [CODE]
- Licence: MIT
- Affected: P7-T03, P7-T04, P7-T16, ADR-026

### T4-05 Issue title and body are concatenated into the prompt
- Topic: prompt injection through issue text
- Their approach: the problem statement is the title, a newline, and the body. No fence, no instruction/data split.

```105:107:analysis/_repos/SWE-agent__SWE-agent/sweagent/utils/github.py
    title = issue.title if issue.title else ""
    body = issue.body if issue.body else ""
    return f"{title}\n{body}\n"
```

  `GithubIssue.get_problem_statement` returns that string. Permalink: https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/utils/github.py#L99-L107 and https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/problem_statement.py#L149-L151
- Argus plan: `phases/P07-argus-guard.md`, P7-T07. "Config runs against the fix-loop with stub tools ... test cases are listed per attack vector." The vectors are ticket, repo file, and skill. P7-T09 then requires "data and instruction separation". The title is part of the ticket. Hours delta: 0. P7-T07 should include a title that says to ignore the bug, not only a body.
- Evidence: [CODE]
- Licence: MIT
- Affected: P7-T07, P7-T09, P7-T18, ADR-024

### T4-06 Label triggers check the label name, not the actor
- Topic: label triggers and permission checks
- Their approach: `examples/03_github_workflows/` only. PR review runs on `pull_request` types `labeled` and `review_requested`, and the job `if` compares the label name or the requested reviewer login. TODO management does the same for `automatic-todo`, or `workflow_dispatch`. No workflow in this directory uses `issues: [labeled]`. No step reads `github.event.sender` or the sender's permission.

```29:32:analysis/_repos/OpenHands__software-agent-sdk/examples/03_github_workflows/02_pr_review/workflow.yml
        if: |
            github.event.label.name == 'review-this' ||
            github.event.requested_reviewer.login == 'openhands-agent'
```

  Permalink: https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/02_pr_review/workflow.yml#L17-L32 and https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/03_todo_management/workflow.yml#L33-L54
- Argus plan: `phases/P08-argus-app.md`, P8-T08 and P8-T24. "a label added by a user without write access is ignored." That check is already stronger than these examples. Hours delta: 0. Keep it. P8-T24 should also record that a write-capable actor's issue body is still untrusted input for P7-T07. Passing the permission check does not skip the injection cases.
- Evidence: [CODE]
- Licence: MIT
- Affected: P8-T08, P8-T24, P7-T07, ADR-024

### T4-07 The agent job is given GITHUB_TOKEN and contents:write
- Topic: token scopes
- Their approach: the TODO workflow's permissions are `contents: write`, `pull-requests: write`, and `issues: write`. The process step exports `GITHUB_TOKEN` into the environment of `agent.py`. The prompt tells the model the token is available and to run `gh pr create`. The README says the token "is automatically provided" and lists `contents: write`. The basic-action workflow uses the same three write permissions. The PostHog and Datadog examples are narrower: `contents: read` and `issues: write`.

```42:45:analysis/_repos/OpenHands__software-agent-sdk/examples/03_github_workflows/03_todo_management/workflow.yml
permissions:
    contents: write
    pull-requests: write
    issues: write
```

```6:9:analysis/_repos/OpenHands__software-agent-sdk/examples/03_github_workflows/03_todo_management/prompt.py
- Use the `gh pr create` command to create the PR
- The GITHUB_TOKEN environment variable is available for authentication
- PR Title: "[Openhands] {description}"
- Branch name "openhands/todo/***"
```

  `get_default_agent` is what these scripts call. It chooses tools. It does not inspect a GitHub token or a scope list. Permalink: https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/openhands-tools/openhands/tools/preset/default.py#L76-L84 and https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/03_todo_management/workflow.yml#L174-L178
- Argus plan: `phases/P08-argus-app.md`, P8-T04. "no secret is passed except through the tenant's own secrets." `phases/P07-argus-guard.md`, P7-T18. "pass no secrets into the sandbox." The plan does not say the Actions-injected `GITHUB_TOKEN` is removed from the agent step. A job with `permissions: contents: read` still receives a token. Hours delta: 0. P8-T04 and ADR-026 should say the agent step's environment has no `GITHUB_TOKEN`, and ADR-026 should name which principal pushes: the tenant workflow token, or the App installation token. Those are different scopes.
- Evidence: [CODE] the workflow and `get_default_agent`. [DOCS] `03_todo_management/README.md` lines 65-67.
- Licence: MIT
- Affected: P8-T04, P7-T04, P7-T18, P7-T20, ADR-026, ADR-027

### T4-08 PR creation is a POST, and dedup is a sentence in the prompt
- Topic: idempotent PR creation
- Their approach: after the agent exits, the workflow commits, pushes, and `curl` POSTs `/pulls`. It does not search for an existing PR. The branch is `git checkout -B` from a slug of the TODO description. The prompt tells the model to search for a PR titled `[Openhands]` and to stop if one exists. The model and the shell can each create a PR. `01_basic_action/agent_script.py` will also `urlopen` whatever `PROMPT_LOCATION` is and use the bytes as the prompt.

```298:303:analysis/_repos/OpenHands__software-agent-sdk/examples/03_github_workflows/03_todo_management/workflow.yml
                  curl -X POST \
                    -H "Authorization: token $GITHUB_TOKEN" \
                    -H "Accept: application/vnd.github.v3+json" \
                    "https://api.github.com/repos/${{ github.repository }}/pulls" \
                    -d "$PR_PAYLOAD"
```

  Permalink: https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/03_todo_management/workflow.yml#L189-L303 and https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/03_todo_management/prompt.py#L12-L14 and https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/01_basic_action/agent_script.py#L64-L67
- Argus plan: P8-T09, as in T4-02. "re-running updates the same PR." Hours delta: 0. The acceptance test should show one creator, the find-or-create step, and that the agent process cannot call the pulls API. The reusable workflow should not load a prompt from a URL.
- Evidence: [CODE]
- Licence: MIT
- Affected: P8-T09, P8-T04, P6-T21, ADR-027

### T4-09 Untrusted text is interpolated into the shell
- Topic: prompt injection through issue text
- Their approach: `TODO_DESCRIPTION` is expanded inside a JSON heredoc, a `git commit -m` string, and the PR title. A description that contains quotes or command substitution is shell input. The same string is passed through `PROMPT.format(description=description)` into the instruction block.

```204:210:analysis/_repos/OpenHands__software-agent-sdk/examples/03_github_workflows/03_todo_management/workflow.yml
                  TODO_JSON=$(cat <<EOF
                  {
                    "file": "$TODO_FILE",
                    "line": $TODO_LINE,
                    "description": "$TODO_DESCRIPTION"
                  }
                  EOF
```

  Permalink: https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/03_todo_management/workflow.yml#L204-L210 and https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/03_todo_management/agent_script.py#L68-L72
- Argus plan: P7-T07 covers the model prompt. It does not cover a workflow shell. Hours delta: 0. P8-T09 and P8-T20 should build the PR through the API with the title and body as JSON fields. A fixture title containing `$(...)` must not be executed.
- Evidence: [CODE]
- Licence: MIT
- Affected: P8-T09, P8-T20, P7-T07, P7-T09

### T4-10 A failed issue search falls through to create
- Topic: idempotent creation
- Their approach: `search_existing_issue` in the PostHog example returns `None` on a request error, a JSON error, or a missing key. The caller then creates an issue. A closed issue also returns `None`, so a new issue is opened.

```522:528:analysis/_repos/OpenHands__software-agent-sdk/examples/03_github_workflows/05_posthog_debugging/posthog_debugging.py
    except (
        requests.exceptions.RequestException,
        json.JSONDecodeError,
        KeyError,
    ) as e:
        print(f"⚠️  Error searching for issues: {e}")
        return None
```

  Permalink: https://github.com/OpenHands/software-agent-sdk/blob/46b1fa5cb91ada17e6ec938c7e8624a4fa19fa98/examples/03_github_workflows/05_posthog_debugging/posthog_debugging.py#L478-L528
- Argus plan: P6-T21 and P8-T09 say find-or-create. They do not say what happens when the lookup itself errors. Hours delta: 0. The lookup error must leave the existing PR or issue untouched and must not create another one.
- Evidence: [CODE]
- Licence: MIT
- Affected: P6-T21, P8-T09, P6-T07

### T4-11 Default conflict path comments and aborts; the other mode commits the conflict
- Topic: backport conflict handling
- Their approach: `conflict_resolution` defaults to `fail`. That path runs `git cherry-pick` and, on a non-zero exit that is not an empty pick, aborts the cherry-pick and throws. `handleTargetResultLegacy` posts that failure on the source PR and returns. Push is `git push --set-upstream` with no `--force`, and it runs only after a cherry-pick result comes back. The other value, `draft_commit_conflicts`, runs `git commit --all -m BACKPORT-CONFLICT` and the PR is opened as a draft.

```592:599:analysis/_repos/korthout__backport-action/src/backport.ts
    if (result.status === "failed") {
      const message = composeFailureMessage(result);
      console.error(message);
      await this.github.createComment({
        owner: workflowOwner,
        repo: workflowRepo,
        issue_number: pullNumber,
        body: message,
```

  A GitHub 422 whose message starts with "A pull request already exists for " returns `skipped`, and the comment helper returns without posting. Permalink: https://github.com/korthout/backport-action/blob/08d2ffecdef82bdb06ea268ba07f50381440e4c4/src/git.ts#L250-L267 and https://github.com/korthout/backport-action/blob/08d2ffecdef82bdb06ea268ba07f50381440e4c4/src/backport.ts#L507-L518
- Argus plan: `phases/P08-argus-app.md`, P8-T10. "on conflict it comments and does nothing destructive." P8-T23. "The bot comments the conflict and leaves branches untouched." The default matches that. Hours delta: 0. P8-T23 should name the rejected options: committing conflict markers, opening a draft that contains them, and `git push --force`.
- Evidence: [CODE]
- Licence: MIT
- Affected: P8-T10, P8-T23, ADR-026

### T4-12 A second run can keep a stale branch and still try to open the PR
- Topic: idempotent PR creation
- Their approach: if `git push` fails, the action fetches the branch and continues to PR creation. The comment in the source says the recovered branch is not guaranteed to be up to date. If that fetch also fails, the original push error is returned and a failure comment is posted.

```471:478:analysis/_repos/korthout__backport-action/src/backport.ts
          console.info(
            `Branch ${branchname} may already exist, fetching it instead to recover previous run`,
          );
          await this.git.fetch(branchname, this.config.pwd, 1, remote);
          console.info(
            `Previous branch successfully recovered, retrying PR creation`,
          );
          // note that the recovered branch is not guaranteed to be up-to-date
```

  Permalink: https://github.com/korthout/backport-action/blob/08d2ffecdef82bdb06ea268ba07f50381440e4c4/src/backport.ts#L464-L487
- Argus plan: P8-T09 says a re-run updates the same PR. P8-T10 does not say what a second backport run does when the branch already exists. Hours delta: 0. P8-T10 should find the existing backport PR and update it, or no-op, and must not report failure for a PR that is already open. A fetch of an old branch must not count as success.
- Evidence: [CODE]
- Licence: MIT
- Affected: P8-T10, P8-T23, P6-T22

### T4-13 Do not run a conflict-resolution command from the PR
- Topic: permission checks
- Their approach: ADR 0003 says the action never runs code from the pull request it backports, and that a command to resolve conflicts was declined because the PR could change the command and then force a conflict. It says the README recommends `pull_request_target`. I did not open that README. **not verified** for the README wording. The ADR text was opened.

```13:17:analysis/_repos/korthout__backport-action/docs/adr/0003-scope-and-safety.md
**Only merged pull requests are backported, and the action never runs code from them.** The README recommends `pull_request_target`, which runs with the repository's secrets, so every feature must be safe by default for public repositories.
- Backporting unmerged pull requests was declined
- Running a command to resolve conflicts was declined. A pull request could change what that command does and then force a conflict
```

  Permalink: https://github.com/korthout/backport-action/blob/08d2ffecdef82bdb06ea268ba07f50381440e4c4/docs/adr/0003-scope-and-safety.md#L13-L16
- Argus plan: P8-T10 does not list a conflict-command field. `.argus.yml` fields are start command, test command, routes, and budget. Hours delta: 0. P8-T10 and ADR-026 should say there is no tenant-configured conflict command, and the bot does not check out the PR head in a workflow that holds the installation token.
- Evidence: [DOCS] the ADR. The README recommendation is [DOCS] only as quoted by that ADR.
- Licence: MIT
- Affected: P8-T10, P8-T05, ADR-026, ADR-027

### T4-14 sqren force-pushes the backport branch; conflict modes include commit and theirs
- Topic: backport conflict handling
- Their approach: `pushBackportBranch` always passes `--force` for the backport branch ref. It does not force-push the target branch. `conflictResolution` is `abort`, `commit`, or `theirs`, default `abort`. Non-interactive `abort` throws `merge-conflict-exception`. Non-interactive `theirs` aborts and retries the cherry-pick with `--strategy-option=theirs`. Non-interactive `commit` adds and commits the conflicted tree. The status comment for a merge-conflict exception says the backport failed because of merge conflicts.

```23:26:analysis/_repos/sorenlouv__backport/src/lib/git/push.ts
    const res = await spawnPromise(
      'git',
      ['push', repoForkOwner, `${backportBranch}:${backportBranch}`, '--force'],
      cwd,
    );
```

```65:65:analysis/_repos/sorenlouv__backport/src/options/option-schema.ts
  conflictResolution: z.enum(['abort', 'commit', 'theirs']).default('abort'),
```

  Permalink: https://github.com/sorenlouv/backport/blob/f9d847e91713a58c6b8e76208241c7575569cd44/src/lib/git/push.ts#L21-L27 and https://github.com/sorenlouv/backport/blob/f9d847e91713a58c6b8e76208241c7575569cd44/src/lib/cherrypickAndCreateTargetPullRequest/wait-for-cherrypick.ts#L127-L148 and https://github.com/sorenlouv/backport/blob/f9d847e91713a58c6b8e76208241c7575569cd44/src/lib/github/v3/create-status-comment.ts#L135-L154
- Argus plan: P8 goal. "The backport bot comments on conflict and does not force-push." P8-T23 leaves branches untouched. Hours delta: 0. The assertion has to cover the bot's own backport branch. `abort` plus a comment is the path to copy. `commit`, `theirs`, and `git push --force` are the paths the test must fail on, including a retry after a human has pushed to that branch.
- Evidence: [CODE]
- Licence: Apache-2.0
- Affected: P8-T10, P8-T23

### T4-15 A step result is recorded after the call; a recorded error is not run again
- Topic: step checkpoint, recovery, idempotency
- Their approach: `record_step_result` calls the function, then `record_operation_result`. On replay, `check_existing_result` returns the stored output or re-raises the stored exception and does not call the function. `retries_allowed` defaults to false. `DEFAULT_MAX_RECOVERY_ATTEMPTS` is 100, which bounds how often a PENDING workflow is recovered, not how often a stored error is retried. Recovery re-enqueues a PENDING row so one dequeue wins.

```2478:2485:analysis/_repos/dbos-inc__dbos-transact-py/dbos/_core.py
            step_output["error"] = serialized_e
            step_output["serialization"] = serialization
            dbos._sys_db.record_operation_result(step_output)
            raise
        serialized_r, serialization = serialize_value(output, None, dbos._serializer)
        step_output["output"] = serialized_r
        step_output["serialization"] = serialization
        dbos._sys_db.record_operation_result(step_output)
```

  Permalink: https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_core.py#L2455-L2518 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_dbos.py#L1400-L1417 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_recovery.py#L15-L23 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_registrations.py#L10
- Argus plan: `phases/P06-argus-flow.md`, P6-T03. "steps re-run safely when repeated." P6-T21. "kill the worker right after the PR is opened and before the step result is stored." That kill matches the window before `record_operation_result`. The plan does not say a stored exception is replayed as an exception. Hours delta: 0. P6-T19 should kill once before the record and assert a second GitHub call is find-or-create, and once after a recorded error and assert GitHub is not called again. This does not replace the state machine.
- Evidence: [CODE]
- Licence: MIT
- Affected: P6-T03, P6-T19, P6-T21, ADR-020

### T4-16 Recovery is filtered by executor and app version; LISTEN is sticky
- Topic: recovery, and risk 3 (Neon CU-hours and Render sleep)
- Their approach: if `DBOS__APPVERSION` is empty, launch replaces it with an MD5 of the workflow sources. The comment says a workflow-source change breaks recovery, so the version changes. Startup recovery loads PENDING rows for `GlobalParams.executor_id` and that version. `executor_id` is `DBOS__VMID` or `"local"`. If `conductor_key` is set and this is not DBOS Cloud, launch sets `executor_id` to a new UUID, so the next boot looks up a different id. `use_listen_notify` defaults to true and "may not be changed after the system database is first created." The Postgres listener holds a raw connection and issues `LISTEN`. The scheduler thread starts even with no user schedules; `scheduler_polling_interval_sec` defaults to 30.

```351:356:analysis/_repos/dbos-inc__dbos-transact-py/dbos/_dbos.py
    def compute_app_version(self, app_name: str) -> str:
        """
        An application's version is computed from a hash of the source of its workflows.
        This is guaranteed to be stable given identical source code because it uses an MD5 hash
        and because it iterates through the workflows in sorted order.
        This way, if the app's workflows are updated (which would break recovery), its version changes.
```

```815:816:analysis/_repos/dbos-inc__dbos-transact-py/dbos/_dbos.py
            if self.conductor_key is not None and not GlobalParams.dbos_cloud:
                GlobalParams.executor_id = generate_uuid()
```

  Permalink: https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_dbos.py#L351-L376 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_dbos.py#L895-L909 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_sys_db.py#L3201-L3222 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_dbos_config.py#L49-L54 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_sys_db_postgres.py#L379-L396
- Argus plan: `PLAN.md`, risk 3. "Neon CU-hours and Render sleep collide with DBOS polling." P6-T14. "states whether polling keeps the database awake." ADR-022 is the topology decision. The plan does not name `use_listen_notify`, the scheduler interval, `DBOS__APPVERSION`, or `DBOS__VMID`. Hours delta: 0. P6-T11 must choose `use_listen_notify` before the first migration. P6-T14 should separate the listener connection and the 30s scheduler poll from the Argus reconcile poller. P6-T12 and ADR-020 should pin a stable application version and executor id for the life of in-flight runs, and should not set a conductor key on Render. P6-T19 is invalid if the restarted process has a new version or a new executor id. No CU-hour figure is claimed here.
- Evidence: [CODE]
- Licence: MIT
- Affected: P6-T11, P6-T12, P6-T14, P6-T19, ADR-020, ADR-021, ADR-022. Risk 3 in `PLAN.md` and `PROJECT.md`.

### T4-17 One workflow id, a non-blocking webhook, and an idempotency key on the QA message
- Topic: webhooks vs polling, duplicate side effects
- Their approach: `SetWorkflowID` assigns an id to the first workflow started in the block. `workflow_id_reuse_policy` is `return-existing` or `reject`. `DBOS.send` takes an optional `idempotency_key`. When the key is omitted, the message uuid is a fresh UUID, so a second send is a second row. When the key is set, the uuid is `key::destination` and the insert is `on_conflict_do_nothing`. The widget-store starter (no licence file; ideas only, no quote) starts checkout under `SetWorkflowID(idempotency_key)` and then waits on `DBOS.get_event` before the HTTP handler returns. The payment route sends on the workflow id and waits again. The queue-worker starter enqueues with a queue name and a workflow name and no deduplication id, so each POST is a new workflow. The transactional-outbox starter's notification is an ordinary `@DBOS.step()` whose comment says it will be retried until it succeeds. The library default in T4-15 does not match that sentence: a recorded exception is re-raised. Permalink, library: https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_context.py#L648-L669 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_dbos.py#L1922-L1949 and https://github.com/dbos-inc/dbos-transact-py/blob/718d06613d9b7dc4c935e098e4608b6745267760/dbos/_sys_db.py#L3858-L3886. Permalink, demos, no quote: https://github.com/dbos-inc/dbos-demo-apps/blob/5568fc9fdb61a91e6f7cb300ef6f1cd254d219a6/python/widget-store/widget_store/main.py#L100-L130 and https://github.com/dbos-inc/dbos-demo-apps/blob/5568fc9fdb61a91e6f7cb300ef6f1cd254d219a6/python/queue-worker/server.py#L35-L45 and https://github.com/dbos-inc/dbos-demo-apps/blob/5568fc9fdb61a91e6f7cb300ef6f1cd254d219a6/python/transactional-outbox/transactional_enqueue.py#L113-L142
- Argus plan: P6-T06. "Handler returns 202 after enqueueing and does no GitHub reads inline." P6-T22. "store the delivery id and key the workflow by ticket id." The plan does not say the DBOS workflow id is the ticket id for both the webhook and the poller. A delivery id and a ticket id as two workflow ids start two workflows. `return-existing` keeps the first call's arguments, so it is not how the poller learns new GitHub state. Hours delta: 0. P6-T02 and P6-T06 should use one `SetWorkflowID(ticket_id)`, return 202 without `get_event` or `recv`, and treat the delivery id as a hint-dedup record. P6-T08 and P6-T10 should pass an idempotency key on the QA signal so a replayed review comment is one message. The state machine stays [ME].
- Evidence: [CODE] for the library. The demo behaviour is [CODE] read in this review and described without a quote. The demo's retry sentence is [DOCS] inside an unlicensed file, checked against the library.
- Licence: dbos-transact-py MIT. dbos-demo-apps has no licence file at this SHA. Ideas only.
- Affected: P6-T02, P6-T06, P6-T07, P6-T08, P6-T10, P6-T22, ADR-021, ADR-023

## Lessons from their issue tracker

Ranking note. The highest-comment issues are often install and environment threads. Those are listed only where the title was returned by `gh`. They are outside P6–P8. "not specified" means the plan has no task for them.

1. https://github.com/SWE-agent/SWE-agent/issues/66 — closed, 26 comments, top of the comments sort. The title is "Streamlining the installation and usage process." The plan does not guard installer friction. not specified.
2. https://github.com/SWE-agent/SWE-agent/issues/23 — closed, 4 comments, on the reactions sort. The body asks to process this repo's issues automatically as a GitHub Action or bot. P8-T08 is that product. This tree does not contain it (T4-01).
3. https://github.com/SWE-agent/SWE-agent/issues/717 — closed, 18 comments. A run that looked successful still printed "no patch to save" and wrote no diff. P8-T09 does not say a run with no patch opens no PR. not specified. Add that assertion to P8-T09. Hours delta: 0.
4. https://github.com/SWE-agent/SWE-agent/pull/35 — merged, 4 comments, on the reactions sort. The PR body lists the safeguards still in `open_pr`: draft, success, issue open, nobody assigned, no `closes #N` commit, issue not locked. P8-T09 copies the draft idea only if T4-02 is applied. The assignee skip is not specified, and a label is already an explicit opt-in, so do not add it.
5. https://github.com/korthout/backport-action/issues/470 — closed, 1 comment, on the reactions sort. Two label events, or a second run, posted error comments and tried to create the first PR again. The expected behaviour in the issue is to detect the existing branch and PR and continue. At this SHA a 422 skip posts no comment (T4-11), and a push failure can still comment (T4-12). P8-T23 does not mention a second label event. Add it there. Hours delta: 0.
6. https://github.com/korthout/backport-action/issues/379 — open, 1 comment, on the reactions sort. Backport PRs do not trigger CI, and the reporter asks for a README note pointing at the `pull_request` token limitation. P8-T20 lints the reusable workflow and does not say a backport PR must be allowed to run the tenant's tests. not specified. ADR-027 should say the backport head is a branch the tenant workflow is allowed to test. Hours delta: 0.
7. https://github.com/korthout/backport-action/issues/506 — closed, 5 comments, first on the reactions sort. `action.yml` failed to load because an expression used `github` in a context where that name was illegal. P8-T20 already runs reusable-workflow lint. Guarded.
8. https://github.com/OpenHands/software-agent-sdk/issues/1563 — closed, 34 comments. The reporter does not want the Docker socket mounted, because that is host control. P7-T12 includes the Docker socket escape probe, and P7-T05 requires no network. Guarded.
9. https://github.com/OpenHands/software-agent-sdk/issues/2078 — closed, 152 comments, top of the comments sort. The title is "[Tracker] Daily Integration Runs." The plan's CI jobs are the deterministic ones in P6-T20, P7-T17, and P8-T20. A daily live agent run is not specified, and it would spend quota, so do not add one.
10. https://github.com/dbos-inc/dbos-transact-py/issues/147 — closed, 10 comments. A scheduled workflow that raised on the first execution was not re-executed, and the reporter asked where in the schema to see the retry. That matches T4-15: a recorded exception is replayed, not run again. P6-T19 does not yet assert that. Hours delta: 0.
11. https://github.com/dbos-inc/dbos-demo-apps/issues/341 — closed, 2 comments, second on the comments sort. The reporter asks that `runStep` names inside a loop be unique so each result is stored. That issue points at a TypeScript file. The Python library keys the checkpoint by `function_id` (`dbos/_core.py` `check_existing_result`), which I did open. P6-T03 should still say the workflow body stays deterministic: inserting a step changes later function ids and, with the default app version, changes the hash that recovery filters on (T4-16). Hours delta: 0.

`dbos-inc/dbos-demo-apps` top comments issue is https://github.com/dbos-inc/dbos-demo-apps/issues/20 (closed, 3 comments, "Use ORM in Shop Demo"). not specified. `sorenlouv/backport` top comments issue is https://github.com/sorenlouv/backport/issues/27 (closed, 14 comments, "Per project configuration"). not specified. The token lesson from that repo is in the code (T4-14) and in https://github.com/sorenlouv/backport/pull/165 (merged, 1 comment, reactions sort, "Send access token via auth header"), which matches T4-04.

## Summary

17 entries. 11 issue-tracker lessons.
DBOS recovers only pending rows for the same executor id and application version, and its default LISTEN connection plus a 30-second scheduler poll stay up while the process is up. P6-T14 and ADR-022 do not name either fact.
A pull request is safe to retry only in the window before the step result is recorded. A recorded error is not run again. SWE-agent opens a new random branch instead of finding the existing PR.
The OpenHands example workflows put `GITHUB_TOKEN` in the agent job and expand untrusted text in the shell. P8-T04 and P8-T09 do not forbid that.
Hours delta for the whole note: 0. The state machine stays [ME].
