# docs-drift lane

Lane: docs-drift. Edits docs only (.md, plus the .html pages where a stated fact was wrong). No code under `packages/*/src` touched. Nothing committed.
Checked against: `git log` HEAD `bc52e16`, `TASKS.md` (49 `[x]` / 223 `[ ]`), `packages/*/README.md`, `.github/workflows/`, `docs/notes/p0-t29.md`, `docs/adr/`.

## Checks that found no drift

| Check | Result |
|---|---|
| Totals: 556 h / 255 core tasks, 596 h / 272 with P9 | Recomputed from the `TASKS.md` task lines: P0–P8 = 556 h / 255, P9 = 40 h / 17, all = 272. Phase table in `PLAN.md:216-227` and `PROJECT.md:183-193` agree |
| `TASKS.md:3` "Weeks under 20 h" (hand-maintained) | Recomputed per week: under 20 h are weeks 9, 10, 15, 19, 20, 27, 31, 32, with 19/19/19/18/19/19/19/16 h. Matches the line and `PROJECT.md:286`. Every `## Week N (X h scheduled)` header equals its task sum (30 weeks, 2 buffers) |
| `[x]` count | 49 = P0 (32) + P1 (17). Matches the lane brief |
| Package list | 15 folders under `packages/` = the 15 rows in `PROJECT.md`, `repo-structure.md`, `PROJECT.html` |
| Versions | React 19.3.1, Vite 8.3.5, Tailwind 4.3.3, Playwright 1.64.1, `@playwright/mcp` 0.0.83, MCP SDK 2.3.0 identical in `PLAN.md:51-58`, `PROJECT.md:119-125`, `PROJECT.html:239-245`. Not re-fetched from the web (docs-only lane); dated 2026-10-30 in the docs |
| ADR files | `docs/adr/` holds 0001–0005 only; 006–030 are planned in every index |

## Approved `PLAN_REVIEW.md` items: applied or not

Spot-checked every "apply before P0" line against the current text.

| Item | State |
|---|---|
| FACT-001..013 (versions, Groq row, Neon "100 CU-hours/project", Render "about one minute", Rolldown, MCP bundling, Langfuse MIT, `/dev/kvm`) | Applied in `PLAN.md` and `PROJECT.md`. **Leaks found** in `phases/P06-argus-flow.md:15` (monthly), `architecture.html:145` ("100 CU-h/mo"): fixed below |
| PLAN-001/002/004/005 (556 h wording, weeks under 20 h, P6 and P9 weeks lines) | Applied (`PROJECT.md:286`, `TASKS.md:3`, `phases/P06:3`, `phases/P09:3`) |
| PLAN-007/008 (graph edges) | Applied in `PLAN.md:164-197` (no P6→P9 edge; P5.5→P6 present; no P4→P6, P5→P6) |
| PLAN-010 (archetype check on P0-T13) | Applied (`phases/P00-argus-bench.md:48`) |
| PLAN-011/012/013 (risk register rows 1, 6, 7) | Applied (`PLAN.md:310,315,316`, `PROJECT.md:336,341,342`) |
| PLAN-014..017 (cut-list retargets) | Applied (`PLAN.md:320-325`) |
| PLAN-022 (remove P9 dashboard second series; remove P0 "OTel helpers") | **Not fully applied.** Leaks in `PROJECT.md:368`, `repo-structure.md:22`, `PROJECT.html:173`: fixed below. `phases/P05` header "OTel helpers in `argus-core`" is the P5 placement and stays |

## Edits

All hours deltas are 0. No numbers added.

| # | File | Line | Before | After | Reason |
|---|---|---|---|---|---|
| 1 | `PROJECT.md` | 5 | "This folder is the plan. It holds documents only. No application code is written here, and every results cell stays empty until a real run fills it." | "This folder is the plan, and it now also holds the P0 and P1 code and their runs (TASKS.md: P0 and P1 are `[x]`; P2 to P9 are README stubs). Every results cell stays `—` until a run id backs it. The P1 numbers are fixture replay, not a live model (see `phases/P01-repro-agent.md`)." | Stale status. P0 and P1 code exists (`packages/bench`, `bugsmith`, `repro-agent`, `argus-core`, `target-app`) |
| 2 | `PROJECT.md` | 66, 71 | "Planned layout, once code exists:" and no `config/` line | "Layout (the `.github/workflows/` files and the P0 and P1 packages exist; the other packages are README stubs):" and a `├── config/profiles.md  platform.md` line | Stale status. `config/` and `.github/workflows/{golden,repro}.yml` exist and `repo-structure.md:46-47` lists `config/` |
| 3 | `PROJECT.md` | 87 | "Today only the planning documents and the three HTML companions are present." | "Today the planning documents, the HTML companions, and the P0 and P1 packages (`argus-core`, `target-app`, `bench`, `bugsmith`, `repro-agent`) are present. The other ten package folders hold a README stub each." | Stale status. 10 stub READMEs counted: app, dashboard, dom2src-mcp, dom2src-plugin, eval, fix-loop, flow, guard, skills, verify |
| 4 | `PROJECT.md` | 368 | "…joins the existing Actions jobs. A second series on the dashboard. No new host" | "…joins the existing Actions jobs. No new host" | PLAN-022 approved removal not applied here (`PROJECT.html:397` and `PLAN.md` deploy track already lack it) |
| 5 | `PLAN.md` | 15 | "No application code is written in the planning step. This folder holds documents only. Every results table ships empty; no numbers are invented." | "The plan came first; code follows phase by phase. P0 and P1 code and runs now exist (TASKS.md), and P2 to P9 are README stubs. Results cells stay `—` until a run id backs them; no numbers are invented. The P1 results are fixture replay, not a live model (`phases/P01-repro-agent.md`)." | Stale status; also P0/P1 results tables are filled, so "ships empty" was false |
| 6 | `PLAN.md` | 350-352 | ADR 003, 004, 005 as plain numbers | Linked to `docs/adr/0003-…`, `0004-…`, `0005-…` | Files exist; only 001 and 002 were linked |
| 7 | `repo-structure.md` | 22 | "`argus-core` … quota ledger, OTel helpers" | "… quota ledger" | PLAN-022 (OTel helpers belong to P5). The code in `packages/argus-core/src` has none |
| 8 | `PROJECT.html` | 100 | kicker "Learning plan · documents only" | "Learning plan · P0 and P1 built" | Stale status |
| 9 | `PROJECT.html` | 103 | "This folder holds the plan, not the software. No application code is written in the planning step. Every results cell stays empty until a real run fills it." | "This folder holds the plan and the P0 and P1 code and runs; P2 to P9 are README stubs. Every results cell stays empty until a run id backs it. The P1 numbers are fixture replay, not a live model." | Same as #1 |
| 10 | `PROJECT.html` | 168 | "Today only the planning documents and three HTML companions exist." | "Today the planning documents, the HTML companions, and the P0 and P1 packages exist; the other ten package folders hold a README stub." | Same as #3 |
| 11 | `PROJECT.html` | 173 | argus-core "…quota ledger; OTel helpers" | "…quota ledger" | Same as #4/#7; now matches `PROJECT.md:48` |
| 12 | `PROJECT.html` | 174 | target-app: "React 19.2, Vite 8, Tailwind 4. Six routes, animations off, fonts pinned" | "Binding to the dcortex Canvas and copa-local Postgres in `config/platform.md`. Not a second UI" | Wrong fact. Describes the old scaffolded UI that `PLAN.md:19`, `PROJECT.md:49` and `packages/target-app/README.md` replaced with a binding. React 19.2 also contradicts the 19.3.1 pin |
| 13 | `PROJECT.html` | 157 | "[CLAUDE] … target-app UI, seeded-bug boilerplate" | "… target-app binding to dcortex, seeded-bug boilerplate" | Same as #12; matches `PROJECT.md:39` |
| 14 | `architecture.html` | 202 | target-app card "React 19.2 · Vite 8 · Tailwind 4" | "binding to dcortex Canvas · not a second UI" | Same as #12 |
| 15 | `architecture.html` | 145 | Neon "workflow state · 100 CU-h/mo" | "workflow state · 100 CU-hours/project" | FACT-006: "per month" is not stated |
| 16 | `architecture.html` | 59 | footer "versions checked 2026-10-01" | "versions checked 2026-10-30" | The only versioned card left (SDK 2.3.0) matches the 2026-10-30 table |
| 17 | `argus-learning.html` | 195 | chip "commit none" | "commit bc52e16" | Wrong fact: the checkout is a git repo with 14 commits (HEAD at lane start) |
| 18 | `argus-learning.html` | 214 | "This folder is not a git repository, so there is no commit hash. No application code is written here." | "This checkout is a git repository (commit bc52e16). P0 and P1 code and runs exist and P2 to P9 are README stubs. P1 results are fixture replay." | Same as #17 and #1 |
| 19 | `argus-learning.html` | 488 | "architecture.html still says React 19.2, versions checked 2026-10-01, and “100 CU-h/mo”." | "architecture.html used to say … and were aligned on 2026-10-30." | Made false by #14–16 |
| 20 | `phases/P06-argus-flow.md` | 15 | "compared with the 100 CU-hour monthly free limit." | "compared with 100 CU-hours/project. "per month" is not stated." | FACT-006 leak; `P6-T14` (line 50) already uses this wording |
| 21 | `phases/P01-repro-agent.md` | 79 | (note ends) "…so the token and latency deltas are left blank." | adds: "Caveat: 28/30 is fixture replay (`host` is `fixture`), not a live-model result, so the +0.933333 delta sets a replay against the live P0 baseline and does not show the model got better. No live repro run exists yet." | The table's Delta column compared fixture replay to a live 0/10 with no warning in the same cell group. Source: `batch.py:67` `host="fixture"`, ADR-005 |
| 22 | `docs/architecture/p1.md` | 93 | "…the text-only batch as this phase." | adds: "Both P1 batches are fixture replay (`host` is `fixture`), so 28/30 is not a live-model result." | Phase close line had no caveat |
| 23 | `packages/repro-agent/README.md` | 20 | "The reply is recorded in the runner, so these commands do not call a model provider." | "The reply is recorded in the runner (`host` is `fixture`), so these commands do not call a model provider, and the 28/30 `valid` they report is fixture replay, not a live-model result." | Ties the README command to the number it produces |
| 24 | `phases/P00-argus-bench.md` | 94 (new) | none | "Caveat: the rates are over attempted tasks only. A attempted 10 of its 30 tasks and B attempted 1 of its 30. The rest were exit 2 (prompt over the minute cap) or provider errors (`docs/notes/p0-t29.md`). The intervals overlap, so this reads as no difference. This 0/10 is the only live-model number in the project so far." | The ablation table shows `0/10` and `0/1` with no hint that 20 and 29 tasks were not attempted. Facts from `docs/notes/p0-t29.md` per-task list. The P1 delta is measured against this baseline |
| 25 | `packages/argus-core/README.md` | new file (was 0 bytes) | empty | Install line, a table of the four modules in `src/argus_core/`, schema folder, test command | Empty README in a done phase (P0-T31 says "README shows install"). Test command run: `uv run pytest packages/argus-core/tests -q` → 13 passed |

Line endings: the touched files keep their existing endings (`git diff --stat` shows only the edited lines changed). The new README is LF; git warns it will become CRLF on checkout, as for other files.

## Drift found and NOT fixed

| Drift | Why not |
|---|---|
| `PROJECT.md:44` and `repo-structure.md:3` say the folder "becomes the root" | Tense is now slightly off but nothing contradicts it. Left to keep the edit set surgical |
| ADR-030 title differs: `PROJECT.md` "Which interfaces held when a second lane was added" vs `PLAN.md`, `TASKS.md`, `phases/P09` "Reuse boundary between lanes". Other ADR descriptions in `PROJECT.md` are also paraphrases | Same decision, different phrasing in a description column. Not a contradiction |
| `TASKS.md:3` weeks-under-20-h list is hand-maintained | Correct today (recomputed). Cannot be made automatic without a generator, which is out of scope. Risk: it goes stale on any hour change. Suggest a one-line check script in a later lane |
| `PROJECT.md` / `PLAN.md` / `PROJECT.html` tables still show `P0 … Ablation: Seeded vs mutated` etc. as plan text | They describe the plan, not results. Fine |
| `PLAN.md:229` / `PROJECT.md:176` "28 weeks of work plus 2 buffer weeks, so 30 weeks" | Correct (30 calendar weeks, buffers at 17 and 25). The PLAN-001 wording fix is already in |
| `phases/P05-argus-eval.md:3`, `P05.5:3`, `P07:3`, `P08:3` headers say "W16–19 / W19–20 / W23–25 / W25–28 in the base plan (calendar weeks in `TASKS.md` include the buffer)" | Intentional, explained in the header itself. Calendar weeks in `TASKS.md` are the ones to use |
| `phases/P0*.md` ADR task rows for P0 (`ADR-001..003`) have no "Status: accepted" tracking in the index | The index is a plan table, not a status table; ADR files carry their own Status line |
| `README.md` stubs for P2–P9 (41–72 bytes, one line each, BOM in some) | Correct for "not started". Left as is |
| 14 commits exist but `docs/notes/p0-t29.md` says "There is no git commit. This run did not create one." | It is a point-in-time record of that run, true when written |
| `production.html`, `142-fix.html` | Read by grep only for stale status, versions, hours. No contradictions found. They are worked examples, not status pages |
| The analysis files (`analysis/PLAN_REVIEW.md` "Nothing … has been edited", `verification_report.md`, `merges.md`) | Historical records of the review pass; not mine to edit (outside docs scope in the brief) |
| Version pins and the free-tier numbers themselves | Not re-fetched from the web; this lane is docs-consistency only. Each phase's T00 re-checks them |

## Verification log

- Re-opened every edited line with `grep -n` after the edit (line numbers above are from that run).
- `git diff --stat`: 12 files, 56 insertions, 25 deletions; only the lines in the table changed.
- Parsed the `<script>` blocks of `argus-learning.html`, `architecture.html`, `PROJECT.html` with `new Function(...)`: no syntax errors.
- Recomputed hours, task counts, `[x]` count and under-20 h weeks from `TASKS.md` with a script: all match the docs.
- `uv run pytest packages/argus-core/tests -q`: 13 passed (supports the new README's test line).
- Corrected during the lane: my first read of `PROJECT.md:367` said the row was in the HTML only; it was in the Markdown (line 368 after edit #3), so edit #4 targets `PROJECT.md`.
- Not verified: the 28/30 figure itself (that is the `swarm-verify` lane's job); the web-sourced version and quota numbers.
