# argus-workbench

P10: a local web UI with five screens (New issue, Live run, Review, PR raised, History) over scripted and replayed runs. It binds 127.0.0.1, has no login and calls no model. **Every run it makes is SIMULATED or REPLAY and is in no aggregate.** The PR it builds goes to an in-memory mock GitHub; no real PR is created.

**Status, in one paragraph.** Everything below was built and run on one Windows 11 machine, on 127.0.0.1. **Nothing was pushed and nothing has run on GitHub.** No model was called, in code or in tests. A real PR needs the registered GitHub App, which does not exist yet (P8 owner step). The workbench has not been hosted and must not be (see [ADR-031](../../docs/adr/0031-workbench-local-unauthenticated.md)). The judge label on the Review screen is advisory because the judge's alpha was never computed. Read the "State" column in the controls table; it is the honest one.

## Install

From the repo root (a uv workspace):

```bash
uv sync --all-packages --locked
```

`--all-packages` is needed: the workbench imports `argus-core`, `flow`, `argus-app`, `fix-loop`, `verify`, `eval` and `argus_bench` from the same workspace. Python 3.12 or newer.

## Serve

```bash
uv run --all-packages argus-workbench serve            # http://127.0.0.1:8765/
uv run --all-packages argus-workbench serve --port 9000
```

- **127.0.0.1 only.** There is no `--host` option on purpose (a test tries `--host`, `--bind`, `-H` and an abbreviation). A real start was checked with `netstat`: it listens on `127.0.0.1:<port>` only.
- **A token per start.** Each start makes a new token. It goes into the page (`<meta name="argus-token">`) and is sent in the `X-Workbench-Token` header on every request that changes something (POST, PUT, PATCH, DELETE). The command prints only its first four characters. A token in a URL, a body or a cookie does not count. A Host other than `127.0.0.1` or `localhost`, or a foreign Origin on a changing request, is refused. No CORS header is ever sent.
- No login. Another program on the same machine can read the page and get the token. ADR-031 says what that does not defend.
- If the `argus-workbench` launcher is blocked (the owner's Windows machine blocks `.exe` launchers, error 4551), use the same code as a module: `uv run --all-packages python -m argus_workbench.cli serve --port 8765`.

Environment variables (all optional):

| Variable | Default | What |
|---|---|---|
| `ARGUS_WORKBENCH_RUNS` | `.local/workbench/runs` under the repo root (git-ignored) | where run folders are written. Tests always point it at a temp folder |
| `ARGUS_WORKBENCH_RESULTS` | the P5 dashboard's list of real result files | result files for the History metrics, separated by `os.pathsep`; empty means none |
| `ARGUS_WORKBENCH_LEDGER` | `.local/quota-ledger.json` | the quota ledger the meter and the quota share read |

## The five screens

Tabs carry the label of the design spec (`docs/notes/p10-spec.json`) verbatim, plus the line "local, scripted". The labels are the spec's, not this build's: tab 4 still reads PLANNED P8 although the screen is built (mock transport only).

| # | Screen | What you do | Spec label |
|---|---|---|---|
| 1 | **New issue** | Type the issue text (required, 1 to 10,000 characters), optionally attach a PNG or JPEG screenshot (max 5 MiB, judged by its first bytes, never by its name), pick the repo and route from the allowed list, pick a SIMULATED scenario, tick "public or synthetic code only". Start creates a run folder and starts it. A refusal is a typed error shown next to its field. The GitHub-label trigger is shown as spec text only; nothing is connected | PARTLY BUILT |
| 2 | **Live run** | Watch the stage bar (Reproduce, Locate, Fix, Verify) and the step timeline fill while the run plays (polling every 700 ms, not SSE). Tokens in, out and cached per step. A quota meter. Stop ends the run. Retry makes a NEW run and never changes the old one; it is disabled while the quota is used up | PARTLY BUILT |
| 3 | **Review** | Four checks in order (pixel, overflow, axe, console) with the first failure, an advisory judge card, the before/after report in a sandboxed frame, the patch summary. Approve (disabled when the verifier failed; needs a written reason when the judge says fail), Request changes (needs a note; starts a new run), Reject (needs a listed reason). One decision per idempotency key; the server enforces every rule, the buttons only mirror them | PARTLY BUILT |
| 4 | **PR raised** | After Approve: the draft PR on the mock GitHub with title, one stable branch, body (verdict, judge label, trajectory link, report link), CI state ("not run"), backport follow-up. An empty patch gives no PR. "Approve again" finds and updates the same PR. "Mark ready for review" is always disabled and says why | PLANNED P8 |
| 5 | **History** | The list of runs with state, stop reason, decision and PR, each SIMULATED or REPLAY run with a badge. Four metrics (resolve rate with a Wilson 95% interval, tokens per bug, latency, quota share), each backed by a named real result file or shown as a dash with the reason. Simulated and replay runs are in no number | PARTLY BUILT |

## The five scenarios

Chosen on screen 1 (the run is SIMULATED either way). Steps and token counts come from the illustrative `sim` block of the spec; none is a measurement.

| Scenario | Ends in | Stop reason | Shown as | Files besides ticket, state, trajectory |
|---|---|---|---|---|
| `normal` | `awaiting-qa` | `submit` | awaiting-qa | patch, report, verdict (4 checks pass, judge `pass`) |
| `quota` | `failed` | `QuotaExceeded` (raised by the real `argus_core.ledger`) | `quota-wait` | none |
| `stuck` | `failed` | `stuck` (same tool call three times) | `stuck` | none |
| `verifier` | `failed` | `submit` | failed, "Verifier failed: overflow on /ops/horizon" | patch, report, verdict (overflow fails, judge `not run`) |
| `judge` | `awaiting-qa` | `submit` | awaiting-qa | patch, report, verdict (4 pass, judge `fail`, advisory) |

State names are `flow.states` values. `quota-wait` and `stuck` are display states derived from the stop reason, never stored.

## The runners

| Runner | What it does | Model |
|---|---|---|
| `ScriptedRunner` (`runner.py`) | Plays one of the five scenarios step by step. The quota scenario is stopped by the real ledger | none |
| `ReplayRunner` (`runner.py`) | Plays a stored `trajectory.jsonl` (validated first) one step per tick, tagged REPLAY. Writes no patch, report or verdict. Over the API: `POST /api/runs/{id}/start` with `{"replay_from": "<run id>"}` | none |
| `FixLoopRunner` (`fixloop_runner.py`) | Wraps `fix_loop.run_fix`. **Never run against a real model.** It needs a scripted model function passed in (no default), reads no key, URL or model name, builds no client, refuses shell tools unless `allow_shell=True`, and is not reachable from the HTTP API. Only tests and local scripts construct it | scripted function only |

`RunManager` (`manager.py`) starts, stops and retries runs. Stop ends a running run in `failed` with the stop reason empty and the last step `owner-stop` ("stopped by owner").

## The run folder, in short

One folder per run under the run store: `<root>/<run_id>/`. `run_id` must match `[a-z0-9-]{1,64}`; file names are never taken from a caller. Files are written atomically and checked against their schema on read.

| File | What |
|---|---|
| `ticket.json`, `intake.json` | the typed ticket; repo, route and the acknowledgement |
| `state.json` | state, stop reason, display state, origin (`SIMULATED` or `REPLAY`), scenario, retry-of |
| `trajectory.jsonl` | one step per line with tokens in, out and cached |
| `verdict.json`, `report.html`, `patch.diff` | the four checks and the judge label; the before/after report; the patch (empty means no PR) |
| `decision.json`, `pr.json` | the decision (written once); the mock PR (tagged SIMULATED) |

Full contract with schemas and who writes what: [`docs/architecture/p10.md`](../../docs/architecture/p10.md), section "Run folder contract". Example folders for every scenario: `argus_workbench.fixtures.write_all_fixtures(root=...)` (all SIMULATED).

## Tests

```bash
uv run --all-packages python -m pytest packages/workbench/tests -q
```

607 passed in about 65 s on 2026-11-10 (Windows 11, no Postgres, no network, no model). One package at a time; do not run one pytest across packages. `tests/test_no_model.py` checks that importing every module reads no key, token or model-name variable, and that the source names no model client.

The four break-its (inert rendering, hostile uploads, forged requests, double approve) are `tests/test_break_it_t10.py`, `test_break_it_t11.py`, `test_break_forged.py` and `test_break_double_approve.py`; each was run against a mutated build and failed. Index: [`docs/notes/p10-break-its.md`](../../docs/notes/p10-break-its.md).

## The controls

State words: **tested locally** = a test from a run on this machine. **seen in a browser** = clicked in a real Chromium (Playwright) on 127.0.0.1 against a local server, screenshots in `docs/shots/`. **mock** = runs against a stand-in (mock GitHub, scripted runner, fixture file), never the real thing. **not run** = not run at all.

| Control | What it does | Where | State |
|---|---|---|---|
| `argus-workbench serve` | 127.0.0.1 only, no `--host`, per-start token | `cli.py`, `server.py` | Tested locally; **seen in a browser** (served on port 8765, `netstat` showed `127.0.0.1` only). The `.exe` launcher is blocked on the owner's machine; the module form was used |
| Request guards | token, Host and Origin checks, CSP, no CORS | `security.py`; `test_security.py`, `test_break_forged.py` | Tested locally; four mutated builds failed |
| Screen 1, typed intake | caps, magic bytes, allowed lists, acknowledgement, typed errors | `routes/issues.py`; `test_issues.py`, `test_break_it_t11.py` | Tested locally; **seen in a browser**. Stored ticket passes `bench validate` only next to a task's four other files (the bare folder fails, by design; see `docs/notes/p10-t03.md`) |
| Screen 1, GitHub-label trigger | spec text only | `issue.js` | **Not built.** Only the typed trigger works; `github` is refused with `trigger_not_typed` |
| Scripted scenarios (5) | normal, quota, stuck, verifier, judge | `runner.py`; `test_runner.py`, `test_e2e_http.py` | Tested locally; all five **seen in a browser**. **Simulated**: the numbers are the spec's illustration |
| Quota scenario | stopped by the real ledger | `argus_core.ledger` | Tested locally. The throwaway ledger is a stand-in for a real provider quota |
| `ReplayRunner` | plays a stored trajectory, REPLAY | `runner.py`; `test_runner.py`, `test_runs_control.py` | Tested locally. Not clicked in a browser (the page has no replay control; API only) |
| `FixLoopRunner` | wraps `fix_loop.run_fix` | `fixloop_runner.py`; `test_fixloop_runner.py` | Tested locally with a **scripted model**. Not reachable from the page. **Never run against a real model** |
| Screen 2, live run | stage bar, timeline, tokens, meter, Stop, Retry | `routes/runs_view.py`, `meter.py`, `run.js`; `test_runs_view.py` | Tested locally; **seen in a browser** (Stop, Retry, growing timeline). Quota meter rows are ILLUSTRATIVE; with no ledger file the meter is a dash |
| Retry after the quota reset | enabled at 00:00 UTC next day | `manager.py` | Tested locally. **Not seen in a browser** (needs the day to roll) |
| Screen 3, review | four checks, advisory judge, sandboxed report, decision rules | `routes/review.py`, `decisions.py`; `test_review.py` | Tested locally; Approve, the disabled Approve and the judge reason **seen in a browser**. **Request changes and Reject were not clicked in a browser** (server side tested) |
| Judge label | pass, fail or not run, advisory | `verdict.json` | **Mock.** No judge runs in P10; the label is scripted. Alpha was never computed (100 null labels), so it is advisory |
| Screen 4, PR raised | draft PR with evidence, one stable branch, update on repeat, no PR for an empty patch | `pull_request.py`, `mock_github.py`; `test_pr.py` | Tested locally; **seen in a browser**. **Mock GitHub only**: the URL ends in `.invalid`, no network call. Mark ready, merged and conflict states are not built |
| Double approve | one decision and one PR under races | `decisions.py`, `pull_request.py`; `test_break_double_approve.py` | Tested locally; failed on a mutated build. One process only: two server processes on one folder are not covered |
| Screen 5, history | run list, four metrics from real result files, badge, exclusion | `routes/history.py`, `history_metrics.py`; `test_history.py` | Tested locally; **seen in a browser**. Three metrics read `packages/eval/results/ablation-B.json`, which is **not a P10 result** (an earlier phase's run). Quota share is a dash (no tenant ledger file) |
| Inert rendering | text stays text on every screen, report in a sandboxed frame | `static/dom.js`, `security.py`; `test_break_it_t10.py` | Tested locally; failed on a mutated build; checked by hand in a browser for the Review and Issue screens |
| End-to-end walk | issue, run, review, PR, history | `test_e2e_http.py`; `docs/notes/p10-t14.md` | HTTP walk tested locally (6 tests); browser walk **seen**, 23 screenshots. Chromium only |
| CI job for the workbench | none exists | `.github/workflows/` | **Not run.** No workflow was written for this package; nothing ran on GitHub |
| ADR-031 | local, file-backed, unauthenticated; what it does not defend | `docs/adr/0031-workbench-local-unauthenticated.md` | Written by Claude, **proposed**, the owner decides |

## Owner-only steps

None of these is done, and none can be done from this package.

| Step | Why only the owner | Where |
|---|---|---|
| Register the GitHub App, install it, put its id, key and webhook secret in Render | needs the owner's GitHub account and secrets. Until then no real PR exists; the PR screen only talks to the mock | P8 steps: [`p8-t02-owner-steps.md`](../../docs/notes/p8-t02-owner-steps.md), [`p8-t03-owner-steps.md`](../../docs/notes/p8-t03-owner-steps.md) |
| A real PR from an approved run | needs the registered App and a model key for a real run (`argus_app.pr` has code for it; no running service calls it) | [`packages/app/README.md`](../app/README.md) |
| Host the workbench | not defended: no login, no tenant isolation, no rate limit, no TLS. It needs a new design and a new ADR | ADR-031, section 2 |
| Calibrate the judge | a person must fill the 100 labels in `packages/verify/fixtures/calibration/labels.json`; alpha of at least 0.80 before the label can stop being advisory | ADR-013, `docs/notes/p4-runtime-judge.md` |
| Real runs for History | a real model run is the only thing that can give History a number of its own. The workbench makes none | `packages/eval` |
| Push the branch and see the first CI run | the branch was not pushed | owner |
| Decide the open tick boxes | `TASKS.md` P10-T03 (bench-validate reading), P10-T07 (Request changes and Reject not clicked in a browser) and P10-T10 (the PR-body clause was skipped when written) are left unticked by their authors | `docs/notes/p10-t03.md`, `p10-t07.md`, `p10-break-it-t10.md` |
| Fix the spec tab label for screen 4 (reads PLANNED P8, the screen is built) | the label is the spec's text, copied verbatim by rule | `docs/notes/p10-spec.json` |

## Where things are

| Path | What |
|---|---|
| `src/argus_workbench/` | `store`, `errors`, `spec`, `fixtures`, `cli`, `server`, `security`, `runner`, `manager`, `fixloop_runner`, `decisions`, `pull_request`, `mock_github`, `meter`, `history_metrics`, `routes/`, `static/` |
| `tests/` | one file per task plus the four break-its |
| `docs/shots/` | screenshots from the browser run (T14) |
| `../../docs/architecture/p10.md` | the architecture agreements, the run folder contract and one section per task |
| `../../docs/notes/p10-*.md` | spec, waves, per-task notes, the four break-it write-ups |
| `../../phases/P10-argus-workbench.md` | tasks and the phase report against P8 |
