# ADR-019: Skill trust model

Status: proposed (P5.5-T11), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. Revisit when a second reviewer exists, when a skill may carry scripts, or after the first reviewed skills have been through the break-its (P5.5-T13 to T16).

## Context

A skill is a Markdown file the agent can load into its context during a fix run (`packages/skills/skills/<name>/SKILL.md`, loaded by `fix_loop.skills`). Its text is read by the model as instructions. So a skill is a way to change what the agent does, and an edit to a skill is an edit to the agent. The question is what the loader checks before a skill can influence a run, and what it still cannot check.

Everything below is read from the code and tests on the P5.5 integration branch as they are now. At this commit `packages/skills/skills.lock.json` has no entries and `packages/skills/skills` holds no reviewed skill, so the model has been exercised by unit tests (`packages/fix-loop/tests/test_skill_trust.py`, `test_skills.py`, `packages/skills/tests/test_pin.py`, `test_lint.py`) and not yet on a real reviewed skill. The break-it runs (T13 to T16) are separate and are not evidence in this ADR.

## Decision

### What is trusted

| Trusted | Where it lives | Why |
|---|---|---|
| The owner's sign-off | an entry in `packages/skills/skills.lock.json`: `reviewed: true`, `sha256`, `reviewed_by`, `reviewed_on`. Written by `python -m skills.pin NAME --by WHO` (`skills/pin.py`) | The lock is the anchor. A skill file is the thing that gets edited, so a flag inside it proves nothing. |
| The loader and the tool list | `fix_loop.skills` (`trust_refusal`, `tool_denied`) and `fix_loop.tools.ALLOW` | Code reviewed like any other code in the repo. |
| The sandbox | `fix_loop.sandbox.run` (ADR-010) when the caller uses it | See the run-time section: the allowlist does not replace it. |

Not trusted, whatever it says: the whole SKILL.md (body, `description`, every frontmatter field), including `metadata.argus-status`, which is a label for people and the lint and which the loader never reads.

### What is verified at load time

`load_skills(directory, lock)` calls `_load_one` for each skill folder, at the start of a run (`run_fix` in `loop.py`). The checks run in this order and the first failure stops the skill. Each failure is a typed `Reason`, is logged as `skill refused: <name> (<reason>): <detail>`, and leaves the skill out of the catalog in the system message, out of the `name` enum of `tool_spec`, and unknown to `load_skill` (it answers `not-found`; `test_a_refused_skill_is_not_offered_or_loadable_in_a_run`).

| # | Check | Code | Reason | Detail |
|---|---|---|---|---|
| 1 | Strict frontmatter | `_parse`, `_check_fields`, `_StrictLoader` | `bad-frontmatter` | UTF-8; starts with `---` and has a closing `---`; YAML loaded with a `SafeLoader` that rejects a repeated key; only the six spec fields in `FIELDS` (so a field like `reviewed: true` is refused, it cannot look like a control); `name` is 1 to 64 lowercase letters, digits and single hyphens and equals the directory name; `description` is 1 to 1,024 characters; `compatibility` is at most 500; `metadata` maps strings to strings. Tested in `test_bad_frontmatter`. |
| 2 | Size limit | `MAX_BODY_CHARS = 8000` in `_load_one` | `too-large` | The body (after the closing `---`, trimmed, CRLF read as LF) is at most 8,000 characters: 8,000 passes, 8,001 fails (`test_body_limit_boundary`). |
| 3 | Review flag | `trust_refusal` | `unreviewed` | No lock entry, or `reviewed` is not `true`. A draft has no entry, so a draft is refused. |
| 4 | Content-hash pin | `trust_refusal`, `content_hash` | `not-pinned`, `hash-mismatch` | A reviewed entry must carry a 64-character lowercase hex `sha256` (`not-pinned` if not). The file must hash to it (`hash-mismatch` if not). The hash is SHA-256 of the whole file with CRLF read as LF, so a Windows checkout gives the same hash. It covers the frontmatter, so a change to `allowed-tools` or `argus-status` after review is a `hash-mismatch`. The hash and the parse use the same bytes (`raw`), so what was pinned is what is loaded. |
| 5 | Tool allowlist at load | `trust_refusal` | `tool-not-allowed` | Every name in `allowed-tools` must be one of `fix_loop.tools.ALLOW` (`read_file list_dir search edit run_cmd submit ast_grep`). Bare names only: `Bash(curl:*)` is refused. |

The lock fails closed. A missing, unreadable, wrong-version or wrongly shaped `skills.lock.json` gives an empty map, so every skill is `unreviewed`; the problem is logged at error level and the run goes on without skills (`lock_skills`, `read_lock`, `test_a_missing_or_broken_lock_trusts_nothing`). The lock is read from the parent of the skills directory unless a path is passed.

### What is enforced at run time

`tool_denied(skills, loaded, name)`, called in `loop.py` right before the tool runs (`tool_denied(...) or act(...)`):

- While at least one skill is loaded, the agent may call only the tools that every loaded skill allows, intersected with the loop's tools. A skill can narrow the tools and never widen them. Loading a narrow skill after a wide one narrows the run (`test_loaded_skills_narrow_the_tools_and_never_widen`).
- A loaded skill with no `allowed-tools` gets the read-only set `READ_ONLY` (`read_file list_dir search ast_grep`). A fix skill must list `edit` to be able to fix.
- `submit` and `load_skill` always pass. A run must be able to end, and without this a skill without `submit` would hold the run until the step cap.
- With nothing loaded there is no limit: a run without a loaded skill behaves as it did before skills existed.
- A refused call is a `ToolError` with code `not-allowed` and a message that starts `tool-not-allowed:`. `ToolErrorCode` (and its JSON schema) has no `tool-not-allowed` member, so the step is stored with `tool_error: "not-allowed"` and the reason is in the message text (`test_run_refuses_a_tool_outside_the_loaded_skills_allowlist`).
- The check looks at the tool name only. It does not look at arguments: an allowed `edit` may write any file inside the worktree, and an allowed `run_cmd` may run any command.

### What the lint adds in CI

`python -m skills.lint` (`packages/skills/src/skills/lint.py`, workflow `.github/workflows/skills-lint.yml`, on a push or pull request that touches `packages/skills/**` or `fix_loop/skills.py`). No model call and no network. It calls the loader's own `_parse`, `MAX_BODY_CHARS`, `lock_skills` and `trust_refusal`, so the reasons mean the same as at load time (`test_every_lint_reason_is_the_loaders_reason`). It adds:

- any file in a skill folder other than `SKILL.md` (v1 has no scripts or resource files);
- a lock entry for a skill that no longer exists;
- a missing or unusable lock file, when there is at least one skill folder;
- a skill whose frontmatter says `argus-status: reviewed` but has no reviewed lock entry.

A draft with no reviewed entry and no such claim passes the lint, because it is the normal state before review (the loader still refuses it). The lint does not yet check `argus-status: unreviewed` on a skill the lock calls reviewed, `argus-archetype` when reviewed, or `argus-sources` against the held-out ids. The lint is a pre-merge check; it adds nothing at run time. The workflow has not run on GitHub yet, because the branch is not pushed.

## Alternatives

- **The review flag inside the SKILL.md.** Rejected: whoever can edit the skill can edit the flag. Today `argus-status` is only a label, and a file that says `reviewed` with no lock entry is still refused (`test_no_lock_entry_means_unreviewed_even_if_the_file_says_reviewed`).
- **A hash in the lock but no review flag.** Rejected: a hash says the file did not change, not that anyone read it. `pin` writes both, and only when the loader would accept the skill.
- **Signed skills (GPG or Sigstore).** Not chosen: one owner and no key management in this project. The lock diff in a pull request is the control. Revisit with a second reviewer.
- **Tool patterns such as `Bash(curl:*)`.** Rejected: the allowlist is bare names from `ALLOW`, so there is nothing to parse and nothing to escape. A pattern would also suggest that argument-level control exists, and it does not.
- **A run-time check that also covers runs with no skill loaded.** Not built: it would change every run without a skill. The sandbox is the control for those.

## Consequences

- A draft cannot influence a run until the owner reads it, edits it and runs `skills.pin`. Any later edit, even a changed character in the description, needs a new pin.
- Review is one act the owner can repeat and the lint and loader can both check: the lock diff in the pull request shows who approved which hash.
- The cost is friction: every edit of a reviewed skill goes through the owner again.

## What this does not show, and the residual risk

- **A reviewed skill can be wrong or stale.** The hash pins bytes. Nothing checks that a file or path the body names still exists in the platform repo, nothing re-reviews a skill when the repo changes, and nothing measures whether a loaded skill helps (T07, T08, T15 and T16 are the planned evidence).
- **The owner is the single reviewer.** `skills.pin` does not authenticate anyone: `--by` is free text, and `reviewed_by` and `reviewed_on` are written but never read by the loader. The lock and the skills are in one repository and there is no `CODEOWNERS` file, so anyone who can commit both can approve their own skill. The control is review of the lock diff. This ADR does not add branch protection.
- **Prompt injection through a skill body.** `load_skill` returns the body as a tool result and the model is told to follow it, so the body has the weight of instructions by design. A reviewed body that contains a harmful instruction, or a tricked reviewer, is not caught by any check here. The `description` is more exposed than the body: it is in the system message of every run from the first step, before any skill is loaded, and it has no size limit other than 1,024 characters.
- **The hash pins the file, not its meaning.** Two identical files mean different things when the repo around them changes, and a body that is accurate today can be misleading after a refactor. The hash also ignores line endings by design.
- **The allowlist is not a sandbox.** It limits tool names after a skill is loaded, only while loaded, and the model chooses whether to load one. It does not stop a skill that allows `edit` from writing any file in the worktree, or one that allows `run_cmd` from running any command. The default `run_cmd` in `tools._run` is a host shell with the worktree as the working directory; the Docker sandbox with `--network none` and a read-only `/checks` mount (ADR-010) applies only when the caller passes `execute` that uses `sandbox.run`, as `fix_loop.turn`, `eval.t14_turn` and the live path of `eval.ablation` do. The break-its T13 and T14 are meant to test that boundary.
- **Refusals are logged, not surfaced.** `run_fix` keeps only the loadable skills; a refused skill is visible in the log, not in the stored trajectory.
- **Not run on a real skill.** See the Context.
