# Swarm brief (shared by every lane)

Project: Argus, a learning project that turns a UI bug ticket into a verified PR (reproduce -> locate -> fix in sandbox -> verify -> PR). $0 budget, 20 h/week. Root of this checkout is the repo root. Read `PROJECT.md`, `PLAN.md`, `TASKS.md`, `phases/`, `docs/` first.

State: **P0 (bench + bugsmith) and P1 (repro-agent) are done** per TASKS.md (49 `[x]`, 223 `[ ]`). P2-P9 are README stubs. Known caveat to confirm or refute: P1's "28/30 valid" comes from fixture replay (`packages/repro-agent/src/repro_agent/batch.py` hard-codes canned scripts, `host=fixture`); the only live-model number is the P0 baseline 0/10.

Goal of the swarm: verify the project, find gaps, find optimizations, then feed one hand-built HTML explainer with two tabs: (1) Plan & tracker (problem, solution, HLD, ops-console UI examples, edge cases, tracker), (2) Learning graph of industrial concepts.

## Lane method (every lane)
research/analyze -> synthesize -> write your file -> verify (re-open every cited line, run the cheap check if one exists) -> update the file with what verification changed. End your file with a `## Verification log` section listing what you re-checked and what you corrected.

## Rules
- Docs/analysis only. **Do not edit code under `packages/`.** Only lane `docs-drift` may edit existing .md/.html docs.
- Write ONLY the files named in your lane. Other lanes write at the same time in the same checkout. Commit nothing, switch no branch, run no git stash.
- Never open credential files: `dcortex env`, `developers_openai_api_key`, `github-recovery-codes.txt`, any `.env` or key file. Read code and docs only.
- Every claim cites `file:line` or a URL. No invented numbers (repo rule: results cells stay `—`). Say "unverified" instead of guessing.
- Existing HTML pages (`PROJECT/architecture/production/142-fix/argus-learning.html`) already exist; do not duplicate their content, add what they lack.
- Be concise: tables and bullets, no essays. JSON outputs must parse (`node -e "JSON.parse(require('fs').readFileSync(f))"`).
- Final message: 5 lines max: file(s) written, 3 key findings, anything blocking.
