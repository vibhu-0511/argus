# Argus explainer: build contract (all fragment sessions read this)

Output: one self-contained `argus-explainer.html` at repo root, assembled by `node analysis/explainer-src/build.mjs` from `analysis/explainer-src/00-shell.html` + `10..50-*.html`. **Built from scratch**: no template, no framework, no CDN, no web fonts, no external requests. Hand-written CSS, JS and SVG. Works offline via file://.

Audience: the owner, a backend engineer learning the agentic layer at architect level, using this page to *understand, decide and finish tasks in parallel*. Every screen should answer "what do I do or learn next?", not just describe.

## Two tabs (shell owns them)
1. **Plan & tracker** (`data-pane="plan"`), sub-views: `problem`, `hld`, `console`, `edges`, `tracker`.
2. **Learning graph** (`data-pane="graph"`), one view.
Hash routing `#plan/problem`, `#plan/hld`, `#plan/console`, `#plan/edges`, `#plan/tracker`, `#graph`. Default `#plan/problem`. Tabs are real `role=tablist` buttons, arrow-key navigable.

## Fragment contract
Each fragment file is an HTML snippet (no `<html>/<head>/<body>`) containing:
- one or more `<section class="sub" id="sub-<name>" data-pane="plan|graph" hidden>` (the shell shows exactly one, by hash). Ids: `sub-problem` (10), `sub-hld` (20), `sub-console` (30), `sub-edges` and `sub-tracker` (40), `sub-graph` with `data-pane="graph"` (50).
- its own `<style>` block, **every selector prefixed with your fragment prefix** (`.pr-`, `.hl-`, `.cn-`, `.ed-`/`.tk-`, `.gr-`) so fragments never collide. Use only shell CSS variables for colour/space/type (below); no hard-coded colours except inside the console mock frames (see 30).
- its own `<script>` IIFE reading `window.ARGUS` (see Data) and rendering into its section on `DOMContentLoaded`. Lazy-render heavy views when the sub becomes visible: shell dispatches `document.dispatchEvent(new CustomEvent('argus:show',{detail:{pane,sub}}))`.
- No global names except `window.ARGUS` (read-only) and your own `window.__<prefix>` if needed. No `eval`, no inline `on*=` attributes (use addEventListener). Escape any data you inject (`textContent`, or a small `esc()`).
- `localStorage` only in try/catch, only for per-viewer conveniences (learned marks, filters); page must work without it.

## Shell CSS variables (defined by 00-shell, light + dark via `prefers-color-scheme` and `[data-theme]`)
`--bg --surface --surface-2 --ink --ink-2 --ink-3 --line --line-2 --accent --accent-ink --ok --warn --bad --info --focus` plus phase hues `--p0 … --p9` and `--p55`; spacing `--s1..--s6` (4,8,12,16,24,40 px); radii `--r1 --r2`; fonts `--serif --sans --mono` (system stacks only: `ui-serif, Georgia, 'Iowan Old Style', serif`; `system-ui, sans-serif`; `ui-monospace, 'SFMono-Regular', Consolas, monospace`). Helper classes from shell: `.card .chip .chip.ok/.warn/.bad/.info .kbd .tbl .muted .mono .grid .stack .row .sr-only .btn .btn.ghost .seg`(segmented control). Status is never colour alone: always text or icon too.

## Visual direction (distinct from the existing Argus pages, which are a light mono blueprint look and a dark amber/cyan look)
A **field-notebook / mission-control hybrid**: warm paper background (`#f4efe6`-ish) with ink-black text and one vermilion accent in light; deep ink-blue background with warm off-white text in dark. Serif display headings with tight tracking, sans body, mono for ids/numbers. Generous margins, thin rules, numbered section marks ("01 Problem"), margin notes. Cards have hairline borders, not shadows. Motion: short (120-200 ms) opacity/translate only; respect `prefers-reduced-motion`. No emoji-as-icons; small inline SVG icons only. 16 px side gutter on phones, no horizontal page scroll at 375 px (tables get their own scroll container). Min tap target 40 px.

## Honesty rules (repo rule: no invented numbers)
- Results cells are `—` unless a number is in `ARGUS` data with a source. Any illustrative mock value (console screens) carries a visible "illustrative" tag.
- Always show P0/P1 status as "checked done in TASKS.md" **plus** the evidence label from `ARGUS.evidence` (REAL / FIXTURE_ONLY / REFUTED...). Never present the P1 "28/30 valid" as a model result.
- Cite sources as short `file:line` chips that copy to clipboard on click.

## Data: `window.ARGUS` (built from analysis/swarm/*.json)
`problem, solution, components[39], failureDomains, trustZones, flows[5], boundaries[11], stores[13], idempotency[10], edgeCases[65]` (from `hld-edges.json`); `console {designTokens, patternSources, screens[4]}` (from `ops-console.json`); `tracker {phases[11], tasks[272], criticalPath, weekly, cuts, checks}` (from `tracker.json`); `graph {nodes[89], edges[146], groups[12]}` (from `concepts.json`); `evidence {claims, testRuns, fixBeforeP2, withItsPhase, deferred}` (from `evidence.json`). **Open the JSON files and read the real shapes before coding.** Do not copy data into your fragment; read `ARGUS`.

## Fragments and owners
| File | Section | Must contain |
|---|---|---|
| `00-shell.html` | tabs, nav, tokens, theme toggle, routing, print CSS | Full document with `<!--@DATA-->` in `<head>` (before fragments) and `<!--@FRAGMENTS-->` inside `<main>`; header with project title, "as of 2026-10-30", theme toggle; skip link; footer with how to regenerate (`node analysis/explainer-src/build.mjs`) |
| `10-problem-solution.html` | `sub-problem` | Problem (who hurts, cost), why naive fixing fails (P0 baseline 0/10 labelled with its real meaning), solution as 5 stages each with its invariant, constraints, **"Where the project really stands"** panel: P0/P1 done + evidence claims table with verdict chips + the fix-before-P2 list (from `ARGUS.evidence`) |
| `20-hld.html` | `sub-hld` | Hand-drawn SVG HLD (not the phase-coloured block diagram that `architecture.html` already has): lanes by trust zone, components as nodes (built vs planned styled differently), flows selectable (5 flows animate/highlight their path), click a node for responsibility, I/O, failure domain, idempotency key, sources. Toggle layers: trust boundaries, failure domains, state stores |
| `30-console.html` | `sub-console` | The 4 ops-console screens as interactive mockups inside device-like frames, using the extracted dcortex-style dark tokens from `ARGUS.console.designTokens` (the only place hard-coded dark console colours are allowed, via CSS variables defined in the fragment). Screen switcher; per screen a state switcher (normal / loading / empty / error / slow / quota-exhausted / stuck run as defined in the data), clickable rows that open detail, a "borrowed from" note naming the sibling project/file, and an "edge cases this screen must handle" list. Everything labelled illustrative |
| `40-edges-tracker.html` | `sub-edges`, `sub-tracker` | Edge explorer: filter by component, phase, severity, search; each case shows scenario / what goes wrong / handling / test idea / sources; severity matrix summary. Tracker: phase board with done/open hours, parallel **wave board** per phase (tasks grouped by wave, owner chip ME/CLAUDE/PAIR, hours, deps on hover, never-delegate marker), critical-path highlight, weekly burn vs 20 h/week, cut-list order, "what can I do in parallel next" panel (open tasks whose deps are all done, split ME-only vs delegable), progress totals that must equal `tracker.checks` (49 done / 223 open / 272). Include a "checked done but evidence says otherwise" strip for P0/P1 |
| `50-graph.html` | `sub-graph` | Learning graph: own layout (layered by prerequisite depth within group lanes, or hand-rolled force sim), pan/zoom, search, filter by group/phase/level/status, click node for summary / why it matters / repo path chip / source link / prerequisites and what it enables, highlight the prerequisite chain, "mark learned" with progress ring (localStorage, try/catch), a guided 8-step learning path (from `analysis/swarm/concepts.md`), keyboard accessible list view fallback. Built vs planned vs external nodes styled distinctly |

## Done when (per fragment)
Renders with real data, no console errors, works at 375 px and 1280 px, light and dark, keyboard reachable, nothing hard-coded that exists in `ARGUS`. Run `node analysis/explainer-src/build.mjs` and open `argus-explainer.html` to test with whatever fragments exist (the build tolerates missing fragments; a missing `00-shell.html` is the only fatal case, until the shell session writes it use a throwaway copy outside the repo dir).

## Ground rules
Write only your own file(s) in `analysis/explainer-src/`. Do not edit `build.mjs`, `DESIGN.md`, `analysis/swarm/*`, or any other repo file. Commit nothing, switch no branch. Do not rebuild `argus-explainer.html` more than needed: other sessions rebuild it too; treat it as disposable output. Final message: 4 lines max (what you built, how to test, known gaps).
