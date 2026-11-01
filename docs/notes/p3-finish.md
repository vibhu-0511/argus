# P3 finish log

Run by Claude at the owner's request, for the owner to review. Date: 2026-10-31.

## Substitution (deviation from PLAN.md)

PLAN.md's fixer row is Devstral on Mistral's free tier. The owner has no Mistral key (Free plan, `docs/quotas.md`) and will not pay. `PLAN.md` and its Mistral rows are unchanged and no Mistral number is written anywhere.

Groq has measured rows (`openai/gpt-oss-120b` is the strongest), but all 30 seeded tasks edit private dcortex Canvas files, and a free hosted tier may train on prompts. Ollama is not installed. So no hosted free tier and no local model was used. On the owner's instruction the live runs use **Claude (a session as the model)**: a Claude subagent reads what the loop shows it and replies with one JSON tool call per step. The loop, tools, sandbox, scorer and trajectory recorder are the project's own (`src/fix_loop/turn.py` adds only the file-backed model client). Nothing was sent to Groq or any free tier.

These runs are labelled `model: claude-session`. They are not $0 in plan-quota terms, they use no provider ledger (the ledger there is a self-imposed 300-request run budget, not a provider limit; no Claude row was added to `docs/quotas.md`), and they are not comparable with a Groq or Mistral run.

## What ran

**Variant A (no compaction), 29 of the 30 seeded tasks.** Resolved 20/29, Wilson 95% `[0.507695, 0.827246]`. Easy 9/10, medium 5/9, hard 6/10. The 30th task, `bug-17`, is excluded: its `bug.patch` and `golden.patch` no longer apply to platform HEAD (see `packages/fix-loop/runs/README.md`). Per-task table, run ids and caveats: that README and `packages/fix-loop/runs/p3-a-claude-results.json`.

Plan: a 3-task pilot first (`p3-pilot-*`), then the other 26 tasks in three waves of nine (`p3-a-claude-*`), after the owner approved the cost.

Cost. Loop estimate (chars/4), mean per task over the 29: 202904 tokens in, 205 out, 0 cached; mean 7.8 steps. Subagent tokens as reported by the harness, including each subagent's own prompt and tool use: 2,562,923 for the 29 valid runs (mean 88,377), 67,460 for the excluded bug-17 attempt, and 394,187 for the invalid or blocked attempts (pilot v1, two v2 runs). About 3.0M in all.

What the run shows, and what it does not:

- 9 of 29 were unresolved: 6 edited the right place with a guessed value (the ticket names no target), 3 never edited because a first search flooded the history and hit the 400000 token cap. Details and the draft labels: `docs/notes/p3-failures.md`.
- 5 of 29 stopped on `token-cap`, 1 on `step-cap`. seed-h06 (token-cap) and seed-h05 (step-cap) still scored resolved, because a cap stop scores the worktree diff and keeps its reason (ADR-008).
- The ticket text, not the loop, decided many outcomes. Resolve rate here is for one model family driven as a stateful session and says nothing about Devstral, Groq or Mistral.
- Latency was not recorded, so the latency cells stay `—`.

Bugs found and fixed in the harness during the run (driver only, `turn.py`): stdout encoding crash on non-ASCII; silent output truncation by the Bash tool (the driver now cuts at 20000 characters and says so); the scorer call no longer needs `uv`; token cap raised from 150000 to 400000 after the v1 pilot hit it on every run. Model rules (use only the two driver commands) were mostly followed. Reported slips: one `ls packages/verify` while diagnosing the workspace error; several subagents read a background-task output file to see a slow driver response; several sent two `edit` answers in parallel (see the caveats in the runs README).

## Task status

| Task | Status | One-line reason |
|---|---|---|
| P3-T17 | open | Not attempted. mini-swe-agent needs an OpenAI-compatible endpoint, and a mock-endpoint proof also needs a bash image (an install). Pinned mini is in an ignored venv at `.local/mini-venv` (from the clone at 04d809c; litellm reads `OPENAI_BASE_URL` then `OPENAI_API_BASE`). |
| P3-T18 | ticked | 29 of 30 trajectories and verdicts; `bug-17` cannot be set up on the current platform HEAD (documented exclusion). The owner said on 2026-10-31 that 29 of 30 counts. No provider ledger exists for a Claude session; the 300-request run budget is self-imposed. |
| P3-T19 | open | Not run. A Claude session keeps its own memory, so an output cap, offload or summary applied to the loop's messages would not shrink what the model has already read. Needs a stateless model (provider endpoint or Ollama). |
| P3-T20 | open | Done later with a Claude-session relay: 29 tasks run, see "Variant E on 29 tasks" below. |
| P3-T21 | open | `docs/notes/p3-failures.md` is a draft for the 9 variant A failures only; the Done-when covers the T19 runs. |
| P3-T23 | open | `docs/adr/0009-context-management.md` is a draft by Claude, status "draft, not accepted". The ablation table has only the variant A row, so it names no default. |
| P3-T33 | open | README has the run and replay commands; the phase report "This phase" row is filled from variant A. The delta cells stay `—`: P2 has no resolve rate to subtract from, and the model differs from the P0 baseline. The owner decides whether that meets the Done-when. |

Nothing was ticked in `TASKS.md`. Nothing was committed: the work is not complete, and the tree holds other uncommitted P3 files.

## Other things seen

- `packages/bench/tests/test_golden.py::test_platform_repo_and_seeded_tasks` fails before and after my changes: `task_dirs()` returns 330 (300 mutated + 30 seeded) and the test expects 30.
- At 08:20 another session added `packages/verify` to `members` in the root `pyproject.toml` and to `pnpm-workspace.yaml`. `packages/verify` has no `pyproject.toml`, so `uv run` fails in the shared checkout until that is fixed. I did not touch it.
- `run_cmd` runs on the host unless the caller passes `execute`; `turn.py` passes one that routes it to the Docker sandbox.

## Stateless per-step pilot for the context ablation (P3-T19, pilot only; run by Claude at the owner's request, for the owner to review)

Why: a Claude session keeps its own memory, so capping, offloading or summarizing the loop's messages changes nothing for it (ADR-009 draft). So each loop step here is one fresh Claude subagent. `python -m fix_loop.turn start <task> <run> none|cap|offload|summary [budget]` runs the loop statelessly: `show <run>` prints the whole message list the loop would send, `answer` records one reply and prints one status line (never the next turn). Strategies come from `src/fix_loop/strategies.py` (cap 8000 characters, offload with a 200-character head, rolling summary). Context budget 32,000 estimated tokens, a strategy runs at 80% of it (my choice, not measured). Model: the session's own model (labelled `claude-session`), one fresh subagent per step.

Scope: one task, `seed-e07`, four strategies. This is a pilot of the method and its cost, not an ablation: one task cannot rank the strategies.

| Run id | Strategy | Result | Steps | Note |
|---|---|---|---|---|
| `p4b-pilot-cap-e07` | cap | resolved, `submit` | 10 | valid |
| `p4b-pilot-offload-e07` | offload | resolved, `submit` | 20 | valid; used all 20 steps |
| `p4b-pilot-none2-e07` | none | unresolved, `token-cap` | 7 | valid; the uncompacted history passed the 400000-token cap |
| `p4b-pilot-none-e07` | none | not scored | 5 | invalid: step 5 prompt was about 1.1M characters; the subagent could not read it and answered from a partial view |
| `p4b-pilot-summary-e07` | summary | not scored | 11 | invalid from step 11: the summarizer's input was about 1 MB and it summarized a partial view |

Harness findings (fixed or open):

- Fixed in `turn.py`: the no-compaction prompt must carry the same per-message 20000-character display cut the stateful variant A runs had, otherwise a single huge `search` result makes a prompt no subagent can read. Applied to every non-summary prompt; the first `none` run was started before the fix and is kept only as an invalid record.
- Open: the summary strategy's input (all earlier turns joined) is not cut, so it can be as large as the raw tool output. Before any full run, the cut should be applied to the tool output at the source for every strategy (in `_execute`), and the summary run redone. Not done here.
- Replay cost: every call replays the whole run from `answers.jsonl` and re-executes every `run_cmd` in Docker, so the work grows with the square of the step count. A 20-step run took about 45 to 200 s per step.
- Reading: on one task the strategies cannot be ranked. `cap` and `offload` resolved; the uncompacted run hit the token cap. That is consistent with the idea that output caps help, and is not evidence for it.
- Not run: tasks `seed-e05` and `seed-e02` (the pilot was cut to one task; `p4b-pilot-*-e05` and `-e02` folders hold started runs with 0 to 2 answers and no verdict, and are not results).

Cost (estimates from the harness's per-call usage, not a summed ledger): a step costs about 67,000 to 100,000 subagent tokens (first steps about 67,000; steps with a large prompt up to about 100,000). 57 steps were taken in all, so the pilot is about 4M tokens, about twice the 2M I estimated for the e07-only pilot, because the runs ran 10 to 20 steps. A full T19 (4 strategies x 29 tasks x about 10 steps) would be roughly 80M tokens; that was not run. Wall-clock for the e07 pilot: about 2 hours of orchestration, limited by one step at a time per run.

Also run in the same session: P4-T17 with the Claude judge, about 70,000 tokens per pair, about 3.5M for the 50 pairs (see `p4-finish.md`).

Redo of the summary run (after the summarizer-input cut was added in `turn.py`, test `test_summary_strategy_cuts_each_turn_before_summarizing`): run `p4b-pilot-summary2-e07`, 10 steps, **unresolved, stop reason `retry-cap`**: three consecutive replies the loop did not parse as a tool call. The recorded replies show the cause is probably not the model: reply 2 is a plain-text summary after only one tool call, and replies 4 to 10 are all JSON tool calls, so summary requests and normal turns share one ordered answer list. Once the summary strategy fires it fires after every observation (cumulative usage stays over 80% of the budget), and a failed parse also triggers it, so the replay can pair a reply with the wrong kind of request. Root cause not confirmed; I did not debug it. The summary row was **not measured** at that point; see the guarded rerun below. Next step if you want it: a scripted-`complete` offline test of `run_fix` with `summary_strategy` and a small budget, printing the order of `complete` calls, then fix the pairing before any further spend.

Pilot summary (e07 only): cap resolved, offload resolved, none unresolved (token cap), summary not measured. Cost of the redo: 10 more steps at about 68,000 to 77,000 tokens each, about 0.7M. Pilot total now about 67 steps, about 4.7M tokens. No Ablation-table cell was filled from this pilot.

Summary pairing, debugged offline (no model calls). A scripted `complete` against `run_fix` with `summary_strategy` and a small budget shows the loop is correct: once the strategy fires it calls `complete` strictly as turn, SUMMARY, turn, SUMMARY, and so on, one summary request after every observation. In the real run the recorded replies were turn, summary, turn, JSON, turn, JSON, ...: the model-side subagents answered the summary requests in slots 4, 6, 8 and 10 with tool calls, so the loop took a tool-call string as the summary and the pairing drifted until three replies failed to parse. Root cause: the driver let a reply of the wrong kind be recorded, and a one-step subagent could not always tell a summary request from a turn.

Fix in `turn.py` (test `test_a_reply_of_the_wrong_kind_is_rejected`; fix-loop suite 54 passed): (1) each replay writes `pending.json` with the kind of the pending request; (2) `answer` rejects a tool call sent to a summary request and plain text sent to a turn, records nothing and exits 3; (3) a summary request now starts with `THIS TURN IS A SUMMARY REQUEST. REPLY WITH PLAIN TEXT ONLY, NOT JSON.` Checked end to end on a real run with no model calls (`p4b-guardcheck-summary-e07`, 2 recorded replies, both wrong-kind replies rejected). The guarded rerun is `p4b-pilot-summary3-e07` below.

Guarded rerun of the summary run: `p4b-pilot-summary3-e07` (after the reply-kind guard and the summary marker), 17 steps, **resolved, `submit`**, no rejected replies. This is the valid summary result for e07. Final pilot table, all on `seed-e07`, one run per strategy, same session model, same 32,000-token budget:

| Strategy | Run id | Result | Steps |
|---|---|---|---|
| none | `p4b-pilot-none2-e07` | unresolved, `token-cap` | 7 |
| cap | `p4b-pilot-cap-e07` | resolved, `submit` | 10 |
| offload | `p4b-pilot-offload-e07` | resolved, `submit` | 20 |
| summary | `p4b-pilot-summary3-e07` | resolved, `submit` | 17 |

Invalid and kept only as records: `p4b-pilot-none-e07` (unreadable prompt), `p4b-pilot-summary-e07` (unreadable summarizer input), `p4b-pilot-summary2-e07` (wrong-kind replies recorded, now rejected by the guard). One task and one run each cannot rank the strategies or give a rate. Cost of the whole pilot: about 84 steps at about 67,000 to 100,000 subagent tokens, about 6M tokens (an estimate from per-call usage, not a summed ledger); the guarded summary rerun alone was 17 steps, about 1.2M. A full T19 (4 strategies x 29 tasks x about 12 steps) would be roughly 100M tokens. No cell of the Ablation table in `phases/P03-fix-loop.md` was filled from this pilot. P3-T19 stays open.

## Pilot extension to three tasks (P3-T19, still a pilot; run by Claude at the owner's request, for the owner to review)

The owner asked for two more tasks after the e07 pilot. Added `seed-e05` and `seed-e08` (two easy tasks with large contexts in variant A: peak prompts 62,319 and 61,542 estimated tokens), four strategies each, run ids `p4b-pilot2-<strategy>-<task>`. Same method, same 32,000-token budget, same session model, same harness as the e07 reruns (display cut, summarizer-input cut, reply-kind guard). One run per cell.

| Task | none | cap | offload | summary |
|---|---|---|---|---|
| seed-e07 | unresolved (token-cap, 7) | resolved (10) | resolved (20) | resolved (17) |
| seed-e05 | unresolved (submit, 6) | resolved (4) | resolved (14) | unresolved (submit, 15) |
| seed-e08 | resolved (3) | resolved (3) | resolved (3) | resolved (3) |
| **resolved of 3** | 1/3 [0.061490, 0.792345] | 3/3 [0.438494, 1.000000] | 3/3 [0.438494, 1.000000] | 2/3 [0.207655, 0.938510] |

Steps in parentheses. Wilson 95% intervals computed with `fix_loop.baseline.rate_label`. **Reading:** every interval overlaps every other; three tasks cannot separate the strategies and these are not Ablation-table results. What can be said: cap and offload resolved all three, no-compaction was the weakest, summary sat between, and e08 (a small, easy fix) was resolved by all four in 3 steps, so it does not discriminate. The e05 miss under `none` is a submitted wrong fix, not a token-cap stop; `summary` on e05 also submitted a wrong fix. Offload and summary used far more steps than cap (14 and 15 against 4 on e05; 20 and 17 against 10 on e07), which is a cost the resolve rate hides. For comparison, the stateful variant A (full memory) on e05 was unresolved.

Cost: the extension was 51 steps at about 67,000 to 100,000 subagent tokens each, about 3.7M tokens (an estimate from per-call usage). The whole stateless pilot is now about 135 steps, about 9.7M tokens, over about 7 hours of wall-clock. Latency per step was not recorded in a file. The Ablation table in `phases/P03-fix-loop.md` is still empty for B, C and D; P3-T19 stays open. To fill it for the 29 tasks would take roughly 100M tokens and was not run.

## Stateless context ablation on 29 tasks (P3-T19; run by Claude at the owner's request, for the owner to review)

Method as in the pilot sections above: one fresh Claude subagent per loop step, four strategies (none, cap, offload, summary), the 29 runnable seeded tasks (`bug-17` excluded). Run ids `p4b-full-<strategy>-<task>`; e05 and e08 come from `p4b-pilot2-*`, e07 from the pilot ids in the e07 table. Every number below is printed by `packages/fix-loop/swarm/tally.py` from `verdict.json` and `trajectory.jsonl`. **One run per cell, one model (the session model, labelled `claude-session`), not comparable with Groq or Mistral rows.** The harness choices (32,000-token budget, 20,000-character message cut, a strategy running at 80% of the budget) are mine and were not measured.

| Strategy | Resolved | Unresolved | Excluded | Resolve rate over resolved+unresolved (Wilson 95%) | Mean model turns | Stop reasons | Mean est. loop tokens in / out per task | Peak prompt tokens (mean of per-task max, max) |
|---|---|---|---|---|---|---|---|---|
| none | 18 | 10 | 1 | 18/28 [0.458300, 0.792944] | 6.24 | submit 27, token-cap 2 | 100467 / 170 | 34060, 484541 |
| cap | 21 | 7 | 1 | 21/28 [0.566440, 0.873237] | 7.55 | submit 29 | 43105 / 200 | 7276, 18118 |
| offload | 20 | 8 | 1 | 20/28 [0.529404, 0.847462] | 8.97 | submit 26, step-cap 3 | 32430 / 228 | 5505, 14400 |
| summary | 17 | 12 | 0 | 17/29 [0.407375, 0.744871] | 13.31 (9.79 loop steps) | submit 21, step-cap 5, summary 2, stuck 1 | 23485 / 250 | 5180, 8339 |

Tokens are chars/4 estimates of the messages, cached tokens are 0 in every row. For `summary` the summarizer's own calls are not trajectory step rows, so its token cells undercount; its extra model turns are the summary replies (386 turns for 284 loop steps). All four intervals overlap.

**Excluded (score exit 2, counted as neither resolved nor unresolved):** `p4b-full-offload-m07`, `p4b-full-none-h08`, `p4b-full-cap-h05`. Exit 2 is the scorer's infrastructure code (missing tree, node runner failed, runner timed out at 120 s, or unparseable runner output). The driver discards the scorer's output and deletes the tree after scoring, so which of those happened is not recorded and the cause is not confirmed. For `offload-m07` the submitted diff sets `.landing-brand` to 18px where the check expects 20px, so it would most likely have scored unresolved. The machine was heavily loaded during these runs, which fits a timeout, but that is a guess. Re-scoring would need the tree rebuilt from `bug.patch` plus `diff.patch`; not done.

**Strategies disagree on 10 of 29 tasks** (none / cap / offload / summary; R resolved, U unresolved, X excluded): e02 R R R U; e05 U R R U; e07 U R R R; m02 R R R U; m03 R R R U; m05 U R R U; m07 R U X R; h03 R R U R; h05 U X U U; h08 X R R R. The other 19 agree across all four strategies.

**Reading, with the limits.** Cap has the best point estimate (21/28) and offload is next (20/28), but the intervals overlap for all four and one run per cell cannot separate them; run-to-run noise of a single subagent chain is not measured. What the files do show: `none` costs 2 to 4 times the input tokens of the others and is the only strategy with `token-cap` stops (2); `summary` has the lowest peak prompt and the highest turn count; its 5 `step-cap` runs and its 1 `stuck` run were all unresolved, and its 2 `summary` stops (the summary did not shrink; h03 and h09) were both scored resolved from the diff; offload and summary spend far more turns than cap for no better resolve rate. `summary` runs on e02, m02, m03 and m05 took 31 to 33 turns and ended unresolved while the other three strategies mostly resolved them. The stateful variant A row (20/29, full memory) is a different method and is not a baseline for these rows.

**Cost (estimate, not a summed ledger):** 1,046 model turns across the 29 x 4 cells x about 70,000 subagent tokens per step is about 73M tokens. Worker token usage is only visible inside the coordinators; no file sums it. Per-step latency was not recorded.

Odd things: workers occasionally ran one extra command or had a first reply rejected by the reply-kind guard and resent it; the one extra `sed` in `p4b-full-summary-h09` failed and changed nothing. P3-T19, P3-T21 and P3-T23 are not ticked: that is the owner's call.

## Variant E setup: mini-swe-agent through a Claude-session relay (P3-T17; run by Claude at the owner's request, for the owner to review)

Choice made by the owner: the session model is the model for variant E too, so there is no provider endpoint. `packages/fix-loop/swarm/mini/` holds the setup. `relay.py` is a local OpenAI-compatible server (`/<run id>/v1/chat/completions`). Each request is written to `runs/<run id>/mini/req-N.json` and waits for `rep-N.json`, which a fresh Claude subagent writes through `mini_turn.sh answer` (`show` prints the pending request). Every call goes through `argus_core.ledger.Ledger` (self-imposed 300-call budget, as in `turn.py`, not a provider limit). `mini_run.py` (run by `mini_run.sh` in the pinned mini venv `.local/mini-venv`, mini 2.4.6) builds `DefaultAgent` + `LitellmModel` + `DockerEnvironment` from `mini.yaml`, runs it, scores the worktree with `bench score` as `turn.py` does, writes `verdict.json`, `diff.patch`, `mini-traj.json` (mini's own JSON) and `trajectory.jsonl` (the mini message list mapped to Trajectory JSONL, one step per assistant message; checked with `Trajectory.from_jsonl`). Workers and coordinators: `step_mini.md`, `coord_mini.md`.

Settings (ADR-011 overrides): `cost_limit` 0, `cost_tracking` `ignore_errors`, `--network none` plus the Argus CPU cap (1) and memory cap (512m), worktree mounted at `/work`, checks mounted read-only at `/checks`, interpreter `["bash", "-lc"]`. The endpoint variable is `OPENAI_BASE_URL` (litellm reads it), set to `http://127.0.0.1:<port>/<run id>/v1`; `OPENAI_API_KEY` is the dummy `relay-local`, which the relay ignores. The stock observation cut (10000 characters, 5000 head and tail) stays.

Deviations from ADR-011 and from the stock setup, all mine and unmeasured:
- `step_limit` 20 (stock 0 = unlimited), the same cap as the Argus loop, because every step is a subagent. A run that hits it exits `LimitsExceeded`, recorded as `step-cap`.
- A new image `argus-mini-sandbox:p3` (`swarm/mini/Dockerfile`): the Argus sandbox base plus `apk add bash`, because mini's interpreter needs bash and the Argus image has none. The only network use is that build; runs use `--network none`.
- `mcp` (and its dependencies) was installed into the ignored mini venv with `uv pip install`, because `litellm.completion` imports it whenever `tools` is passed. Nothing in the repo's own dependencies changed.
- The model sees mini's own prompt, which prints the host's `uname` (Windows 11) while commands run in Alpine; that is stock mini behavior and was not changed.
- The scored artifact is the worktree diff through `bench score`, not mini's `submission` string.

T17 check: fixture `seed-e08`, run `p4b-mini-e08b` (6 model calls, 6 fresh subagents): **resolved**, `Submitted`, ledger shows 6 requests, `mini-traj.json` records `cost_limit` 0, `step_limit` 20, interpreter `["bash", "-lc"]`, `--network none`. `p4b-mini-e08` is an aborted first attempt (litellm needed `mcp`) with no verdict: ignore it. A stray "The system cannot find the path specified." line at the end of a run comes from mini's cleanup shell command on Windows and changes nothing.

## Variant E on 29 tasks (P3-T20; run by Claude at the owner's request, for the owner to review)

All 29 runnable seeded tasks ran once through mini-swe-agent with the setup in the section above (relay, Argus Docker sandbox, ADR-011 overrides plus `step_limit` 20, scored on the worktree diff). Run ids `p4b-mini-<task>`; for e08 the valid run is `p4b-mini-e08b`. Each task was run by its own session in batches of at most 6 coordinators, one fresh Claude subagent per model call. Every number is printed by `packages/fix-loop/swarm/tally.py` (its final section) from `verdict.json`, `trajectory.jsonl` and the `mini/req-*.json` files. **One run per task, one model (`claude-session`), not comparable with Groq or Mistral rows.**

| Variant | Resolved | Unresolved | Excluded | Rate over resolved+unresolved (Wilson 95%) | Mean model turns | Stop reasons | Mean est. loop tokens in / out per task | Peak prompt tokens (mean, max) |
|---|---|---|---|---|---|---|---|---|
| E mini-swe-agent | 19 | 10 | 0 | 19/29 [0.473448, 0.800595] | 12.76 | submit 27, step-cap 2 | 47878 / 446 | 6440, 11249 |
| A stateless (none) | 18 | 10 | 1 | 18/28 [0.458300, 0.792944] | 6.24 | submit 27, token-cap 2 | 100467 / 170 | 34060, 484541 |

Unresolved E runs: e05 and e07 (step-cap), m01, m05, m07, h01, h04, h05, h07, h10 (submit, check still failing). Paired with stateless A, E and A agree on 26 of 29 tasks: both resolved on 17, both unresolved on 9. They differ on m04 (A unresolved, E resolved), m07 (A resolved, E unresolved) and h08 (A excluded by a scorer exit 2, E resolved).

**Reading, with the limits.** By the ADR-011 rule, a framework is justified only when E's interval lies entirely above A's; E's interval [0.473, 0.801] overlaps A's [0.458, 0.793] almost completely, and the point estimates differ by one task, so this does not justify adopting mini-swe-agent and does not show it is worse. Not comparable beyond that: the interfaces differ (one `bash` tool against six typed tools), E has no token cap or stuck check and was given a step cap of 20, and the harness is mine and unmeasured. E took about twice the model turns of stateless A (12.76 against 6.24), but because mini cuts every observation at 10,000 characters its peak prompt stayed at 11,249 estimated tokens, so its total input is about half of no-compaction A and about the same as the cap row (43,105 per task).

**Caveats.** (1) Coordinators reported one worker fewer than model turns on 8 of 29 runs (e05, m05, m06, m07, h04, h05, h08, h10; the other runs reported equal counts), counts that come from the reports; request and reply files match the turn count in every run. Either a coordinator miscounted or one worker answered two requests, and the files do not show which. If a worker answered two, that step was not stateless; this is unresolved. (2) mini prints the host's `uname` (Windows) in its prompt, a stock behavior. (3) Mini's cleanup shell line fails on Windows ("The system cannot find the path specified."), harmless; the runner now removes the container itself. (4) `p4b-mini-e08` is an aborted first attempt with no verdict.

**Cost (estimate, not a ledger):** 370 model turns for variant E x about 70,000 subagent tokens per step is about 26M tokens. The ledger files (`runs/p4b-mini-*/mini/ledger.json`) hold chars/4 estimates only.

## P0 one-shot baseline redone with the session model (P0-T28 method, for the P3-T33 delta row; run by Claude at the owner's request, for the owner to review)

Why: the phase report's delta row had nothing to subtract from. P2 never resolved bugs, and the P0 baseline (`0/10`) is one `openai/gpt-oss-20b` call on 10 tasks, a different model. So the P0 method was redone with `claude-session` on all 29 runnable seeded tasks: one call per task, `argus_bench.baseline._prompt` (ticket text plus the current text of the files named in `bug.patch`), no tools, one fresh Claude subagent per task, reply = a unified diff, applied to the buggy worktree and scored with `bench score` like a loop run. Harness: `packages/fix-loop/swarm/oneshot/` (`oneshot.py`, `oneshot.sh`, `prep_all.sh`, `step_oneshot.md`); run ids `p0c-oneshot-<task>`; `swarm/tally.py` prints the section. Every number below comes from those run files.

Deviations from the P0 run, all mine and unmeasured: the model; the worker is told to reply with a unified diff only (the P0 prompt had no such line); code fences around the diff are stripped; the first answer is final, a retry is refused; the diff is applied with `git apply --recount --unidiff-zero --whitespace=nowarn` (models miscount hunk headers and leave out context lines); 29 tasks instead of 10.

| Row | Resolved | Unresolved | Rate (Wilson 95%) | Mean est. tokens in / out | Diff did not apply |
|---|---|---|---|---|---|
| one-shot, `git apply` only | 22 | 7 | 22/29 [0.578920, 0.877817] | 8322 / 257 | h02, h05, h06 |
| one-shot, then GNU `patch -l --fuzz=3` on the same saved reply (used for the delta row) | 23 | 6 | 23/29 [0.616096, 0.901541] | 8322 / 257 | h02 |

Unresolved with the fallback: m01, h01, h02, h03, h05, h07. Two re-scores used the same saved model reply and no new call: `p0c-oneshot-e02-rescore` (the first run failed `git apply` on a context-free diff, before `--unidiff-zero` was added; its verdict in `p0c-oneshot-e02` is superseded) and `p0c-oneshot-h02-lenient`, `-h05-lenient`, `-h06-lenient` (only h06 flipped, to resolved; h02 still does not apply, h05 applies and fails its check). `p0c-oneshot-check-e08` is a harness check with the golden patch, not a result.

Deltas (variant minus one-shot, points over resolved+unresolved, GNU-patch row): A stateful -10.3, A stateless -15.0, B -4.3, C -7.9, D -20.7, E -13.8. All intervals overlap the one-shot interval; the strongest case is A stateless against one-shot, 16 tasks resolved by both, 2 only by A, 7 only by the one-shot.

**Reading, with the limits.** With this model, a single call without tools resolved at least as many tasks as every loop variant, so the loop did not beat the P0 method here. This does not show the loop is no use: the one-shot prompt is given the exact files containing the bug (the P0 design), while the loop has to find them, and the seeded tasks are small fixes (the ones inspected here were one- or two-line CSS changes). The comparison also says nothing about harder tasks where the file is not known. It is one run per task, one model, and a tolerant diff applier whose effect is one task (22 against 23). The numbers do not support the hypothesis that a loop with context management beats the one-shot method on these 29 tasks; they do not refute it either, because the intervals overlap.

Cost (estimate): 29 workers, about 70,000 to 105,000 subagent tokens each, about 2.5M tokens in all (an estimate from per-call usage).
