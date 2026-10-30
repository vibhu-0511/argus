# Learning graph: industrial concepts for Argus

Lane: `concepts`. Data: [`concepts.json`](concepts.json) (89 nodes, 146 edges, 12 groups). Written 2026-10-30 from `PLAN.md`, `PROJECT.md`, `phases/`, `docs/adr/`, `analysis/research/`, `packages/*` and the headings of `argus-learning.html`.

## Shape of the graph

| Measure | Value |
|---|---|
| Nodes | 89 (level 1: 10, level 2: 25, level 3: 38, level 4: 16) |
| Status | 32 `built` (exercised by P0/P1), 56 `planned` (P2-P9), 1 `external` (`outbox`, not scheduled in any phase) |
| Edges | 91 `prereq`, 43 `related`, 12 `enables` |
| Longest `prereq` chain | 8 nodes |
| Entry points (no incoming `prereq`) | 26, so a learner can start on several fronts |
| Orphans / disconnected components | 0 / 1 component |

Groups: loop (13), context (7), limits (3), sandbox (5), durable (8), protocol (5), observe (7), evalstat (16), verify (7), locate (4), security (6), delivery (8).

Rule used for `built`: the concept is implemented or decided in a file that exists in this checkout, and `inRepo` points at the most direct file. 32 of 32 paths exist (checked by the validator).

### Honest caveats on `built`
- **`fixture-replay-testing`, `wilson-ci`, `ablation-design`** are built as *machinery*. The P1 "28/30" numbers come from recorded replies (`batch.py:67` sets `host="fixture"`), so they test the harness, not model quality (see `docs/adr/0005-screenshot-in-ticket-context.md`). Learn the concept, do not read the number as evidence.
- **`mutation-testing`** is used inverted: bugsmith injects faults to *make benchmark bugs*, not to grade a test suite. `bug-synthesis` and `mutant-validity-filter` are the exact P0 pieces.
- **`repro-revise-loop` is not `agent-loop`.** P1 is a generate-run-revise loop. The full tool-use loop with stuck detection and context management is P3, so `agent-loop` is `planned`.
- **`docker-sandbox`** is built at the `--network none` tier (`packages/repro-agent/src/repro_agent/verify.py:40-41`). The same command also passes `--ipc=host` (line 42), which shares the host IPC namespace. That is a hardening question for the P7 `sandbox-tiers` work, not a P1 bug.
- **`outbox`** has no phase task. It is in the graph because DBOS durable steps solve the same dual-write problem and an architect should know the pattern by name (`analysis/research/T4-delivery.md` cites a DBOS transactional-outbox demo).

## Suggested learning path (8 steps)

Follow `prereq` edges inside each step. Steps 1-4 are mostly already built in the repo, so you read the code and then explain it. Steps 5-8 are ahead of you.

| # | Step | Concepts (ids) | Do / read |
|---|---|---|---|
| 1 | **Measure before you build** (P0) | `model-client`, `token-accounting`, `rate-limits`, `quota-ledger`, `baseline-agent`, `wilson-ci`, `tri-state-verdicts`, `trajectory-recording` | Read `ledger.py` and ADR-002. Explain why the check runs before the HTTP call. Compute a Wilson interval for 0/10 by hand. |
| 2 | **The environment is the oracle** (P0) | `git-worktrees`, `golden-fix-ci`, `mutation-testing`, `bug-synthesis`, `mutant-validity-filter`, `flaky-test-quarantine`, `computed-style-checks`, `pixel-diff` | Read `validity.py`, `flake.py`, ADR-003. List the four reasons a mutant is rejected. |
| 3 | **A first agent and its interface** (P1) | `mcp-basics`, `tool-schema-design`, `tool-allowlist`, `tool-error-taxonomy`, `a11y-snapshot-refs`, `tool-output-truncation`, `repro-revise-loop`, `stop-conditions`, `repro-validity`, `docker-sandbox`, `mcp-version-negotiation` | Read `tools.py`, `loop.py`, ADR-004. Add one new `ToolErrorCode` on paper and trace what changes. |
| 4 | **Honest evaluation** (P1) | `trajectory-replay`, `fixture-replay-testing`, `ablation-design`, `multimodal-context` | Run one live (non-fixture) repro batch and compare it to the replay row. This closes the caveat above. |
| 5 | **Locate, then the real loop** (P2-P3) | `source-mapping-data-src`, `source-maps`, `repo-map`, `embeddings-pgvector`, `mcp-server-authoring`, `agent-loop`, `edit-formats`, `stuck-detection`, `gate-feedback`, `context-budget`, `compaction` | Before coding P3, write the stop-condition and compaction rules as an ADR. |
| 6 | **Verify and judge** (P4) | `verifier-pipeline`, `visual-masks`, `antialiasing-thresholds`, `axe-a11y`, `llm-as-judge`, `self-preference-bias`, `inter-rater-agreement`, `judge-calibration`, `best-of-k` | Label pairs by hand before any judge runs; compute alpha, not percent agreement. |
| 7 | **Observe, route, gate, distil** (P5, P5.5) | `tracing-observability`, `otel-genai-semconv`, `trace-backend`, `trace-normalizer`, `trajectory-metrics`, `prompt-caching`, `routing`, `cost-modelling`, `regression-gate`, `swe-bench`, `agent-skills`, `skill-distillation`, `skill-trust` | Emit one span per tool call; price a run in $-equivalent; set a gate threshold from an interval. |
| 8 | **Durable, safe, multi-tenant** (P6-P9) | 8a: `idempotency`, `durable-execution`, `dbos`, `temporal`, `outbox`, `webhooks-as-hints`, `reconciliation-polling`, `stateless-protocols`, `mrtr`, `human-in-the-loop-wait`. 8b: `prompt-injection`, `threat-modelling`, `owasp-agentic`, `least-privilege-tokens`, `gvisor`, `firecracker`, `sandbox-tiers`, `red-teaming`, `github-apps`, `reusable-workflow-tenancy`, `backporting`, `per-tenant-budgets`, `planner-subagents`, `backend-lane`, `adr` | Write ADR-020/021 and ADR-024/025 *before* the code; each answers "what breaks if this is wrong?" |

Why this order: it follows the dependency of evidence. You cannot trust an agent number (4-6) before you trust the oracle (2), and you cannot trust the oracle before you can count honestly (1). Durability and security come last because they harden a pipeline that must already exist, but read `prompt-injection` earlier if a tool ever touches untrusted text.

## Sources: what "verified" means here

- Every node has a `source.url`; none is `null`. 71 distinct URLs.
- On 2026-10-30 each URL returned HTTP 200 via `curl -L`. 41 of them also had their page `<title>` read to confirm the page is the one named (all arXiv papers, OWASP agentic, MCP spec and blog, Anthropic engineering posts and caching docs, DBOS, Groq, Stripe, gVisor, Temporal, promptfoo, Langfuse, GitHub apps/checks/reuse docs, agentskills, outbox, Kubernetes, Sentry, Docker, ECMA-426, Playwright snapshots, semconv-genai).
- **Status-only (HTTP 200, title not read, content not re-checked):** mini-swe-agent, playwright-mcp, Playwright aria-snapshots, OpenHands SDK, Aider edit-formats and repomap, MDN (429, getComputedStyle), git-worktree, Firecracker NSDI page, dbos-transact-py, GitHub webhook best practices, Fielding REST, OTel traces, OpenInference, Fowler (CI, TestDouble), Wikipedia (mutation testing, Wilson, ablation, Krippendorff), Google flaky-tests post, pixelmatch, axe-core, Babel jsx-development, pgvector, Willison trifecta, OWASP threat modeling, backport-action, Nygard ADR. A 200 does not prove the page supports the node's claim; treat those as pointers.
- The OTel GenAI node cites the `semantic-conventions-genai` repository, not `opentelemetry.io/docs/specs/semconv/gen-ai/`, because the latter now serves a "Moved" notice. The PLAN version row (stability `development`) is the reason the node says the conventions are still in flux.
- Source choice is a pointer to a primary or well-known explanation, not a claim that it is the only reference. Several repo-internal facts (error taxonomy, quarantine rule, quota semantics) have no external source, so those nodes cite the closest general reference and point `inRepo` at the real decision.

## How to re-run the check

```bash
node -e "JSON.parse(require('fs').readFileSync('analysis/swarm/concepts.json'))"
```

The full validator (ids unique, enums, summary <= 160 chars, edge endpoints exist, no `prereq` cycles, no orphans, one connected component, `built` paths exist, URL in the verified set) lived in the session scratchpad and is not committed (lane rule: write only these two files). Its last output: `nodes=89 edges=146 built=32 planned=56 external=1 roots=26`, no `prereq` edge goes from a higher level to a lower one, `OK`.

## Verification log

| Check | Result |
|---|---|
| JSON parses | Yes |
| Node count in the 60-90 brief | First draft had 101; merged 12 minor concepts into neighbours (position bias into `llm-as-judge`, test-time compute into `best-of-k`, LSP into `repo-map`, overflow/console/check-runs into `verifier-pipeline`, CI shell injection into `prompt-injection`, state machine into `durable-execution`, offload-to-files into `compaction`, Vite plugin into `source-mapping-data-src`) and dropped `structural-search`, `agents-md`, `crash-recovery` as stand-alone nodes. Final: 89. |
| Edge endpoints / cycles / orphans | All endpoints exist; `prereq` subgraph is acyclic; 0 orphans; one connected component. |
| `built` file paths | 32/32 exist. Re-opened `verify.py:36-46` (found `--network none` and `--ipc=host`), `batch.py:67` (`host="fixture"`), `tools.py:174` (`cap_text`), `flake.py:54`, `golden.py:46` (`git worktree add`), `checks.ts:60` (`pixelmatch` threshold 0.1), `types.py` (`TrajectoryMeta`, `StopReason`). |
| Corrected after verification | `docker-sandbox` `inRepo` changed from `docker/Dockerfile` to `verify.py`, because the `--network none` flag is in `verify.py`, not the Dockerfile. OTel GenAI source switched from the "Moved" docs page to the genai repo. |
| Concepts with no repo evidence | `idempotency`, `outbox`, `prompt-caching` (only cached-token accounting exists, in `ledger.py`), `pgvector`, `OTel`, `Krippendorff`, `mask` all grep to zero code hits, so they are `planned` or `external`, not `built`. |
| Not done | Did not diff `argus-learning.html` content in detail; only its headings (Architecture, Box/job, Low-level design, Learning path, Phase table) were read. This graph is concept-first with prerequisites, which that page's phase-first layout does not give. Did not read every `phases/P0x` task table; phase tags come from `PLAN.md` phase map and ADR index. |
