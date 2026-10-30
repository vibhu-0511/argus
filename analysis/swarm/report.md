# Fix report: generated-file spec (lane: fix-report)

As of 2026-10-30. Machine-readable twin: [`report.json`](report.json). Sample rendering: `analysis/explainer-src/62-report.html` (route `#plan/report`).

**What it is.** One self-contained, shareable HTML file per run. The owner (or a reviewer) opens it, sees the ticket, the proof, the diff and the before/after on the UI, then decides: **Approve -> raise PR**, **Request changes**, or **Reject**.

**Honesty box.** Nothing in the generator exists. Real inputs today exist for one task only: seeded `bug-17` (`ticket.json`, `bug.patch`, `golden.patch`, `checks.json`, `meta.json`, `shots/radar-card.png`, and a fixture-replayed repro under `packages/repro-agent/runs/*/bug-17/`). No verifier, judge, `locate()`, fix-loop or report renderer is built, and no task in `TASKS.md` builds the renderer (P8-T09 only puts verdict, judge label, trajectory link and two screenshots in the PR body). Every pass/fail chip in the sample is illustrative.

## Design rules

- One file, no network, no CDN, no fonts: works from disk, from an Actions artifact, or attached to a PR.
- Every number has a source field; a missing source renders "-", never a default.
- Status is never colour alone: each state has a word and an icon.
- Not run is not pass: overall status is pass_with_gaps when anything was skipped.
- Untrusted text (ticket, rationale) goes in through textContent; the file ships with a script-src hash CSP.
- Print-friendly: decision bar becomes a static block, all collapsed panels expand.

## Data contract: `FixReport` (proposed `argus.fix_report/0`)

Top-level keys: `schema`, `run_id`, `task_id`, `generated_at`, `generator{name,version}`, `base_commit`, `patch_sha256`, `ticket`, `repro`, `locate`, `patch`, `shots[]`, `verdict`, `judge`, `trajectory`, `risks[]`, `decision`.

Schemas that **exist** in `packages/argus-core` or the repro runs: Ticket; Screenshot; Task; TaskMeta; Check; CheckType (pixel_diff, bounding_box, computed_style); Trajectory; TrajectoryMeta; TrajectoryStep; StopReason (submit, step-cap, token-cap, QuotaExceeded, stuck, consecutive-timeout, retry-cap, tool-unavailable); repro verdict.json {task_id, verdict, stop_reason}; Usage / Ledger (argus-core ledger.py).

Schemas that are **planned**: LocateResult (P2-T06); VerifierVerdict (P4-T06); JudgeLabel (P4-T08, T11); BestOfK record (P4-T19); PullRequest record (P6-T21, P8-T09); FixReport (new, assembles all of the above).

Field status key: `real` = a file backs it today; `fixture` = file exists but a fixture produced it; `derived` = computed from real files by the renderer or read by hand for this sample; `planned` = nothing exists.


## 01 Ticket as filed

*Reviewer question:* What did the person actually report, and what did the agent see?  
*Delivered by:* P0 schema; P6-T07 / P8-T08 intake; console upload planned

| Field | Type | Comes from | Status |
|---|---|---|---|
| `ticket.id` | string | Ticket.id (argus-core types.py:30, ticket.schema.json) | real |
| `ticket.text` | string, untrusted | Ticket.text (rendered with textContent only; never as HTML (prompt-injection text must stay inert, P4-T27)) | real |
| `ticket.screenshot` | {media_type, path} | null | Ticket.screenshot (single, optional) | real |
| `ticket.source` | {kind: console | github_issue, ref} | intake step: console upload (owner flow) or labelled issue (PLAN.md route) (not in the Ticket schema today; add to FixReport, not to Ticket) | planned |
| `task.meta.{archetype,tier,source}` | enum | TaskMeta (task.schema.json) (bench tasks only; a live ticket has no archetype) | real |

**bug-17, real today:**
- ticket.json text (verbatim, 921 chars) and the 103 536-byte radar-card.png (375 px wide at 1.25 DPR, 469 x 834)
- meta.json: seeded, font-size, medium
- the ticket itself says the patch covers radar.css only and that Horizon, Flights, Control Tower and admin tags are not covered

**bug-17, planned / not available:**
- ticket.source (no intake exists)
- a second screenshot (schema allows exactly one)

**Edge cases**

| When | The report shows |
|---|---|
| no screenshot (29 of 30 seeded tickets) | text-only card with a chip "text-only ticket (ADR-005)"; the before/after section still has to capture its own pair |
| screenshot media type does not match its bytes | P1-T06 already rejects it as a tool error; the report shows "screenshot rejected, not shown to the agent" instead of the image |
| ticket text is long (> ~600 chars) | first lines plus an expander; full text always in the file |
| text contains HTML or an instruction ("ignore the rubric") | escaped literal text; a chip "contains instruction-like text" when the P4-T27 detector flags it |
| screenshot holds tenant data (flight numbers, crew) | sharing warning in the file header; redaction is a P7 threat-model item, not solved here |

## 02 Reproduction and proof

*Reviewer question:* Did something fail on the buggy tree and pass on the fixed one, and how much should I trust that?  
*Delivered by:* P1 (built, fixture-replayed); P3-T16 wires it into the loop

| Field | Type | Comes from | Status |
|---|---|---|---|
| `repro.script` | string (Playwright test body) | runs/<mode>/<task>/repro.spec.ts | real |
| `repro.verdict` | valid | passes-on-bug | fails-on-golden | error | runs/.../verdict.json (verify.py) | real |
| `repro.stop_reason` | StopReason | verdict.json + last Trajectory step | real |
| `repro.mode` | host + model + prompt_hash | TrajectoryMeta (host = "fixture" means no model was called) | real |
| `repro.runs[]` | [{tree: buggy|golden|patched, outcome, exit_code, duration_ms, trace_path}] | repro loop run_trees (loop.py injects the runner) (today only the final verdict is stored, not per-run rows) | planned |
| `repro.evidence` | REAL | FIXTURE_ONLY | ARGUS.evidence claim C1 (a fixture repro must never look like a live proof) | derived |

**bug-17, real today:**
- the stored script is two lines: click "Sign in", expect heading "Welcome"
- verdict "valid", stop "submit", host "fixture", model openai/gpt-oss-20b
- evidence C1: batch.py returns one hard-coded script for every task, so this proof says nothing about font size

**bug-17, planned / not available:**
- a style-assertion repro (computed font-size under 12 px); P1 tool surface has no computed-style read and the saved-script rule is role + accessible name only (docs/architecture/p1.md), so a font-size repro may not be expressible in P1 as built. Open design question, not decided here
- per-tree run rows and the fail-before / pass-after table

**Edge cases**

| When | The report shows |
|---|---|
| no repro saved (retry-cap, tool-unavailable, vague ticket) | stop reason in red, "no reproduction"; the report is still produced and Approve needs an explicit acknowledgement |
| verdict passes-on-bug (loose selector) | proof marked INVALID, not green; this is the P1-T14 case |
| verdict fails-on-golden / error (test.skip, test.fixme) | proof marked INVALID with the verdict word |
| non-interaction bug (style, size, z-index) | proof is the bench check (checks.json computed_style) instead of a click script; say so in a line |
| flaky repro | k/n runs and the word "flaky"; never summarised as pass |
| fixture host | FIXTURE badge on the whole section; fixture proofs cannot enable one-click Approve |

## 03 Located source

*Reviewer question:* Where in the code did the agent look, and is that where the change landed?  
*Delivered by:* P2-T02 (data-src plugin), P2-T05..T08 (locate)

| Field | Type | Comes from | Status |
|---|---|---|---|
| `locate.query` | selector or role+name | repro script / fix-loop locate() call | planned |
| `locate.data_src` | "file:line:col" (repo-relative, no tag suffix) | data-src attribute on the DOM node (P2-T02, dev/test builds only) | planned |
| `locate.ambiguous` | bool + ranked candidates[{file,line,col,why}] | LocateResult (P2-T06) | planned |
| `locate.error` | not-found | ambiguous | no-source-info | LocateResult errors (P2-T06) | planned |
| `locate.patched_file_line` | file:line of the edit | patch hunks (differs from data_src for CSS bugs: the DOM points at JSX, the fix is in a stylesheet) | derived |

**bug-17, real today:**
- file contents: Radar.tsx:996 is <span className="radar-locked-fact-label"> (col 21), :991 the CRITICAL pill (col 17); .radar-locked-fact-label is radar.css:140, .radar-pill :183 in the dcortex worktree (read-only look; these lines carry the seeded 10 px values)

**bug-17, planned / not available:**
- the data-src attribute itself: the plugin does not exist, so the file:line:col shown is derived by reading the source, not returned by a tool
- col base (0 or 1) is not fixed by P2-T02; 1-based used here

**Edge cases**

| When | The report shows |
|---|---|
| ambiguous (wrapper or repeated element) | ranked candidate list; bug-17 has one: .radar-pill is rendered at Radar.tsx:991, :1090 and :1148 |
| no-source-info (production bundle) | "located by search, not by data-src" chip; confidence lowered |
| located file is not the patched file | two rows: element (Radar.tsx) and rule (radar.css); the bridge is the class name |
| patch touches files nobody located | flag in risks: edit outside the located area |

## 04 The diff

*Reviewer question:* Exactly what changed, in which files?  
*Delivered by:* P3 (fix-loop produces the patch; worktree manager P3-T04)

| Field | Type | Comes from | Status |
|---|---|---|---|
| `patch.origin` | agent | golden | human | loop run record (bug-17: golden (reference), no agent has produced a patch) | planned |
| `patch.files[]` | [{path, status, additions, deletions}] | git diff --numstat on the worktree | planned |
| `patch.hunks[]` | [{old_start, new_start, lines[{t: ctx|del|add, text}]}] | unified diff | planned |
| `patch.sha256` | hex | hash of the unified diff; binds every later decision to this exact patch | planned |
| `patch.base_commit` | git sha | worktree manager (bench meta.json has no base_commit field today) | planned |

**bug-17, real today:**
- golden.patch: 1 file (apps/canvas/src/ops/radar.css), 6 hunks, 12 declarations, +12 / -12; each changes only font-size to 12

**bug-17, planned / not available:**
- an agent-made patch: P0 one-shot logged bug-17 as exit2_bug, "bug.patch did not apply" (docs/notes/p0-t29.md:74), so no agent patch exists

**Edge cases**

| When | The report shows |
|---|---|
| multi-file patch | file list with +/- counts and one collapsible panel per file; first file open; a combined "download .patch" |
| large diff (> ~400 lines) | collapsed by default with counts; never truncated silently |
| patch edits bench check files or the report inputs | red banner; those are mounted read-only (P3-T05), so a non-empty edit means the run is invalid |
| empty patch | no report, no PR (P8-T09: "no PR when the patch is empty"); a run page with the stop reason instead |
| binary file or rename | one row, no hunks, "binary, not shown" |

## 05 Before / after on the production UI

*Reviewer question:* Can I see the fix, on the real screen, at the size the bug was filed at?  
*Delivered by:* P4 (capture + pixel diff), P3 (patched tree), P8-T09 (two screenshots in the PR)

| Field | Type | Comes from | Status |
|---|---|---|---|
| `shots[].route` | string | check.params.flow (task.schema Check.params) (bug-17: /ops/radar) | real |
| `shots[].viewport` | {w, h, dpr}, theme | capture config (bug-17 before: 375 x 667 css px at 1.25 (469 x 834 px), light theme, inferred from the image) | derived |
| `shots[].before` | {path, sha256, media_type, w, h} | screenshot of the buggy tree (bug-17 only has this one: shots/radar-card.png) | real |
| `shots[].after` | {path, sha256, media_type, w, h} | null | screenshot of the patched tree (no real after image exists anywhere in the repo) | planned |
| `shots[].diff` | {changed_ratio, cap, masks[{x,y,w,h,why}], pass} | pixel-diff check (P4-T02) (a changed-pixel ratio with its unit written next to it) | planned |
| `shots[].build` | test | production | capture runner (see edge cases: the screenshots come from a test build, not the deployed site) | planned |

**bug-17, real today:**
- the before image, byte for byte

**bug-17, planned / not available:**
- the after image: the fragment draws an ILLUSTRATIVE re-render of the card from golden.patch (10 -> 12 px on the fact labels and the pill)
- diff overlay is element-level, from the patch; the real pixel diff is P4-T02

**Edge cases**

| When | The report shows |
|---|---|
| no screenshot of the after tree (capture failed) | "after not captured" panel; Approve disabled; slider hidden |
| before and after sizes differ | both at native size side by side, slider disabled; P4-T02 fails a size change without scaling |
| flaky pixel diff (font load, radar sweep, LIVE dot animation) | masked regions drawn as hatched boxes; ratio shown with its cap; runs n/n stable, else status flaky (P4-T26: wait for fonts and network idle) |
| multiple routes / themes / viewports | tabs per shot; the table in section 06 names every route; dark and light are separate shots |
| "production UI" is a test build | label "built from the base and patched commits, served from the sandbox, data-src on"; the plugin is absent from production builds (P2-T02), so a screenshot of the deployed site cannot also carry the located source |
| images are large | downscaled copy embedded (limit ~1 MB per image, whole file well under 16 MB), original sha256 kept |

## 06 Verifier checks

*Reviewer question:* Which deterministic checks ran, which failed, and what was not run?  
*Delivered by:* P4-T02..T06 (checks and pipeline), P4-T22 (final gate)

| Field | Type | Comes from | Status |
|---|---|---|---|
| `verdict.overall` | pass | fail | error | pass_with_gaps | VerifierVerdict (P4-T06) (pass_with_gaps is a proposal so "not run" cannot read as pass) | planned |
| `verdict.order` | string[] | one config place (P4-T06, ADR-012) | planned |
| `verdict.first_failure` | check id + reason | null | pipeline short-circuit | planned |
| `checks[].{id,type,status,reason,detail,duration_ms}` | status: pass | fail | not_run | error | flaky | one row per check | planned |
| `checks[].detail.axe.new_violations` | [{rule_id, nodes}] vs baseline | axe-core on buggy tree minus patched tree (P4-T04) (only violations absent from the clean baseline count) | planned |
| `bench.check` | {type: computed_style, flow: /ops/radar, property: font-size, min_px: 12} | checks.json (Check schema) (its result on the real app is not real: evidence C5, the scorer runs on a synthetic page) | real |

**bug-17, real today:**
- the one bench check definition: computed_style font-size >= 12 px on /ops/radar

**bug-17, planned / not available:**
- every result cell: no verifier has run on bug-17, so pass/fail chips in the sample are ILLUSTRATIVE
- no golden screenshot is stored for bug-17, so the pixel check would be not_run

**Edge cases**

| When | The report shows |
|---|---|
| check not run (no golden shot, short-circuit, tool error) | grey "not run" with the reason; counts toward "gaps"; Approve then needs an acknowledgement |
| first hard failure | later rows "not run: short-circuit"; judge section says "skipped"; decision bar offers no Approve |
| axe finds violations that were already there | counted as baseline and listed collapsed; only new rule ids drive the status |
| flaky pixel diff | status flaky with n runs; verdict cannot be pass |
| check backend down | status error, never pass (P4-T28 fail-closed) |
| collateral route changed (P4-T25) | row names the route that moved |

## 07 Judge label and its limits

*Reviewer question:* Does a second reader think the fix meets the ticket, and how far should I trust that reader?  
*Delivered by:* P4-T08 (rubric), T11/T16 (runners), T13/T14 (alpha), T18 (ADR-013)

| Field | Type | Comes from | Status |
|---|---|---|---|
| `judge.label` | rubric label (P4-T08 defines the set); sample uses intent_met | partial | not_met | error | judge runner structured output (P4-T11) | planned |
| `judge.rationale` | string, <= ~400 chars | judge output | planned |
| `judge.model / family` | string | runner config (Gemma cross-family; Mistral same-family control) | planned |
| `judge.order_swapped_label` | label | second run with before/after swapped (P4-T24) (disagreement is reported, never averaged) | planned |
| `judge.alpha` | {value, ci_low, ci_high, n} | null | calibration set vs your labels (P4-T12..T14) (null until measured; target >= 0.80 on held-out split) | planned |
| `judge.advisory` | bool | ADR-013 policy when alpha < 0.80 | planned |

**bug-17, real today:**
- nothing: no judge exists. The partial rationale in the sample is built from the ticket text, which itself says Horizon, Flights, Control Tower and admin tags are not in the diffs

**bug-17, planned / not available:**
- everything else

**Edge cases**

| When | The report shows |
|---|---|
| judge disagrees with the checks | both shown side by side; checks pass + judge partial or not_met = "needs a human"; checks fail + judge met = fail (the judge does not override, PLAN.md); bug-17 sample is the first case |
| swapped-order labels differ | label "unstable", pill grey; advisory only |
| unparsed output or backend down | label error (stays in the alpha denominator); never pass |
| alpha below 0.80 or not measured | permanent "advisory" tag with the number or "not measured" |
| judge family equals fixer family | self-preference warning chip |
| checks failed, judge skipped | "skipped, a check failed first" |

## 08 Trajectory summary

*Reviewer question:* What did the agent do, what did it cost, and why did it stop?  
*Delivered by:* P3-T08 (recorder), P5 (metrics), argus-core ledger

| Field | Type | Comes from | Status |
|---|---|---|---|
| `traj.meta` | {run_id, task_id, model, host, prompt_hash, git_commit, seed} | TrajectoryMeta (first JSONL line) | real |
| `traj.steps` | int | count of TrajectoryStep rows | real |
| `traj.tokens` | {in, out, cached} shown separately | sum of TrajectoryStep.tokens_* (PLAN.md reports the three counts separately; tokens/bug must include retries, judge calls and best-of-k samples) | real |
| `traj.stop_reason` | StopReason enum (8 values) | last step | real |
| `traj.tool_errors / stuck` | int / bool | P5-T02 formulas (docs/metrics.md) | planned |
| `traj.best_of_k` | {k, selected, reason, candidates[]} | P4-T19 selector record | planned |
| `traj.link` | relative path or Actions artifact URL | trajectory.jsonl | derived |

**bug-17, real today:**
- repro trajectory: 1 step, tokens in 1 / out 1 / cached 0 (fixture placeholders), stop submit, host fixture, git_commit field holds the mode name "text-only", not a commit

**bug-17, planned / not available:**
- fix-loop trajectory: none exists, so steps, tokens and cost stay "-"

**Edge cases**

| When | The report shows |
|---|---|
| stop reason is not submit (QuotaExceeded, stuck, step-cap, tool-unavailable) | red stop chip and no Approve: there is no accepted patch |
| fixture host | tokens shown as "recorded, not measured" |
| best-of-k used | k candidates, which was chosen and why; tokens are the sum over all candidates |
| ledger has no cost for a run | "-"; no $-equivalent without a run id (PLAN.md rule) |
| trajectory file missing | the link renders as "not stored"; section degrades, report still opens |

## 09 Risks and things not checked

*Reviewer question:* What could still be wrong, and what did nobody look at?  
*Delivered by:* assembled by the renderer from verdict gaps + rules; human notes added at review

| Field | Type | Comes from | Status |
|---|---|---|---|
| `risks[].{id,severity,source,text}` | severity: high | med | low; source: auto | human | renderer rules over the report fields | planned |
| `risks[].evidence_ref` | section id | link back to the row that triggered it | planned |

**bug-17, real today:**
- ticket-vs-patch scope gap (the ticket says so itself)
- no golden screenshot
- repro is a fixture

**bug-17, planned / not available:**
- all automatic rules: none is built

**Edge cases**

| When | The report shows |
|---|---|
| no risks found | still prints "checked: ..." and "not checked: ..." lists; an empty list never reads as "all clear" |
| any check not run, judge advisory, fixture repro, test build | each is an automatic risk row |
| patch smaller than the ticket scope | high severity row: partial fix |

## 10 Decision bar (sticky)

The only interactive control that changes the world. Sticky at the bottom of the viewport; in print it becomes a static block.

| Action | Effect | Enabled when |
|---|---|---|
| Approve and raise PR | confirm dialog, then the QA signal (P6): mark the draft PR ready, or create it if it does not exist yet. Idempotent on (run_id, patch_sha256) | overall is pass or pass_with_gaps with the acknowledgement ticked; no hard failure; stop_reason = submit; non-empty patch |
| Request changes | reason box (required) becomes a review comment and context for one fix-loop retry (P4-T22 allows one retry) | always |
| Reject | reason stored, run ends, PR stays for a person to close or rework (production.html, qa step) | always |

| State | When | UI |
|---|---|---|
| `ready` | all checks pass, judge met, repro valid and live | Approve primary |
| `needs_ack` | any check not run, judge partial/not_met/unstable/advisory, fixture repro | Approve disabled until the acknowledgement checkbox lists the gaps by name |
| `blocked` | a hard check failed, stop_reason is not submit, or the patch is empty | no Approve button; the reason is shown in its place |
| `offline` | file opened with no decision endpoint | buttons produce copyable text (gh pr ready <n>, a review comment body) instead of calling anything |
| `decided` | a decision for this (run_id, patch_sha256) exists | shows who, when, reason; buttons removed. A re-run produces a new patch hash and a new report; deciding on a stale report is refused |

bug-17 sample renders in state `needs_ack`: checks pass with one not run, judge says partial, repro is a fixture. Approve is held until the three gaps are acknowledged by name.

**Where this differs from the plan**

- Owner flow: the owner types the issue (text or screenshot) in a console and gets this report. PLAN.md route: a labelled GitHub issue starts a durable workflow (P6-T07, P8-T08). The report is the same file either way; only ticket.source differs. (`phases/P08-argus-app.md:44, phases/P06-argus-flow.md:14`)
- Owner flow: the PR is raised after Approve. Plan: a draft PR is opened first (find-or-create on one stable branch, draft until QA), and the QA signal marks it ready. In this report Approve therefore means "mark the draft ready", unless the owner decides to delay PR creation. (`phases/P06-argus-flow.md:57, phases/P08-argus-app.md:45`)
- The decision bar needs somewhere to send the decision. A static HTML file opened from disk has none, so it falls back to copyable commands (gh pr ready <n>). The plan's endpoint is the P6 QA signal: MRTR input_required or a review comment with an approve keyword. (`phases/P06-argus-flow.md:45-46`)
- "Production UI" cannot mean the deployed site: data-src exists only in dev/test builds and the platform target is the synthetic copa-local cell. (`phases/P02-dom2src.md:9, config/platform.md`)

## Before/after viewer

Three modes over the same pair: **slider** (a range input, arrow keys move it), **side by side** (stacks below ~600 px), **diff overlay** (changed regions boxed). In the real generator the overlay is the P4-T02 pixel diff with its masks drawn hatched. In the sample it is element-level, drawn from `golden.patch`, because no after image exists to diff against. The before image is the real `radar-card.png`; the after is a CSS re-rendering of the same card with the two changed rules applied (labels and pill 10 -> 12 px), tagged ILLUSTRATIVE.

## What the generator needs built

| Section | Phase | Built | Missing |
|---|---|---|---|
| 01 Ticket | P0 (done) + P6-T07 / P8-T08 | Ticket schema, bench tickets | intake that stamps ticket.source (console upload or labelled issue) |
| 02 Reproduction | P1 (done, fixture-replayed) | script, verdict, trajectory | per-tree run rows; a live (non-fixture) run; a way to express style bugs |
| 03 Located source | P2 | nothing | data-src plugin (T02), locate() core and schema (T05, T06), MCP server (T07), ambiguity (T08) |
| 04 The diff | P3 | nothing for a patch | worktree manager (T04), loop (T06), recorder (T08), patch hash |
| 05 Before / after | P4 + P3 | one before image | capture of before and after at fixed viewport (needs fonts waited, animations masked), pixel diff with masks (P4-T02), after-screenshot storage |
| 06 Verifier checks | P4 | bench check definitions (synthetic page) | pixel (T02), overflow (T03), axe new-only (T04), console (T05), pipeline and structured verdict (T06) |
| 07 Judge | P4 | nothing | rubric (T08), 100-pair labels (T09, T10), runners (T11, T16), alpha (T12-T14), ADR-013 (T18) |
| 08 Trajectory | P3 + P5 | schema, ledger, repro trajectories | fix-loop recorder (P3-T08), metrics (P5), best-of-k record (P4-T19) |
| 09 Risks | renderer | nothing | rule set over report fields; human notes |
| Decision bar | P6 + P8 | nothing | approve/reject endpoint = QA signal (P6-T09 MRTR or P6-T10 review comment), draft-PR find-or-create (P6-T21), PR body with verdict, judge, trajectory, two shots (P8-T09) |
| The generator itself | none | hand-made 142-fix.html | No task in TASKS.md builds the FixReport schema or the HTML renderer. P8-T09 only puts the verdict, judge label, trajectory link and two screenshots in the PR body. Proposed: one new task after P4 (schema + static renderer + golden-file test), so the P6 QA wait has something to show |

## Findings worth acting on

1. **No task builds the report.** Add one after P4: `FixReport` schema, static renderer, golden-file test (rendering a stored report must be byte-stable). The P6 QA wait (T08-T10) has nothing to show without it.
2. **The recorded bug-17 repro proves nothing about font size.** It is the fixture sign-in script (`evidence.json` C1). The report marks it FIXTURE and keeps one-click Approve off until a live proof exists.
3. **A style bug may not be reproducible by the P1 tool surface** (role + accessible name only, no computed-style read; `docs/architecture/p1.md`). Decide whether `checks.json` is the repro for style archetypes.
4. **"Production UI" is a test build.** The `data-src` plugin is absent from production builds (`phases/P02-dom2src.md:9`), and the target is the synthetic `copa-local` cell. Say so on the before/after panel.
5. **The located file is not the fixed file for CSS bugs.** `data-src` gives `Radar.tsx:996:21`; the fix is `radar.css:140`. The report shows both.
6. **bug-17 is a partial fix by its own ticket text**, and the bench check (`flow: /ops/radar`) cannot see the other screens. The report surfaces that as a high-severity risk rather than a pass.
7. **Decision needs an endpoint.** A static file cannot call GitHub. Either the PR body links an Actions artifact (static, copy-command fallback) or a P6 control-plane URL hosts the file and the QA signal.

## Open questions for the owner

- Where does the report live for the reviewer: an Actions artifact link in the PR body (static, no decision endpoint) or a control-plane URL (P6, has the endpoint)?
- Can a style bug (font-size, z-index) have a click-script repro at all given the P1 tool surface, or is the bench check its repro?
- Does Approve create the PR (owner flow) or mark a draft ready (plan)?
- Screenshots of the real tenant UI contain tenant data: who may see the report?
