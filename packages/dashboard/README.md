# dashboard

Static dashboard for the eval results: the phase-over-phase table (same rules as `python -m eval report`) and one chart per metric (resolve rate with its Wilson interval, tokens per bug, latency, trajectory rates), each with a text table beside it. Vanilla JS and inline SVG, no framework, no CDN, no install.

```
python packages/dashboard/build.py                         # reads the two results files in the repo, writes packages/dashboard/data.js
python packages/dashboard/build.py a.json b.json [--out D] # your own results files, in order: previous, this
uv run pytest packages/dashboard -q                        # builder checks
```

Then open `packages/dashboard/index.html` in a browser. It works straight from disk (`file://`) because the data is a script file, not a `fetch`. `data.js` is committed so the page opens without building.

- Input: results JSON files that follow `packages/eval/schemas/results.schema.json` (`schema_version` 1). Default files: `packages/eval/fixtures/gate/baseline.json` (real: the P3 variant A run) and `worse.json` (**made up**, kept to exercise the delta; the page labels it "made up" everywhere it appears).
- The page shows "This phase" = the last real run and "Previous phase" = the real run before it. The two pickers change that; "none" prints the dash row, as the report does with no file.
- A missing value (`null`) is a dash, never zero. The baseline has no latency, no trajectory metrics and no `$_equivalent`, so those cells and charts show dashes until a run that has them is added.
- Made-up runs are drawn dashed and lighter, with "(made up)" in the name; a note says so.
- `screenshot-desktop.png`: the page opened from disk at 1280 px wide (Edge, dark scheme).

T22 publishes this folder to GitHub Pages from an Action; there is no workflow here yet.
