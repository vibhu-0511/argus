# P2 — dom2src

**Budget:** 44 h · **Weeks:** W6–8 · **Packages:** `dom2src-plugin` (ts), `dom2src-mcp` (py), uses `target-app`

## Goal
Map a rendered DOM element back to its source file and line, expose that as a `locate()` MCP tool on the 2026-07-28 spec, and measure it against text-based code retrieval.

## Done when
- A Vite plugin adds a repo-relative `data-src="file:line:col"` attribute, with no tag suffix, for the definition and the JSX call site, to every JSX host element in test/dev builds of the dcortex Canvas worktree in `config/platform.md`, and the plugin is absent from production builds (both asserted by tests on the five flows named there).
- `locate()` returns file and line for an element given a selector, and returns a typed "ambiguous" result with candidates when a wrapper component is involved; `locate()` stays the Python tool, with no client and no companion server.
- The MCP server passes a handshake and one `locate()` call from an MCP Python SDK v2 client; the spec version is recorded.
- Top-1 file accuracy is measured for all three retrieval variants on a 30-task stratified subset (ablation table filled).
- CI runs the plugin and server tests with no LLM calls.
- Phase report filled against P1.

## Agentic concepts learned
1. **Grounding an agent in the DOM** — why a build-time `data-src` attribute is the only robust route now that React 19 dropped `_debugSource` (React issue #32574).
2. **Retrieval strategies for code** — repo-map plus LSP (structure) vs embeddings in pgvector (semantics), and when each wins.
3. **Designing a tool as an MCP server** — one narrow tool, a typed input/output contract, typed errors.
4. **Protocol currency** — building against the stateless 2026-07-28 core and noticing what a client does not support.
5. **Ambiguity as a result type** — returning candidates instead of guessing.

## Interview questions
1. Why can't a React 19.2 agent rely on `_debugSource` to find the source of a DOM node, and what do you do instead?
2. For "which file contains this bug?", when would you prefer a repo-map with LSP over an embedding index, and what would change your mind?

## Prereq reading
- [React issue #32574 (removal of debug source info)](https://github.com/react/react/issues/32574)
- [Aider repo map](https://aider.chat/docs/repomap.html)
- [MCP 2026-07-28 release post](https://blog.modelcontextprotocol.io/posts/2026-07-28/)

## Tasks
| ID | Title | Owner | Type | Est hrs | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| P2-T00 | Re-verify pinned versions via web search | [CLAUDE] | doc | 1 | P1-T16 | Versions table re-checked, including MCP spec, MCP Python SDK and `@playwright/mcp` |
| P2-T01 | Read React issue #32574 and the Aider repo-map docs, write notes | [ME] | learn | 1 | P2-T00 | Notes state what React removed, why a build-time attribute is needed, and how a repo-map ranks files |
| P2-T02 | Build Vite plugin that injects `data-src` on JSX host elements | [PAIR] | build | 4 | P2-T00, P0-T09 | In a dev build of the dcortex Canvas worktree in `config/platform.md`, host elements on the five flows carry repo-relative `data-src="file:line:col"` for the definition and the JSX call site, with no tag suffix; the plugin is absent from production and registered before JSX; a unit test checks a sample file's transform output |
| P2-T03 | Add plugin tests: attribute on every host element, stripped in production build | [CLAUDE] | test | 2 | P2-T02 | One Playwright test counts elements without the attribute (expect 0 in dev/test); a second asserts none carry it in the production build |
| P2-T04 | Write ADR-006: `data-src` attribute vs source maps | [ME] | doc | 1 | P2-T03 | ADR compares the two on robustness, build cost and production safety, and records the decision |
| P2-T05 | Implement locate() core: selector to DOM node to `data-src` to file and line | [ME] | build | 3 | P2-T02 | For 10 hand-picked elements, locate() returns the right file and line; nonexistent selector returns a typed `not-found` |
| P2-T06 | Define MCP tool schema for locate() (input, output, typed errors) | [ME] | build | 2 | P2-T05 | Schema file validates; input and output examples pass; errors enumerated: `not-found`, `ambiguous`, `no-source-info` |
| P2-T07 | Build the MCP server for locate() on the 2026-07-28 spec with SDK v2 | [ME] | build | 4 | P2-T06 | A stateless server handshakes with the SDK v2 client and answers one locate() call; the server records the spec version it speaks |
| P2-T08 | Handle ambiguity: wrapper components and repeated elements return candidates | [ME] | build | 2 | P2-T07 | For a wrapper-rendered button, locate() returns an `ambiguous` result with at least 2 ranked candidates, the definition and the JSX call site; `locate()` stays the Python tool, with no client and no companion server |
| P2-T09 | Build repo-map plus LSP index of the dcortex Canvas worktree | [PAIR] | build | 4 | P2-T00 | `index.json` lists symbols per file in the worktree named in `config/platform.md`; a query for a symbol returns definition and reference locations from the language server |
| P2-T10 | Build pgvector variant with a local embedding model (CPU) | [PAIR] | build | 3 | P2-T00 | A local Postgres with pgvector holds embeddings of the Canvas source in the worktree named in `config/platform.md`; a query returns ranked files; runs offline. This Postgres is not the copa-local airline database |
| P2-T11 | Build retrieval harness: top-1 and top-3 file accuracy against the golden patch's file | [ME] | eval | 2 | P2-T09, P2-T10 | Harness takes a task list and a retriever, prints top-1 and top-3 accuracy; verified on a stub retriever with known answers |
| P2-T12 | Run ablation: repo-map/LSP vs pgvector vs data-src locate() on 30-task stratified subset | [ME] | eval | 3 | P2-T08, P2-T11 | Three rows filled in the Ablation table from real runs on the same 30 tasks, with Wilson 95% intervals |
| P2-T13 | Write ADR-007: Retrieval strategy | [ME] | doc | 1 | P2-T12 | ADR cites the ablation table and states which retriever is default and which is fallback |
| P2-T14 | Add CI job for plugin and MCP server tests, no LLM calls | [CLAUDE] | deploy | 2 | P2-T07, P2-T03 | Workflow green on push; no secrets; runs both the Playwright attribute tests and the server handshake test |
| P2-T15 | Break it: render a button through a wrapper component | [ME] | test | 2 | P2-T08 | locate() returns `ambiguous` instead of a wrong single answer; written up in the Break it section |
| P2-T16 | Break it: run locate() against a production build | [ME] | test | 2 | P2-T03 | locate() returns `no-source-info`, not a guess; written up in the Break it section |
| P2-T17 | Break it: edit a file after the repo-map is built | [ME] | test | 2 | P2-T09 | Stale-index retrieval is detected by a content hash check; written up in the Break it section |
| P2-T18 | Break it: connect with a client that speaks an older MCP spec | [ME] | test | 2 | P2-T07 | Handshake fails with a clear version error rather than a hang; written up in the Break it section |
| P2-T19 | Write package READMEs and phase report against P1 | [CLAUDE] | doc | 1 | P2-T13 | READMEs show install and run commands; phase report has previous-phase, this-phase and delta rows filled |

## Break it on purpose
1. **Wrapper component (P2-T15).** *Induced failure:* a button rendered through a shared `<Button>` wrapper, so the DOM node's `data-src` points at the wrapper definition. *Expected signal:* `locate()` returns `ambiguous` with candidates, never a single confident wrong file. *Fix:* return the wrapper plus the call-site candidates, and let the fix-loop pick using the ticket.
   Observed: `locate("#save")` on a button stamped `apps/canvas/src/ui/Button.tsx:4:3` inside a host stamped `apps/canvas/src/screens/Page.tsx:8:5` returned `Ambiguous` (`ambiguous`). Rank 1 is the call site `Page.tsx:8:5`. Rank 2 is the wrapper definition `Button.tsx:4:3`. It did not return a single file.
2. **Production build (P2-T16).** *Induced failure:* point `locate()` at a production bundle. *Expected signal:* typed `no-source-info`. *Fix:* the plugin is dev/test only by design; the agent must run against a test build, and the tool says so in its error.
   Observed: `locate()` ran on production HTML with the same ten host elements and no `data-src` attributes. Each match returned `NoSourceInfo` (`no-source-info`) and no file or line. Selectors that matched nothing stayed `NotFound` (`not-found`).
3. **Stale index (P2-T17).** *Induced failure:* edit a file after the repo-map is built. *Expected signal:* the content-hash check marks the index stale and retrieval refuses to answer or re-indexes. *Fix:* re-index incrementally on hash mismatch.
   Observed: temp file `apps/canvas/src/Widget.tsx` was edited after the index stored its sha256. `query` raised `StaleIndex` (`stale index: apps/canvas/src/Widget.tsx`) and returned no locations.
4. **Older MCP client (P2-T18).** *Induced failure:* connect a client that speaks an earlier spec to the server. *Expected signal:* version-mismatch error at the handshake, not a hang. *Fix:* the server states the spec version it supports; the client falls back to calling the core function directly.
   Observed: client mode `legacy` raised `MCPError` (`protocol versions do not match: client 2025-11-25, server 2026-07-28`) at the handshake and did not hang.

## Ablation
**Hypothesis:** repo-map plus LSP beats pgvector on top-1 file accuracy for UI bugs, and DOM-grounded `locate()` beats both when a DOM is available.
**Variants:** A = repo-map plus LSP; B = pgvector with local embeddings; C = `locate()` via `data-src`.
**Metric:** top-1 file accuracy (Wilson 95% interval) on a 30-task stratified subset; also latency and tokens where a model call is involved.

| Variant | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug | Quota share/bug | p50 latency | p95 latency | Top-1 file accuracy |
|---|---|---|---|---|---|---|---|
| A | — | — | — | — | 0.003275s | 0.006280s | 0/30 [0.000000, 0.113517] |
| B | — | — | — | — | 0.415103s | 0.717434s | 15/30 [0.331539, 0.668461] |
| C | — | — | — | — | 0.000941s | 0.005071s | 0/30 [0.000000, 0.113517] |

Run `p2-abl-20261030T204633Z`: `uv run python -m dom2src_mcp.ablation --reindex --out-dir docs/notes/results`. The raw command, commit, per-task ranks and output are in `docs/notes/results/p2-abl-20261030T204633Z.txt`. The accuracy cells reproduce the earlier unrecorded run exactly; the earlier latency cells (A 0.006171s/0.011220s, B 0.822504s/2.906274s, C 0.001800s/0.006850s) had no run behind them and are replaced by this run's.

The 30 tasks are `packages/bench/tasks/seeded`: 10 easy, 10 medium, 10 hard. Every golden path is a CSS file. Repo-map ranks symbol names in the tsserver index. That index has no `.css` files, and the run scored top-1 and top-3 at 0/30. No ticket contains a `#id` or `data-testid` selector, and no task directory has an HTML file, so `locate()` returned no file. That run also scored 0/30 and 0/30. pgvector top-1 is 15/30 and top-3 is 19/30. Eleven tasks touch only `apps/canvas/src/styles`, which the embed scope does not index. Nineteen touch a file under `apps/canvas/src/ops`. Those counts describe the subset. They are not the hit list. Latency is the nearest-rank percentile, index `ceil(p/100*n)-1`, on the 30 timed calls after one warmup call that is not included. No LLM was called, so resolve rate, tokens, dollars, and quota stay —. Model load printed a Hugging Face hub warning about unauthenticated requests. The weight progress completed from the local cache, 103 of 103.

**Phase report (against previous phase):**

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase | 28/30 [0.786762, 0.981523] | 1.0000, 1.0000, 0.0000 | — | — | — |
| This phase | — | — | — | 0.415103s | 0.717434s |
| Delta | — | — | — | — | — |

The previous row is P1's text-only batch. Its 28/30 is fixture replay (`host` is `fixture`), not a live-model result, so it is not a baseline for anything measured here. This phase did not resolve bugs. Its measured rate is top-1 file accuracy in the ablation table, so the resolve cell stays — and is not subtracted from 28/30. The latency cells are the pgvector per-task times from run `p2-abl-20261030T204633Z`. P1 left latency blank, so the latency delta stays —.

## Verifier finding (2026-10-31)
The plan-verifier's report (2026-10-30) found, and the re-run `p2-abl-20261030T204633Z` confirmed, that the three-way comparison was not actually run.
- All 30 golden paths are CSS files. Variant A's index has no CSS, and variant C got no selector and no DOM (no ticket has a `#id` or `data-testid`, no task directory has an HTML file). A and C could not score above 0 by construction, so their 0/30 says nothing about repo-map or `locate()` on JSX bugs. Only B had a chance to score.
- The default order in ADR-007 (pgvector first, `locate()` as the fallback) conflicts with the approved design (`analysis/swarm/hld-edges.json` edge 9: `locate()` first; `ambiguous` returns ranked candidates; `no-source-info` falls back to text retrieval). Which is right is an owner decision and neither is changed here.
- Open: redo the ablation on tasks whose bug is in JSX, with a ticket and a DOM. bugsmith's JSX operators (`remove-class`, `swap-flex-direction`, `drop-prop`, `change-element`) make the bug patch cheap, but each task also needs a ticket text and rendered HTML, which that package does not produce. Not done.

## ADRs to write
All [ME].
- **ADR-006 — `data-src` attribute vs source maps.** Which mapping from DOM to source survives React 19 and a bundler change?
- **ADR-007 — Retrieval strategy.** Which retriever is the default for "which file has the bug", and when does the fallback apply?

## Deploy checkpoint
GitHub Actions runs the repro-agent fixture tests and now the plugin and MCP server tests (`dom2src.yml`, without the `live` tests) on every push; the golden-fix run is manual-dispatch (see P0). Still no LLM calls in CI. `dom2src.yml` has not run on GitHub, so P2-T14 stays unticked until a green run id exists.

## Portfolio artifact
A small, reusable Vite plugin plus MCP server repo for "DOM element to source line", with the three-way retrieval ablation.
