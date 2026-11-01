# verify

Deterministic checks, then a vision judge. The judge does not override a passed check run.

## Install

From the repo root, with Python 3.12:

```
uv sync
```

## Checks

```
uv run pytest packages/verify/tests -q
uv run --package verify python -m verify ci packages/verify/fixtures/ci/match
node --experimental-strip-types --test packages/verify/test/capture.test.ts
```

`python -m verify ci <dir>` reads `before.png`, `after.png`, and `verdict.json`. It exits 0 when the screenshots match and the verdict file parses with `"ok": true`. It exits non-zero when the changed-pixel ratio is over `CHANGED_PIXEL_RATIO` (0.02 changed pixels / unmasked pixels), or when the verdict file is missing or not JSON. It does not call a model.

The four checks are `pixel`, `overflow`, `axe`, and `console`, in that order (`ORDER` in `src/verify/pipeline.py`). A hard failure stops the run. The verdict names the check and the reason.

`src/capture.ts` waits on `document.fonts.ready` and `networkidle` before a screenshot.

## Judge

The rubric is `rubric.md`. The runner pastes it verbatim and puts the ticket in a separate data section.

```python
from verify.judge import GEMMA_MODEL, judge_pair, ollama_backend, rubric_text

result = judge_pair(ollama_backend(GEMMA_MODEL), ticket, before_png, after_png, rubric_text())
```

`result.label` is `pass`, `fail`, `collateral`, or `error`. A backend that raises returns `error` and does not accept the patch. `gemma4:e4b` is the cross-family model. `pixtral-12b-2409` is the same-family model (`mistral_backend`); there is no Mistral endpoint yet, so it was never called.

On the CPU of the dev machine (Ollama 0.40.13, `gemma4:e4b`, 8192 context, two 1280x800 PNGs per pair) a pair takes about 72 s once the model is loaded (the first call took 139 s with the load; three timing pairs are in `runs/judge-timing3.jsonl`). A full run is a resumable background job:

```
python -m verify.judge_run --pairs fixtures/calibration --out runs/judge-<run id>.jsonl --run-id <run id> --order both
python calibration/score_judge.py runs/judge-<run id>.jsonl
```

`judge_run` writes one line per pair and order, plus `<out>.progress.json`. `score_judge.py` refuses to print an alpha for a run that did not finish, and its numbers are always labelled "provisional, vs Claude draft labels" (see Calibration).

`best_of_k(k, draw=..., verify=..., judge=..., ledger=...)` returns the selected patch and every candidate. Token use per candidate is on the ledger. ADR-014 sets the policy: default k is 1 and the cap is 5. The function itself takes `k` as a required argument and does not enforce a cap; enforcing it is open.

`verify.png.decode_png` reads 8-bit RGB and RGBA PNGs with every scanline filter (the kind Chromium writes), about 1.7 s for a 1280x800 shot; it matches pngjs byte for byte on the real calibration shots (`tests/test_png.py`). The pixel check's fringe test looks only at each changed pixel's 3x3 neighbourhood (set lookup), so it is linear in the pixel count: 2.5 to 6 s on a real 1280x800 pair, where the all-pairs scan took hours. The rule is unchanged, and `tests/test_checks.py` checks the lookup against the old all-pairs rule on random inputs.

## Calibration

`fixtures/calibration/` has 100 pairs of real dcortex Canvas screenshots (1280x800, mocked API data, frozen clock): ticket, before, after, and a 40 correct, 30 wrong, 30 collateral mix. They come from 20 of the 29 usable seeded bench tickets (the other 9 bugs do not change a screenshot) and from the platform HEAD, the bug patches, and the P3 and P4-T20 run diffs. Pairs of one ticket are correlated: 20 tickets, 3 to 7 pairs each, and 38 of the 40 `correct` pairs are the golden fix seen on different screens. `calibration/README.md` says how they were built and how to rebuild them. `meta.json` `constructed_as` records the construction; it is not the label and must not be copied into `labels.json`.

`labels.json` holds the 100 labels the judge is scored against. They are **Claude's draft labels adopted by the owner**: the owner reviewed part of the set in `review.html`, found most drafts convincing, and told Claude to use the drafts for all 100 (2026-10-31). The drafts were made blind to `meta.json` and to any judge output. `labels.provenance.json` records `owner-accepted-draft` for every pair, and the owner's own individual choices were not saved, so no label here is an independently produced human label. Any alpha is therefore agreement with adopted Claude drafts, and must be described that way. `labels.claude-draft.json` keeps the drafts, with reasons and confidence. `calibration/merge_labels.py` can still merge an exported `labels.json` of the owner's own labels (it refuses to overwrite a labelled file). `meta.json` `constructed_as` records the construction; it is not the label. `review.html` is still there for relabelling.

The old 16x16 square set is kept as `fixtures/calibration-squares/`, for plumbing tests only.

Krippendorff's alpha is computed by `calibration/score_judge.py` against `labels.json` (adopted drafts). The judge is advisory (ADR-013).

## Phase report

P3 variant A (a Claude session as the model, 29 seeded tasks, no compaction) resolved 20 of 29. This phase ran best-of-k with k = 1, 3, 5 on the same 29 tasks with the same model (`claude-session`) and an oracle selector (the task's own scorer; the judge was not used). k = 1 is the P3 run by construction. k = 3 resolved 24 of 29 and k = 5 also 24 of 29, at about 2.0x and 3.0x the tokens. Details are in `phases/P04-verify.md` (rows C to E). $-equivalent stays "—" until P5.

| Report | Resolve rate | Tokens/bug | $-equivalent | p50 latency | p95 latency |
|---|---|---|---|---|---|
| Previous phase (P3 variant A) | 20/29, 0.690 (Wilson 0.508 to 0.827) | 202904 in, 205 out, 0 cached | — | — | — |
| This phase (best-of-5, oracle selector) | 24/29, 0.828 (Wilson 0.655 to 0.924) | 607582 in, 1016 out, 0 cached | — | — | — |
| Delta | +4 tasks (+0.138; intervals overlap) | +404678 in, +811 out | — | — | — |
