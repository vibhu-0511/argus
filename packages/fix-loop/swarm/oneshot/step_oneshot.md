You are the model in a one-call coding-fix baseline. RUN is given in your task. Do exactly this and nothing else.
1. Run: bash '/c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm/oneshot/oneshot.sh' show RUN
   It prints a ticket and the current text of the file(s) that contain the bug. If it says the prompt is too long and names a file, read that whole file with the Read tool (in pieces if needed).
2. Reply with the unified diff (git format, paths a/... and b/..., hunk context copied exactly from the file text) that fixes the ticket with the smallest change, and nothing else. You cannot run or search anything: use only that text.
3. Save your diff to /c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm/oneshot/replies/RUN.diff using a quoted heredoc (cat > FILE <<'XEOF' ... XEOF), then run: bash '/c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm/oneshot/oneshot.sh' answer RUN < /c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm/oneshot/replies/RUN.diff
   If it prints "rejected", fix the file and run it again (at most twice).
4. Report only the last line the answer command printed.
Rules: run no other commands. Do not list, cat or search the repo. Do not open other run folders or other files.
