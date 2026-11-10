# ADR-031: The workbench is local, file-backed and unauthenticated

Status: proposed (P10-T15), written by Claude, owner to decide. It is accepted when the owner approves it. **Nothing in it was run against a hosted setup, and it makes no claim that a test passes.** The workbench code and its tests are built by other P10 tasks; this ADR describes the design decisions and what `phases/P10-argus-workbench.md` requires. Revisit it before anyone proposes to host the workbench, give it a second user, or let it call a model.

ADR-030 is reserved for P9 (the optional lane, not built). That is why this one is 031.

## Context

P10 adds `packages/workbench` (`argus_workbench`, command `argus-workbench serve`): a small web UI with five screens (new issue, live run, review and decision, PR raised, history). The owner types an issue, watches a run, reviews a before/after report, decides, and gets a PR built against the mock GitHub transport (`argus_app.pr`, `flow.github_write`).

The design is in `docs/notes/p10-spec.json`. Its section `differsFromPlan` lists six points where the owner's flow differs from the plan:

| ID | Point | What it means for this ADR |
|---|---|---|
| D1 | Typed intake instead of a labelled GitHub issue | A backend is needed, and it takes text and files from a browser. That is the trust boundary below. |
| D2 | The HTML report is read before the PR | The report is a file made by a run; it is shown only in a sandboxed frame. |
| D3 | The PR opens on approve, as a draft | Approve is the one action with a side effect (a mock PR), so it needs a server-side guard. |
| D4 | "Production UI" against the synthetic-only rule | Free-tier prompts may be used for training (`PLAN.md:14`). Screen 1 asks for a "public or synthetic only" acknowledgement. Real production screenshots would break the rule. |
| D5 | Request changes | A retry makes a new run folder; the old run is not changed. |
| D6 | Quota is a first-class state | Shown as `quota-wait`, derived from the stop reason `QuotaExceeded`. |

Run state is a folder per run under `.local/workbench/runs/<run_id>/` (git-ignored): `ticket.json`, `state.json`, `trajectory.jsonl`, `verdict.json`, `report.html`, `patch.diff`, `decision.json`, `pr.json`. The exact contract is in `docs/architecture/p10.md`.

## Decision

### 1. Local, file-backed, unauthenticated

The workbench is a tool for one person on one machine.

- **Binds 127.0.0.1 only.** The command has no `--host` option, so there is no flag that opens it to the network.
- **File-backed.** The run store is plain files. There is no database and no service to run.
- **No login.** There are no users, no sessions, no passwords. The person at the keyboard is the owner.
- **A per-start token** is made when the server starts and is needed on every request that changes something. It is never logged in full.
- **Host and Origin checks.** A request whose `Host` is not the local address and port is refused (this is the DNS-rebinding case). A state-changing request with a foreign `Origin` is refused. No CORS header is sent for another origin.
- **A Content-Security-Policy** with no inline script and no external source, so a page the server serves cannot run script it did not ship.
- **Typed errors.** Every JSON error has the shape `{"error": {"code", "field", "message"}}`.

These controls exist because "local" is not the same as "safe". A web page open in another tab of the same browser can send requests to `127.0.0.1`. The token, the Host check and the Origin check are what stop that page from creating runs, approving a patch or writing to the run store.

### 2. What is NOT defended (a hosted workbench)

If the workbench were put on a network address, these would all be open. Nothing here was built to cover them:

| Gap | Why it is a gap |
|---|---|
| No login | Anyone who can reach the port and read the token can act as the owner. The token is a guard against a hostile web page, not an identity. |
| No tenant isolation | One run store, one owner. Runs of two people would share the same folder and the same history. Compare ADR-027 and ADR-028 for the tenancy that the App path has. |
| No rate limit | A caller can create runs and uploads without limit. The only size limit is the upload maximum (proposed 5 MB in the spec; no schema sets one). |
| File store races across processes | Writes are made safe inside one server process (a lock around decide-and-open-PR, one decision per idempotency key). Two server processes on one run folder are not coordinated. |
| No TLS | The traffic is plain HTTP. On 127.0.0.1 it does not leave the machine; on a network it would be readable. |
| No audit log of who did what | There is only one actor. A hosted version would need to record the actor. |
| Secrets in the browser | There are none by design. A hosted version that kept a GitHub App key or a model key would need the handling in ADR-026. |

Those are not "later features". Each is a reason the workbench must not be hosted as it stands. Turning on a public address is a new design, with a new ADR.

### 3. The typed-intake trust boundary

D1 means the workbench takes input that anyone could have written. Everything that crosses in is **untrusted data, not instructions** (ADR-024 sets the same line for the pipeline):

- **Ticket text** (`ticket.json`), **screenshots**, and **reviewer notes** (`decision.json`) come from the person typing, who may have pasted text from a bug report written by someone else.
- A run folder written by a runner is also data. A replayed `trajectory.jsonl` can contain anything its author put in it.

Rules that follow:

1. **Rendered as text.** The page sets text with `textContent` only. There is no `innerHTML` for run data, no inline script, no inline event handler. `<script>`, an `onerror` image and `$(...)` in a ticket, a run id, a reviewer note, the report or the PR body show as plain characters on every screen.
2. **Run ids are checked** against `[a-z0-9-]{1,64}` before they touch a path, so an id cannot walk out of the run store.
3. **Uploads are decided by magic bytes**, not by the file name or the declared content type. HTML named `.png`, SVG, an oversize file, a zero-byte file and a name containing `..` are refused with a typed error, and nothing is stored for a refused upload.
4. **The report is shown only in a sandboxed frame** with no script permission and no same-origin access. `report.html` is made by a run, so it is treated like any other untrusted HTML.
5. **The server decides, the button does not.** An approve after a failed verifier is refused by the server, not just hidden in the UI.

Where the checks will be tested: `packages/workbench/tests`. The four break-its are P10-T10 (hostile text), T11 (hostile uploads), T12 (forged requests) and T13 (double approve). Each must fail on a mutated build, and each has a write-up in `docs/notes/p10-break-it-txx.md`. This ADR does not say they pass; their write-ups do, once they have been run.

### 4. Why runs are scripted or replayed by default

P10 makes **no model call**, in code or in tests. A run in the workbench is one of:

- `ScriptedRunner` (five scenarios: normal, quota, stuck, verifier failed, judge disagrees),
- `ReplayRunner` (plays a stored `trajectory.jsonl`),
- `FixLoopRunner`, an adapter over `fix_loop.run_fix`, tested with a scripted model only (a plain Python function).

Reasons:

1. **No spend and no key.** No API key, model URL or model name is read at import time. The workbench works with nothing configured.
2. **The free-tier data caveat (D4).** Free-tier prompts may be used for training, so only public or synthetic code may go through them. A UI where anyone can paste a ticket and a screenshot is the easiest place to break that rule by accident. With no model behind it, a pasted production screenshot goes nowhere. The acknowledgement on screen 1 stays, so the habit is in place if a model is ever connected.
3. **Nothing a UI run produces is a measurement.** The token counts, timings and verdicts in a scripted run are placeholders chosen to show the screen shape (`sim.note` in the spec says so). Every run is tagged **SIMULATED** or **REPLAY**, no file is ever tagged as a real model result, and these runs are in **no aggregate**. Metrics on the history screen show a dash unless a real result file backs them. There is no resolve rate, token count per bug or latency from P10.
4. **The judge label is advisory** (ADR-013): alpha is not calibrated. A scripted "judge disagrees" scenario shows the screen state; it says nothing about the judge.

### 5. No real PR

The PR screen uses the mock transport. A real PR needs the registered GitHub App (ADR-026, owner steps), which does not exist yet. That is an owner step and is out of scope for P10.

## Alternatives

- **A hosted workbench with a login.** Not now. It needs an identity provider, per-tenant stores, rate limits, TLS, a secrets store and an abuse policy, none of which a one-owner tool needs. It would also put the owner's tickets and screenshots on a server that falls under the free-tier caveat. The plan's intake is already a labelled GitHub issue on an installed repo (D1), served by the App path (P6, P8); the workbench is the local, typed way in, not a second product.
- **Driving a real model from the UI.** Not now. It needs a key in the process, the spend and quota rules from ADR-002 and ADR-028, and the free-tier data caveat applied to whatever a user pastes. It would also make the screen numbers look like measurements. The `FixLoopRunner` adapter keeps the door open: a real model is a different callable passed to the same adapter, behind an owner decision.
- **A database instead of files.** Not chosen. One owner, one machine, and a folder per run is easy to look at, copy and delete. Revisit with a second process or a second user.
- **Session login on localhost.** Not chosen. The per-start token already answers the real threat on a local port, a hostile page in the same browser. A password adds nothing against the person who owns the machine.

## Consequences

- The workbench is safe to leave running on 127.0.0.1 and not safe to expose. Anyone who wants to host it has to write the missing pieces (section 2) and a new ADR first.
- A person who starts it must know that what it shows is simulated or replayed. Every run carries the tag, and the history screen has dashes where no real result exists.
- The file store is simple to inspect and to wipe, and it will not survive two server processes on one folder.
- Because the token is per start, a bookmarked URL with the token stops working on restart. That is the intended cost.
- The checks in section 3 are only as good as their tests. They are listed in P10-T10 to T13; this ADR stays "proposed" until the owner has read those write-ups.
- A later phase that adds a real model has to revisit section 4 and ADR-026 first, and the history screen needs a way to separate real results from simulated ones before they share a number.

## References

- `docs/notes/p10-spec.json`: `differsFromPlan` D1 to D6, `sim`, `meta.honesty`.
- `phases/P10-argus-workbench.md`: goals, the decisions made before the phase, the break-its, "ADRs to write".
- `docs/notes/p10-waves.md`: the run folder contract and the rules for task sessions.
- ADR-024: threat model and trust boundaries (untrusted data is not instructions).
- ADR-026: secrets handling and token scopes (secrets are environment variables; the App is the path to a real PR).
- ADR-013: judge selection (the judge label is advisory).
- ADR-027 and ADR-028: tenancy and per-tenant quota, the hosted-side counterparts this ADR does not have.
- ADR-030: reserved for P9.
