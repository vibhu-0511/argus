# Brief: finish the open Phase 4 (verify) tasks (run this in the MAIN checkout)

Open a Claude session whose folder is `C:\Users\vibha\Downloads\data\personal\argus` (branch `p0-bench`), then paste: "Read `C:\Users\vibha\Downloads\data\personal\argus\.claude\worktrees\agent-swarm-verification-b4db5f\analysis\swarm\p4-finish-brief.md` and do what it says."

Start it after the P3 session (`finish-p3`) has written up, because both work in that checkout and both touch `TASKS.md`.

Why there: P4 is uncommitted in that checkout, on top of the uncommitted P3 files (`packages/verify/**`, `docs/adr/0012-gate-ordering.md`, `0013-judge-selection.md`, `0014-best-of-k.md`, `docs/architecture/p4.md`, `docs/notes/p4-*.md`, `.github/workflows/verify.yml`, edits to `TASKS.md`, `phases/P04-verify.md`, `pyproject.toml`, `uv.lock`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`). A session scoped to another worktree is blocked from editing them. Read them first and never discard or overwrite them.

## UPDATE 2026-10-31 (supersedes the "do not run T11/T13/T14" lines below): Ollama is now available
- The owner approved installing dependencies. Ollama 0.40.13 is installed at `C:\Users\vibha\AppData\Local\Programs\Ollama\ollama.exe`. It is on the user PATH, but older shells may not see it; call it by full path if `ollama` is not found. The server auto-starts; its OpenAI-compatible endpoint is `http://localhost:11434/v1`.
- `gemma4:e4b` (about 6 GB) was being pulled in the background (95% at the last check). Run `ollama list`; if it is not listed yet, wait and re-check rather than starting a second pull. Never delete or reinstall anything.
- Machine: i7-13620H, 16 threads, 15.7 GB RAM with little free (Cursor and Docker run too), Intel iGPU only, so CPU inference. Before the 100-pair run, time 3 pairs and write down seconds per pair and the projected total. Run the full 100 as a background job with a progress file so it survives the turn ending (see `docs/notes/p4-judge-design.md`). If memory pressure kills the run, shrink the image size or context, record the change, and say it in the log. Do not claim a number from a run that did not finish.
- So T11, T13 and T14 are now in scope. Order: draft labels (T10) -> build the Ollama runner (T11) -> run the judge over the 100 pairs (T13) -> iterate the rubric against a dev split, scoring on a held-out split (T14). Alpha here is judge-vs-**Claude-draft** labels, because no human labels exist yet. Print it as "provisional, vs Claude draft labels", never as the Done-when's human alpha, and leave T10 and T14 unticked until the owner has reviewed the labels.
- T17 (same-family vs cross-family ablation) still needs a same-family vision judge. The plan names a Mistral vision model, and there is no Mistral key. Do not substitute silently. Leave T17 unticked and write down what unblocks it (an endpoint the owner provides, or an owner decision on a different control, e.g. a second local vision model).
- Sequence note: P3's own remaining work and the P3/P4 fixer session run AFTER this one, not at the same time (same checkout, same `TASKS.md`, same CPU).

## Open tasks (`TASKS.md` P4 block and `phases/P04-verify.md`; read each Done-when)
- P4-T10 Label all 100 calibration pairs by hand ([ME]).
- P4-T11 Local Gemma judge runner with vision input (Ollama, CPU).
- P4-T13 Run the local judge over the 100 pairs.
- P4-T14 Iterate the rubric and prompt until alpha reaches 0.80 or the budget runs out.
- P4-T17 Ablation: same-family vs cross-family judge.
- P4-T20 Best-of-k with k = 1, 3, 5 on the 30-task subset.

`docs/notes/p4-iteration-log.json` records the current state: every label is null, Ollama is not installed, held-out alpha is null. ADR-013 keeps the judge advisory; ADR-014 keeps default k at 1 and the cap at 5.

## The owner's decisions (2026-10-31)
- **T10 labels: Claude drafts, the owner reviews.**
  - Look at each pair's `before.png`, `after.png`, `ticket.txt` and `meta.json` under `packages/verify/fixtures/calibration/<id>/`. Judge using only `packages/verify/rubric.md`.
  - Do **not** write into `fixtures/calibration/labels.json`, whose `label: null` is the slot for human labels. Write your draft to a separate file `packages/verify/fixtures/calibration/labels.claude-draft.json`, one record per pair: id, draft label, a one-line reason, and `labeled_by: "claude-draft"`, `human_review: "pending"`.
  - Tell the owner how to review (for example, what to open and which of the 100 pairs you were least sure of), so their review is fast and real.
  - Never compute or publish Krippendorff's alpha with these as if they were human labels. T10 stays unticked until the owner has reviewed.
- **T20: pilot best-of-k with Claude as the model.** Reuse the P3 approach: the file-backed model client and driver in `packages/fix-loop/src/fix_loop/turn.py` and the P3 pilot notes in `docs/notes/p3-finish.md`. Do not build a new harness.
  - Cost grows with k, and k=1, 3, 5 on 30 tasks is about nine times the P3 baseline. So run a small pilot: a handful of easy-tier seeded tasks, with the cost estimate written down first and a 3-task pilot before anything bigger.
  - Label every result `model: claude-session`. It is not comparable with the plan's Devstral or Gemma rows, and the judge in the pipeline stays advisory (ADR-013). State the real denominator in every result and write raw per-task output to a results file with a run id.
  - Leave T20 unticked unless its Done-when is truly met (k=1, 3, 5 on the 30-task subset); say what remains.
- **T11, T13, T14, T17: do not run.** Ollama is not installed and nothing may be installed. Leave them unticked with a one-line reason and what unblocks each (the owner installs Ollama and pulls `gemma4:e4b`; the owner's review of the labels).

## Also do, if the verifier's P4 report exists
Look in `analysis/swarm/conformance/` of `C:\Users\vibha\Downloads\data\personal\argus\.claude\worktrees\agent-swarm-verification-b4db5f` for a `report-*-p4.md`. If it lists doc-only gaps (README, phase report against P3, ADR consistency, a ticked task without evidence), fix those in the P4 files. Do not change owner-decision items.

## Honesty and boundaries
- No invented numbers. A results cell stays `—` unless a file with a run id backs it. Keep live and fixture results separate and labelled.
- Tick a task only when its Done-when is met. Work Claude did on an [ME] task is marked "run/drafted by Claude at the owner's request, for the owner to review".
- Log to `docs/notes/p4-finish.md`: what ran, the model, steps/cost, what is still open. Run the non-live P4 suites before and after (use the repo venv python if `uv run` fails, as P3 found). They must stay green. A bench test already failing before P3/P4 is not yours to fix.
- No `git add -A`; the tree holds many other uncommitted files. Commit only your own files with clear messages, and only when the work is complete and tested. No push, no merge.
- Do not touch the `p2-conformance-fixes` branch, the swarm/explainer branch, or other worktrees. Install nothing. Do not open any env, key or credential file.

## Done when
Each remaining task is either ticked with evidence or left unticked with a one-line reason in `docs/notes/p4-finish.md`; the draft labels exist in their own file, clearly marked as Claude's. Final report, five lines or fewer: tasks closed, tasks open and why, model used and cost, run ids, test results.
