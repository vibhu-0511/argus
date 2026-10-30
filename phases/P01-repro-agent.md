# P1 — repro-agent

**Budget:** 32 h · **Weeks:** W5–6 (starts in the tail of W4) · **Packages:** `repro-agent` (builds on `argus-core`, `bench`)

## Goal
Turn a ticket (text, optionally a screenshot) into a Playwright reproduction script that fails on the buggy tree and passes on the golden-fixed tree.

## Done when
- The interop spike between Playwright MCP and an MCP Python SDK v2 client has a written go/no-go. If it is no-go, the mitigation is ADR-004, not an unscheduled direct-Playwright build.
- `repro-agent` runs over all 30 seeded tasks and writes one verdict per task, produced by the repro verifier (fail on buggy tree, pass on golden tree), not by reading the script.
- Both rows of the Ablation table (text only, text plus screenshot) are filled from real runs.
- A CI job runs the repro-agent tests on recorded fixtures with no LLM calls and no secrets.
- The phase report is filled against the P0 baseline.

## Agentic concepts learned
1. **Tool schema design** — the repro tools' names, parameters and error messages decide whether the model can use them.
2. **MCP client/server interop and spec currency** — what the 2026-07-28 spec changed (stateless core, MRTR, Tasks as an extension) and what your client actually supports.
3. **Verifying generated tests** — a repro script is only credible if it fails before the fix and passes after it.
4. **Bounded agent loops** — generate, run, revise with a hard cap on retries and a clear stop reason.
5. **Multimodal context cost** — what a screenshot buys you in accuracy and what it costs in tokens and quota.

## Interview questions
1. A generated reproduction script passes on the buggy tree. What are three possible causes, and which verifier check catches each?
2. What changed in MCP between earlier specs and 2026-07-28, and how would you find out whether a given server supports it?

## Prereq reading
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [MCP 2026-07-28 release post](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [Building effective agents (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P1-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P0-T31 | Versions table re-checked; `@playwright/mcp` and MCP spec/SDK rows especially; date updated and changes listed |
| P1-T01 | Spike: call Playwright MCP from an MCP Python SDK v2 client | [ME] | learn | 3 | P1-T00 | A script launches the server, lists tools and runs one navigate plus snapshot; the result is a written go/no-go in `docs/notes/p1-mcp-spike.md` with exact versions; a go allow-lists the six repro tools, leaves `browser_run_code_unsafe` off, and does not add `page.evaluate`; it records the `initialize` protocol version and the tool list from the spike process, and schemas are not copied from the 1.65-next or 1.64-alpha tree onto the pinned row |
| P1-T02 | Write ADR-004: Playwright MCP vs direct Playwright as tool | [ME] | doc | 1 | P1-T01 | ADR states the choice, the spike evidence and the fallback, and notes whether Playwright MCP supports the 2026-07-28 spec; marked as the Risk 4 mitigation |
| P1-T03 | Read the MCP 2026-07-28 post and the playwright-mcp README, write notes | [ME] | learn | 1 | P1-T00 | Notes list the three spec changes that affect this project and one open question each |
| P1-T04 | Define repro tool schemas (navigate, snapshot, click, type, assert-visible, screenshot) | [ME] | build | 2 | P1-T02, P0-T03 | Each tool has a typed schema, a description and a typed error result; those six tools are the allow-list, `browser_run_code_unsafe` is off, and `page.evaluate` is not added; `assert-visible` is role plus accessible name; `stale-target` and `not-unique` are typed errors; the snapshot takes a depth or byte cap; schema files validate; one test per tool against the target app |
| P1-T05 | Build Docker image to run Playwright repro scripts with no network egress beyond the app | [CLAUDE] | build | 2 | P1-T04 | `docker run` executes a sample script and returns its exit code; the container cannot reach the internet; `browser_run_code_unsafe` stays off and `page.evaluate` is not added; each repro run gets its own user-data-dir |
| P1-T06 | Assemble ticket and screenshot prompt (text-only and text-plus-image modes) | [PAIR] | build | 2 | P1-T04 | One function builds both modes from a Ticket; a snapshot test shows the image is attached only in image mode; a bad image is a typed tool error, and the bytes must match the declared media type, so one bad shot does not burn the next model call |
| P1-T07 | Build repro agent loop: generate script, run it, revise on error, hard retry cap | [ME] | build | 4 | P1-T04, P1-T05, P1-T06, P0-T05 | Loop stops on a script that fails on the buggy tree and passes on the golden tree, on cap or on `QuotaExceeded`, and records a stop reason; the cap reason is `retry-cap` recorded by the loop, and empty model output counts toward that cap; the saved script uses the logged role and name, not the ephemeral ref, and it contains a symptom assertion before the loop's stop; one trajectory file per run validates against the Trajectory schema |
| P1-T08 | Build repro verifier: script must fail on buggy tree and pass on golden tree | [ME] | build | 2 | P1-T07, P0-T15 | Verifier returns one of `valid`, `passes-on-bug`, `fails-on-golden`, `error`; skip or `test.fixme()` is `error`; four hand-made scripts exercise each verdict |
| P1-T09 | Add CI job for repro-agent tests on recorded fixtures, no LLM calls | [CLAUDE] | deploy | 2 | P1-T08 | Workflow green on push; contains no secrets; replaying a fixture gives the stored trajectory |
| P1-T10 | Run repro-agent on 30 seeded tasks, text only | [ME] | eval | 2 | P1-T08 | 30 verdicts and 30 trajectories saved; ledger shows the run stayed inside the quota; the next task still starts after a crashed server |
| P1-T11 | Run repro-agent on 30 seeded tasks, text plus screenshot | [ME] | eval | 2 | P1-T10 | 30 verdicts and 30 trajectories saved; same seeds and model as T10 |
| P1-T12 | Write ADR-005: When to include the screenshot in ticket context | [ME] | doc | 1 | P1-T11 | ADR cites the ablation table and states a rule with its cost |
| P1-T13 | Break it: give the agent a vague ticket with no steps | [ME] | test | 2 | P1-T08 | Failure mode recorded as in the Break it section; stop reason is visible in the trajectory |
| P1-T14 | Break it: make the script pass on the buggy tree (selector too loose) | [ME] | test | 2 | P1-T08 | Verifier returns `passes-on-bug`; written up in the Break it section |
| P1-T15 | Break it: kill the MCP server mid-run | [ME] | test | 2 | P1-T07 | Loop reports a tool-unavailable stop reason, does not hang past a timeout, and falls back as the fix says; a server exit between calls is the same `tool-unavailable` stop, inside the existing timeout |
| P1-T16 | Write package README and phase report against P0 | [CLAUDE] | doc | 1 | P1-T12 | README shows the run command; phase report table has the previous-phase and this-phase rows filled |

## Break it on purpose
1. **Vague ticket (P1-T13).** *Induced failure:* a ticket that says "the page looks wrong" with no route or element. *Expected signal:* the retry cap is hit, stop reason `retry-cap`, no valid script. *Fix:* add a clarification step that asks for the missing route/element, or fail fast with a typed reason.
2. **Script passes on the buggy tree (P1-T14).** *Induced failure:* a selector so loose that it matches in both trees. *Expected signal:* verifier verdict `passes-on-bug`. *Fix:* require the agent's script to include an assertion on the symptom, and feed the verdict back to the next attempt.
3. **MCP server dies mid-run (P1-T15).** *Induced failure:* the Playwright MCP process dies during a tool call, or it has already exited when the next call starts. *Expected signal:* stop reason `tool-unavailable` within the timeout, no hang. *Fix:* restart the server once, then stop with `tool-unavailable`. Direct Playwright is not the fallback (ADR-004).

## Ablation
**Hypothesis:** adding the screenshot to the ticket raises repro success on layout bugs enough to justify its extra tokens and quota.
**Variants:** A = ticket text only; B = ticket text plus the ticket image, attached once rather than a new screenshot each revision.
**Metric:** repro success (verdict `valid`) with a Wilson 95% interval; also tokens/bug and quota share.

| Variant | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug | Quota share/bug | p50 latency | p95 latency | Repro success |
|---|---|---|---|---|---|---|---|
| A | — | — | — | — | — | — | — |
| B | — | — | — | — | — | — | — |

**Phase report (against previous phase):**

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase | — | — | — | — | — |
| This phase | — | — | — | — | — |
| Delta | — | — | — | — | — |

## ADRs to write
All [ME].
- **ADR-004 — Playwright MCP vs direct Playwright as tool.** Does the MCP interop spike justify using MCP for the browser, or is direct Playwright the safer tool?
- **ADR-005 — Screenshot in ticket context.** When does the screenshot earn its tokens, and when is text enough?

## Deploy checkpoint
GitHub Actions keeps running the P0 golden-fix run on every push, and now also runs the repro-agent tests on recorded fixtures. Neither calls an LLM.

## Portfolio artifact
A short write-up of the MCP interop spike (what worked, versions, what failed) plus the text-vs-screenshot ablation table.
