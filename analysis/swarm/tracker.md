# Tracker lane: waves, critical path, weekly view

Data: `analysis/swarm/tracker.json` (272 tasks, 11 phases, validated with node). Built by a scratchpad parser from `TASKS.md` and the Tasks tables in `phases/P00..P09`. Wave model copied from `docs/architecture/p1.md:47-59`; the parser reproduces that P1 split exactly (11 waves, same members).

## 1. Reconciliation (nothing forced)

| Claim | Source | Parsed | Verdict |
|---|---|---|---|
| 49 done / 223 open | brief | 49 / 223; every `[x]` is a P0 or P1 task, every P0/P1 task is `[x]` | matches |
| 272 tasks, 255 core + 17 P9 | `TASKS.md:7` | 272 = 255 + 17 | matches |
| 556 core h, 40 P9 h, 596 total | `TASKS.md:7`, `PLAN.md:227` | 556 / 40 / 596 | matches |
| Per-phase h and tasks | `PLAN.md:216-226` | all 11 rows equal the table sums and each phase header Budget | matches |
| Checklist vs phase tables (title, owner, hours) | `TASKS.md` vs `phases/` | 0 mismatches, 0 orphans | matches |
| Unknown deps / cycles | | 0 / 0 | clean |
| Checklist order respects every dep | | 0 violations | clean |
| Weeks under 20 h | `TASKS.md:3` | 9, 10, 15, 19, 20, 27, 31, 32 with 19, 19, 19, 18, 19, 19, 19, 16 h | matches |
| "a week can run up to 3 h over" | `TASKS.md:3` | max over is 2 h (weeks 8, 18 = 22 h; 12, 14, 23, 26 = 21 h) | true but loose: the bound observed is 2 h |
| Week headings "(N h scheduled)" | `TASKS.md` | all 30 non-buffer headings equal the sum of their tasks | matches |
| Week = floor(start h / 20) + 1, buffers 17 and 25 | `TASKS.md:3` | reproduces every task's listed week | matches |
| Done so far | | 108 h = 5.4 weeks of 20 h (weeks 1-5 full, week 6 holds P1-T12..T16 only) | |

Honest gaps found while parsing (none change the 556 / 255 figures):

- **Phase gates are soft.** Each phase's T00 depends only on the previous phase's final README task, and that README depends on a subset. 131 tasks (269 h) in P0-P8 are not ancestors of the next phase's T00, for example 18 of P3's 34 tasks (the five break-its T28-T32, ADR-008..010, the context ablation T19 and the failure taxonomy T21 among them) do not gate P4-T00. Per-phase list: `checks.tasksNotGatingNextPhase` (checked against the P3 table: P4-T00 depends on P3-T33, which depends on P3-T25). Today only checklist order, not the graph, forces "break-its before phase close". A dependency-driven scheduler would let P4 start before P3's break-its.
- **Cut 3 retarget is half-specified.** `PLAN.md:322` says P6-T00 "moves off" P5.5-T17 but names no replacement. Only P7-T07 gets an explicit replacement (P7-T02, from the conditional dep). Inference, not in the plan: P5-T28.
- **Cuts do not shrink the schedule on paper.** `PLAN_REVIEW.md:39-42` says the -28, -6, -3, -3 h from cuts 3, 2, 4, 5 "stay unbooked". Real freed hours if taken: cut 1 = 40, cut 2 = 6, cut 3 = 28, cut 6 = 6 (cuts 4 and 5 remove no task; 3 h each is the unbooked amount).
- Phase header weeks differ from calendar weeks (P5-P8) because headers use the base plan before buffer weeks, and say so (e.g. `phases/P05.5-argus-skills.md:3`). Not an error.

## 2. Waves and critical path per phase (intra-phase deps; earlier phases treated as met)

`CP` = longest path by hours. A single person is bound by total hours, not CP; CP shows what is dependency-free.

| Phase | Status | h / tasks | Waves | Widest wave | CP h | CP chain (task numbers) |
|---|---|---|---|---|---|---|
| P0 | done | 76 / 32 | 10 | 5 | 25 | T00>T01>T09>T10>T21>T22>T24>T26>T29>T31 |
| P1 | done | 32 / 17 | 11 | 4 | 21 | T00>T01>T02>T04>T05>T07>T08>T10>T11>T12>T16 |
| P2 | open | 44 / 20 | 9 | 4 | 21 | T00>T02>T05>T06>T07>T08>T12>T13>T19 |
| P3 | open | 84 / 34 | 10 | 8 | 27 | T00>T01>T02>T06>T07>T15>T18>T19>T21 |
| P4 | open | 72 / 30 | 10 | 6 | 28 | T00>T01>T08>T11>T13>T14>T19>T20>T21>T29 |
| P5 | open | 64 / 29 | 10 | 5 | 21 | T00>T01>T02>T03>T04>T05>T21>T22>T23>T28 |
| P5.5 | open | 28 / 18 | 7 | 5 | 11 | T00>T03>T04>T05>T06>T08>T09 |
| P6 | open | 52 / 26 | 9 | 6 | 20 | T00>T01>T02>T03>T05>T06>T07>T19>T21 |
| P7 | open | 44 / 23 | 7 | 6 | 13 | T00>T01>T02>T05>T12>T13>T15 |
| P8 | open | 60 / 26 | 10 | 7 | 24 | T00>T02>T03>T08>T09>T10>T16>T17>T19>T25 |
| P9 | open | 40 / 17 | 11 | 3 | 25 | T00>T01>T02>T05>T06>T07>T08>T10>T11>T12>T16 |

- **Whole core plan (P0-P8, cross-phase deps): CP = 198 h over 90 tasks (35.6% of 556 h).** Including P9: 223 h over 101 tasks. Because each T00 gates on the previous README, phases are serialized in the graph; the core CP is the sum of the gated phase segments. The other 358 core hours are off-path and could slide, but one person still has to do them.
- Wave detail (members, hours, per task `wave` and `globalWave`) is in the JSON. Widest waves mix strategy builds, CI, break-its and ADRs (P3 wave 6 = 8 tasks: T10, T11, T12, T15, T26, T27, T29, T30; P8 wave 5 = 7).

## 3. Who can run what in parallel

Per task `parallel.kind` (open tasks / all): serial 29 / 38, claude-alongside-me 67 / 78, idle-wait-overlap 46 / 59, independent-serialize-for-one-person 81 / 97.

- **truly concurrent (two workers):** `claude-alongside-me`: wave-mates where one is [CLAUDE] and another is [ME]/[PAIR]. Examples: P2-T03 (CLAUDE tests) beside P2-T05 (locate core, ME); P8-T04 (CLAUDE reusable workflow) beside P8-T03 (PAIR) and P8-T15 (ADR, ME).
- **one person + idle wait:** `idle-wait-overlap`: wave contains a long run, so do a wave-mate while it runs. 20 tasks carry `idleWait` (overnight / 48 h / quota-bound runs): P0-T26, P0-T29, P1-T10, P1-T11, P2-T12, P3-T18/T19/T20, P4-T13 (overnight CPU), P4-T17, P4-T20, P5-T14, P5-T20, P5.5-T08, P6-T14 (48 h), P6-T19, P7-T08, P7-T13, P8-T12, P9-T10. Heuristic, not hand-labelled. P1-T11, P3-T18 and P9-T10 have no wave-mate, so the run blocks the phase unless work from the next phase is pulled in (`PLAN.md:231` says this is the intent).
- **independent but still one person:** DAG-independent, but each needs a human; they serialize. Most break-it and ADR wave-mates.
- **[ME]-only, do not delegate** (`PLAN.md:18`, `PROJECT.md:38`): 170 tasks, 383 h (360 h core, 315 h open). Split: core-build 51 tasks / 155 h (loop, tool schemas, context manager, verifier, judge, eval scorer, workflow state machine, threat model), eval-run 31 / 86 h, break-it 46 / 93 h, ADR 30 / 32 h (all 30 ADRs), reading-notes 12 / 17 h. Flag fields: `meOnly`, `neverDelegate`, `meKind`. PAIR is 51 tasks / 125 h (you write, Claude reviews); CLAUDE is 51 tasks / 88 h, so at most ~15% of hours are fully delegable.

## 4. Weekly view at 20 h/week

- Calendar: 32 weeks = 30 working weeks + buffers at 17 and 25. Core ends in week 30 (week 30 holds 15 core h + 5 h of P9); P9 ends week 32.
- 556 / 20 = 27.8 weeks -> 28 + 2 buffers = 30, as `PLAN.md:229` says. 596 / 20 = 29.8 -> 32 with buffers.
- Remaining: 223 tasks, 488 h (448 core) = 24.4 weeks, scheduled weeks 6 (tail) to 32. Per-week table: `weekly.perWeek` (hours, phases, tasks, done flag).
- Cumulative cut scenarios (remaining h / weeks): after cut 1 = 448 / 22.4; +2 = 442 / 22.1; +3 = 414 / 20.7; +4, +5 = 414 (nothing booked); +6 = 408 / 20.4. Dropping to the hard cut line after P6 is a different scenario (P7 44 h + P8 60 h removed = 104 h plus P9); not in `PLAN.md`'s cut list, so not computed as a cut.

## 5. Cut list (`PLAN.md:318-327`) and retargets

| # | Cut | Removes | h | Retargets (default -> when cut) |
|---|---|---|---|---|
| 1 | P9 | all 17 P9 tasks | 40 | none |
| 2 | P8 multi-tenancy | P8-T07, T14, T21 | 6 | P8-T20: P8-T07, P8-T04 -> P8-T04 (budget assertion dropped) |
| 3 | P5.5 skills | all 18 P5.5 tasks | 28 | P7-T07: P7-T02, P5.5-T10 -> P7-T02; P6-T00: P5.5-T17 -> unspecified (see gaps) |
| 4 | Firecracker tier | none (P7-T11 stays) | 0 booked, 3 unbooked | P7-T13 acceptance allows empty row C (text, not a dep) |
| 5 | MRTR | none (P6-T09 would be freed) | 0 booked, 3 unbooked | P6-T18: P6-T09, P6-T10 -> P6-T10 |
| 6 | SWE-bench Multimodal | P5-T19, P5-T20 | 6 | none; no task depends on them |

Never cut (`PLAN.md:327`): P3 loop, P4 judge calibration, bugsmith generator, P5 OTel work, best-of-k. The task-id mapping for the last four (`cuts.neverCut`) is mine, marked as inference. Phase-level `cutOrder` is set on P0, P3, P4, P5 and P5.5-P9 (P1, P2 have none).

## Verification log

Re-checked:
- `node` parses `tracker.json`; counts 272 tasks, 11 phases, 49 done, 223 open, 255/556 core, 17/40 P9, 596 total.
- P1 wave output equals `docs/architecture/p1.md:49-59` line by line.
- All 4 irregular dependency cells (`P0-T00` "—", plus the three "when the X cut is taken" cells at `phases/P06-argus-flow.md:54`, `phases/P07-argus-guard.md:42`, `phases/P08-argus-app.md:56`) parse as intended; conditional deps use the no-cut list as default.
- Week sums recomputed from tasks against each `## Week N (… h scheduled)` heading and the 8 under-20 weeks named at `TASKS.md:3`.
- `PLAN.md:216-227` per-phase hours and task counts against parsed sums.
- Cut hours (-28, -6, -3, -3) against `PLAN_REVIEW.md:39-42`; grep confirmed nothing depends on P5-T19/T20.

Corrected during the run:
- First draft reported "week 6" as the first open week; it holds five done P1 tasks, so the remaining view says "week 6 (tail)".
- Added `tasksNotGatingNextPhase` after noticing that P6's per-phase CP ended at a break-it, not the README.
- Wave and `idleWait` / `parallel.kind` are derived (heuristic labels); `meKind` and the never-cut task mapping are my classification, not stated in the plan.

Not verified: free-tier timing of the long runs (no quota numbers exist yet, `docs/quotas.md` is P0-T06's output and was not read); whether tasks marked done have real artifacts (that is another lane).
