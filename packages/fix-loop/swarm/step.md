You are one model turn in a coding-fix loop. RUN is given in your task. Do exactly this and nothing else.
1. Run: bash '/c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm/turn.sh' show RUN
   It prints the conversation so far (system message, ticket, earlier tool calls and their results). If it says the prompt is too long and names a file, read that whole file with the Read tool (in pieces if needed).
2. Decide the next step yourself, using only that text. Reply with exactly one JSON object {"tool": "<name>", "arguments": {...}}; the tools are listed in the system message. If the prompt starts with "THIS TURN IS A SUMMARY REQUEST", reply with plain text only (the summary), not JSON.
3. Save your reply to /c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm/replies/RUN.json using a quoted heredoc (cat > FILE <<'XEOF' ... XEOF), then run: bash '/c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm/turn.sh' answer RUN < /c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm/replies/RUN.json
   If the answer command prints "rejected", your reply was the wrong kind: fix it and run the answer command again (at most twice).
4. Report only the last line the answer command printed.
Rules: run no other commands. Do not list, cat or search the repo. Do not open other run folders. Never run start.
