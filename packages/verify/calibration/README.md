# Building the real calibration set

`fixtures/calibration/` holds 100 pairs of real Canvas screenshots. This folder is the tooling that built them. Nothing here writes to the dcortex platform checkout.

## What the shots are

Real dcortex Canvas UI (Vite dev server, platform HEAD `ac86acc75`), rendered in Chromium at 1280x800 with the clock frozen at 2026-10-01 12:00 UTC. There is no backend: `/api` answers come from a mock in `render.mjs` (a session, a handful of flights, tasks, airports). So the layout and CSS are the real ones, the data is made up. `shot_source` in each `meta.json` says `real-canvas-mocked-api`.

A pair is `before.png` (platform HEAD plus the task's `bug.patch`), `after.png` (the tree after a candidate fix), and the task's ticket text. All trees are the four CSS files the seeded tasks edit (`ops.css`, `radar.css`, `landing.css`, `tokens.css`).

`meta.json` `constructed_as` records how the after tree was built. It is not the label:

| constructed_as | After tree |
|---|---|
| correct | platform HEAD (the golden fix), or a P3/P4-T20 run's diff that scored resolved and still renders differently |
| wrong | the bug left in place; one bug hunk left unfixed; the bug plus an unrelated regression; or an unresolved P3/P4-T20 run's diff |
| collateral | platform HEAD plus one regression hunk taken from a different task's `bug.patch` |

## Why it is not 100 independent pairs

The seeded bugs are small CSS mutations, and many do not change a static screenshot at all. `screen.py` renders HEAD and every task's buggy tree on five screens and keeps a bug only if the changed-pixel ratio on some screen is at least 0.0003 (a 20 px to 8 px text is about 0.0004). Of the 29 usable seeded tasks (`bug-17` is out: its patches no longer apply to HEAD), 20 pass. The other 9 (`seed-e03`, `e06`, `e09`, `e10`, `h03`, `h09`, `h10`, `m03`, `m09`) cannot be judged from a screenshot and are not in the set. The 100 pairs are 20 tickets, each used 3 to 7 times on different screens and different after trees, so pairs of one ticket are correlated. The `correct` class is mostly the golden fix seen on different screens (38 of 40).

## Rebuild

1. Serve Canvas (needs the platform checkout's `node_modules`; nothing is installed or written there, the Vite cache goes to `RIG_CACHE`):
   `cd <platform>/apps/canvas && RIG_CACHE=<scratch>/vitecache node_modules/.bin/vite --config <this folder>/vite.rig.config.mjs`
2. Playwright and Chromium: set `PLAYWRIGHT_MODULE` (a `file:///` URL of `@playwright/test`) and edit `CHROME` in `common.py` to an installed Chromium.
3. `python screen.py <work>` then `python build_set.py candidates <work> <work>/screen/screening.json` then `python build_set.py select <work> <dest>`.

Rendering is deterministic for a given tree, so shots are reused between runs.

## Files

`render.mjs` renders views with CSS swapped in the browser. `diff.mjs` is the pixelmatch ratio. `common.py` is the shared helpers. `rescore_runs.py` rescores fix-loop runs from `diff.patch`. `t20_results.py` builds the P4-T20 pilot table.
