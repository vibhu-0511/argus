# P3 — fix-loop

**Budget:** 84 h · **Weeks:** W8–12 · **Packages:** `fix-loop` (builds on `argus-core`, `bench`, `repro-agent`, `dom2src-mcp`)

## Goal
Write the agent loop that turns a ticket plus a reproduction into a patch, from scratch with no agent framework, inside a sandbox, and compare it against mini-swe-agent as the baseline.

## Done when
- `fix-loop` runs end to end over a 30-task stratified subset and writes one validated trajectory per task, with a recorded stop reason.
- The package imports no agent framework (checked by a dependency check in CI).
- Every run executes in a git worktree plus a Docker container with `--network none`, and the bench checks are mounted read-only.
- The context budget manager supports four strategies (none, output caps, offload-to-files, summarize), and all four are run on the same 30 tasks.
- mini-swe-agent is run on the same 30 tasks with the same model and ledger.
- A recorded trajectory replays deterministically with no LLM call.
- The Ablation table and phase report are filled against P2 and the P0 baseline.

## Agentic concepts learned
1. **Anatomy of an agent loop** — observe, decide, act, with explicit stop conditions and stuck detection.
2. **Context engineering** — caps, offload-to-files and summarization as different answers to "what stays in the window".
3. **Tool design for models** — small tools with typed errors that teach the model to recover (agent-computer interface).
4. **Gates and reward hacking** — deterministic gates, read-only checks, and why a model will edit the test if it can.
5. **Baseline before framework** — a from-scratch loop measured against mini-swe-agent so any later framework has to earn its place.

## Interview questions
1. List your loop's stop conditions. What does each one record, and which one would you alert on in production?
2. Offload-to-files and summarization both shrink context. What does each lose, and on what kind of task does each fail?

## Prereq reading
- [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)
- [Effective context engineering for AI agents (Anthropic)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [SWE-agent: agent-computer interfaces](https://arxiv.org/abs/2405.15793)

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P3-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P2-T19 | Versions table re-checked, plus model names and free-tier limits for the fixer; date updated |
| P3-T01 | Read the mini-swe-agent source and the context-engineering post, write notes | [ME] | learn | 2 | P3-T00 | `docs/notes/p3-loop-design.md` lists mini-swe-agent's loop, its tools and its termination rules, and three choices you will make differently |
| P3-T02 | Define agent tool schemas: read_file, list_dir, search, edit, run_cmd, submit | [ME] | build | 4 | P3-T01, P0-T03 | Each tool has a typed schema, description and typed error results; `edit` is an exact unique match, the error names the line numbers, with no whitespace flex, no fuzzy matcher, and no second whole-file tool; `read_file` and `edit` return a typed error for a path outside the worktree, and the host-filesystem probe stays P7-T12; schema files validate; one unit test per tool |
| P3-T03 | Add ast-grep as a structural search and rewrite tool | [PAIR] | build | 3 | P3-T02 | The tool runs an ast-grep pattern over the dcortex Canvas worktree in `config/platform.md` and returns matches with file and line; a bad pattern returns a typed error |
| P3-T04 | Build worktree manager: create and destroy a git worktree per task | [CLAUDE] | build | 2 | P3-T00 | Create gives a clean tree at the task's base commit; destroy leaves no leftover worktree (checked by `git worktree list`) |
| P3-T05 | Build Docker sandbox runner: `--network none`, CPU and memory caps, worktree mount, checks read-only | [CLAUDE] | build | 3 | P3-T04 | A test inside the sandbox fails to reach the network and fails to write to the checks directory |
| P3-T06 | Build core agent loop: message history, model call, stop conditions | [ME] | build | 4 | P3-T02, P0-T05 | Loop stops on `submit`, step cap, token cap, `QuotaExceeded`, stuck detection, and a consecutive-timeout stop distinct from `stuck`; each command has a timeout; an interactive command is rejected; each stop reason appears in the trajectory |
| P3-T07 | Build tool dispatch with argument validation and error handling | [ME] | build | 3 | P3-T06 | Malformed arguments return a typed error to the model rather than raising; a tool error is a normal step with a flag; the error codes are a closed enum distinct from `stuck`; dispatch is tested with 5 bad inputs, and one of them is a non-unique `edit` whose error names the line numbers; there is no whitespace flex, no fuzzy matcher, and no second whole-file tool |
| P3-T08 | Build trajectory recorder (every step as a Trajectory record) | [PAIR] | build | 3 | P3-T06, P0-T03 | A run writes one JSONL file that validates against the Trajectory schema; it includes tokens in, out and cached per step; a rejected tool call remains a Trajectory record that contains the raw response, and replay can see that step; an omitted cache field is zero |
| P3-T09 | Build context budget manager: token counting and a strategy interface | [ME] | build | 4 | P3-T06 | Manager reports tokens used per step and calls a pluggable strategy when 80% of the budget is reached; tested with a fake model |
| P3-T10 | Implement context strategy: output caps | [ME] | build | 3 | P3-T09 | A 50k-character tool output is cut to the cap with a visible truncation marker; unit test passes |
| P3-T11 | Implement context strategy: offload-to-files with a pointer | [ME] | build | 3 | P3-T09 | Large output is written to a file and replaced by a path and a short head; the model can read the file with `read_file` |
| P3-T12 | Implement context strategy: rolling summary | [ME] | build | 3 | P3-T09 | Older turns are replaced by a summary produced by the cheap-tier model; the system prompt and the first user message survive; a summary that does not shrink the window is a stop; last-N elision is not added; summary tokens are counted in the ledger |
| P3-T13 | Write AGENTS.md for the dcortex worktree and load it into the system prompt | [PAIR] | build | 2 | P3-T06 | AGENTS.md covers the layout, run commands and gotchas of the repo in `config/platform.md`; a test shows it is in the system message |
| P3-T14 | Build gates: build, typecheck, lint, unit tests and bench checks run before submit | [PAIR] | build | 3 | P3-T05 | `run_gates` returns a pass or fail per gate; a deliberately broken tree fails the right gate |
| P3-T15 | Feed gate results back into the loop as structured messages | [ME] | build | 3 | P3-T14, P3-T07 | A failed gate produces a short structured message naming the gate and the first error; the loop continues instead of stopping |
| P3-T16 | Wire the repro script and locate() hint into the task prompt | [PAIR] | build | 2 | P3-T06, P2-T07, P1-T08 | A fixture task shows the repro result and the locate() file hint in the first user message |
| P3-T17 | Set up mini-swe-agent against the OpenAI-compatible endpoint | [PAIR] | build | 4 | P3-T05, P0-T05 | mini-swe-agent solves or fails one fixture task through the same ledger and sandbox; it sets `cost_limit` 0, `cost_tracking=ignore_errors`, `--network none`, interpreter `["bash", "-lc"]`, and names the environment variable that pinned mini reads for the OpenAI-compatible endpoint; its trajectory is converted to the Trajectory format by mapping the mini JSON message list into JSONL |
| P3-T18 | Run fix-loop baseline (no compaction) on a 30-task stratified subset | [ME] | eval | 3 | P3-T15, P3-T16, P3-T08 | 30 trajectories and verdicts saved; ledger shows quota stayed within the day budget; resolve rate computed with Wilson 95% interval |
| P3-T19 | Run context ablation: all four strategies on the same 30 tasks | [ME] | eval | 4 | P3-T10, P3-T11, P3-T12, P3-T18 | Four rows of the Ablation table filled from real runs; runs split across days where the quota requires it |
| P3-T20 | Run mini-swe-agent on the same 30 tasks | [ME] | eval | 3 | P3-T17, P3-T18 | One more row filled from a real run with the same model and seed policy |
| P3-T21 | Label failed runs with a failure taxonomy | [ME] | eval | 3 | P3-T19 | Every failed trajectory has one label from a written list, and that list includes the P3-T06 stop reasons; the labels are a closed error-code enum distinct from `stuck`, and `FailureKind` is not copied into the failure notes; counts per label are in `docs/notes/p3-failures.md` |
| P3-T22 | Write ADR-008: Loop control, stop conditions and tool-call format | [ME] | doc | 1 | P3-T18 | ADR lists each stop condition and its reason code, picks exact unique match for `edit` with the line numbers in the error, and decides that a token-cap or stuck stop still scores the worktree diff and does not rewrite that stop reason; this scoring rule is a planning choice, not a measured result |
| P3-T23 | Write ADR-009: Context management policy | [ME] | doc | 1 | P3-T19 | ADR cites the ablation table and states the default strategy and when to switch, and says the system prompt and the first user message survive, a summary that does not shrink is a stop, and last-N elision is not added |
| P3-T24 | Write ADR-010: Sandbox baseline (worktree plus Docker, no network) | [ME] | doc | 1 | P3-T05 | ADR states the threat it addresses and the tier upgrade path to gVisor and Firecracker |
| P3-T25 | Write ADR-011: Framework adoption rule after the baseline | [ME] | doc | 1 | P3-T20 | ADR says what evidence would justify adopting a framework, using the mini-swe-agent comparison, states that the scored artifact is stdout after `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` and that the stop reasons differ from Argus, and names which mini config is variant E |
| P3-T26 | Add CI job: unit tests and dependency check on recorded trajectories, no LLM | [CLAUDE] | deploy | 2 | P3-T08 | Workflow green; fails if an agent-framework package appears in the dependency list; no secrets |
| P3-T27 | Build deterministic replay of a recorded trajectory with no LLM call | [PAIR] | build | 2 | P3-T08 | `fix-loop replay <file>` reproduces the final patch byte for byte from the stored model responses; it keeps the stored model message and does not replay by shelling the actions again; if the tool-call format uses ids, a resumed log has one observation per id |
| P3-T28 | Break it: make the model repeat the same tool call | [ME] | test | 2 | P3-T06 | Stuck detection fires and the run ends with reason `stuck`; written up in the Break it section |
| P3-T29 | Break it: return a 5 MB tool output | [ME] | test | 2 | P3-T09 | No context-overflow error; the active strategy shrinks the output; written up in the Break it section |
| P3-T30 | Break it: make the model send malformed tool arguments | [ME] | test | 2 | P3-T07 | A typed error goes back to the model, the run does not crash, and repeated errors end the run; a provider payload missing `choices` is a typed error returned to the loop, and the run does not crash; written up |
| P3-T31 | Break it: let the model try to edit the bench checks | [ME] | test | 2 | P3-T05 | The write fails inside the sandbox; the attempt is logged in the trajectory; written up |
| P3-T32 | Break it: make the model run a destructive shell command | [ME] | test | 2 | P3-T05 | The command only affects the disposable worktree and container; the host tree is unchanged (hash check); each command has a timeout; consecutive timeouts are a stop distinct from `stuck`; an interactive command is rejected; written up |
| P3-T33 | Write package README and phase report against P2 and P0 | [CLAUDE] | doc | 1 | P3-T25 | README shows run and replay commands; phase report has previous-phase, this-phase and delta rows filled |

## Break it on purpose
1. **Repeated tool call (P3-T28).** *Induced failure:* a fake model that calls `read_file` on the same path forever. *Expected signal:* stuck detector fires, stop reason `stuck`, step count in the trajectory. *Fix:* detect N identical consecutive calls and end the run or inject a "you are repeating yourself" message once.
2. **Tool output flood (P3-T29).** *Induced failure:* `read_file` on a 5 MB file. *Expected signal:* the context budget manager triggers its strategy; no provider error about context length. *Fix:* cap or offload at the dispatch boundary, so a single tool result cannot exceed a fixed share of the window.
3. **Malformed arguments (P3-T30).** *Induced failure:* a fake model sends `edit` with a missing field and a wrong type. *Expected signal:* typed validation error returned as the tool result; run continues; after repeated errors it stops. *Fix:* put the schema's required fields in the error message so the model can correct itself.
4. **Editing the checks (P3-T31).** *Induced failure:* the model tries to overwrite a bench check to make it pass. *Expected signal:* write rejected by the read-only mount; the attempt is recorded. *Fix:* keep checks outside the writable tree, and fail any patch that touches them.
5. **Destructive command (P3-T32).** *Induced failure:* `rm -rf` on the repo root inside `run_cmd`. *Expected signal:* damage limited to the disposable worktree; the host tree hash is unchanged; the gate flags a broken tree. *Fix:* recreate the worktree per run, and never mount anything writable except the worktree.

## Ablation
**Hypothesis:** at least one non-trivial context strategy (output caps, offload-to-files or summarize) beats no compaction on resolve rate or tokens/bug, and the from-scratch loop is competitive with mini-swe-agent under the same model.
**Variants:** A = no compaction; B = output caps; C = offload-to-files; D = summarize; E = mini-swe-agent baseline, the mini config ADR-011 names.
**Metric:** resolve rate (Wilson 95% interval), tokens/bug, peak context tokens, quota share.

| Variant | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug | Quota share/bug | p50 latency | p95 latency | Peak context tokens |
|---|---|---|---|---|---|---|---|
| A | — | — | — | — | — | — | — |
| B | — | — | — | — | — | — | — |
| C | — | — | — | — | — | — | — |
| D | — | — | — | — | — | — | — |
| E | — | — | — | — | — | — | — |

**Phase report (against previous phase):**

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase | — | — | — | — | — |
| This phase | — | — | — | — | — |
| Delta | — | — | — | — | — |

## ADRs to write
All [ME].
- **ADR-008 — Loop control, stop conditions and tool-call format.** What ends a run, and what does each ending record?
- **ADR-009 — Context management policy.** Which strategy is the default, and what triggers a switch?
- **ADR-010 — Sandbox baseline.** Is worktree plus Docker with no network enough for P3, and what is the upgrade path?
- **ADR-011 — Framework adoption rule.** What measured gap versus mini-swe-agent would justify adopting an agent framework?

## Deploy checkpoint
GitHub Actions runs the deterministic golden-fix run on every push, plus the fix-loop unit tests on recorded trajectories. No LLM calls in CI; real runs are done locally against the free tiers and their trajectories are committed as fixtures.

## Portfolio artifact
A from-scratch coding-agent loop with a context-strategy ablation and a head-to-head against mini-swe-agent, with the trajectory replay tool.
