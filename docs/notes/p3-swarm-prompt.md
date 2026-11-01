# Prompt for the swarm session (P3-T19 context-strategy ablation)

Continue the P3 context-strategy ablation in this worktree: C:\Users\vibha\Downloads\data\personal\argus\.claude\worktrees\agent-swarm-calibration-1cdc29 (branch claude/agent-swarm-calibration-1cdc29). Open the session with this folder as the working directory.

READ FIRST: docs/notes/p3-finish.md, the sections "Stateless per-step pilot for the context ablation" and "Pilot extension to three tasks"; then the docstring of packages/fix-loop/src/fix_loop/turn.py; then packages/fix-loop/swarm/ (step.md, coord_runs.md, start_task.sh, status.sh, turn.sh).

WHAT THIS IS. 4 context strategies (none, cap, offload, summary) on the 29 runnable seeded tasks. The model is a Claude subagent, one FRESH subagent per loop step (stateless), so a strategy really changes what the model sees. Driver: `python -m fix_loop.turn` (wrapper packages/fix-loop/swarm/turn.sh). Context budget 32,000 estimated tokens, step cap 20, token cap 400,000, each message cut at 20,000 characters, a reply of the wrong kind (tool call vs summary text) is rejected. Run ids: p4b-full-<strategy>-<task suffix>, e.g. p4b-full-cap-h05. Results: packages/fix-loop/runs/<run id>/verdict.json.

STATE AS OF 2026-11-01 (check it again with `bash packages/fix-loop/swarm/status.sh`, a run is done when verdict.json exists):
- Done, 4 of 4 strategies, 20 tasks: e01 e02 e03 e04 e06 e09 e10 m01 m02 m03 m04 m05 m06 m07 m08 m09 h01 h02 h03 h04.
- Done in the earlier pilot (different run ids): e05 (p4b-pilot2-<strategy>-e05), e08 (p4b-pilot2-<strategy>-e08), e07 (none: p4b-pilot-none2-e07, cap: p4b-pilot-cap-e07, offload: p4b-pilot-offload-e07, summary: p4b-pilot-summary3-e07). Ignore p4b-pilot-none-e07, p4b-pilot-summary-e07, p4b-pilot-summary2-e07 and every p4b-pilot-*-e02/-e05 folder: invalid or unstarted.
- No other session is running anything. YOUR TASKS: h05 h06 h07 h08 h09 h10 (not started): one batch of 6 coordinators.
- bug-17 is excluded (cannot be set up).
- Odd verdicts already seen: p4b-full-offload-m07 is `excluded` (score exit 2); p4b-full-summary-h03 stopped with reason `summary` (the summary did not shrink) and still scored resolved; several summary runs ended on `step-cap` (summary runs use two replies per step).

HOW TO RUN A BATCH (4 to 6 tasks at once, never more than 6 coordinators at a time, the machine slows a lot above that):
1. For each task in the batch run `bash packages/fix-loop/swarm/start_task.sh <suffix>` with run_in_background (it takes minutes on a loaded machine). Wait for ALL its completion notifications before step 2.
2. For each task start ONE coordinator: Agent(subagent_type general-purpose) with prompt: `RUNS = p4b-full-none-<s>, p4b-full-cap-<s>, p4b-full-offload-<s>, p4b-full-summary-<s> (in this order). Read the file C:\Users\vibha\Downloads\data\personal\argus\.claude\worktrees\agent-swarm-calibration-1cdc29\packages\fix-loop\swarm\coord_runs.md with the Read tool and follow it exactly.` (Use /c/Users/... in the path if the Read tool needs it.) A coordinator only starts one fresh step worker at a time and relays; it never decides a fix. A task takes about 25 to 45 minutes.
3. When a coordinator reports, record its four verdict lines, then start the next task (start_task.sh in the background, then its coordinator). If a line says "no verdict after N workers", start a coordinator for that run id alone (it continues from the recorded replies).
4. Notifications arrive twice for one agent (a message and a task-notification): do not launch twice for the same report. Do not poll or sleep.
5. Show a text progress bar (tasks finished of 26, runs with a verdict) every time a coordinator reports.

PITFALLS ALREADY MET:
- Summary runs use two replies per loop step (turn plus summary), so a summary run can need up to about 40 workers; the limit in coord_runs.md is 45.
- A bash command over 120 s is moved to the background by the tool; that is why start_task.sh must run in the background.
- A verdict of `excluded` (score exit 2) happened once: p4b-full-offload-m07. Find out why (read its trajectory.jsonl, diff.patch and the scorer's exit-2 rule in packages/bench) before you tally; report it as excluded, do not count it as resolved or unresolved, and say what caused it.
- Workers sometimes run one extra no-op command; that is fine unless it changes the tree.
- The Edit and Write tools may be blocked by a hook for this worktree if your session lives in another worktree; write files with Bash heredocs. In Python patches avoid backslash escapes (use chr(10)).

FINAL TALLY (after all 29 tasks have 4 verdicts):
1. Write one small script (packages/fix-loop/swarm/tally.py) that reads the verdict.json files (full runs plus the pilot run ids above) and prints, per strategy: resolved, unresolved, excluded, the Wilson 95% interval with fix_loop.baseline.rate_label over resolved+unresolved, mean steps, stop-reason counts, and mean estimated loop tokens in/out per task from trajectory.jsonl (chars/4, as in the variant A table). Pair the four strategies per task and list the tasks where strategies disagree.
2. Write the table and a short reading into docs/notes/p3-finish.md (new section). Say plainly: one run per cell, one model (the session model, labelled claude-session), not comparable with Groq or Mistral rows, harness choices (32,000 budget, 20,000-char cut) are mine and not measured. Compare with the stateful variant A row (20 of 29) only as a different method.
3. Fill rows A (none, stateless), B (cap), C (offload), D (summary) of the Ablation table in phases/P03-fix-loop.md ONLY with numbers backed by run files; leave E and every cell without a backing file as a dash. Do NOT tick P3-T19 or P3-T21 or P3-T23: ask the owner.
4. Token cost: worker token usage is only visible inside the coordinators, so do not invent a total. State the estimate as steps x about 70,000 and label it an estimate.

RULES: work only in this worktree; commit nothing, push nothing, merge nothing, never `git add -A`; invent no numbers; install nothing; do not open env, key or credential files; delete nothing; keep PYTHONPATH separators as ':' (the scripts already do); run packages/verify/tests (47 passed) and packages/fix-loop/tests (54 passed) before and after; finish with a report of five lines or fewer: tasks finished, model and cost estimate, run ids, anything excluded or odd, test results.
