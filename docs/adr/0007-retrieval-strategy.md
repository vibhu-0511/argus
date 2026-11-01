# ADR-007: Retrieval strategy

Status: accepted (P2-T13).

## Context

P2 has three ways to name the file a UI bug lives in. Repo-map ranks symbol names from the tsserver index of `apps/canvas/src`. pgvector ranks chunks of the scoped Canvas files with `all-MiniLM-L6-v2` on CPU. `locate()` reads `data-src` on a DOM node.

The comparison is the 30 seeded tasks, 10 in each tier. The ablation table in `phases/P02-dom2src.md` holds the run. Every golden path in that set is a CSS file.

## Decision

For a prose ticket with no DOM, pgvector is the default. On those 30 tasks its top-1 file accuracy is 15/30 [0.331539, 0.668461] and its top-3 is 19/30 [0.455132, 0.781263]. Repo-map scored 0/30. `locate()` scored 0/30 because no task gave it a `#id` or `data-testid` selector and an HTML file.

When the caller has a supported selector and HTML stamped with `data-src`, `locate()` is the fallback. It returns the stamped file and line instead of a ranked guess. This run did not measure that case. Repo-map is not the fallback for these stylesheet bugs. Its index has no `.css` files, so it cannot name the golden path.

## Alternatives

- Default to repo-map plus LSP. The index was built by tsserver 5.8.3 and contains TypeScript symbols, not stylesheets. The run scored 0/30 top-1 and 0/30 top-3.
- Default to `locate()` for every ticket. The seeded tickets do not carry a DOM node. The run scored 0/30.
- Treat 15/30 as a solve rate. The Wilson interval is [0.331539, 0.668461]. Eleven tasks touch only `apps/canvas/src/styles`, which the embed scope does not index.

## Consequences

A ticket with no DOM goes to pgvector. A caller that already has a selector and stamped HTML calls `locate()`. Repo-map stays the symbol index. It is not the file ranker for a CSS bug. No LLM was called. Tokens, dollars, and quota were not measured.

## Verifier finding (2026-10-31)

The decision above is unchanged and is the owner's to confirm. The plan-verifier found that the comparison it rests on was not a three-way comparison, and run `p2-abl-20261030T204633Z` (`docs/notes/results/p2-abl-20261030T204633Z.txt`) reproduced the same counts.

- All 30 golden paths are CSS files. Repo-map's index has no CSS, and `locate()` was given no selector and no DOM. A and C could not score above 0 by construction. Only pgvector could score, so "pgvector is the default" is a statement about CSS tickets with no DOM, not about the three retrievers.
- The default order here (pgvector, then `locate()`) conflicts with the approved design in `analysis/swarm/hld-edges.json` edge 9: `locate()` first, `ambiguous` returns ranked candidates, `no-source-info` falls back to text retrieval. Neither order has been measured on JSX-origin bugs.
- Redoing the ablation on JSX-origin tasks is an open item (`phases/P02-dom2src.md`, Verifier finding).
