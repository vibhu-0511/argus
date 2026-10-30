# Addendum: final product UI + UI-by-phase (read `DESIGN.md` first; everything there still applies)

Goal: the explainer must let the owner *see* the finished Argus and *see how its UI grows* phase by phase.

## The target product flow (the owner's words, 2026-10-30)
The owner types an issue, with a screenshot or text only. An agent returns **an HTML report with before and after the fix, shown on the production UI**. The owner verifies it; once satisfied, the agent **raises the PR**. Today Argus does none of this end to end: only P0 (bench) and P1 (repro, fixture-replayed) exist. `PLAN.md` routes it differently (GitHub labelled issue -> durable workflow -> draft PR -> QA signal as MRTR or review comment, P6/P8). The product UI must show the owner's flow as the main path **and** mark where it differs from the plan (GitHub issue as an alternative trigger; PR opened as draft until approval) so the gap is visible, not hidden.

## Three new sub-views (hash routes; the shell nav already lists them)
| Route | Section id | Fragment | Owner lane |
|---|---|---|---|
| `#plan/product` | `sub-product` | `60-product.html` | final-product |
| `#plan/report` | `sub-report` | `62-report.html` | fix-report |
| `#plan/growth` | `sub-growth` | `70-ui-growth.html` | ui-growth |
Same fragment contract and CSS prefixes as `DESIGN.md`: `.pd-` (product), `.rp-` (report), `.ug-` (growth). Link between views with plain `href="#plan/report"` etc.; never call another fragment's code.

## Data (extra keys on `window.ARGUS`, written by the lanes into `analysis/swarm/`, merged by `build.mjs`)
`finalUi` <- `final-ui.json` (final-product lane), `report` <- `report.json` (fix-report lane), `phaseUi` <- `phase-ui.json` (ui-growth lane). Existing keys still available: `console` (design tokens, 4 screens), `tracker`, `components`, `flows`, `evidence`, `graph`. Fragments read `window.ARGUS`; a lane's JSON is the contract for its own fragment (other fragments may read it too, defensively: it may not exist yet).

## Honesty labels (mandatory on every screen / rung / artifact)
- `BUILT TODAY`: exists in the repo now; show the **real** artifact (real file contents, real CLI output, real ids) and cite the path.
- `PLANNED (Pn)`: a mock; carries the phase tag and an "illustrative data" tag. No invented results: metrics stay `-`/`—` unless backed by a file. Before/after pixels are illustrative unless a real artifact backs them (the only real screenshot in the repo is `packages/bench/tasks/seeded/bug-17/shots/radar-card.png`, the "before" of seeded bug-17; there is NO real "after" image).
- Where the owner's flow differs from `PLAN.md`, show a small "differs from plan" note citing `PLAN.md`/`phases/` lines.

## Visual language
Product UI in the explainer is shown inside device/browser **frames**, using the dcortex-style dark console tokens (`ARGUS.console.designTokens`, same approach as `30-console.html`; scope the variables to your frame). The surrounding explainer page keeps its field-notebook look. The fix report (`sub-report`) should look like a standalone artifact a reviewer would open: you may style it differently from the dark console (it is a generated, shareable HTML file), but keep it self-contained and print-friendly.

## Real artifacts you may use (read-only)
`packages/bench/tasks/seeded/bug-17/{ticket.json,bug.patch,golden.patch,checks.json,meta.json,shots/radar-card.png}`, `packages/repro-agent/runs/text-only/bug-17/{repro.spec.ts,trajectory.jsonl,verdict.json}`, `packages/repro-agent/runs/text-plus-image/bug-17/*`, `packages/*/README.md`, `docs/architecture/p1.md`, `142-fix.html` (hand-made sample fix report), `production.html`, `architecture.html`, `config/platform.md`, `analysis/swarm/ops-console.{md,json}`, sibling product code under `C:\Users\vibha\Downloads\data\dcortex\dcortex_claude\` (read-only; NEVER open env, key, credential or `.env` files). An image may be embedded as base64 only if it is under ~150 KB (radar-card.png is 103 KB: ok).

## Done when (per lane)
Your JSON parses; your fragment renders from real `ARGUS` data; `node analysis/explainer-src/build.mjs` succeeds; in a real browser (serve the repo root over http on a free port, e.g. `python -m http.server <port>`, and add `?v=N` to dodge the 1 h cache; stop your server when finished) your route works at 375 px and 1280 px, light and dark, with no console errors and no page-level horizontal scroll (`document.documentElement.scrollWidth === clientWidth`), keyboard operable, and every screen carries its honesty label. Write only your own files. Do not edit `00-shell.html`, `build.mjs`, `DESIGN*.md`, or other fragments. Commit nothing, no stash, no branch switch. Final message: 5 lines max (files, how to test, honest gaps).
