# P4 finish log

Run by Claude at the owner's request, for the owner to review. Date: 2026-10-31.

## Where this was done

The brief says to run in the main checkout. This session was opened in the worktree `agent-swarm-calibration-1cdc29`, where a hook blocks every write to the main checkout. At the owner's instruction ("Work in worktree") a read-only snapshot of the uncommitted P3/P4 files was copied from the main checkout into this worktree, and all edits are here. Nothing was written to the main checkout, apart from one mistake that was undone (see Slips). The owner merges this worktree's changes back: `TASKS.md` and `phases/P04-verify.md` were copied from main as they stood on 2026-10-31 and edited here, so they will conflict if main changed since.

## Slips

- A smoke run of the turn driver wrote `p4-t20-smoke` into the **main** checkout's `packages/fix-loop/runs/` and added a platform worktree there. Cause: I joined `PYTHONPATH` with `;` in Git Bash, so Python fell back to the editable install that points at main. I removed exactly that directory and that platform worktree (nothing else in main was touched; `git status` of main shows no `smoke` entry). Later runs use `:` and were checked to land in this worktree.
- A first render script run wrote PNGs to a mangled path `C:\c\Users\vibha\AppData\...` (an MSYS `/c/...` path read as a Windows path). I moved the PNGs into the scratchpad. An **empty directory tree `C:\c` is left** on the C: drive; the harness blocks removing it. It holds no files; please delete it.
- `packages/bench/node_modules` here is a directory junction to main's `packages/bench/node_modules` (the scorer could not find `@playwright/test` in this worktree, and the first draws of the T20 pilot were scored `excluded` for that reason; see T20). The link is untracked. Nothing was installed.

## Real calibration set (replaces the 16x16 squares)

`packages/verify/fixtures/calibration/` is now 100 pairs of **real dcortex Canvas screenshots**, built from the seeded bench tasks and the P3/P4-T20 run diffs. How, and the limits, are in `packages/verify/calibration/README.md`. In short:

- **Denominator: 100 pairs from 20 distinct tickets** (3 to 7 pairs per ticket, on 5 different screens). Mix as built: 40 correct, 30 wrong, 30 collateral (`constructed_as`, which is the construction and not a label). Pairs of one ticket are correlated.
- Of the 29 usable seeded tasks, **9 bugs do not change a static screenshot** at all (`seed-e03`, `e06`, `e09`, `e10`, `h03`, `h09`, `h10`, `m03`, `m09`: overflow, z-index and `div.` selector-specificity mutations). They cannot be judged from images, so they are not in the set. `bug-17` is excluded because its patches no longer apply to platform HEAD.
- Shots are the real Canvas UI at platform HEAD `ac86acc75`, rendered in Chromium (1280x800, clock frozen at 2026-10-01 12:00 UTC) with a **mocked API** (no backend): the CSS and layout are real, the flights and tasks are made up. Because of that, some screens show a "Session expires soon" banner and a STALE pill in both images.
- Class composition is thin in places and should be known before trusting any alpha: 38 of the 40 `correct` pairs are the golden fix on different screens; 20 of the 30 `wrong` pairs are "bug still there plus an unrelated regression from another task"; the `collateral` pairs add one hunk lifted from another task's bug patch. Only 5 pairs use a model-written diff (P3 or T20 runs).
- The old squares are kept as `fixtures/calibration-squares/` (plumbing fixture only); `tests/test_pairs_ci.py` now tests both sets.
- Size: about 23 MB of PNGs. Whether to commit them is the owner's call.
- Finding, decoder fixed afterwards: `verify.png.decode_png` read only scanline filter 0, so it could not read these real screenshots (`png filter` error). See "PNG decoder" below. The pixel check's fringe test is still too slow for a real differing pair (also in the verifier's report).

## P4-T10: labels (ticked 2026-10-31, as adopted drafts)

**Update:** the owner reviewed part of the set in `review.html`, found most drafts convincing, and told Claude (twice) to use the drafts for all 100. `labels.json` is now the drafts for every pair, `labels.provenance.json` says `owner-accepted-draft` for all 100, and T10 is ticked on that basis. The owner's own individual choices were never exported, so they are not in the file. These are **adopted Claude drafts, not independently produced human labels**, and every alpha below is worded that way. The review notes that follow are the state before that decision.

Drafted by Claude at the owner's request, for the owner to review. Four fresh subagents (25 pairs each) labelled by looking at `before.png`, `after.png` and `ticket.txt` and using only `rubric.md`. **Deviation from the brief:** they were not shown `meta.json`, because it records how each pair was built and would bias the label. They also saw no judge output. Drafts: `packages/verify/fixtures/calibration/labels.claude-draft.json`, one record per pair (`id`, `label`, `reason`, `confidence` 1 to 3, `labeled_by: "claude-draft"`, `human_review: "pending"`). `labels.json` is untouched and still all null.

Draft counts: 47 pass, 31 fail, 22 collateral. Confidence: 43 clear, 46 fairly sure, 11 guesses. Agreement with how each pair was constructed: 83 of 100.

**How to review (about 30 to 45 minutes).** Open `packages/verify/fixtures/calibration/review.html` in a browser. It shows the ticket and the two screenshots; pick pass, fail or collateral for each pair **before** clicking "show Claude's draft". Your choices are kept in the browser; "Export labels.json" downloads the file to put at `fixtures/calibration/labels.json`. Review these first:

- the 11 pairs where the draft is a guess: `029, 034, 050, 058, 069, 076, 084, 086, 090, 096, 097`;
- the 17 pairs where the draft differs from how the pair was built: `002, 012, 022, 023, 026, 045, 067, 070, 071, 073, 074, 086, 087, 089, 094, 097, 098` (either the draft or the construction is wrong; 086 and 097 are on both lists);
- the clock tickets (`000, 011, 012, 017, 019, 020`): the ticket says the rule is gone or the size changed, and the labellers took the large bold clock as the intended state, which is a judgement call;
- tickets that name two things where one is not visible on the shown screen (`004, 011, 013, 016, 019, 076, 084, 090`): the label can only cover the half you can see, so decide the rule for these once.

(Superseded by the update above: alpha is now computed against the adopted drafts and labelled as such.)

## P4-T11: Ollama runner (ticked; drafted and run by Claude at the owner's request, for the owner to review)

Runner: `judge.ollama_backend` (`/api/chat`, images base64, temperature 0, `think: false`, fixed `num_ctx`) driven by the new `verify.judge_run` (resumable, writes `<out>.jsonl` and `<out>.progress.json`). Evidence: `packages/verify/runs/judge-timing3.jsonl`, 3 real pairs judged end to end on CPU through `gemma4:e4b` (Ollama 0.40.13, i7-13620H, no GPU): 139 s for the first call (includes the model load), then 72.6 s and 71.4 s. Each pair is about 1,380 prompt tokens (two images) and 7 output tokens. Done-when (one pair judged end to end, time per pair recorded) is met. One earlier call returned HTTP 400 once and was not reproduced; the runner records such a failure as `error`.

## P4-T13 (ticked) and P4-T14 (open): judge runs

All numbers are agreement with `labels.json`, which is Claude's draft labels adopted by the owner (not independently human-labelled). Judge model `gemma4:e4b` on CPU, 8192 context, temperature 0.

**Baseline, rubric v1 (the owner's `rubric.md`, prompt v1), all 100 pairs, forward order:** run id `p4-judge-gemma4e4b-rubric-v1` (`runs/judge-p4-judge-gemma4e4b-rubric-v1.jsonl`, scored in `.scored.json`). The judge answered `pass` for **all 100** pairs: alpha **-0.245** (bootstrap 95% -0.309 to -0.192), false-accept rate 1.0 (every `fail` and `collateral` was accepted), 0 errors, 79 s per pair on average. Held-out half (50 pairs) -0.197, dev half -0.286. T13's Done-when (judge labels saved, alpha with an interval) is met, so T13 is ticked. The reverse-order half was stopped after one pair: the baseline said `pass` for everything, so its order-disagreement rate would be uninformative and the CPU was needed for T14.

**T14 iteration 1 (rubric `rubrics/v2.md`, prompt v2), dev split only (50 pairs, seed 0):** run id `p4-judge-gemma4e4b-v2-dev`. Changes: the prompt makes the judge name the largest difference (or "no difference") and say whether it is what the ticket asks for before the JSON label (`--prompt v2`, the label is the last JSON object in the reply); the rubric gains a "How to decide" section (parts that look the same did not change; identical images mean `fail`; a ticket with two problems is judged on the one visible on this screen). Result on dev: alpha **-0.005** (bootstrap 95% -0.199 to 0.182), agreement 17 of 50, false-accept rate 0.40, 0 errors, 109 s per pair; the same 50 pairs under v1 gave -0.286. The judge now varies its answers (23 pass, 14 collateral, 13 fail against 20, 11, 19 labelled) but is about at chance.

**Stopped there.** The T14 estimate is 4 h and two further CPU hours per 50-pair iteration were not available alongside the other runs, so the budget is spent. alpha did not reach 0.80, and the next idea (hand the judge a deterministic pixel-diff image as a third input, or a bigger vision model) is a different judge, not a rubric iteration. **Final held-out result** (run id `p4-judge-gemma4e4b-v2-heldout`, v2 on the held-out 50, forward 50/50 and reverse 50/50 finished; scored with `calibration/score_split.py`, file `runs/judge-p4-judge-gemma4e4b-v2-heldout.held_out.scored.json`): agreement with the adopted Claude drafts alpha **0.116** (bootstrap 95% -0.118 to 0.343), agreement 24 of 50, false-accept rate 0.57, 0 errors, 90.7 s per pair. Judge labels 30 pass, 10 collateral, 10 fail against 27, 11, 12 labelled. **Order-disagreement rate 0.40** (forward and reverse differ on 20 of 50 pairs). Dev was -0.005, so there is no sign of a real gain; the interval includes zero. Alpha is far below 0.80, so the judge stays advisory (ADR-013). Written to `docs/notes/p4-iteration-log.json` and ADR-013. T14's Done-when (each iteration logged, final alpha on the held-out split) is met, so T14 is ticked.

Scoring commands: `python packages/verify/calibration/score_judge.py <jsonl>` for a 100-pair run; the dev and held-out scores use `verify.alpha` on the ids in `runs/split-seed0.json`.

## P4-T17: same-family control (ticked 2026-10-31, with a changed judge)

The plan's same-family judge (Mistral `pixtral-12b-2409`) has no endpoint. On 2026-10-31 the owner chose Claude as the same-family judge, because the fixer in these runs is a Claude session. Run `p4-judge-claude-v2-heldout` (drafted and run by Claude at the owner's request, for the owner to review): rubric v2 and prompt v2, the 50 held-out pairs, forward order only. One fresh Claude subagent per pair saw only the prompt and the two images (copied to neutral file names; no meta.json, labels or other pairs). Helper: `packages/verify/calibration/claude_judge.py`; scored with `score_split.py`.

Result against the adopted drafts: alpha **0.671** (bootstrap 95% 0.469 to 0.836), agreement 40 of 50, false-accept rate 0.13, 0 errors; labels 27 pass, 12 fail, 11 collateral against 27, 12, 11 judged. Gemma on the same pairs: alpha 0.116, false-accept 0.57. Rows A and B of the P4 ablation table are filled.

Read it with care. (1) The labels are Claude's own drafts, so a Claude judge agrees with them partly by construction; this is not independent evidence and not a clean self-preference test. (2) The judges differ in capability, not only in family. (3) Forward order only: no reverse run, so no order-disagreement figure for Claude. (4) Cost: about 70k harness tokens per pair, about 3.5M for the 50 (seconds and token counts are not recorded in the run file). (5) Alpha is below 0.80 and the interval reaches 0.47, so the judge stays advisory (ADR-013).

## P4-T20: best-of-k on the 29 runnable tasks (run; one decision left for the owner)

Model: `claude-session` (a Claude session as the model; one fresh subagent per draw). Tasks: all 29 seeded tasks that run (`bug-17` cannot be set up: its patches no longer apply to platform HEAD). Draw 1 is the P3 variant A run; draws 2 to 5 are 104 new runs `p4-t20-<task>-d<n>`. Pilot first (3 tasks, 12 draws), then the other 26 tasks in waves of 10 to 13. Raw output: `packages/fix-loop/runs/p4-t20-seed-*`; aggregates: `p4-t20-subset29-claude-session.json` (run id `p4-t20-subset29-claude-session`, from `calibration/t20_results.py ... all`) and the earlier `p4-t20-pilot-claude-session.json`.

| k | Resolved of 29 | Wilson 95% | Easy / medium / hard | Mean loop tokens per task, in / out / cached |
|---|---|---|---|---|
| 1 | 20 | 0.508 to 0.827 | 9/10, 5/9, 6/10 | 202904 / 205 / 0 |
| 3 | 24 | 0.655 to 0.924 | 10/10, 7/9, 7/10 | 401522 / 584 / 0 |
| 5 | 24 | 0.655 to 0.924 | 10/10, 7/9, 7/10 | 607582 / 1016 / 0 |

k = 1 is the P3 result by construction. k = 3 added four tasks (`seed-e05`, `seed-h02`, `seed-m04`, `seed-m07`); k = 5 added none, at about 3.0 times the tokens of k = 1. Five tasks were never resolved in 5 draws (`seed-h01`, `h04`, `h07`, `m01`, `m05`); their tickets give no target value or location. Of the 145 draws, 98 resolved (67.6%); stop reasons 128 submit, 15 token-cap, 2 step-cap. One draw (`e07-d4`, step-cap) could not be scored and counts as unresolved. The selector is `best_of_k` with the task's own scorer as the verifier, an **oracle**: this is what extra draws buy with a perfect selector. The checks-plus-judge selector was not run (the judge is at chance, above). With 29 tasks the intervals are wide and k = 1 and k = 3 overlap.

Cost. Loop tokens are the loop's chars/4 estimate. Harness tokens for the 116 new subagent runs (104 draws, the 12 pilot draws, plus 4 retries that were not needed, see below): about 70,000 to 113,000 each, a mean near 85,000 by the per-run reports, so about 9.5 million tokens in all (I added the first 12 exactly, 968,431; the rest are read from reports, not summed). That is in line with the estimate of about 9 times the P3 baseline. Latency was not recorded (`—`). Quota: a Claude session has no provider quota, so there was nothing to split across days; all runs were made on 2026-10-31.

Caveats. (1) Several subagents were run at once (10 to 21), so many commands hit the tool's 120 s limit. When that happened the run had often already finished, usually on the token cap, and the driver had deleted its checkout, so the next answer reported "not a working tree" or "cannot change to ...". I first took four of these for crashes and reran them (`p4-t20-seed-m01-d3-retry`, `p4-t20-seed-m08-d3-retry`); they were not crashes (the originals have verdicts), so the aggregate uses the originals and ignores retries that were not needed. (2) Subagents sometimes sent a stray no-op `echo` or two answers in parallel; none changed a run's tree. (3) Five verdicts were rechecked by rescoring from `diff.patch` (`rescore_runs.py`) and all matched. (4) A 29-task subset, not 30: the owner decides whether 29 meets the Done-when, as with P3-T18. That is why T20 is not ticked here; say the word and it can be.

## PNG decoder (fixed at the owner's request, after the first report)

`packages/verify/src/verify/png.py`: `decode_png` now reads 8-bit, non-interlaced RGB and RGBA PNGs with all five scanline filters (alpha is dropped); anything else (16-bit, palette, interlaced) raises `unsupported png`. Evidence: it matches pngjs (the bench's PNG library) byte for byte on six real calibration shots, which use filters 1 to 4; `tests/test_png.py` has a per-filter round trip (RGB and RGBA, each filter used several times), the two refusals, and one real shot pinned to the pngjs hash. A 1280x800 shot decodes in about 1.7 s in pure Python (no dependency added). `python -m verify ci` on an identical real pair: exit 0 in 8 s.

Pixel check speed (fixed at the owner's follow-up request): `pixel_diff`'s fringe test compared every changed pixel with every unchanged pixel, so a real 1280x800 pair that differed did not finish in 280 s (the verifier's report measured 46 s at 300x150). `checks._near` now looks only at the pixel's window (`FRINGE_PX` = 1, so 8 neighbours) in a set of unchanged, unmasked pixels. The rule is the same: a changed pixel is fringe when an unchanged, unmasked pixel is within Chebyshev distance `FRINGE_PX`. Evidence: `test_fringe_lookup_agrees_with_the_all_pairs_rule` compares it with the old all-pairs rule on 40 random images, limits 0 to 2; `test_pixel_diff_is_usable_at_screenshot_size` runs a 1280x720 frame in about 4 s; on real calibration pairs `pixel_diff` takes 2.5 to 6 s, and `python -m verify ci` on the pair that timed out now exits in 6 s. The thresholds and the thin-stroke question (a 1 px hairline can pass as fringe) are unchanged and remain the owner's T02 design call. `python -m verify ci` still uses its own changed-pixel ratio, so a small change such as the radar clock exits 0 there.

## Ticked-ahead tasks (from the verifier's P4 report; not changed here)

`report-2026-10-31-p4.md` lists P4 tasks ticked while a task they depend on was open (T15, T18, T19, T21, T24, T27, T28, T29) and tasks that check hand-built data rather than a real tree (T03, T04, T05). Whether to untick them is the owner's call, so the ticks are as I found them. What this session adds: T24's order swap needs T13's reverse-order half (running); T27 and T28 have not been exercised against the live judge (stopping Ollama would kill the running job). The report's code items (best-of-k default k and cap not enforced, pixel fringe cost, PNG decoder, `jsonschema` undeclared, judge label not in `Verdict`) are code decisions and were left alone.

## Task status

| Task | Status | One-line reason |
|---|---|---|
| P4-T09 | ticked before; now true | the 100 pairs are real shots from the seeded tasks and runs; labels blank |
| P4-T10 | ticked | labels = Claude drafts adopted by the owner (provenance file says so); not independently human-labelled |
| P4-T11 | ticked | runner built; 3 pairs judged end to end on CPU; 72 s per pair |
| P4-T13 | ticked | baseline v1 over all 100 pairs: alpha -0.245 (judge said `pass` for all 100), vs adopted drafts |
| P4-T14 | ticked | v2 dev alpha -0.005; held-out alpha 0.116 (95% -0.118 to 0.343), order disagreement 0.40; below 0.80, judge stays advisory |
| P4-T17 | ticked | Claude as the same-family judge by owner decision (no Mistral endpoint): held-out alpha 0.671 (0.469 to 0.836), false-accept 0.13; circular labels, forward order only |
| P4-T20 | ticked | k = 1, 3, 5 ran on 29 tasks (`bug-17` cannot be set up), oracle selector: 20, 24, 24 of 29; the owner said on 2026-10-31 that 29 of 30 counts. These are what extra draws buy with a perfect selector, not what the judge-based selector achieves |

## Tests

Before my changes (the snapshot as found): `packages/verify/tests` 40 passed.
After my changes: `packages/verify/tests` 47 passed (41 before the decoder and pixel fixes; 4 new in `test_png.py`, 2 in `test_checks.py`); `packages/fix-loop/tests` 51 passed (includes `test_verify_gate.py`); `node --experimental-strip-types --test packages/verify/test/capture.test.ts` 1 passed. Run with the repo venv python and `PYTHONPATH` set to this worktree's `src` folders (`uv run` was not used). Nothing was committed: the work is not complete (T10, T13, T14, T17, T20 open), and this worktree also holds the copied, still-uncommitted P3 files.

