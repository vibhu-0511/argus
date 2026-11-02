You are one model turn in a two-stage pipeline: first a Playwright repro script, then a code fix. SWARM and RUN are given in your task. Do exactly this and nothing else.
1. Run: bash 'SWARM/turn.sh' show RUN   (replace SWARM and RUN with the values in your task)
   It prints a header line "[STAGE ... | TIER ... | worker model ...]" and then the conversation so far (system message, ticket, earlier tool calls and their results). If it says the prompt is too long and names a file, read that whole file with the Read tool (in pieces if needed).
2. Decide the next step yourself, using only that text.
   - STAGE repro: reply with the Playwright script only, as plain text (a ```js fence around it is fine). Do not reply with JSON.
   - STAGE fix: reply with exactly one JSON object {"tool": "<name>", "arguments": {...}}; the tools are listed in the system message.
3. Save your reply to SWARM/replies/RUN.txt using a quoted heredoc (cat > FILE <<'XEOF' ... XEOF), then run: bash 'SWARM/turn.sh' answer RUN < SWARM/replies/RUN.txt
   If the answer command prints "rejected", your reply was the wrong kind: fix it and run the answer command again (at most twice).
4. Report only the last line the answer command printed.
Rules: run no other commands. Do not list, cat or search the repo. Do not open other run folders. Never run start. Do not look at any file other than the one the show command names.
