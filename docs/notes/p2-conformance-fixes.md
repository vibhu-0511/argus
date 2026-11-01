# P2 conformance fixes

Answers `analysis/swarm/conformance/report-2026-10-30.md` (plan-verifier, read-only, in the sibling worktree `agent-swarm-verification-b4db5f`). Branch `claude/p2-conformance-fixes-593529`, cut from `p0-bench` at `97719bd`. Nothing pushed, nothing merged into `p0-bench`. Done 2026-10-31 by a Claude session, not by the owner.

Python was run from a short venv path (`UV_PROJECT_ENVIRONMENT=C:\uvenv\p2`) because the worktree path is long. "Platform checkout" is the dcortex-platform repo named by `ARGUS_PLATFORM_REPO`; it was only read. Its working tree already had 150 modified files before this session and I did not write to it. For fix 5 I added one detached `git worktree` of it, used it, and removed it again.

## 0. Merge of the CI-fix branch

`git fetch origin` then `git merge origin/claude/quizzical-varahamihira-069352` (`069f9c5`). Clean merge, no conflicts to resolve. It brings the new `repro.yml`, the manual-only `golden.yml`, and the `config/platform.md` Repo row without a local path.

That row change broke two P2 modules (verifier "Integration hazards" 1): `embed.py` and `repo_map.py` parsed a local path out of the row. Both now read the env var `ARGUS_PLATFORM_REPO`, like `argus_bench.golden.platform_repo`. A hard-coded `C:\Users\vibha\...` path in the `repo_map.py` header comment went with it.

`pnpm install` was run, and `pnpm-lock.yaml` now has the `packages/dom2src-plugin` importer (verifier hazard 2, recommended fix 3).

## Fix 1. Dependencies and pgvector setup (T10, recommended fix 1)

- `packages/dom2src-mcp/pyproject.toml`: added `psycopg[binary]`, `sentence-transformers`, `jsonschema`, and `torch`. `torch` is named only so a `[tool.uv.sources]` entry can take the CPU wheel index on Linux (CI); Windows uses PyPI. `uv.lock` refreshed.
- `packages/dom2src-mcp/docker-compose.yml`: one command, `docker compose -f packages/dom2src-mcp/docker-compose.yml up -d`. Same image and settings as the existing `argus-canvas-embed` container (`pgvector/pgvector:pg16`, user `argus`, database `canvas_embed`, trust auth, now bound to 127.0.0.1). `CANVAS_EMBED_PORT` overrides the host port.
- `README.md` of the package: install, compose, and the commands that rebuild `index.json` and the pgvector table.
- Pytest marker `live` (root `pyproject.toml`) on the two tests that need the private platform checkout or the database: `test_embed.py::test_query_returns_ranked_canvas_files` and `test_repo_map.py::test_query_returns_definition_and_references_from_language_server`.
- Verified the compose file from scratch: started it on port 5437 under another project name, ran `test_embed.py` against it with `ARGUS_EMBED_DSN`, tore it down.

Result: `ARGUS_PLATFORM_REPO=... ARGUS_EMBED_DSN=postgresql://argus@127.0.0.1:5437/canvas_embed uv run pytest packages/dom2src-mcp/tests/test_embed.py -q` gives `3 passed in 289.63s`. The lockfile install now collects `test_embed.py`.

Open: the Linux CPU-torch source in `uv.lock` could not be exercised here (no Linux, no GitHub run).

## Fix 2. `dom2src.yml` (T14, H3, recommended fix 2)

`.github/workflows/dom2src.yml` now follows `repro.yml`: `pnpm/action-setup`, Node 24 with pnpm cache, `uv sync --all-packages --locked`, `pnpm install --frozen-lockfile`, `uv run pytest packages/dom2src-mcp/tests -m "not live" -q`, `pnpm --filter @argus/dom2src-plugin test` (`transform.test.ts`), `playwright install --with-deps chromium`, then the attribute test. No `npm install`, no secrets.

Two defects the reproduction exposed, both fixed:
- `transform.test.ts` read a local path out of `config/platform.md` and would have failed in CI. Its Canvas test now reads `ARGUS_PLATFORM_REPO` and is skipped when unset (6 pass, 1 skipped; 7 pass with it set).
- `test/installed-browser.cjs` did `require.resolve("playwright-core/package.json")`, which fails under pnpm's strict layout. It now resolves from `@playwright/test`. This, not only the missing rolldown binary the verifier hit, is why `test:attribute` could not run under pnpm. It now runs here.

P2-T14 is **unticked** in `TASKS.md` with the note that it needs a green Actions run id. `docs/architecture/p2.md` (H3, H4) now says the workflow has not run on GitHub and no longer opens with "Nothing in P2 is done yet".

Local reproduction of the workflow's commands (platform path unset, as in CI):

```
uv sync --all-packages --locked        Resolved 79 packages / Checked 76 packages
pnpm install --frozen-lockfile         Done in 441ms
uv run pytest packages/dom2src-mcp/tests -m "not live" -q     51 passed, 3 deselected in 105.70s
pnpm --filter @argus/dom2src-plugin test                      tests 7, pass 6, skipped 1, fail 0
pnpm --filter @argus/dom2src-plugin run test:attribute        2 passed (29.6s)
```

Open: GitHub has not run this. Not run locally: the `repro.yml` suites (not touched by this work).

## Fix 3. MCP ambiguity (T08, T06, T15, recommended fix 4)

- `server._result` has an `Ambiguous` branch: `structured_content` is `{error: "ambiguous", message, candidates: [{file, line, col, rank}]}` with `is_error` true, like the other typed failures.
- `schemas/locate.schema.json`: `candidates` on the `ambiguous` error (required for `ambiguous`, forbidden for the other codes, at least two items) and a new `Candidate` def. Examples updated.
- Unsupported selectors: `locate()` returns `UnsupportedSelector` (`unsupported-selector`, a fourth error code in the schema) instead of raising `ValueError`.
- Tests: `test_server.py` drives the stdio client for the verifier's case (`#save` on a wrapper button: two ranked candidates, validated against the schema) and for an unsupported selector; `test_locate.py` covers five unsupported selectors; `test_locate_schema.py` rejects an `ambiguous` error with no or one candidate.

Result: `uv run pytest packages/dom2src-mcp/tests -m "not live" -q` was `50 passed` after this fix (51 after fix 4).

Open: the explainer's `report.json` has `candidates[{file,line,col,why}]`; the code has `rank` and no `why`. Left as `rank`. Whether the error should carry `is_error` true for `ambiguous` is a design call I made to match the other typed errors.

## Fix 4. Stale-index protection (T17, recommended fix 5)

- `index.json` rebuilt with `python -m dom2src_mcp.repo_map` from the platform checkout at `ac86acc75`: 395 files, 5052 symbols, tsserver 5.8.3, now with `content_hashes` for all 395. The `files` section is unchanged (the diff is 397 added lines, none removed).
- `repo_map._file_hash` hashes with CRLF folded to LF. The platform checkout here is CRLF in the working tree and LF in git, so without this the committed hashes would never match on Linux.
- `test_repo_map.py::test_committed_index_is_checked_for_staleness` (not live): the committed index has a hash for every file, `query()` against an empty tree raises `StaleIndex` listing all of them, and one edited file is reported. `test_committed_index_matches_the_platform_checkout` (live) checks no file is stale against the checkout.

Result: `test_repo_map.py` `4 passed in 19.36s` with the platform path set; `2 passed, 2 deselected` without it.

Open: the committed `index.json` still contains the symbol index of private dcortex code. Not deleted, not gitignored (owner decision). It is regenerable with the documented command. `_stale_files` still leaves an index with no `content_hashes` unchecked; the committed one has them and the test pins that.

## Fix 5. Plugin on the real Canvas (T02, T03, Done-when 1, recommended fix 6)

It could run, so I did not reword T02/T03.

- `packages/dom2src-plugin/canvas/`: `setup.mjs` makes a detached `git worktree` of the platform checkout (default folder in the OS temp dir, `ARGUS_CANVAS_WORKTREE` overrides), links the checkout's installed `node_modules` into it, and writes `apps/canvas/vite.dom2src.config.ts` there, which adds `dom2srcPlugin()` before the Canvas's own plugins. `canvas.spec.ts` serves it with the platform repo's own Vite 6.4.3 and opens the routes in Chromium. There is no BFF: `/api` is answered by a synthetic admin session, one synthetic `desk-monitor` reply, and 403 for every other read. Synthetic cell only, no database, no env or credential file opened.
- Run with `ARGUS_PLATFORM_REPO=<checkout> pnpm --filter @argus/dom2src-plugin run test:canvas`.
- Assertions per route: the screen's own source file is among the stamped files; every stamped value matches `apps/canvas/src/...tsx:line:col`; **the source file at that line and column starts with `<tag`** for the stamped element's tag; every unstamped element is a router `<Link>`, an SVG node, or markup owned by the prebuilt `@dcortex/canvas-ui`.

Result, `test:canvas`, 12 passed (2.0m), platform `ac86acc75`:

| Route | Stamped / unstamped | Screen file stamped |
|---|---|---|
| `/login` (+ sign-in modal) | 34 / 0 | `Landing.tsx`, `AuthModal.tsx` |
| `/ops/login` | 16 / 0 | `OpsApp.tsx`, `Landing.tsx` |
| `/ops/radar` | 190 / 3 | `ops/Radar.tsx`, `RadarScope.tsx` |
| `/ops/operations` | 177 / 3 | `ops/Operations.tsx`, `Timeline.tsx` |
| `/ops/launchpad` | 16 / 3 | `ops/Launchpad.tsx` |
| `/ops/rules` | 17 / 3 | `ops/Rules.tsx` |
| `/desk?sel=console` | 425 / 122 | `screens/Desk.tsx` |
| `/desk?sel=timeline` | 426 / 102 | `desk/DeskTimelineBoard.tsx` |
| `/desk?sel=crew` | 426 / 102 | `desk/DeskCrewBoard.tsx` |
| `/desk?sel=brief` | 426 / 102 | `desk/DeskBriefBoard.tsx` |
| `/admin/users` | 558 / 62 | `screens/UserAdmin.tsx` |
| `/admin/audit` | 544 / 61 | `screens/AuditLog.tsx` |

Not proven, and now written down in ADR-006:
- Elements from the prebuilt workspace package `@dcortex/canvas-ui` (page shell, desk header) and SVG from `lucide-react` carry no `data-src`. `locate()` would say `no-source-info` for them. So "every JSX host element" in Done-when 1 holds for `apps/canvas/src`, not for that package. I did not reword Done-when 1; the ADR-006 follow-up states the limit.
- The desk console tab showed shell elements only; the synthetic reply has no rows. Tab content was stamped for timeline, crew and brief.
- Responses are synthetic, so data-dependent markup is unseen. Only the dev server was tried; no production build of the Canvas.
- The platform's own `apps/canvas/vite.config.ts` is unchanged. The plugin was added through a wrapper config in the throwaway worktree.
- The platform checkout is behind its `origin/dev` by 2659 commits (pre-existing); the index and this run use its local HEAD `ac86acc75`.

## Fix 6. Ablation honesty (T12, T13, H1, H2, recommended fix 7)

- New `packages/dom2src-mcp/src/dom2src_mcp/ablation.py`. Command: `uv run python -m dom2src_mcp.ablation --reindex --out-dir docs/notes/results`. It prints the run id, command, argus and platform SHAs, then the golden path and top-3 per task for each variant, the nearest-rank p50/p95 after one warm-up call, and the harness's top-1/top-3 line.
- Run `p2-abl-20261030T204633Z`, committed as `docs/notes/results/p2-abl-20261030T204633Z.txt` (argus `e827dca`, platform `ac86acc75`, 79 files re-indexed). A 0/30 top-1 and 0/30 top-3 (p50 0.003275s, p95 0.006280s); B 15/30 [0.331539, 0.668461] top-1 and 19/30 top-3 (p50 0.415103s, p95 0.717434s); C 0/30 and 0/30 (p50 0.000941s, p95 0.005071s).
- The accuracy cells reproduced the earlier, unrecorded run exactly. The earlier latency cells did not reproduce, so the table's latency cells (and the "This phase" row) now carry this run's values. Resolve rate, tokens, dollars and quota stay `—`.
- H1: done as above. H2: the "Previous phase 28/30" cell now says it is fixture replay. H3, H4: see fix 2. P0/P2 deploy-checkpoint wording about "on every push": see fix 7.
- ADR-007 and `phases/P02-dom2src.md` have a "Verifier finding" note. It says A and C could not score above 0 by construction (all 30 golden paths are CSS; repo-map has no CSS; `locate()` got no selector or DOM), that the three-way comparison was therefore not run, and that the default order conflicts with `hld-edges.json` edge 9 (locate first). The ADR-007 decision and default order are unchanged.
- Redo on JSX-origin tasks: **not done, left as a documented open item.** bugsmith's four JSX operators produce the bug patch cheaply, but each task also needs a ticket text and rendered HTML, which bugsmith does not produce.

## Fix 7. P0 Done-when #1 (recommended list, owner decision 4)

Amended minimally: `phases/P00-argus-bench.md` Done-when 1 and its deploy checkpoint, `PLAN.md` deploy table row P0 to P3, and `PROJECT.md` deploy row P0-P3 now say the golden-fix run is manual-dispatch (`golden.yml`) while dcortex-platform is private, and that push-time CI is the other workflows. The `P02` deploy checkpoint was reworded to match.

Left alone, because they are other people's or other phases' wording: the P0-T17 task text and acceptance ("golden-fix run on every push"), and the "keeps running the golden-fix run on every push" lines in the P01, P03 and P04 deploy checkpoints. They are now inconsistent with `golden.yml`. Say if you want them amended too.

## For the owner (not decided here)

- Who owns the 13 [ME] and 3 [PAIR] P2 tasks that an agent did (including ADR-006/007, the T06 schema, T08, T12, T13, T17). Tags and boxes untouched, apart from T14.
- Whether the committed `packages/dom2src-mcp/index.json` (private dcortex symbols, 395 files) stays in a repo meant to go public.
- The ADR-007 default order (pgvector first, per ADR-007; locate first, per `hld-edges.json`).
- Push and merge order of this branch, PR 1 and PR 2. This branch already contains the PR 2 merge.
- Task boxes: T02, T03, T08, T12, T13 and T17 are still ticked. After these fixes T08, T17, T02 and T03 are backed by tests; T12 and T13 rest on an ablation that did not compare the three variants (see fix 6).

## Not run

The `repro.yml` suites (argus-core, bench, repro-agent), a real GitHub Actions run, anything on Linux, and the `p0-bench` branch.
