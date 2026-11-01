# Brief: finish the open Phase 3 tasks (run this in the MAIN checkout)

Open a Claude session whose folder is `C:\Users\vibha\Downloads\data\personal\argus` (branch `p0-bench`), then paste: "Read `C:\Users\vibha\Downloads\data\personal\argus\.claude\worktrees\agent-swarm-verification-b4db5f\analysis\swarm\p3-finish-brief.md` and do what it says."

Why there: the P3 work is uncommitted in that checkout (`packages/fix-loop/`, `docs/adr/0008`, `0010`, `0011`, `docs/architecture/p3.md`, `docs/notes/p3-loop-design.md`, `.github/workflows/fix-loop.yml`, edits to `TASKS.md`, `phases/P03-fix-loop.md`, `pyproject.toml`, `uv.lock`). A session scoped to another worktree is blocked from editing them. Read them first; never discard or overwrite them.

## Tasks (from `TASKS.md` Week 11 and `phases/P03-fix-loop.md`; read each Done-when)
- P3-T17 Set up mini-swe-agent against the OpenAI-compatible endpoint.
- P3-T18 Fix-loop baseline (no compaction) on a 30-task stratified subset.
- P3-T19 Context ablation, all four strategies, same 30 tasks.
- P3-T20 mini-swe-agent on the same 30 tasks.
- P3-T21 Failure taxonomy labels for failed runs.
- P3-T23 ADR-009: context management policy.
- P3-T33 Package README and phase report against P2 and P0.

## The blocker and the owner's decisions (2026-10-31)
- The plan's fixer is Devstral on Mistral's free tier. The owner has no Mistral key (the Free plan cannot create one; `docs/quotas.md`, Mistral section) and will not pay. Do not ask for or look for a key. The `personal` profile is $0 (`config/profiles.md`).
- All 30 seeded tasks edit **private dcortex Canvas files**. A free hosted tier may train on prompts, so do **not** send those to Groq or any free hosted tier. Ollama is not installed and nothing may be installed without the owner's OK.
- **Owner's answer to "what about T18 to T21?":** run the live tests with Claude as the model and share the numbers. Interpret that as follows:
  - The model for T18, T19, T21 is Claude (a Claude Code session or subagents), driving the same fix-loop tool interface (`read_file`, `list_dir`, `search`, `edit`, `run_cmd`, `submit`), with trajectories written by the loop's own recorder. Use the smallest mechanism that does this honestly, for example a model client that takes the turn from a file or stdin that the Claude session fills. Do not fake a model by replaying the golden patch.
  - Label every result with: `model: Claude (session as model)`, not the OpenAI-compatible endpoint path, not $0 in plan-quota terms, and not comparable with a Groq or Mistral run. Say in ADR-009 and the README that this is a substitution for the plan's Devstral row. Do not edit PLAN.md's Mistral rows, and do not write a Mistral number.
  - Do a pilot of 3 tasks first, report the step and token cost, then decide whether all 30 fit. Run in parallel with subagents if that is cheaper in wall time. If you stop short of 30, publish the real denominator in every result and leave the task unticked unless its Done-when is truly met.
  - T17 and T20 (mini-swe-agent) need an OpenAI-compatible endpoint. Follow ADR-011 on how mini-swe-agent is brought in and keep it out of the core loop. If no endpoint exists without a key or an install, prove T17 on a synthetic task with a mock endpoint, mark T20 blocked, and say what unblocks it (an endpoint the owner provides, or Ollama).

## Honesty rules
- No invented numbers. A results cell stays `—` unless a file with a run id backs it. Raw per-task output goes to a results file with a run id, cited from the docs.
- Live and fixture/replay results stay separate and labelled.
- Tick a task only when its Done-when is met. [ME] tasks (T18 to T21, T23) that you draft or run are marked "run/drafted by Claude at the owner's request, for the owner to review". Do not claim the owner did them.
- Write the log to `docs/notes/p3-finish.md`: what ran, the model, cost/steps, what is still open. Run the non-live `uv run pytest` before and after; it must stay green.

## Don't
- No `git add -A`; the tree holds many other uncommitted P3 files. Commit only your own files, with clear messages, and only when the work is complete and tested. No push, no merge.
- Do not touch the `p2-conformance-fixes` branch, the swarm/explainer branch, or other worktrees.
- Do not open any env, key or credential file.

## Done when
Each remaining task is either ticked with evidence or left unticked with a one-line reason in `docs/notes/p3-finish.md`. Final report, five lines or fewer: tasks closed, tasks open and why, model used and cost, run ids, test results.
