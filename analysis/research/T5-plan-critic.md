# T5 plan critic

Scope: this note checks only `PROJECT.md`, `PLAN.md`, `TASKS.md`, `repo-structure.md`, every file in `phases/`, `architecture.html`, `production.html`, `142-fix.html`, and `analysis/CONSTRAINTS.md`. No competitor repo was opened. No URL was fetched. No application code was written, and no plan file other than this one was edited. Hours below are sums of the `Est hrs` column and of the `Nh` marks on `TASKS.md` checkboxes. Where two counts disagree, both are printed. Nothing here is a proposed rewrite.

## 1. Hours and task counts

Phase task tables, the `PLAN.md` phase map, the `PROJECT.md` phase table, and the `TASKS.md` checkbox list all carry the same per-phase hours and the same ids. Checkbox titles, owners, and hours match the phase rows (272 ids, 0 mismatches, 0 duplicates, 0 ids present on only one side). Week headers in `TASKS.md` match the sum of that week's checkboxes, including the two empty buffer weeks.

| Phase | Header budget | Table tasks | Table hours | Sum of hours |
|---|---|---|---|---|
| P0 | 76 h, 32 tasks | P0-T00–T31 | 32 | 76 |
| P1 | 32 h, 17 tasks | P1-T00–T16 | 17 | 32 |
| P2 | 44 h, 20 tasks | P2-T00–T19 | 20 | 44 |
| P3 | 84 h, 34 tasks | P3-T00–T33 | 34 | 84 |
| P4 | 72 h, 30 tasks | P4-T00–T29 | 30 | 72 |
| P5 | 64 h, 29 tasks | P5-T00–T28 | 29 | 64 |
| P5.5 | 28 h, 18 tasks | P5.5-T00–T17 | 18 | 28 |
| P6 | 52 h, 26 tasks | P6-T00–T25 | 26 | 52 |
| P7 | 44 h, 23 tasks | P7-T00–T22 | 23 | 44 |
| P8 | 60 h, 26 tasks | P8-T00–T25 | 26 | 60 |
| P9 | 40 h (phase file says "about 40 h"), 17 tasks | P9-T00–T16 | 17 | 40 |

Core P0–P8: 76+32+44+84+72+64+28+52+44+60 = 556 h, and 32+17+20+34+30+29+18+26+23+26 = 255 tasks. With P9: 556+40 = 596 h, and 255+17 = 272 tasks. That matches `TASKS.md` ("255 core tasks (556 h, P0 to P8) plus 17 optional P9 tasks (40 h)"), the phase-map footer in `PLAN.md`, the phase table in `PROJECT.md`, and `analysis/CONSTRAINTS.md` ("556 h / 255 tasks / 30 weeks"). No task is over the stated 4 h cap; the maximum in every table is 4.

Checkbox sums by week (header in parentheses): W1 20 (20), W2 20, W3 20, W4 20, W5 20, W6 20, W7 20, W8 22 (22), W9 19 (19), W10 19 (19), W11 20, W12 21 (21), W13 20, W14 21 (21), W15 19 (19), W16 20, W17 0 (buffer), W18 22 (22), W19 18 (18), W20 19 (19), W21 20, W22 20, W23 21 (21), W24 20, W25 0 (buffer), W26 21 (21), W27 19 (19), W28 20, W29 20, W30 20, W31 19 (19), W32 16 (16). Adding the headers: weeks 1–7 are 140, then +22+19+19+20+21+20+21+19+20+0+22+18+19+20+20+20+21+20+0+21+19+20+20+20+19+16 = 596. Core hours inside that total are 596−40 = 556. Week 30 is 15 h of P8 (T18–T25) plus 5 h of P9 (T00 1, T01 1, T02 3).

### T5-01 28 weeks times 20 h is not 556 h
- Claim: "Core work is P0 through P8: 556 hours, 255 tasks, 28 weeks of work plus 2 buffer weeks, so 30 weeks." Hours are "at 20 h/week."
- Where: `PROJECT.md`, section "Phases"; the same product is in `PLAN.md`, section "Phase map" ("about 556 h, 28 weeks of work, plus 2 buffer weeks") and in `analysis/CONSTRAINTS.md` item 2.
- Contradiction: the task tables sum to 556 h, and the non-buffer weeks in weeks 1–30 are 28 weeks, but 28×20 = 560, which is 4 h more than 556. Those 28 weeks' checkbox hours sum to 561, not 560 and not 556: week 30 holds 5 h of P9 on top of the 556 core hours (556+5 = 561), and the per-week gaps against 20 sum to +1 (over: W8 +2, W12 +1, W14 +1, W18 +2, W23 +1, W26 +1 = +8; under, through W30: W9 −1, W10 −1, W15 −1, W19 −2, W20 −1, W27 −1 = −7; W30 is 20). 5 h of P9 inside the core calendar, minus that +1 h, is the 4 h gap.
- Evidence: [CODE]
- Severity: Low. The checklist, the phase budgets, and the 556 / 255 totals agree with each other. Only the sentence that treats 28 weeks at 20 h/week as 556 h does not multiply through.
- Hours effect: 4 h (560−556). No task is missing from the 556.

### T5-02 Several scheduled weeks are not 20 h
- Claim: "Weeks are 20 hour bins in task order" (`PROJECT.md`, "Week by week"). `PLAN.md`, "Week-by-week timeline", adds that a week "can run up to 3 h over 20 because a task is placed in the week it starts."
- Where: `PROJECT.md`, "Week by week"; `PLAN.md`, "Week-by-week timeline"; `TASKS.md` week headers.
- Contradiction: the checkbox sums are not all 20. Over 20, all inside the +3 allowance: W8 22, W12 21, W14 21, W18 22, W23 21, W26 21. Under 20, which neither intro explains except for the two buffers: W9 19, W10 19, W15 19, W19 18, W20 19, W27 19, W31 19, W32 16. W17 and W25 are 0, as stated. Each `TASKS.md` header matches its own checkbox sum, so the headers and the list agree; they disagree with an unqualified 20 h bin.
- Evidence: [CODE]
- Severity: Low. `PLAN.md` already allows the overs. The unders do not change any phase budget.
- Hours effect: none on the 556 / 596 totals. The overs and unders are already inside those totals.

## 2. ADR numbering

`PLAN.md` "ADR index" and `PROJECT.md` "ADR index" both list 001 through 030 once, in order, with the same phase on each row: 001–003 P0, 004–005 P1, 006–007 P2, 008–011 P3, 012–014 P4, 015–017 P5, 018–019 P5.5, 020–023 P6, 024–026 P7, 027–029 P8, 030 P9. There is no missing number and no duplicate number. Title wording is a paraphrase (for example PLAN 005 "Screenshot in ticket context" versus PROJECT 005 "When the screenshot is worth its tokens"); the number and the phase do not change.

Each index row has one writing task in the matching phase file, and every "Write ADR-NNN" task has an index row: P0-T04 (001), P0-T08 (002), P0-T27 (003), P1-T02 (004), P1-T12 (005), P2-T04 (006), P2-T13 (007), P3-T22 (008), P3-T23 (009), P3-T24 (010), P3-T25 (011), P4-T07 (012), P4-T18 (013), P4-T21 (014), P5-T10 (015), P5-T15 (016), P5-T18 (017), P5.5-T09 (018), P5.5-T11 (019), P6-T15 (020), P6-T16 (021), P6-T17 (022), P6-T18 (023), P7-T14 (024), P7-T15 (025), P7-T16 (026), P8-T13 (027), P8-T14 (028), P8-T15 (029), P9-T12 (030). `repo-structure.md` says "ADRs 001 to 030". No phase file names an ADR outside 001–030.

### T5-03 ADR-004 is written before the check that is supposed to feed it
- Claim: Risk 4 is mitigated by "P1-T01, P1-T02, P2-T00". P2-T00's acceptance says: "if Playwright MCP still lacks 2026-07-28 support, note it for ADR-004".
- Where: `PLAN.md`, "Risk register" row 4; `phases/P02-dom2src.md`, task P2-T00; `phases/P01-repro-agent.md`, task P1-T02.
- Contradiction: P1-T02 ("Write ADR-004") is in `TASKS.md` Week 5. P2-T00 is in Week 6, after P1-T16. No later task says to revise `docs/adr` for ADR-004. The writing task's own dependency is P1-T01 only.
- Evidence: [CODE]
- Severity: Low. ADR-004 still has a writing task and an index row. The later spec check has nowhere to land except a note.
- Hours effect: none. P1-T02 remains 1 h.

## 3. Week table versus phase table

`PLAN.md` and `PROJECT.md` week tables name the same phase on each week from 1 through 32. Both put buffers, with no tasks, at weeks 17 and 25. `TASKS.md` Week 17 and Week 25 have no checkboxes. Both tables say a phase may start in the tail of the previous phase's last week. These tails are real in the checklist: P1 starts in W4 (P1-T00, P1-T01), P2 in W6, P3 in W8, P4 in W12, P5 in W16, P5.5 in W20, P7 in W24, P8 in W27, P9 in W30. P6 does not: Week 22 is only P6-T00–T08.

Phase-file `Weeks` lines for P0 (W1–4), P1 (W5–6, and it says it starts in the tail of W4), P2 (W6–8), P3 (W8–12), and P4 (W12–16) use the same week numbers as `TASKS.md`. `PROJECT.md` narratives match the calendar for the later phases too: P5 "weeks 16–20, with a buffer week at 17", P5.5 "weeks 20–21", P6 "weeks 22–24", P7 "weeks 24–27, with a buffer week at 25", P8 "weeks 27–30".

The later phase files instead say "in the base plan" and tell you that `TASKS.md` calendar weeks include the buffer. One shift fits four of those lines and not P6. Insert the week-17 buffer as +1 for base weeks 17 and later, and insert the week-25 buffer as another +1 for base weeks 24 and later: base ≤16 stays, 17–23 become calendar+1, 24 and later become calendar+2. Under that shift, P5 "W16–19" lands on calendar 16, 18, 19, 20 (where P5-T00–T28 actually are; W17 is empty). P5.5 "W19–20" lands on calendar 20–21. P7 "W23–25" lands on calendar 24, 26, 27. P8 "W25–28" lands on calendar 27–30. The same shift does not fit P6.

### T5-04 P6's weeks line does not land on the weeks that hold its tasks
- Claim: P6 weeks are "W20–23 in the base plan (calendar weeks in `TASKS.md` include the buffer)."
- Where: `phases/P06-argus-flow.md`, budget line. `PROJECT.md` narrative says "P6 — flow (weeks 22–24)". `PLAN.md` week table puts P6 on weeks 22, 23, and 24 (week 24 shared with P7).
- Contradiction: the shift above, which is the one that makes the other "base plan" lines match `TASKS.md`, maps base W20–23 to calendar weeks 21–24. Week 21 is P5.5-T06 through P5.5-T17 and sums to 20 h, with no P6 id. P6-T00 is the first checkbox of Week 22; P6-T25 is in Week 24. A reader who adds only the one buffer the parenthetical mentions (week 17) still starts P6 in calendar week 21, which is full. `PROJECT.md` and `PLAN.md` already use 22–24.
- Evidence: [CODE]
- Severity: Med. Following the phase file's week line schedules P6 onto a week that the checklist has already filled with P5.5, so the phase header cannot be used as the calendar.
- Hours effect: none. The 52 h still sit in weeks 22–24 (20+21+11).

### T5-05 P9's weeks line does not mention the week-30 tail
- Claim: P9 weeks are "+2 weeks after P8 (first on the cut list)." `PROJECT.md` says P9 "adds about 40 hours and 17 tasks, two more weeks" and the week table's row "31–32" is the P9 row, while week 30 says "Optional P9 starts."
- Where: `phases/P09-backend-lane.md`, budget line; `PROJECT.md`, "Phases" and "Week by week".
- Contradiction: `TASKS.md` Week 30 includes P9-T00, P9-T01, and P9-T02 (5 h) before Weeks 31 (19 h) and 32 (16 h). The phase line's "+2 weeks" matches 31–32 and the 40 h, and it does not name week 30, where the phase actually starts.
- Evidence: [CODE]
- Severity: Low. `PROJECT.md`'s week 30 cell already says P9 starts. The phase file's weeks line does not.
- Hours effect: none. 5+19+16 = 40 h either way.

## 4. Dependency order

No `Depends on` cell points at an unknown id. No task lists a dependency that appears later than itself in `TASKS.md`: within each week the dependency is an earlier checkbox, and across weeks it is an earlier week. The solid edges in the `PLAN.md` "Phase dependency graph" that do have a task dependency are P0→P1 (P1-T00 on P0-T31), P0→P2 (P2-T02 on P0-T09), P1→P2 (P2-T00 on P1-T16), P0→P3 (P3-T02 on P0-T03, P3-T06 on P0-T05), P1→P3 (P3-T16 on P1-T08), P2→P3 (P3-T16 on P2-T07), P3→P4 (P4-T00 on P3-T33), P3→P5 (P5-T06 on P3-T06, P5-T12 on P3-T18), P4→P5 (P5-T00 on P4-T29), P5→P5.5 (P5.5-T00 on P5-T28), P3→P5.5 (P5.5-T02 on P3-T06), P6→P7 (P7-T00 on P6-T25), P5.5→P7 (P7-T07 on P5.5-T10), P6→P8 (P8-T03 on P6-T05, P8-T04 on P6-T04, P8-T08 on P6-T07), P7→P8 (P8-T00 on P7-T22, P8-T02 on P7-T04), P8→P9 (P9-T00 on P8-T25), and the dashed P3→P9 (P9-T07 on P3-T14).

### T5-06 P7-T04 tests an App token before the App task that depends on it
- Claim: P7-T04 acceptance: "negative tests show a push to a protected branch and a call on an uninstalled repo are refused." P7 done-when repeats that those two refusals are shown. P8-T02 "Create the GitHub App manifest" depends on P7-T04, and its acceptance is "The App registers from the manifest."
- Where: `phases/P07-argus-guard.md`, P7-T04 and "Done when"; `phases/P08-argus-app.md`, P8-T02; `TASKS.md` Week 24 (P7-T04) and Week 27 (P8-T02). P8-T03, which mints the installation token, is Week 28 and depends on P8-T02.
- Contradiction: the token tests are scheduled in week 24. The manifest and the minting task are scheduled in weeks 27 and 28, and both are downstream of P7-T04, so the checklist forbids doing them first. P7-T04's `Depends on` is only P7-T02. Nothing in P7 creates the App.
- Evidence: [CODE]
- Severity: High. P7's exit criterion and P8's first App task each need the other to be finished first, so those two acceptances cannot be met in the order the checklist gives.
- Hours effect: none. P7-T04 is 2 h and P8-T02 is 3 h either way.

### T5-07 The dashed P6-to-P9 edge has no task
- Claim: the phase graph draws `P6 -.-> P9`. P9's package line says it reuses `flow`. The goal says the lane reuses "the P3 to P6 parts."
- Where: `PLAN.md`, "Phase dependency graph"; `phases/P09-backend-lane.md`, budget line and "Goal".
- Contradiction: no P9 task's `Depends on` or acceptance criteria names `flow`, DBOS, the webhook, the poller, or the control plane. The lane tasks stop at the eval runner (P9-T10 names the P5 runner), the reuse script (P9-T11), and ADR-030. not scheduled.
- Evidence: [CODE]
- Severity: Med. The optional lane can still be built as a local loop. The graph's claim that it reuses the deployed workflow is not a task, so that edge cannot be executed.
- Hours effect: none. P9 stays 40 h, and none of those hours are a `flow` task.

### T5-08 P6's graph predecessors are not the task P6 actually depends on
- Claim: the graph draws solid arrows `P4 --> P6` and `P5 --> P6`, and no arrow from P5.5 to P6. P5.5 points at P7 only.
- Where: `PLAN.md`, "Phase dependency graph". P6-T00 depends on P5.5-T17 (`phases/P06-argus-flow.md`). P6-T04's acceptance says the dispatched job "executes repro, fix and verify" and its `Depends on` is only P6-T03. P6-T25's title is "phase report against P5"; its `Depends on` is P6-T18.
- Contradiction: no P6 task lists a P4 id or a P5 id. The only P5.5 id on a P6 task is P5.5-T17, on the first task of the phase, and that edge is not in the graph. "verify" appears as a word in P6-T04, not as a dependency. The phase-report title is the only P6 line that names P5.
- Evidence: [CODE]
- Severity: Med. A reader of the graph can start P6 after P5 and skip P5.5. The checklist's first P6 task does not allow that. Cutting P5.5 makes the same link dangling (T5-13).
- Hours effect: none.

## 5. Acceptance criteria

None of the 272 acceptance cells is empty. The two below do not have a pass/fail a reviewer can apply as written.

### T5-09 P4-T02 fails a shift it also says is masked out
- Claim: "Passes on a clean tree, fails on a tree with a 4 px shift in a masked-out-of-scope area; threshold is a named constant."
- Where: `phases/P04-verify.md`, task P4-T02. The same task builds "pixel-diff check against the golden screenshot with region masks."
- Contradiction: the shift is described as inside an area the mask takes out of scope. A mask that ignores that area passes. The sentence says the check fails. The two outcomes cannot both be the acceptance test.
- Evidence: [CODE]
- Severity: Med. This is the task that defines the pixel check. Its own test does not say whether a masked shift is a pass or a fail.
- Hours effect: none. The task stays 2 h.

### T5-10 P0-T12's criterion is about tasks that do not exist yet
- Claim: "`docs/bug-archetypes.md` lists archetypes and tier criteria; every later seeded task references one archetype."
- Where: `phases/P00-argus-bench.md`, task P0-T12. P0-T13 ("Generate boilerplate for 30 seeded bug tasks") depends on P0-T12 and is the next checkbox (`TASKS.md` Week 2).
- Contradiction: when P0-T12 is the task being accepted, the seeded tasks are still the later task. P0-T13's own acceptance says the 30 directories validate and that there are 10 per tier. It does not say each one references an archetype. The archetype link is only on the task that finishes first.
- Evidence: [CODE]
- Severity: Low. The document half of the criterion is testable. The "every later seeded task" half is not testable at the task it is attached to.
- Hours effect: none. P0-T12 is 1 h.

## 6. Single points of failure

The risk register (`PLAN.md` "Risk register (top 5)", repeated in `PROJECT.md` "Risks") already names these single points and a mitigation: one set of free-tier quotas (row 1, with the ledger and "at least two hosts per role"), a weak fixer (row 2), one Neon database plus one Render service (row 3), one Playwright MCP server (row 4, with a direct-Playwright fallback), and one person at 20 h/week (row 5, with the cut line and the two buffer weeks). The QA wait is specified as two paths (P6-T09 and P6-T10). Those are listed, so they are not repeated here as unlisted.

### T5-11 The judge and the embeddings have one CPU, and that CPU is not a risk-register row
- Claim: the machine is "a 13th-gen Intel i7-13620H with 16 GB RAM, no discrete GPU." The intent judge is "Local Ollama `gemma4:e4b` on CPU for the ~100-pair calibration." Embeddings are "Ollama or sentence-transformers on CPU."
- Where: `PROJECT.md`, "Constraints that shape the design" and "Models". The risk register rows are the five in `PLAN.md` "Risk register". P4-T14 is named under "The three tasks most likely to force a redesign", not in the register. P4-T15 checks for a hosted Gemma; that task is the runtime decision, not a second machine for the calibration.
- Contradiction: the register does not list the single laptop. The calibration run (P4-T13, "overnight, CPU") and the local embedding index (P2-T10) have no second computer in the plan.
- Evidence: [CODE]
- Severity: Med. If this CPU cannot finish the 100-pair judge run, the calibration that the plan says must not be cut has no other machine. The register will not show that until the redesign list, which is a different table.
- Hours effect: none.

### T5-12 GitHub Actions is the only execution plane, and it is not a risk-register row
- Claim: "The actual agent job runs on GitHub Actions." From P6, "GitHub Actions as the execution plane." P8 moves that job into the tenant repo's reusable workflow, still on Actions. The dashboard is GitHub Pages. Row 1's example of a disappeared free tier is "GitHub Models", not Actions minutes or Pages.
- Where: `PROJECT.md`, "What a finished run looks like" and "Infrastructure"; `PLAN.md` risk row 1.
- Contradiction: not in the risk register. There is no second execution plane and no task that names one. Phoenix is a second trace backend (P5-T09), not a second place to run the agent.
- Evidence: [CODE]
- Severity: Med. A change to Actions minutes or to public-repo policy stops both the bench CI and the deployed job. The register's free-tier row does not cover that host.
- Hours effect: none.

### T5-13 Langfuse Hobby's 50k units are a single trace quota and are not a risk row
- Claim: "Langfuse Cloud Hobby is the default viewer" at "50k units/month." Phoenix is the swap, "noted in ADR-015", and P5-T09 is the swap proof.
- Where: `PROJECT.md`, "Infrastructure"; `PLAN.md` risk register (no Langfuse row). The cap is restated in `PLAN.md` "Known free-tier collisions" only as a number, not as a risk row.
- Contradiction: not in the risk register. P5-T25 says a dead trace backend does not fail the agent run, so the fix path survives. The 50k cap can still drop the traces the dashboard and the README are supposed to link (P5-T23).
- Evidence: [CODE]
- Severity: Low. A swap is scheduled, so this is a missing register row, not a missing mitigation task.
- Hours effect: none.

## 7. Cut list

`PLAN.md` and `PROJECT.md` "Cut list" name the same six cuts, in the same order, and the same never-cut line: "the P3 loop, the P4 judge calibration, the bugsmith generator, the P5 OTel work, or best-of-k." None of those five names is also a cut-list item. Bugsmith is P0-T21 through P0-T26, not a cut. Best-of-k is P4-T19 (3 h), P4-T20 (4 h), and P4-T21 (2 h), not a cut. OTel is P5-T06 through P5-T10, not a cut.

Hours below start from the core sum 556 h / 255 tasks and the grand sum 596 h / 272 tasks. A cut's remaining hours are those totals minus only the tasks named here.

P9, the whole lane, is P9-T00–T16, 17 tasks, 40 h. No task after P9 exists, so nothing still on the list depends on a removed id. Remaining: 556 h and 255 tasks (grand total falls from 596 to 556).

SWE-bench Multimodal is P5-T19 (3 h) and P5-T20 (3 h). P5-T20 depends on P5-T19. No other task lists either id. Remaining if this is the only cut: core 556−6 = 550 h, grand 596−6 = 590 h. The P5 portfolio sentence still asks for "the SWE-bench Multimodal subset results", but no remaining task depends on these two.

### T5-14 Cutting P5.5 leaves the first P6 task and a P7 task pointing at removed ids
- Claim: cut 3 is "P5.5, argus-skills." The never-cut line does not include P5.5. The hard cut line is the end of P6, so the cut is meant to drop skills and keep the deployed core.
- Where: `PLAN.md`, "Cut list"; `phases/P06-argus-flow.md` P6-T00 (`Depends on` P5.5-T17); `phases/P07-argus-guard.md` P7-T07 (`Depends on` P5.5-T10, "injection via ticket, repo file and skill").
- Contradiction: P5.5 is P5.5-T00–T17, 18 tasks, 28 h. After those ids are removed, P6-T00 still depends on P5.5-T17, and P7-T07 still depends on P5.5-T10. P6-T00 is the version re-check that starts the deployed core. The graph does not draw P5.5→P6 either (T5-08), so the checklist and the graph disagree on whether P6 needs the thing the cut list deletes.
- Evidence: [CODE]
- Severity: High. Taking the published third cut makes the first task of P6, which the plan says is the part you keep, depend on a task the cut removed.
- Hours effect: 28 h removed. Remaining core 556−28 = 528 h (249 tasks). Remaining grand 596−28 = 568 h. P6-T00 (1 h) and P7-T07 (2 h) are still inside that remainder.

### T5-15 Cutting Firecracker leaves the tier ablation depending on the removed run
- Claim: cut 4 is "The Firecracker tier, reduced to an ADR plus a gVisor measurement." P7 done-when: "If Firecracker is cut, row C stays empty and ADR-025 says why."
- Where: `PLAN.md`, "Cut list"; `phases/P07-argus-guard.md`, "Done when", P7-T11 (3 h), P7-T13, P7-T15 (ADR-025).
- Contradiction: P7-T13 depends on P7-T11 and its acceptance says "Rows A, B and C filled from real runs." The cut deletes the Firecracker run (row C's source) and keeps the ablation and the ADR. P7-T13's acceptance still requires row C. P7-T10 (gVisor, 2 h) and P7-T15 (1 h) are the pieces the cut says to keep.
- Evidence: [CODE]
- Severity: Med. The cut and the task that would remain do not accept the same row C. Someone following the cut list still has a task that cannot be accepted as written.
- Hours effect: only P7-T11's 3 h is clearly the Firecracker run. Remaining core 556−3 = 553 h. P7-T13's 3 h stays on the list. Grand 596−3 = 593 h.

### T5-16 Cutting MRTR leaves ADR-023 depending on the removed task
- Claim: cut 5 is "MRTR elicitation, replaced by plain GitHub review comments (P6-T10 is already the fallback)."
- Where: `PLAN.md`, "Cut list"; `phases/P06-argus-flow.md`, P6-T09 (3 h) and P6-T18.
- Contradiction: P6-T18 ("Write ADR-023") depends on P6-T09 and P6-T10. The cut keeps the fallback (P6-T10, 1 h) and the ADR, and it removes P6-T09. The ADR task still lists the removed id. No other task lists P6-T09.
- Evidence: [CODE]
- Severity: Med. The fallback task is real, so the product path exists. The decision task that the cut still needs cannot be checked off without the task the cut deletes.
- Hours effect: 3 h removed. Remaining core 556−3 = 553 h. Grand 596−3 = 593 h. P6-T18 (1 h) stays.

### T5-17 The multi-tenancy cut does not name ids, and the budget CI task still depends on the budget task
- Claim: cut 2 is "P8 multi-tenancy, down to a single-tenant App." The sentence names no task id.
- Where: `PLAN.md`, "Cut list". The tasks whose titles are the second tenant are P8-T07 "per-tenant quota budgets" (3 h), P8-T14 "ADR-028: Per-tenant quota budgets" (1 h), and P8-T21 "one tenant exhaust its budget while another runs" (2 h), in `phases/P08-argus-app.md`.
- Contradiction: P8-T14 and P8-T21 depend on P8-T07, so removing all three clears those two. P8-T20 still depends on P8-T07 and P8-T04, and its acceptance says the tests "cover token minting, label permissions and budgets." P8-T20 is not a per-tenant task; it is the app CI job, and it remains. Other P8 tasks (the manifest, the reusable workflow, `.argus.yml`, intake, the PR, the backport) are not counted here, because the cut sentence does not say they go.
- Evidence: [CODE]
- Severity: Med. After the cut, a remaining task still requires the per-tenant budget it was supposed to lose. The 6 h figure is only the three titled tasks, not a guess at the rest of P8.
- Hours effect: 6 h if those three are the cut. Remaining core 556−6 = 550 h. Grand 596−6 = 590 h. P8's other 54 h stay. P8-T20 (2 h) stays and still names P8-T07.

## 8. Claims no task schedules, and the HTML companions

Checked against the task tables and not given their own finding, because a task does schedule them: the quota ledger (P0-T07), `docs/quotas.md` (P0-T06), the 300-task generation (P0-T26), the repro spike and verifier (P1-T01, P1-T08), `locate()` (P2-T05–T08), the from-scratch loop and the four context strategies (P3-T06, P3-T10–T12, P3-T18), replay (P3-T27), the 100-pair labels and alpha (P4-T10, P4-T12, P4-T14), best-of-k at k = 1, 3, 5 (P4-T19, P4-T20), OTel and the normalizer (P5-T06, P5-T08), the CI gate (P5-T16, P5-T17), the skills loader and the poisoned-skill break-its (P5.5-T02, P5.5-T13, P5.5-T14), DBOS, the 202 webhook, the poller, and the crash test (P6-T03, P6-T06, P6-T07, P6-T19), the threat model and the escape suite (P7-T02, P7-T12), the reusable workflow, the backport, and the demo video (P8-T04, P8-T10, P8-T18), and the pytest lane (P9-T06–T10). `142-fix.html` is covered at the end of this section.

### T5-18 "At least two hosts per role" is not a task for the fixer or the cheap tier
- Claim: risk 1's mitigation is "at least two hosts per role" plus a local Ollama fallback "for the judge and embeddings."
- Where: `PLAN.md`, risk row 1; `PROJECT.md`, "Models".
- Contradiction: the model table gives the fixer one host (Mistral free tier) and the cheap tier one host (Groq free tier, two model names). P0-T05's client can point at Groq, Mistral, or Ollama by `base_url`. No task adds a second fixer host or a second cheap-tier host. P5-T12 says "fallback to the other host on quota refusal" and does not name that host for the fixer. P4-T15 is the hosted-Gemma check for the judge only. not scheduled for the fixer role or the cheap-tier role.
- Evidence: [CODE]
- Severity: Med. The risk row's mitigation is the thing you would rely on when a free tier disappears, and the task list never builds it for two of the three roles.
- Hours effect: none. No hours are assigned to a second host.

### T5-19 The Playwright no-go branch is an ADR, not a build task
- Claim: "If it is no-go, direct Playwright is wired in as a tool instead (ADR-004)." Risk 4 says the same, and names P1-T01, P1-T02, and P2-T00.
- Where: `phases/P01-repro-agent.md`, "Done when"; `PLAN.md`, risk row 4.
- Contradiction: P1-T02's acceptance is that the ADR "states the choice, the spike evidence and the fallback." It is a doc task (1 h). P1-T04 defines the six tool schemas after the ADR, and it does not say to implement a direct Playwright tool when the spike is no-go. No other task says that. not scheduled as implementation.
- Evidence: [CODE]
- Severity: Med. If P1-T01 is a go, the gap stays closed. If it is a no-go, the mitigation the risk row promises has a document and no build task.
- Hours effect: none. The spike is 3 h and the ADR is 1 h. The fallback has no hours.

### T5-20 Dollar-equivalent is a column from P0, and prices.json is a P5 task
- Claim: every phase report includes "$-equivalent", defined as "Tokens times published list prices from `prices.json`". P0 done-when says the ablation tables "are filled in". The P0 ablation table has a "$-equivalent/bug" column. The same column is on every later phase ablation table.
- Where: `PROJECT.md`, "Metrics contract"; `phases/P00-argus-bench.md`, "Done when" and the ablation table; `phases/P05-argus-eval.md`, P5-T11.
- Contradiction: P5-T11 ("`prices.json` has source URL and date per model") is `TASKS.md` Week 19. P0-T29, which fills the P0 ablation table, is Week 4. No task between P0-T29 and P5-T11 creates the price file. not scheduled in the phases whose tables already have the column.
- Evidence: [CODE]
- Severity: Med. P0 through P4 are told to fill a column whose only source file is built in P5. Leaving the cell as "—" conflicts with "filled in"; inventing a price conflicts with the metrics rule.
- Hours effect: none. P5-T11 is 2 h and stays in Week 19.

### T5-21 Quota share is a fifth metric, and only one P5 run is told to report it
- Claim: "Every phase reports the same five numbers", and the fifth is "Quota share/bug". `PLAN.md`'s "Learning rules" list four (resolve rate, tokens/bug, $-equivalent, and p50/p95 latency) and omit quota share.
- Where: `PROJECT.md`, "Metrics contract" and "Phases"; `PLAN.md`, "Learning rules" and "Metrics contract"; `phases/P05-argus-eval.md`, P5-T04 and P5-T14.
- Contradiction: P5-T04's results JSON is "resolve rate, interval, tokens and latency percentiles." It does not name quota share. P5-T14 does: "tokens, quota share, resolve rate and latency reported", for the routing ablation only. No P0–P4 task says to compute quota share. The ledger (P0-T07) records usage. Dividing by the daily cap is not scheduled for those phases. not scheduled except inside P5-T14.
- Evidence: [CODE]
- Severity: Med. The contract says all five numbers are comparable from phase to phase. The task that would make the fifth number exist does it for one P5 ablation.
- Hours effect: none.

### T5-22 The P9 dashboard series and the P0 OTel helpers have no task in the phase that claims them
- Claim: P9's deploy checkpoint says "the lane's results appear as a second series on the GitHub Pages dashboard." The P0 package `argus-core` "holds" "OTel helpers" (`PROJECT.md` package table and `repo-structure.md`).
- Where: `phases/P09-backend-lane.md`, "Deploy checkpoint"; `PROJECT.md`, "Monorepo"; `repo-structure.md`, package table. The dashboard task is P5-T21. The OTel task is P5-T06.
- Contradiction: no P9 task mentions the dashboard or a second series. P5-T21 renders "one chart per metric from files in the repo", and it is finished in Week 19, before any P9 file exists. No P0 task mentions OTel. P5-T06 is the instrumentation task. not scheduled in P9, and not scheduled in P0.
- Evidence: [CODE]
- Severity: Low. The UI lane's dashboard and the spans are scheduled in P5. What is unscheduled is the second series, and the placement of OTel helpers on the P0 package.
- Hours effect: none.

### T5-23 State names: locate is a state in both HTML files and not in the P6 dispatch task
- Claim: architecture card "Ticket state machine": "repro → locate → fix → verify → PR". `production.html` rail: Queued, Repro, Locate, Fix, Verify, PR open, Awaiting QA, Done. The footer says those "match the P6 machine."
- Where: `architecture.html`, card `o-sm`; `production.html`, `RAIL` and the footer. P6-T03 reaches `done`. P6-T08 pauses in `awaiting-qa`. P6-T04's acceptance: "executes repro, fix and verify". P6's package line uses `fix-loop`, `verify`, and `repro-agent`, and does not list `dom2src`.
- Contradiction: `awaiting-qa` and `done` are in the P6 tasks and in `production.html`. They are not on the architecture state card. `locate` is a separate state in both HTML files. No P6 acceptance criterion names a locate state. The production dispatch summary also says "Repro, fix, and verify" while that step's artifact line includes locate. The locate tool itself is scheduled in P2, and P3-T16 puts a locate hint in the fix prompt. A locate workflow state is not scheduled.
- Evidence: [CODE]
- Severity: Med. The deployed state machine is the P6 deliverable. The two companions and the dispatch task name different states, so it is not determined whether locate is its own step.
- Hours effect: none.

### T5-24 The two HTML files name different phases as the thing that opens the pull request
- Claim: architecture card "Open PR" is phase P8, subtitle "patch + verdict + trajectory". `production.html` step "Open one pull request" is phase P6, "Control plane → GitHub": "The workflow opens the PR with find-or-create."
- Where: `architecture.html`, card `a-pr`; `production.html`, step "Open one pull request". `PROJECT.md` P6 narrative: "opening a pull request is find-or-create, keyed by ticket id." P6-T21 is the crash between opening the PR and saving state. P8-T09 is "Build PR creation with verdict, trajectory link and before and after screenshots."
- Contradiction: P6 and P8 each schedule PR work. The architecture card assigns the open action to P8. The production step assigns it to the P6 control plane. `PLAN.md`'s architecture mermaid has no open-PR node; it has `VERIFY --> GH`. The production step also says the run attaches `142-fix.html`. No task's acceptance mentions an HTML fix-report file. P8-T09 puts the verdict, the judge label, a trajectory link, and two screenshots in the PR body.
- Evidence: [CODE]
- Severity: Med. "Who opens the PR" is answered three ways. The HTML report file the production walkthrough attaches is not a task.
- Hours effect: none. P6-T21 is 2 h and P8-T09 is 3 h, both still scheduled.

### T5-25 Judge versus checks, and where best-of-k sits
- Claim: `PROJECT.md` P4: checks "short-circuit on the first hard failure (ADR-012)." The judge "ships as a hard gate only if" alpha "reaches 0.80. Otherwise it stays advisory." P4-T19: "`best_of_k(k)` returns the selected patch" and "verifier and judge pick one."
- Where: `PROJECT.md`, "P4 — verify"; `phases/P04-verify.md`, P4-T06 ("order is configurable in one place") and P4-T19. `PLAN.md` mermaid: `FIX --> BOK`, `BOK --> VERIFY`, `VERIFY --> JUDGE`. `architecture.html` header: "Deterministic checks gate every patch before any model judge." The guardrail note: "the judge never overrides them." Card `a-ver`: "checks first · judge second · fail closed." Wires: `a-fix` to `a-bok` to `a-ver`, then pixel to overflow to axe to console to judge. `production.html` rules: the four checks "stop at the first hard failure. The vision judge writes an intent note after a full pass." The verify step: best-of-k "is a cost knob in front of this gate", and "If agreement with human labels is below the bar, its note is advisory."
- Contradiction: three orders are written down. The mermaid and the architecture wires put best-of-k before the verifier, then the judge. P4-T19 puts the verifier and the judge inside the selector. The production rules put the judge after a full check pass, as a note. "Never overrides" (architecture) and "hard gate if alpha is at least 0.80" (P4 / ADR-013) are not the same rule: a hard-gate judge rejects a patch the checks passed. P4-T06 also says the check order "is configurable in one place", while both HTML files fix one order.
- Evidence: [CODE]
- Severity: Med. The selector is the P4 result the later phases treat as the verdict. The plan does not pick whether the judge can reject a clean check run, or whether best-of-k runs before those checks or uses them.
- Hours effect: none. P4-T19 is 3 h and P4-T20 is 4 h.

### T5-26 Production's check list drops warnings and drops bench checks
- Claim: P4-T05 is "console check reporting new errors and warnings." Architecture card `v-con`: "new errors and warnings." P3-T14 gates are "build, typecheck, lint, unit tests and bench checks." Architecture card `g4`: "build · typecheck · lint · unit · bench checks (read-only)."
- Where: `phases/P04-verify.md` P4-T05; `phases/P03-fix-loop.md` P3-T14; `architecture.html` cards `v-con` and `g4`; `production.html` verify step ("console, new errors only") and the fix step ("Gates, read-only: build, typecheck, lint, unit tests").
- Contradiction: the production verify step and its sample artifact mention new console errors and do not mention warnings. The production fix step's gate list stops at unit tests. The phase tasks and the architecture cards include warnings and bench checks. The order pixel, then overflow, then axe, then console otherwise matches across `PROJECT.md`'s P4 intro, the architecture wires, and the production step.
- Evidence: [CODE]
- Severity: Low. The phase tasks are the ones with hours. The production page, which is the "one ticket" companion, describes a shorter check list than those tasks.
- Hours effect: none.

`142-fix.html` does not assert a measured result. It is the sample report for the worked example `you/shop-ui#142`. The figures on it are the example ticket's viewport (`375px`) and the example CSS (`min-width: 320px`, then `width: 100%` and `min-width: 0`), the same ticket `production.html` spells out, plus the sample pills "pixel · overflow · axe · console pass" and "judge: intent met". There is no resolve rate, token count, latency, alpha, quota share, or dollar figure. The footer says the checks, not the page, decide whether a pull request opens. That agrees with the production rules and does not add a measured number.

## Findings

| id | severity | one line |
|---|---|---|
| T5-01 | Low | 28×20 h = 560 h, core tasks sum to 556 h, and weeks 1–30's work weeks sum to 561 h because week 30 holds 5 h of P9. |
| T5-02 | Low | Twelve work weeks are not 20 h; TASKS headers match the checkbox sums, and PROJECT still calls every week a 20 h bin. |
| T5-03 | Low | ADR-004 is written in week 5; P2-T00 in week 6 says to note spec support for it, and no task revises the ADR. |
| T5-04 | Med | P6's "base" weeks W20–23 do not map onto TASKS weeks 22–24, where the 52 h actually are. |
| T5-05 | Low | P9's "+2 weeks" omits week 30, which already contains P9-T00–T02 (5 h). |
| T5-06 | High | P7-T04's App-token tests are in week 24, and the App manifest that depends on them is in week 27. |
| T5-07 | Med | The dashed P6→P9 edge is in the graph, and no P9 task mentions flow or DBOS. |
| T5-08 | Med | The graph says P4 and P5 feed P6; the only predecessor id on P6 is P5.5-T17, which the graph does not draw. |
| T5-09 | Med | P4-T02 says a pixel check fails on a shift that the same sentence places in a masked-out area. |
| T5-10 | Low | P0-T12 requires every later seeded task to name an archetype, and those tasks are created by P0-T13. |
| T5-11 | Med | The judge calibration and the embeddings use one laptop CPU, and that CPU is not a risk-register row. |
| T5-12 | Med | GitHub Actions is the only execution plane, and the risk register's free-tier row does not name it. |
| T5-13 | Low | Langfuse's 50k units/month are the default trace quota and are not a risk-register row. |
| T5-14 | High | Cutting P5.5 (28 h) leaves P6-T00 and P7-T07 depending on removed tasks; 528 core hours remain. |
| T5-15 | Med | Cutting Firecracker removes P7-T11 (3 h) and leaves P7-T13 requiring a filled row C; 553 core hours remain. |
| T5-16 | Med | Cutting MRTR removes P6-T09 (3 h) and leaves ADR task P6-T18 depending on it; 553 core hours remain. |
| T5-17 | Med | The per-tenant cut is 6 h of P8-T07, T14, and T21, and P8-T20 still depends on P8-T07; 550 core hours remain. |
| T5-18 | Med | "Two hosts per role" is not scheduled for the fixer or the cheap tier. |
| T5-19 | Med | A Playwright MCP no-go "wires direct Playwright in" only as ADR-004, with no build task. |
| T5-20 | Med | Ablation tables include $-equivalent from P0, and prices.json is created by P5-T11 in week 19. |
| T5-21 | Med | Quota share is a required metric, and only P5-T14 is told to report it. |
| T5-22 | Low | A P9 dashboard series and P0 "OTel helpers" are claimed in phases that have no task for them. |
| T5-23 | Med | Both HTML files make locate its own state; P6-T04 dispatches repro, fix, and verify. |
| T5-24 | Med | Architecture assigns opening the PR to P8; production assigns it to the P6 control plane; 142-fix.html is not a task. |
| T5-25 | Med | Best-of-k is before the checks in the diagram, inside the selector in P4-T19, and the judge is both a note and a hard gate. |
| T5-26 | Low | production.html drops console warnings and bench checks that the phase tasks and architecture cards include. |

Summary: 26 findings. High 2 (T5-06, T5-14). Med 16 (T5-04, T5-07, T5-08, T5-09, T5-11, T5-12, T5-15, T5-16, T5-17, T5-18, T5-19, T5-20, T5-21, T5-23, T5-24, T5-25). Low 8 (T5-01, T5-02, T5-03, T5-05, T5-10, T5-13, T5-22, T5-26). Phase budgets, the 255 / 556 core total, and the 272 / 596 grand total match across the phase tables and `TASKS.md`. File: `c:\Users\vibha\Downloads\data\personal\argus\analysis\research\T5-plan-critic.md`.
