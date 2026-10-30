# Ops-console lane: 4 Argus production-console screens

Source siblings live under `C:\Users\vibha\Downloads\data\dcortex\dcortex_claude\` (abbreviated `dcx/`). Read-only. No `.env`/key files opened.
**All values marked ILLUSTRATIVE are layout placeholders, not results.** Real values are tagged `[real]` with their source. Argus results cells stay `—` (PLAN.md:24).

## 0. What the siblings actually give us

### 0.1 Visual language (extracted)
| Aspect | Extracted | Source |
|---|---|---|
| Palette (dark = source of truth) | navy grounds `#0a0f1a / #101828 / #16233a`; ink `#e6edf7 / #8494ac / #5a6a85`; borders `#1e2a40 / #2a3a58`; accent `#2563eb` (hover `#1d4ed8`, selected `#1e3a8a`); success `#34d399`, warning `#ffb547`, error `#f87171`, info `#60a5fa`; categorical teal/fuchsia/sky/violet | `dcx/dcortex-platform/apps/canvas/src/styles/tokens.css:13-76` |
| Light theme | paper `#f8f9fa/#fff`, same accent, darker status inks (`#059669 / #b45309 / #b91c1c`) via `html[data-theme="light"]` | `tokens.css:79-128` |
| Rule: tokens only | "Components NEVER hardcode colors"; white-on-accent must use `--text-on-accent`, tested | `tokens.css:11-12`; `dcx/dcortex-platform/knowledge-base/decisions/console-radar-theme.md:60-69` |
| Type | IBM Plex Sans (UI) + IBM Plex Mono (numbers, times, codes, table data), bundled OFL, no external font host; `.mono` = tabular-nums | `tokens.css:1-9,58-59,138-141`; `console-radar-theme.md:20-22` |
| Density | body 14px; table 12.5px; `glabel` 10px uppercase +0.05em; pill 10px; row height 30px (`--rowH`), 54px min for radar rows; KPI value 26-32px mono | `tokens.css:130-136,179-186,238-251`; `radar.css:116,160` |
| Radii/shadow | 6/8/12px; cards 12px with 1px border + `shadow-sm` | `tokens.css:54-56,166-174` |
| Status = colour **and** text, never colour alone | StatusPill kinds `info warn ok err neutral fuchsia sky violet`, tint via `color-mix(accent, transparent 80%)` | `dcx/dcortex-platform/platform/canvas-ui/src/StatusPill.tsx:3-6`; `tokens.css:153-160` |
| Heat cells | `heat-1/2/3` amber→red tints relative to busiest cell | `tokens.css:264-267` |
| Motion | live dot pulses; spinner on pending action ("a slow call never looks like a dead button"); `prefers-reduced-motion` slows spinners | `radar.css:353-355`; `ops.css:146-150` |

### 0.2 Console patterns found (with component names)
| Pattern | Where | Component / class | Reuse for |
|---|---|---|---|
| Shell: header + icon rail + body + optional sidebar/toolbar | `dcx/dcortex-platform/platform/canvas-ui/src/Shell.tsx:20-39` (`ShellProps`: brand, logo, controls, rail, sidebar, toolbar) | `Shell`, `ConsoleHeader` | all four screens |
| KPI strip: 4 tiles, click toggles a filtered view; top border amber for "needs action" | `dcx/.../apps/canvas/src/ops/radar.css:111-122`; `Radar.tsx:912-925` | `radar-kpi`, `radar-kpi--action` | Run board counters, Eval headline |
| KPI card with refresh + split pill footer | `canvas-ui/src/KpiCard.tsx` | `KpiGrid`, `KpiCard` (`variant` red/green/amber/teal) | Eval + quota |
| Review queue: grouped `rcard` cards, title + right badge + meta, active = warning ring; tabs "Needs Review / Done" with counts | `canvas-ui/src/ReviewQueue.tsx`, `ReviewSidebar.tsx`; `tokens.css:166-177` | `ReviewQueue`, `ReviewSidebar` | QA verdict inbox |
| Sortable, paged, CSV-exportable table with row-expand detail | `canvas-ui/src/DataTable.tsx:22-56` (`columns[{key,header,render,sortValue,csvValue,cellClass}]`, `rowDetail`, `csvFileName`, `emptyLabel`) | `DataTable` | Run list, eval table, ledger |
| Bank × risk matrix with severity chips + counts per cell | `canvas-ui/src/MonitorMatrix.tsx:1-50`; `styles.css:380-398` (`mon-cell`, `mon-chip.crit`) | `MonitorMatrix` | State × phase board |
| Timeline: 24 h track, draggable window handles with `role=slider` + `aria-valuetext`, density bars above, "now" marker, key steps (arrows ±15 min, PgUp/PgDn ±60) | `dcx/.../ops/Timeline.tsx:130-143,184-205`; `ops.css:36-54` | `Timeline` | Trajectory step scrubber |
| Segmented control (one outer border, square seams) | `ops.css:11-23` | `.ops-view`, `.ops-timeline-rule` | State/variant switches |
| Detail modal: status strip pills, two-card legs, progress track, sections with mono uppercase `h3` | `ops.css:142-200` | `.ops-detail`, `.ops-progress-track` | Run detail, verdict detail |
| Feed freshness pill: live dot / amber "stale" / amber "replay" + stale banner | `Radar.tsx:874-883,1041`; `radar.css:66-68,86,152` | `radar-feed-pill--stale/--replay`, `radar-stale` | Slow, stale and fixture-replay states |
| Locked / selected item card with facts grid + primary/secondary actions | `radar.css:130-150` | `radar-locked*`, `radar-primary`, `radar-secondary` | QA decision pane |
| Append-only audit ledger, HMAC-chained, with a "chain verified / broken at seq N" pill; `config:read` gate shows a distinct "not permitted" state; error state separate | `dcx/.../screens/AuditLog.tsx:9-12,70-85` | `AuditLog` + `DataTable` + `StatusPill` | Approval/audit trail on screens 3, 4 |
| Decision with a 409 "already decided by X" race path (winner actor + decision returned) | `dcx/.../desk/DeskCasePane.tsx:187-200` | `submit()` → `onAlreadyDecided` | Two QA reviewers racing on one PR |
| Run detail: status colour (completed emerald / failed red / else amber), Input/Output/Context `pre` blocks, log lines `time LEVEL [nodeId] message`, "View trace" link, "No logs available" empty text | `dcx/dcortex-agent-builder/src/app/runs/[id]/page.tsx:95-110,150-180` | `RunDetailPage` | Trajectory step detail |
| Infra health tiles ok/warn/bad, 30 s poll, orphan detection with a confirm dialog before a destructive stop | `dcx/dcortex-agent-dock/portal-ui/src/AdminHealth.tsx:17,40,47-60,100-118` | `HealthPanel` | Stuck-run reaper, sandbox health |
| Usage: stat tiles + per-day table with inline bar; "Days are UTC, the same clock your daily token quota resets on"; token breakdown in a tooltip (in/out/cache) | `dcx/dcortex-agent-dock/portal-ui/src/MyUsage.tsx:116,135-176` | `stat-tile`, `my-usage-bar` | Quota ledger |
| Stuck-run recovery: non-terminal runs past `timeoutMs + 10 s grace` are marked FAILED with a reason, attempt count preserved | `dcx/job-scheduler-service/src/scheduler/recoverStaleJobRuns.ts:3-4,17-45` | `recoverStaleJobRuns` | Stuck-run state + reaper |
| Run listing API: `?limit&offset`, returns `{total, limit, offset, runs}`, newest first, 404 if job missing | `dcx/job-scheduler-service/src/routes/runs.ts:7-27` | | Run board pagination |

Not found: a real "approvals" screen with before/after images (dcortex's closest is the desk case pane approve/decline, and ReviewSidebar). The screenshot-diff review in screen 3 is **new for Argus**; it borrows the queue + decision shape, not a sibling image viewer. (`copa-services` and `dcortex-agent-builder` `/ops` are backends or agent UIs; `copa-services` has no UI to borrow.)

### 0.3 Proposed Argus tokens
Reuse the dcortex tokens verbatim (same names) so one stylesheet works; add only what Argus needs. Full list in the JSON `designTokens.proposed`.
- `--state-*` for ticket states, `--verdict-pass/fail/error/advisory`, `--phase-p0…p9` (re-use the PLAN.md architecture colours, PLAN.md:134-145, as tints only).
- `--illustrative` hatch overlay (diagonal stripes + "ILLUSTRATIVE" corner label) on any placeholder cell.
- `--fixture` amber badge `REPLAY · host=fixture` on any run whose `meta.host == "fixture"` (see edge case E1).
- Typography unchanged: Plex Sans/Mono. Argus has no font-licence problem (OFL).

## 1. Shared shell
Left rail: **Runs · Trajectory · Verdicts · Eval & Quota**; header carries: profile (`personal`/`company`, `config/profiles.md`), UTC clock + "quota resets 00:00 UTC" (the ledger rolls on UTC date: `packages/argus-core/src/argus_core/ledger.py:117-120`, `now().date()`; the docs/quotas.md header says daily), freshness pill (live/stale/replay), theme toggle. Same dark/light switch as dcortex.

## 2. Screen 1: Run board (P6 flow)

- **Purpose:** see every ticket by workflow state, where it is stuck, and how much quota is left before launching another run.
- **Users:** the owner (operator and QA). Later the P8 tenant admin.
- **Layout:** header KPI strip (4 tiles) → `MonitorMatrix`-style grid: **rows = ticket states, columns = phase waves** → below it a `DataTable` run list. Right side: quota meter column.
- **Data (real field names):**
  - Ticket: `ticket.id`, `ticket.text` (truncate), `ticket.screenshot` present? (`packages/argus-core/schemas/ticket.schema.json`).
  - Task meta (bench runs only): `meta.tier` (easy/medium/hard), `meta.archetype`, `meta.source` (seeded/mutated), `meta.seed` (`task.schema.json`, `TaskMeta`).
  - Run: `meta.run_id`, `meta.task_id`, `meta.model`, `meta.host`, `meta.prompt_hash`, `meta.git_commit` (`trajectory.schema.json` `TrajectoryMeta`); last step's `stop_reason` (`StopReason`: submit, step-cap, token-cap, QuotaExceeded, stuck, consecutive-timeout, retry-cap, tool-unavailable).
  - Workflow state: **proposed** list, P6-T02 owns the real one (`phases/P06-argus-flow.md:38`): `queued → reproducing → locating → fixing → verifying → awaiting-qa → pr-draft → done`, plus `failed`, `stuck`, `quota-wait`, `timed-out-qa`. Only `awaiting-qa` and `done` are named in the docs today (`P06:44`, `P06:39`).
  - Quota meters per model from ledger state: `models[model].requests / tokens / cached` vs `docs/quotas.md` limits `requests_per_day 1000, tokens_per_day 200000, requests_per_minute 30, tokens_per_minute 8000` for `openai/gpt-oss-20b` `[real]` (`docs/quotas.md:42-47`; ledger `_bucket` fields `ledger.py:112-115`).
  - Wave strip: tasks done / total from TASKS.md (49 of 272 `[x]` per BRIEF; unverified here) and the P-phase colour chips.
- **Actions:** open run → Screen 2; filter by state/tier/archetype/host; "Run next" (disabled when ledger would refuse, shows which limit); "Retry" on a failed run (new `run_id`, never mutates the old); "Mark stuck → fail" (confirm dialog, mirrors the orphan-stop pattern `AdminHealth.tsx:47-60`); CSV export of the list.
- **States:**
  | State | Presentation |
  |---|---|
  | Loading | skeleton rows; KPI values `aria-busy` (as `Radar.tsx:922`) |
  | Empty | "No tickets yet. Run `bench` or file a ticket" + command; counts show `0`, never `—` |
  | Error | red pill with message; panel keeps last data (AdminHealth keeps last state on failed poll, `AdminHealth.tsx:33-35`) |
  | Slow / stale | amber freshness pill "stale N min" + `radar-stale`-style banner; Render cold start (~1 min, PLAN.md:302) shows "service waking" not an error |
  | Quota exhausted | meter turns red, row `quota-wait` with "resets 00:00 UTC (in 7 h 12 m)"; "Run next" disabled; **no retry button spam** |
  | Stuck run | non-terminal for > timeout + grace → amber `stuck` chip with age; reaper action (see `recoverStaleJobRuns.ts:17-45`) |
- **Edge cases:** see E1 (fixture runs), E2 (day roll mid-run), E3 (webhook duplicate → one row, `SetWorkflowID(ticket_id)` `P06:42`), E7 (unknown model → ledger refuses, `ledger.py:83` `unknown-model`).

## 3. Screen 2: Trajectory viewer (P1/P3/P5)

- **Purpose:** replay how the agent got to its answer: step order, tool calls, tokens, why it stopped. This is the trajectory-level eval view P5 argues for (`P05` goal).
- **Users:** the owner while debugging a run or writing a failure taxonomy (P3).
- **Layout:** header = run facts (meta) + stop-reason pill. Left: step timeline (reuse `Timeline` density bars = tokens per step; draggable window to zoom). Right: step detail (`Run detail` style `pre` blocks). Bottom: token strip (in/out/cached stacked).
- **Data (real, `trajectory.schema.json`):** header `meta{run_id, task_id, model, host, prompt_hash, git_commit, seed}`; per step `index, kind="step", tokens_in, tokens_out, tokens_cached, stop_reason, raw_response, message, tool_name, tool_error`. `raw_response` keeps a rejected tool call visible to replay (schema description). Tool names in P1: navigate, click, type, screenshot, snapshot, assert-visible (`packages/repro-agent/schemas/*.schema.json`).
- **Derived (P5-T02, not built yet):** steps, tool-error rate, redundant-call rate, stuck rate, recover-after-gate-failure rate (`PLAN.md:287`). Show `—` until formulas in `docs/metrics.md` exist.
- **Actions:** scrub/step with arrow keys (as Timeline); filter to tool errors; copy `raw_response`; open the verifier verdict for the same `run_id` (Screen 3); "Open trace in Langfuse" link (P5-T07) shown only if configured; download JSONL.
- **States:**
  | State | Presentation |
  |---|---|
  | Loading | step list skeleton; header from `meta` line shown first (first JSONL line) |
  | Empty | trajectory with `meta` and zero steps: "Run started, no step recorded" (valid per schema, `steps` may be empty) |
  | Error | schema validation failure → red pill with the pydantic path; offer raw file download (`extra="forbid"`: any unknown field is an error) |
  | Slow | large JSONL streams in; show "N of M steps" |
  | Quota exhausted | last step `stop_reason=QuotaExceeded`: banner names the model + limit + `used/cap` (the `QuotaExceeded` message is `"{model} would exceed {limit}: {used} of {cap}"`, `ledger.py:18-24`); no further steps are expected |
  | Stuck | `stop_reason=stuck` or `consecutive-timeout`: highlight the repeated tool call pair |
- **Edge cases:** E1 (fixture trajectories have 1 step with `tokens_in=1, tokens_out=1` `[real]`, `runs/text-only/seed-e01/trajectory.jsonl` → label "REPLAY, token counts not real"); step with `tool_error` but `stop_reason=null`; `tokens_cached` absent → defaults 0 (schema); last step with null `stop_reason` = run still live or crashed (check freshness); secrets: `raw_response` may contain page text, treat as untrusted, render as text, never HTML.

## 4. Screen 3: Verifier verdict review (P4/P6)

- **Purpose:** the human QA gate. Show before vs after for the fixed route, the four deterministic checks, the judge label, and let QA approve or reject the PR. Judge never overrides a passed check run (`P04:6`); deterministic checks are the hard gate.
- **Users:** QA (you, then tenant reviewers in P8).
- **Layout:** `ReviewSidebar` queue at left (tabs "Needs QA" / "Decided", grouped by `tier`/archetype). Centre: **before / after / diff** triptych with a slider overlay and a changed-pixel-ratio readout. Right: check list (pixel, overflow, axe, console) + judge card + decision buttons (`radar-primary` approve, `radar-secondary` reject). Foot: audit rows (`AuditLog` pattern).
- **Data:**
  - Real today (bench scorer): `Verdict{task_id, ok, checks[{type: pixel_diff|bounding_box|computed_style, ok, reason}], log}` (`packages/bench/src/argus_bench/verdict.py:13-24`); scorer exit 0 pass, 1 fail, 2 infra error (`score.py:63-117`).
  - Real today (repro): `Verdict` enum `valid | passes-on-bug | fails-on-golden | error` (`packages/repro-agent/src/repro_agent/verify.py:16-20`).
  - **Proposed** P4 verdict (P4-T06 "one structured verdict with per-check results and first-failure reason"): `checks[{name: pixel|overflow|axe|console, status: pass|fail|error|skipped, route, detail, rule_ids[]}]`, `first_failure`, `short_circuited: bool`, `judge{label: pass|fail|error, family, model, order_disagreement, alpha_of_judge_run}`, `judge_advisory: bool`. Axe lists rule ids and only new violations vs clean baseline (P4-T04); pixel diff uses a changed-pixel ratio with region masks (P4-T02); overflow checked at 375 px (P4-T03); console reports new errors/warnings (P4-T05). Marked proposed, schema does not exist yet.
  - Ticket: `ticket.text`, `ticket.screenshot{media_type,path}`.
  - QA signal: `approve|reject`, reviewer, idempotency key, timestamp (P6-T08: "QA signal carries an idempotency key").
- **Actions:** approve / reject (+ reason required on reject, min length); "view all routes" (collateral damage: P4-T25); "re-run checks"; toggle order of before/after (judge-order-swap probe is P4-T24, a calibration action, not a QA one: hide in QA mode); open trajectory (Screen 2).
- **States:**
  | State | Presentation |
  |---|---|
  | Loading | image placeholders with fixed aspect ratio (no layout jump) |
  | Empty | "Nothing waiting for QA" + count of Decided |
  | Error | check shows `error` (never green): "Verdict is `error`, never silently `pass`" (P4-T28 acceptance) |
  | Slow | judge card shows spinner + elapsed; local Gemma on CPU is the slow path (PLAN.md:33, time per pair recorded in P4-T11); approve is **enabled** if checks passed and judge pending: proposed rule is that approve stays enabled only when all four checks pass, and a pending judge shows "advisory, pending" |
  | Quota exhausted | judge-hosted variant → `judge: error (QuotaExceeded)`; local Ollama path unaffected; show "judge unavailable, decide on checks" |
  | Stuck run | run in `awaiting-qa` past the QA timeout → `timed-out-qa` banner, buttons replaced by "Re-request review" (P6-T08 "times out into a defined state") |
- **Edge cases:**
  - Judge disagrees with passed checks → show label, never change the verdict; a failed-check + judge-pass pair shows red.
  - α below 0.80 → judge card carries "advisory only" (ADR-013 policy, `P04:12`).
  - Font-loading flake → pixel diff red but diff image shows text only: offer "re-run once", count reruns (P4-T26).
  - Prompt injection in ticket text rendered as plain text, flagged if the judge output contains the injected word (P4-T27).
  - 409 on decide: another reviewer already decided → show winner + decision, close the pane (pattern `DeskCasePane.tsx:187-200`).
  - Screenshots from a ticket may contain PII; free-tier prompts may be used for training (PLAN.md:14) → banner "public/synthetic code only" in the header on `personal` profile.
  - Missing before or after image → check `error`, not `pass`.

## 5. Screen 4: Eval, regression gate and quota ledger (P5, `docs/quotas.md`)

- **Purpose:** answer "did this phase improve on the last one, with intervals, and may CI let it through?", and "how much free quota did it burn?"
- **Users:** the owner at every phase end; CI reads the same JSON.
- **Layout:** top = `KpiGrid` of the four contract metrics (resolve rate with Wilson CI, tokens/bug in/out/cached, $-equivalent, p50/p95). Middle = phase-over-phase table (Previous / This / Delta, `PLAN.md:276-281` contract) + gate banner (pass/fail with the failing rule). Bottom = ablation table and the quota ledger (per model, per limit, bar + numbers, cached tokens shown apart).
- **Data (real definitions):**
  - Resolve rate = resolved / attempted with Wilson 95% (`batch.py:118-124`, z=1.96), ADR-003 excludes exit 2 and quarantine from attempted.
  - Tokens/bug: input, output, cached **separately** (`PLAN.md:279`); p50/p95 latency excludes quota wait, which is reported separately (`PLAN.md:281`).
  - $-equivalent: `—` until P5-T11 (`PLAN.md:280`), needs `prices.json` with source URL + date.
  - Gate: fails if resolve rate below baseline's lower bound (P5-T16); thresholds in one config file; override policy in ADR-017.
  - Ledger: per model `requests, tokens, cached` today; limits from the yaml block in `docs/quotas.md:37-60`; `measured: partial`, `method: groq-response-headers-plus-published-table`; Mistral has no row, so the ledger refuses it (`quotas.md:25`).
  - Each row carries `run_id`, `model`, `host`, `prompt_hash`, `git_commit` (pinned runs rule, `PLAN.md:284-286`). A number may appear only if a run id backs it (`PLAN.md:274`).
- **Real rows available now** `[real]`:
  - P0 baseline (variant A): `0/10 [-0.000000, 0.277540]`, tokens in/out/cached `4585 / 1044 / 0`, p50 3.652305 s, p95 4.842286 s (`phases/P00-argus-bench.md:85`). **The displayed `-0.000000` lower bound is a formatting artefact** (`batch.py:126` clamps with `max(0.0, …)` and its docstring says the cell formats as `[0.000000, …]`; the P0 doc cell and `docs/notes/p0-t29.md:54-55` carry the unclamped `-0.000000`): the console must clamp at 0.
  - P1 repro verdict counts, both text-only and text-plus-image: 28 valid, 1 passes-on-bug, 1 error, from `packages/repro-agent/runs/*/*/verdict.json` (counted here). These came from fixture replay (`host=fixture`), so the console must show them under a REPLAY badge and must **not** treat them as a model resolve rate.
  - Ledger day `2026-10-30`, `openai/gpt-oss-20b`: requests 30, tokens 60, cached 0 (`runs/text-only/ledger.json`), i.e. 2 tokens per fixture call: not real usage.
- **Actions:** pick baseline run; compare two result files; toggle "show intervals"; export markdown report (P5-T05 generator); open the gate config; link to Langfuse trace; "reset ledger" **not offered** (ledger is the safety: edits go through code and ADR-002).
- **States:**
  | State | Presentation |
  |---|---|
  | Loading | tile skeletons; table keeps header |
  | Empty | the empty results template (P5-T05 prints the empty template): all cells `—`, banner "no run id backs any number yet" |
  | Error | results JSON fails validation → red pill, previous good report kept |
  | Slow | dashboard is static (GitHub Pages, P5-T21): "built at <git_commit, time>" stale pill if older than the latest results commit |
  | Quota exhausted | model bar red, "QuotaExceeded at requests_per_day 1000/1000", next reset time; run list shows partial results (P0 break-it: partial file kept, resume next day) |
  | Gate fail | red banner with the rule and the numbers: "resolve rate lower bound X below baseline lower bound Y"; no override button unless ADR-017 names who |
  | Stuck run | any ledger-active run with no event for > grace: "run may be hung; ledger still holding its estimate" |
- **Edge cases:** n too small (0/1 `[0.000, 0.793]`, P0 variant B) → CI width shown, difference smaller than interval labelled "no difference" (`PLAN.md:286`); mixed hosts in one table → split by `host`; cached tokens that do not count against the cap (`cached_counts: false`) still appear in the cached column; Groq daily-reset boundary is not a calendar day per the `x-ratelimit-reset-requests` observation (`quotas.md:11`) while the ledger rolls on UTC date: show both and flag the mismatch; `tokens_per_day` and `requests_per_minute` are published numbers, not measured (`quotas.md:35`): tag them "published".

## 6. Cross-screen edge cases
| # | Case | Treatment |
|---|---|---|
| E1 | Fixture replay (`host=fixture`) looks like a live run: P1's 28/30 valid are canned scripts (`packages/repro-agent/src/repro_agent/batch.py` hard-codes `VALID`/`LOOSE`, lines 24-31; `host="fixture"` at line 67) | Permanent amber `REPLAY` badge on run, row, and any aggregate that includes it; aggregates default to "live only" |
| E2 | Day roll while a run is in flight (ledger `_roll_day` clears the buckets at UTC midnight) | Meters show "rolled at 00:00 UTC"; a run spanning midnight shows two segments |
| E3 | Duplicate webhook | One row (workflow id = ticket id); toast "duplicate delivery ignored" |
| E4 | Reconciled state differs from the webhook's | Row shows "reconciled from GitHub" tag with the source (issue/PR/run) |
| E5 | Two reviewers decide the same PR | 409 path with winner + decision |
| E6 | Unknown/unlisted model (Mistral on Free plan) | Ledger refuses; board shows "no quota row for <model>", not 0% |
| E7 | Missing artefact (screenshot, verdict.json) | Cell = `error` with the missing path; never blank, never `pass` |
| E8 | Light theme | Same tokens, verdict inks use the darker light-theme greens/reds (4.5:1, `console-radar-theme.md:68`) |
| E9 | Access | Not-permitted state distinct from error (pattern `AuditLog.tsx:70-74`); relevant for P8 tenants |

## 7. Mapping to build phases
| Screen | First buildable | Blocked on |
|---|---|---|
| Trajectory viewer | now (P1 trajectories exist) | nothing; derived metrics wait on P5-T02/T03 |
| Eval + quota | partial now (ledger.json, quotas.md, P0 row) | P5-T04 results JSON, P5-T16 gate |
| Verdict review | after P4-T06 | verdict schema, screenshots from P3-T14 |
| Run board | after P6-T02/T03 | state machine and DBOS workflow; the board before that can only list bench/repro runs |
The dashboard is a static GitHub Pages site (P5-T21, `PLAN.md:45`), so screens 1 and 3 need the P6 FastAPI backend; screens 2 and 4 can be static files.

## Verification log
- Re-opened and confirmed: `tokens.css` colour values and line ranges (13-76, 143-160, 166-186, 238-267); `radar.css` lines 66-68, 86, 111-122, 152, 160, 178, 353; `ops.css` ranges 11-54 and 142-200; `AuditLog.tsx:9-12,70-85`; `DeskCasePane.tsx:187-200`; `canvas-ui` component files exist (ReviewQueue, ReviewSidebar, KpiCard, DataTable, MonitorMatrix, StatusPill, Shell, DetailPanel); `AdminHealth.tsx` POLL_MS line 17, confirm line 47; `MyUsage.tsx:116`; `recoverStaleJobRuns.ts` grace constant.
- Corrected during verification: agent-builder run-detail line cites changed to the lines grep found (status colours 101-102, no-logs 162, log level colours 176, "View trace" 85); radar `--rowH` is 30px but radar rows are `min-height: 54px` (radar.css:160), both listed.
- Counted from disk: P1 `verdict.json` tallies (28 valid / 1 passes-on-bug / 1 error, same in both runs); ledger.json 30 requests, 60 tokens.
- Not verified: TASKS.md 49/272 counts (taken from BRIEF.md); the "wave board" named in a commit message, no file in this checkout defines it; the full P6 state list (proposed); the P4 verdict schema (proposed, not built).
- Finding, not fixed (docs lane owns it): `phases/P00-argus-bench.md:85` and `docs/notes/p0-t29.md:55` show `-0.000000` for a Wilson lower bound, while `batch.py:126` clamps at 0.
- JSON: `node -e JSON.parse` OK, 4 screens, both token blocks present. After writing, re-checked `ledger.py` (cites moved to 112-115, 117-120, 18-24, 83), `batch.py` (clamp is line 126, `VALID`/`LOOSE` 24-31, `host="fixture"` 67), `P04:6,12`, `P06:39`, `P00:85-86`. Other lanes were editing `PLAN.md`/`phases/P00*` at the same time, so those line numbers may drift.
