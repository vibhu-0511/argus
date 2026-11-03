# ADR-024: Threat model and trust boundaries

Status: proposed (P7-T14), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it. The threat model it summarises (`packages/guard/threat-model.md`) was also written by Claude and the owner has not read it yet. **Nothing in this ADR was checked on GitHub:** there is no GitHub App, no Actions run of any P7 workflow, and the live issue to agent adapter does not exist. Revisit when the adapter is built (that is the point where ASI01 becomes live), when the first real Actions run happens, or when the owner decides on the items marked "owner decision" below.

## Context

Argus takes a ticket, runs a model-driven fix loop in a sandbox and opens a draft PR for a human to review. P7 writes the threat model for that pipeline as it was built in P0 to P6, hardens parts of it and tests the hardening. This ADR is the short form: where the boundaries are, what is worth protecting, and which risks are still there after the P7 work. The full model has the data-flow diagram, ten trust boundaries, one section per OWASP ASI01 to ASI10 risk and the injection paths. The OWASP risk names come from the launch post; the PDF text was not read (`docs/notes/p7-t01-owasp-firecracker.md`).

What runs and what has never run matters for reading this ADR. The Render service is live but has handled no webhook, ticket or GitHub write. `agent-job.yml` has never run. The agent does not read a live issue today: `flow.agent_job` accepts seeded task ids only. So most rows below describe a path that is built and unit-tested but has carried no real traffic.

## Decision

### Assets

| ID | Asset | Why it matters |
|---|---|---|
| A1 | Platform source (private repo) | Confidentiality. File text the agent reads goes to the model host |
| A2 | Argus repo, default branch, PRs | Integrity. A patch must land only as a draft PR |
| A3 | Secrets (inventory in `packages/guard/secrets-inventory.md`) | Whoever holds one can act as Argus |
| A4 | Workflow state in Neon | Integrity. Step results are trusted by the next step |
| A5 | Trajectories, patches, `result.json` | They can hold file contents or secrets |
| A6 | Bench checks, `golden.patch`, scorer | If the agent can change what is checked, "resolved" means nothing |
| A7 | Skills and `skills.lock.json` | A skill is instructions the agent obeys |
| A8 | Model quota and Actions minutes | Availability and cost |
| A9 | The audit trail | Evidence of what the agent did |

### Trust boundaries

The model's output is treated as untrusted from the start: its commands, patches and scripts are the thing being contained. Ten boundaries are listed in the threat model (TB1 to TB10). These five carry the decision:

1. **Agent process to model host (TB7).** Everything the agent reads (ticket, repo files, command output, skill text) is sent out, and the reply is untrusted. The model key stays on the runner, outside the sandbox.
2. **Runner host to the Docker sandbox (TB6).** `--network none`, 1 CPU, 512 MB, checks read-only, no environment passed in. This is the main containment control and the only one with test evidence (escape suite, DNS break-it).
3. **Untrusted text to the prompt (TB2, TB8).** Ticket text, repo files and skill bodies are data, not commands. The defences are a fixed tool set with an allowlist, a small blast radius and a human reading the draft PR. Separation and an output filter exist but are off by default.
4. **Render to GitHub and Actions (TB3, TB5, TB9).** Three personal tokens today, an App later. The PR stays a draft. Dispatch inputs and the result artifact are model output and are unsigned.
5. **The scorer and gates on the runner (not drawn as a boundary because there is none).** The patched code runs on the runner host with network and the runner environment. This is the one place where model-written code runs outside any sandbox.

### Top residual risks

"Accepted" means the ADR proposes to live with it; the owner accepts it by approving the ADR. "Owner decision" means there is a real choice with a cost and the owner has to make it. "Open" means no control exists and nothing in P7 builds one, or the control exists but was not shown to work.

| # | Residual risk | Where it comes from | State | What would change it |
|---|---|---|---|---|
| 1 | **The scorer and the gates run the patched code on the runner**, with network and the runner environment (including the model key in the verify job) | `argus_bench.score`, `fix_loop.gates`, `flow.agent_job.verify_step`; threat model ASI05, section 7 | **Owner decision**. This is the largest risk in the model | Cheapest: give the verify step no secrets. Stronger: run the scorer in the sandbox. Neither is in a P7 task |
| 2 | **`run_fix` without an `execute=` argument runs `run_cmd` on the host with the host environment** | `fix_loop/loop.py` default executor; found again in T18. Callers that do it today: `fix_loop.baseline` and `guard.redteam` in stub mode. `flow.agent_job.fix_step`, `fix_loop.turn` and the eval turns pass `execute=` | **Owner decision** | Make the default refuse, or require `execute`. A small change, in no P7 task. Until then a new caller with a real key in its environment is a leak path (T18: all secret-named values reached the patch on this path with `harden` off) |
| 3 | **The T09 mitigations are off by default and no caller turns them on** | `run_fix(harden=False)`; `flow.agent_job.fix_step` was not changed | **Owner decision** | Pass `harden=True` in `fix_step`. The effect on the fix rate was not measured. On the Docker path the T18 break-it showed no secret reaching the model, trajectory, patch or reply with `harden` off, so the flag matters most for file content the model copies (risk 4) |
| 4 | **The red-team ran on one small local model only** (`gemma4:e4b`, about 7.5B parameters, CPU), 3 cases x 5 repeats = 15 runs; never on the production model | T08, T09 results | **Open** | A run on the production model within its quota. Baseline: ticket 3 of 5 runs succeeded, repo-file 1 of 5, skill 0 of 5; hardened: 0 of 5 in each. A small sample on a small model is neither a prediction nor a proof |
| 5 | **The skill path was not actually exercised.** The model loaded the skill in 2 of 5 baseline runs and 0 of 5 hardened runs, so the skill case is blocked mostly because the attack never reached the model | T08, T09 | **Open**. Skills are off by default, which keeps the exposure small | Force the skill into the prompt in a re-run, or run on a model that loads it |
| 6 | **The audit log is not wired into the fix loop's own tool calls.** Only the escape suite and the egress probe write to it. `audited()` exists and is tested, but no caller passes it as `execute=` | T06, T17, T21 | **Open** | Wire `audited` in `fix_step`. Until then "what did the agent do" is answered by the trajectory, which the same process writes |
| 7 | **Tail truncation of the audit log is caught only with a head hash kept elsewhere**, and a consistent rewrite is caught the same way. The head is written to the run summary only by `guard.yml`, which never ran on GitHub | T19 break-it, T17 | **Open** | A real green `guard.yml` run, and the owner copying the head hash somewhere the log's writer cannot edit |
| 8 | **The fix sandbox has no `--pids-limit`, no `--cap-drop` and runs as root.** The escape suite adds `--pids-limit 128` itself; the same fork probe through `fix_loop.sandbox.run` found 301 processes alive | T12 finding | **Open** | Add the flags to `fix_loop/sandbox.py` and re-run the suite |
| 9 | **A reviewer approves a bad patch** | ASI09 | **Accepted**. One owner, a draft PR, checks outside the model. The reviewer is the last line and no control forces a careful read | A second reviewer or required checks |
| 10 | **Long-lived personal tokens on Render until the App exists; branch protection never seen working** | T04, T20 (mock only) | **Owner decision** (create the App, turn on protection; whether a private repo's plan allows protection is not known) | Owner steps in `docs/notes/p7-t04-app-permissions.md` and `p7-break-its.md` |
| 11 | **A success output (the patch) and the result artifact are not redacted**; the trajectory is. A secret in a plainly named variable or in a repo file is never masked | T03, T18 | **Open** | Redact the output on write, or keep such values out of the process |
| 12 | **`ast_grep` runs `npx --yes` on the host with network** | Threat model section 7 | **Open** (owner may accept) | Install the pinned package into the sandbox image |
| 13 | Actions pinned by tag, npm fetched at run time, no dependency scan; DB holders can change a stored step result; the dedup set is in memory; the artifact is unsigned | ASI04, ASI06, ASI07 | **Accepted** for a single-owner project | A second owner, or a public repo |
| 14 | No adapter from a live issue to the agent | `flow.agent_job._task_dir` | **Open**, by design | When built, re-run T07 to T09 against live text |

Of the 14 rows: 2 accepted (9, 13), 4 owner decisions (1, 2, 3, 10) and 8 open (4, 5, 6, 7, 8, 11, 12, 14).

What the evidence supports: the Docker sandbox blocked all probes of the escape suite on this machine (12 of 12, later 14 of 14 with the two DNS probes), the DNS lookup from the sandbox failed and was logged, a scripted ticket asking for the environment got nothing on the Docker path, and an edited audit line is named by `guard verify-log`. What it does not support: any claim about the production model, GitHub itself, gVisor, Firecracker or a Linux host.

## Alternatives

- **Treat the model as trusted and skip the sandbox work.** Rejected: the model reads attacker-controlled text and writes commands. The first red-team run put a canary file's content into the patch in 4 of 10 baseline runs.
- **Switch on every mitigation now and call the injection risk closed.** Not chosen: the effect on the fix rate is unmeasured, the test model is small, and the filter masks only known secrets. The ADR leaves the switch to the owner (risk 3).
- **Move the scorer into the sandbox inside P7.** Not done: it is outside the P7 acceptance text and changes the bench. Listed as the largest risk instead (risk 1).
- **One generic risk list instead of OWASP rows.** Not chosen: the phase asks for ASI01 to ASI10, and the rows make "not applicable" explicit (ASI07 has no agent-to-agent protocol).

## Consequences

- The owner has four decisions to make: the scorer (1), the default executor (2), `harden` in `fix_step` (3), and the App plus branch protection (10). Decisions 2 and 3 are small in code, the cost of 3 is in measuring the fix rate; decision 1 (sandbox the scorer) is a real piece of work.
- The threat model stays the long form. If this ADR and the threat model disagree, the threat model is the one with the file and line references.
- Several controls are marked "tested locally" in the P7 README. None is verified on GitHub. The statement "tested on Actions" in the phase's done-when list is not met.
- A model change (a different production model) invalidates risks 4 and 5 until a red-team run is repeated on it.
