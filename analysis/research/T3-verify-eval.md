# T3 — verify, eval, flake, and red-team config

Planning notes only. No application code. Clones were at the SHAs below (`git rev-parse HEAD` matched each pin). Licences were read from each repo's `LICENSE` / `LICENSE.txt`. Hours delta for every item: **0**. Each change is acceptance text or an ADR sentence on a task that already exists. No new task, no new dependency, no cut-list swap. Verifier, judge rubric, Krippendorff implementation, eval scorer, threat model, and ADRs stay [ME]. Ideas only from these trees.

FastChat at `587d5cfa1609a43d192cedb8441cac3c17db105d` is stale. `git log -1` is 2025-06-02 (`Update constants.py #3733`). `fastchat/llm_judge/` is the 2023 MT-bench judge. Do not treat it as a current calibration library.

| Repo | SHA | Licence |
|---|---|---|
| SWE-bench/SWE-bench | `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e` | MIT |
| garris/BackstopJS | `a11d3657788bbffebd7a2b2eb5212006696afbff` | MIT |
| reg-viz/reg-suit | `5c09c8eb1e356d7e8145e5850e6de17b2b25a5a0` | MIT |
| argos-ci/argos | `500420acac590b5ec0d628236e5d8c456f048ec5` | MIT |
| promptfoo/promptfoo | `e48ed85e08ff8a1ca74fa7d0e41daf47cf155efb` | MIT |
| lm-sys/FastChat | `587d5cfa1609a43d192cedb8441cac3c17db105d` | Apache-2.0 |
| dmtrKovalenko/odiff | `6dd1e9629810042c03a81fc787f37b245772970a` | MIT |

## Entries

### T3-01 A missing suite is an error
- Topic: mutation validity. An empty or unparsed check log must not count as a pass.
- Their approach: SWE-bench grades some UI repos `fail_only`, and under that mode a test absent from the status map is a success. An empty map with no sign the suite ran used to mark every fail-to-pass test resolved. The harness now rejects that log. `compute_fail_to_pass` still returns 1 when the fail-to-pass list is empty. [CODE] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L25-L30 https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L155-L160 https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L221-L228 https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L288-L295 https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/constants/__init__.py#L72-L81

```python
# EvalType.FAIL_ONLY an empty status map scores every F2P test as passing, so a zero
# count read as evidence turns a suite that never ran into a resolved instance.
...
if not status_map and not SUITE_RAN.search(content):
    # No parsed results *and* no sign the suite ran: the run is invalid, not
    # a pass.
...
if total == 0:
    return 1
```

- Argus plan: `phases/P00-argus-bench.md` P0-T15 says exit 0 pass, 1 fail, 2 infra. P0-T24 says the scorer "fails on the mutant and passes on the original." Neither sentence says a task with zero checks, or a log with no parsed result, is exit 2. Add to P0-T15 and P0-T24: zero checks and an unparsed log are exit 2 on both the mutant and the original, and the validity filter drops them. A kept mutant is exit 1 on the mutant and exit 0 on the original, with a non-empty check list.
- Evidence: [CODE]
- Licence: MIT
- Affected: P0-T15, P0-T24, ADR-003

### T3-02 Infra failure is not a valid mutant
- Topic: validity filter. Exit 2 on the buggy tree is a dropped mutant, not a fail-before.
- Their approach: if the log has no parseable tests, `resolved` stays false. Environment failures are labelled and stay advisory. A browser that fails to launch is the case called out in the suite-ran guard. [CODE] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L349-L375 https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/infra_failure.py#L1-L13 https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/infra_failure.py#L28-L37

```python
# Advisory only -- `resolved` stays False either way (#586).
...
1. Classification is post-hoc and read-only.
2. It is advisory. A flagged instance stays in `unresolved_ids` / `error_ids`
   exactly as before, so the scoring denominator is unchanged.
```

- Argus plan: P0-T24 keeps a mutant when the scorer "fails on the mutant." Exit 2 is also a non-zero exit. Add: the filter accepts only exit 1 on the mutant and exit 0 on the original. Exit 2 on either side is a reject reason of its own (`infra`), distinct from "no observable change" and from "breaks the build." P0-T18 quarantines a task if any of the five runs is exit 2, including when all five agree on exit 2.
- Evidence: [CODE]
- Licence: MIT
- Affected: P0-T18, P0-T24, ADR-003

### T3-03 Infra and quarantine leave the denominator
- Topic: resolve rate. One bad environment run must not move the Wilson interval.
- Their approach: SWE-bench keeps the flagged instance in `unresolved_ids`, so the denominator does not change (same `infra_failure.py` lines as T3-02). Full resolution also requires pass-to-pass maintenance, not only fail-to-pass. [CODE] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L309-L326
- Argus plan: `PLAN.md` Metrics contract: "Reported as resolved over attempted, with a Wilson 95% interval." "Attempted" is not specified for exit 2 or `bench/quarantine/`. P0's interview question asks what one flaky check does to that interval. ADR-003's acceptance says the ADR states the flake threshold and what happens to quarantined tasks, and it does not say they leave the denominator. Add to ADR-003 and to the metrics sentence that P5-T04 implements: exit 2 and quarantined tasks are excluded from "attempted", counted in a separate exclusion total, and omitted from the ablation sample in P0-T29. The CI gate in P5-T16 compares rates on that same denominator.
- Evidence: [CODE] for the harness. [DOCS] `PLAN.md` Metrics contract, `phases/P00-argus-bench.md` interview question 1 and P0-T29.
- Licence: MIT
- Affected: P0-T27, P0-T29, P5-T04, P5-T16, ADR-003, ADR-017

### T3-04 Multimodal adapter uses the dev split and the current id
- Topic: P5 subset. The test split withholds the gold patch and the images. The quickstart still names the old Hub org.
- Their approach: the CLI alias `multimodal` resolves to `SWE-bench/SWE-bench_Multimodal`. The dataset guide says the test split leaves `patch`, `test_patch`, and `image_assets` empty, and that `image_assets` are URL lists. The quickstart still loads `princeton-nlp/SWE-bench_Multimodal`. [CODE] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/cli/_datasets.py#L5-L20 [DOCS] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/docs/guides/datasets.md#L72-L85 https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/docs/guides/quickstart.md#L30-L31 https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/docs/reference/cli.md#L7-L14

```python
"image_assets": {
    "problem_statement": ["url1", "url2", ...],
    "patch": ["url1", "url2", ...],
    "test_patch": ["url1", "url2", ...]
}
# test split: patch, test_patch, and image_assets are empty
```

- Argus plan: P5-T19 says "adapter converts each task or records an exclusion reason; at least 10 tasks load." The dataset id and split are not specified. Pin `SWE-bench/SWE-bench_Multimodal` split `dev` (the alias in `_datasets.py` and `docs/guides/datasets.md`). Record an exclusion for every `test`-split row and for any dev row whose `image_assets` URLs are missing. The gold `patch` is scoring-only and is not copied into the agent prompt. `PLAN.md` already says a resolved task has "no bench check file was touched"; the adapter sentence should say the same about the gold patch.
- Evidence: [CODE] and [DOCS]
- Licence: MIT
- Affected: P5-T19, P5-T20

### T3-05 Regrade from the saved log
- Topic: a scorer or parser fix should not require a new Playwright run.
- Their approach: `swebench report` recomputes verdicts from saved logs and does not start containers. Re-running a run id skips instances that already have `report.json`. [DOCS] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/docs/reference/cli.md#L53-L64 [CODE] log names in https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/constants/__init__.py#L36-L41

```text
Recompute verdicts from a finished run's saved logs, without starting containers.
Useful after a log-parser fix, since the test output is already on disk.
Re-running a run id skips instances that already have a report.json.
```

- Argus plan: P0-T15 emits a JSON verdict. It does not say the raw check log is kept beside it. Add: `bench score` writes the verdict and the unsliced check log; a later scorer change can rebuild the verdict from that log with no browser. P5-T04's results JSON points at those logs. P4-T23's fixture job uses the stored screenshots and the stored logs.
- Evidence: [DOCS] and [CODE]
- Licence: MIT
- Affected: P0-T15, P5-T04, P4-T23

### T3-06 Hide a dynamic region without reflow
- Topic: pixel-diff masks for clocks, ads, and animation.
- Their approach: `hideSelectors` sets `visibility: hidden` and keeps layout. `removeSelectors` sets `display: none`, which collapses the box. The README reserves hide for a fixed-size dynamic block and remove for a block whose size is unpredictable. The default mismatch allowance is `0.1` (percent of pixels, see T3-08). [CODE] https://github.com/garris/BackstopJS/blob/a11d3657788bbffebd7a2b2eb5212006696afbff/core/util/runPlaywright.js#L269-L284 https://github.com/garris/BackstopJS/blob/a11d3657788bbffebd7a2b2eb5212006696afbff/core/util/engineTools.js#L8-L9 [DOCS] https://github.com/garris/BackstopJS/blob/a11d3657788bbffebd7a2b2eb5212006696afbff/README.md#L181-L182 https://github.com/garris/BackstopJS/blob/a11d3657788bbffebd7a2b2eb5212006696afbff/README.md#L462-L474

```javascript
document.querySelectorAll(sel).forEach(s => {
  s.style.visibility = 'hidden';
});
```

- Argus plan: P4-T02 says "region masks" and does not say whether the mask keeps layout. P0-T09 already turns animations off. Add to P4-T02: a mask for a fixed-size dynamic region uses visibility hiding or an equivalent pixel rectangle (`odiff` `ignoreRegions`, T3-10). It does not use `display: none`. The mask list is written on the task. Do not take Backstop as a dependency.
- Evidence: [CODE] and [DOCS]
- Licence: MIT
- Affected: P4-T02, ADR-012

### T3-07 The mask acceptance test is backwards
- Topic: P4-T02's one-sentence pass/fail.
- Their approach: hidden selectors are how Backstop stops a dynamic region from failing the diff (README section quoted in T3-06). A shift that exists only inside that region is a pass.
- Argus plan: P4-T02 acceptance: "Passes on a clean tree, fails on a tree with a 4 px shift in a masked-out-of-scope area; threshold is a named constant." That sentence requires a failure for a shift inside the masked area. Split it: the check passes when the only difference is inside the mask; it fails when a 4 px shift is outside the mask. The outside shift must move more pixels than the ignore cap in T3-09.
- Evidence: [DOCS] Backstop README#L462-L470. The Argus sentence is the plan quote above.
- Licence: MIT
- Affected: P4-T02

### T3-08 Name the threshold unit, and fail on a size change
- Topic: a single unnamed constant mixes three units. Padding a smaller image up to a larger one hides a clip.
- Their approach: Backstop compares `misMatchPercentage` to `misMatchThreshold` and documents that number as a percentage; the code default is `0.1`. reg-suit's `thresholdRate` is a ratio from 0 to 1 (default 0) and `thresholdPixel` is an absolute count. `matchingThreshold` is a separate YUV color distance. Argos resizes both images to the max dimensions, then diffs. odiff's `--threshold` is a color distance from 0 to 1, default 0.1, and `--fail-on-layout` is a different exit (21) from a pixel diff (22). [CODE] https://github.com/garris/BackstopJS/blob/a11d3657788bbffebd7a2b2eb5212006696afbff/core/util/compare/compare-resemble.js#L13-L18 https://github.com/reg-viz/reg-suit/blob/5c09c8eb1e356d7e8145e5850e6de17b2b25a5a0/packages/reg-suit-core/src/config-manager.ts#L75-L78 https://github.com/argos-ci/argos/blob/500420acac590b5ec0d628236e5d8c456f048ec5/apps/backend/src/screenshot-diff/diff/image/index.ts#L188-L190 https://github.com/dmtrKovalenko/odiff/blob/6dd1e9629810042c03a81fc787f37b245772970a/src/cli.zig#L50-L68 [DOCS] https://github.com/reg-viz/reg-suit/blob/5c09c8eb1e356d7e8145e5850e6de17b2b25a5a0/README.md#L119-L138 https://github.com/dmtrKovalenko/odiff/blob/6dd1e9629810042c03a81fc787f37b245772970a/README.md#L171-L174

```text
Backstop default misMatchThreshold: 0.1   // percentage points in the README
reg-suit thresholdRate default: 0          // ratio 0..1
odiff --threshold default: 0.1             // color distance 0..1
odiff exit 21 layout, exit 22 pixel diff
```

- Argus plan: P4-T02 says "threshold is a named constant" and does not name the unit. Add: the constant is a ratio of changed pixels, written next to its unit. A color-distance knob, if kept, is a second named constant. Different image width or height is a failure and is not repaired by scaling or padding. Do not add Backstop, reg-suit, Argos, or odiff as a dependency.
- Evidence: [CODE] and [DOCS]
- Licence: MIT for all four
- Affected: P4-T02, ADR-012

### T3-09 A small ignore cap must still fail the 4 px case
- Topic: anti-alias tolerance versus a real shift. Argos runs two odiff passes and then zeros a score under a pixel cap.
- Their approach: one pass uses a higher color threshold "to avoid antialiasing" and ignores up to 2 pixels on a 100×100 image, capped at 20 pixels. A second pass uses a low color threshold and a 3% score cap. odiff is called with `antialiasing: true` and `outputDiffMask: true`. User threshold 0.5 scales those internals by 2×. [CODE] https://github.com/argos-ci/argos/blob/500420acac590b5ec0d628236e5d8c456f048ec5/apps/backend/src/screenshot-diff/diff/image/index.ts#L17-L51 https://github.com/argos-ci/argos/blob/500420acac590b5ec0d628236e5d8c456f048ec5/apps/backend/src/screenshot-diff/diff/image/index.ts#L74-L78 https://github.com/argos-ci/argos/blob/500420acac590b5ec0d628236e5d8c456f048ec5/apps/backend/src/screenshot-diff/diff/types.ts#L11-L17

```text
// On 100x100 images we want to ignore 2 pixels
const BASE_MAX_SCORE = 0.0002;
const MAXIMUM_PIXELS_TO_IGNORE = 20;
const COLOR_SENSIBLE_MAX_SCORE = 0.03; // 3% of image is different
compare(..., { outputDiffMask: true, threshold, antialiasing: true })
```

- Argus plan: one named ratio cannot both ignore font fringe and fail a 4 px shift. Add to P4-T02: at most two named caps (anti-alias fringe, and a color-shift ratio). The 4 px acceptance shift must change more pixels than the fringe cap, so a cap of 20 pixels does not swallow it. Copying Argos's 0.5 default, or odiff's 0.1 color default, is not the constant.
- Evidence: [CODE]
- Licence: MIT (Argos and odiff)
- Affected: P4-T02, P4-T26, ADR-012

### T3-10 Font wait stays; anti-alias is a second fixture
- Topic: P4-T26. Ignoring anti-aliased edge pixels does not cover a screenshot taken before the web font loads.
- Their approach: odiff `--antialiasing` defaults off. Detection marks a pixel only when it has both a darker and a brighter neighbor and those extremes have 3+ identical siblings in both images. A solid region of identical pixels returns false. `ignoreRegions` is an explicit rectangle list. [CODE] https://github.com/dmtrKovalenko/odiff/blob/6dd1e9629810042c03a81fc787f37b245772970a/src/cli.zig#L17-L18 https://github.com/dmtrKovalenko/odiff/blob/6dd1e9629810042c03a81fc787f37b245772970a/src/cli.zig#L56-L62 https://github.com/dmtrKovalenko/odiff/blob/6dd1e9629810042c03a81fc787f37b245772970a/src/antialiasing.zig#L80-L96 [DOCS] https://github.com/dmtrKovalenko/odiff/blob/6dd1e9629810042c03a81fc787f37b245772970a/README.md#L173-L190

```text
--aa, --antialiasing    Ignore antialiased pixels in diff
-i, --ignore            Ignore regions (x1:y1-x2:y2,...)
if zeroes >= 3 or min_sibling_delta == 0 or max_sibling_delta == 0:
    return false   // not anti-aliased
```

- Argus plan: P4-T26's fix is "wait for fonts and network idle, and keep fonts pinned in the test build." P0-T09 already requires two screenshots of each route to be byte-identical. Keep that wait. Add a second fixture: after fonts are ready, an anti-aliased fringe under the named cap passes, and a different font family still fails. Do not raise the pixel ratio until a font swap passes.
- Evidence: [CODE] and [DOCS]
- Licence: MIT
- Affected: P4-T26, P4-T02, P0-T09

### T3-11 Masks are declared, not learned
- Topic: repeated identical diffs must stay failures.
- Their approach: Argos ignore defaults on. Auto-ignore stores a fingerprint after `DEFAULT_AUTO_IGNORE_CHANGES` of 3 occurrences on reference builds, then sets `ignored` on the diff. [CODE] https://github.com/argos-ci/argos/blob/500420acac590b5ec0d628236e5d8c456f048ec5/apps/backend/src/database/models/Project.ts#L40-L54 https://github.com/argos-ci/argos/blob/500420acac590b5ec0d628236e5d8c456f048ec5/apps/backend/src/database/models/Project.ts#L75-L89 https://github.com/argos-ci/argos/blob/500420acac590b5ec0d628236e5d8c456f048ec5/apps/backend/src/screenshot-diff/computeScreenshotDiff.ts#L108-L122

```typescript
export const DEFAULT_AUTO_IGNORE_CHANGES = 3;
// autoIgnore absent means auto-ignore is enabled with the default threshold.
```

- Argus plan: ADR-012 says the ADR states order, why, and when a soft failure may continue. It does not mention learned ignores. Add: a mask is an explicit list on the task (T3-06). A fingerprint that repeats is still a hard failure. Auto-ignore after N identical diffs is out of the verifier.
- Evidence: [CODE]
- Licence: MIT
- Affected: ADR-012, P4-T02, P4-T07

### T3-12 A pixel miss and a bad results file fail the process
- Topic: CI gates that log a difference and still exit 0.
- Their approach: reg-suit `compare` logs `failedItems` and returns. The CLI then `process.exit(0)` whenever the promise resolves. Default `thresholdRate` is 0, so any changed pixel is a failed item, and the process can still exit 0. Backstop's report command throws `Mismatch errors found.` when `failed` is non-zero, which fails the process. [CODE] https://github.com/reg-viz/reg-suit/blob/5c09c8eb1e356d7e8145e5850e6de17b2b25a5a0/packages/reg-suit-cli/src/commands/compare.ts#L4-L8 https://github.com/reg-viz/reg-suit/blob/5c09c8eb1e356d7e8145e5850e6de17b2b25a5a0/packages/reg-suit-cli/src/cli.ts#L109-L114 https://github.com/reg-viz/reg-suit/blob/5c09c8eb1e356d7e8145e5850e6de17b2b25a5a0/packages/reg-suit-core/src/processor.ts#L132-L138 https://github.com/garris/BackstopJS/blob/a11d3657788bbffebd7a2b2eb5212006696afbff/core/command/report.js#L269-L285

```javascript
// reg-suit cli.ts
.then(() => process.exit(0))
// Backstop report.js
if (failed) {
  logger.error('*** Mismatch errors found ***');
  throw new Error('Mismatch errors found.');
}
```

- Argus plan: P5-T16 already exits non-zero when resolve rate is below the baseline lower bound. P5-T17 has a red path for a worse results file. P4-T23 says the verify workflow is green on stored screenshots and does not say a mismatched fixture fails the job. Add to P4-T23 the same red path as P5-T17: a committed pair over the named ratio, or a missing/unparsable results or verdict file, exits non-zero. A missing log stays unresolved in the sense of T3-01; it does not become a green skip.
- Evidence: [CODE]
- Licence: MIT
- Affected: P4-T23, P5-T16, P5-T17, ADR-017

### T3-13 Order disagreement is its own rate
- Topic: position bias. Asking the judge to be fair, then averaging the two orders, hides the flip.
- Their approach: the pairwise prompt says to avoid position bias and length bias. The runner still calls the judge twice with the answers swapped (`g1` then `g2`). If the two winners differ, `show_result.py` records a tie, and `load_pairwise_model_judgments` stores `"inconsistent"`. Agreement math also rewrites the vote so the model-id sort is canonical, which erases presentation order. The repo is stale (header). [CODE] https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/common.py#L325-L336 https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/common.py#L564-L569 https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/show_result.py#L64-L66 https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/compute_agreement.py#L38-L43 https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/data/judge_prompts.jsonl#L1

```python
g1_winner, ... = run_judge_pair(question, answer_1, answer_2, ...)
g2_winner, ... = run_judge_pair(question, answer_2, answer_1, ...)
...
if g1_winner == g2_winner:
    winner = g1_winner
else:
    winner = "inconsistent"
```

The prompt line at `judge_prompts.jsonl` L1 includes: "Avoid any position biases and ensure that the order in which the responses were presented does not influence your decision. Do not allow the length of the responses to influence your evaluation."
- Argus plan: P4-T24 expects the label to flip or drift, and the write-up's fix is "randomise and average over both orders, or fix the order in the rubric and lengthen no inputs." Add: the flip rate (orders disagree) is reported next to α on the held-out split in P4-T14 and in ADR-013. A disagreeing pair is not averaged into one label before α, and before/after images are not sorted into a canonical order. The rubric text stays [ME]. Do not import FastChat's judge.
- Evidence: [CODE]
- Licence: Apache-2.0. Ideas only unless a short attributed snippet is copied. Prefer no copy; the behaviour is the lesson.
- Affected: P4-T14, P4-T24, ADR-013

### T3-14 Percent agreement is not α, and error rows stay in the set
- Topic: judge calibration. FastChat's published "over 80% agreement" is pairwise percent agreement, with ties dropped in a second printout, and with `error` winners removed before the win rate.
- Their approach: `compute_agreement.py` prints `agree/total` with ties banned and with ties kept, for two turns. It only implements gpt4-pair vs human and human vs human. `show_result.py` drops rows where either winner is `error`. An unparsed verdict is the string `error` (`common.py` sets `winner = "error"` when the `[[A]]` / `[[B]]` / `[[C]]` markers are missing). README states the 80% figure. [CODE] https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/compute_agreement.py#L111-L124 https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/show_result.py#L49-L49 https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/common.py#L282-L290 [DOCS] https://github.com/lm-sys/FastChat/blob/587d5cfa1609a43d192cedb8441cac3c17db105d/fastchat/llm_judge/README.md#L153-L156

```text
turn 1 with tie.    #total, #agree, ratio
turn 1 without tie. #total, #agree, ratio
humans and GPT-4 judge achieve over 80% agreement
df_all = df_all[(g1_winner != "error") & (g2_winner != "error")]
```

- Argus plan: P4 done-when requires Krippendorff α ≥ 0.80 with a bootstrap interval. P4-T01's notes should say the FastChat 80% figure is percent agreement on a stale pairwise bench, so it is not a preview of α. P4-T12 stays the [ME] implementation, tested on a published worked example. Add to P4-T11 and P4-T13: an unparsed judge string is `error`, it is not mapped to pass, and it stays in the α denominator (disagreement) or is reported as its own count. Dropping errors before α is the FastChat win-rate path. P4-T28 already covers a dead backend as `error`.
- Evidence: [CODE] and [DOCS]
- Licence: Apache-2.0
- Affected: P4-T01, P4-T11, P4-T12, P4-T13, P4-T28, ADR-013

### T3-15 Static injection cases, three variables, deterministic grade
- Topic: P7 promptfoo config shape. The tool's red-team generator and its LLM grader stay out of the threat model and the judge rubric.
- Their approach: `redteam.plugins` generate attacks. Default `provider` in the docs table is `openai:gpt-5`, default `numTests` is 5, and default strategies include jailbreak variants. The strategy id `prompt-injection` is a deprecated alias of `jailbreak-templates`: 67 static 2022–2023 jailbreak templates, and the code warns that it does not cover modern prompt injection. Indirect injection is a plugin: `indirectInjectionVar` names the untrusted template variable (the docs list support tickets). Its grader is an LLM rubric that returns 0 if the model followed the injection. Generation records token use under `metadata.generation`. [DOCS] https://github.com/promptfoo/promptfoo/blob/e48ed85e08ff8a1ca74fa7d0e41daf47cf155efb/site/docs/red-team/configuration.md#L69-L108 https://github.com/promptfoo/promptfoo/blob/e48ed85e08ff8a1ca74fa7d0e41daf47cf155efb/site/docs/red-team/plugins/indirect-prompt-injection.md#L43-L64 https://github.com/promptfoo/promptfoo/blob/e48ed85e08ff8a1ca74fa7d0e41daf47cf155efb/site/docs/red-team/strategies/jailbreak-templates.md#L7-L13 [CODE] https://github.com/promptfoo/promptfoo/blob/e48ed85e08ff8a1ca74fa7d0e41daf47cf155efb/src/redteam/strategies/index.ts#L330-L337 https://github.com/promptfoo/promptfoo/blob/e48ed85e08ff8a1ca74fa7d0e41daf47cf155efb/src/redteam/plugins/indirectPromptInjection.ts#L7-L24

```yaml
redteam:
  plugins:
    - id: indirect-prompt-injection
      config:
        indirectInjectionVar: name
```

```text
Strategy "prompt-injection" is deprecated. Use "jailbreak-templates" instead.
This strategy applies static jailbreak templates and does not cover modern prompt injection.
```

- Argus plan: P7-T07 says a dry run uses stub tools and no real model calls, with cases listed per attack vector (ticket, repo file, skill). That rules out `promptfoo redteam generate` and the default generation provider. Add: the committed config is three static cases (or one file with three vars), one variable each for ticket text, a repo file, and a skill file. Assertions are deterministic (forbidden tool name, forbidden secret substring, exit status). The grade is not `IndirectPromptInjectionGrader` and not `llm-rubric`. The threat model and the judge rubric stay [ME]. P7-T08 may call a model for the live run; those tokens go through the quota ledger. Do not enable `prompt-injection` / `jailbreak-templates` as the injection suite.
- Evidence: [DOCS] and [CODE]
- Licence: MIT
- Affected: P7-T07, P7-T08, ADR-024

### T3-16 Draw the ablation sample after quarantine
- Topic: flake policy meets the seeded-vs-mutated table.
- Their approach: SWE-bench's resolution status is full only when fail-to-pass is 1 and pass-to-pass is 1 (T3-03). A skipped fail-to-pass test is a failure; a skipped pass-to-pass test is not a regression (`test_failed` vs `test_maintained` in `grading.py` L93-L109). Argus checks are not pytest skips. The transferable rule is the one already in T3-01 and T3-02: absence and infra are not a pass, and a maintained check that still passes is required for a keep. [CODE] https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/grading.py#L93-L109
- Argus plan: P0-T18 moves mixed tasks to `bench/quarantine/`. P0-T29 samples 30 mutated tasks from the 300+. It does not say the sample is taken after quarantine. ADR-003 does not say a quarantined id is absent from the task-set hash. Add: quarantine runs before the hash and before the ablation draw; the hash is of the kept set; the report states the excluded count. A kept mutant still fails its own checks and passes the checks that the original passed (the pass-to-pass analogue), which is the P4-T25 collateral case at bench time.
- Evidence: [CODE]
- Licence: MIT
- Affected: P0-T18, P0-T26, P0-T27, P0-T29, ADR-003

## Lessons from their issue tracker

Counts are from the GitHub API on 2026-10-28. Comment rank is GraphQL `issues` / `pullRequests` with `orderBy: {field: COMMENTS, direction: DESC}` and states open, closed, and merged. Reaction rank is `search/issues?q=repo:OWNER/REPO&sort=reactions&order=desc`. No counts below were estimated. "Guards" means a plan sentence already covers the failure mode.

1. [SWE-bench #465](https://github.com/SWE-bench/SWE-bench/issues/465) (closed, 20 comments, 217 reactions; top of both ranks) — agents can read future repo state, including the solution, during evaluation. Partial: `PLAN.md` Metrics contract says a resolve requires that no bench check file was touched. The multimodal gold `patch` staying out of the prompt is not specified (T3-04).
2. [SWE-bench #402](https://github.com/SWE-bench/SWE-bench/pull/402) (merged, 6 comments; top PR by comments) — test-output parsing was slicing the log and breaking the verdict. Not specified beyond a JSON verdict (P0-T15). T3-05 asks for the unsliced log.
3. [BackstopJS #1300](https://github.com/garris/BackstopJS/issues/1300) (closed, 62 comments; top issue by comments) — Docker arm64 for Apple Silicon. Not specified. Argus CI is GitHub Actions golden-fix, not Backstop's Docker image.
4. [BackstopJS #137](https://github.com/garris/BackstopJS/pull/137) (closed, 36 comments; top PR by comments) — custom screenshot filenames. Not specified. No plan change.
5. [BackstopJS #761](https://github.com/garris/BackstopJS/issues/761) (open, 24 reactions; top by reactions) — retry a run after a critical error to look more stable. Partial: P4-T28 retries a dead judge once and fails closed. Pixel flake is quarantine (P0-T18), not a retry. A retry of a mismatch would hide T3-02.
6. [reg-suit #1](https://github.com/reg-viz/reg-suit/issues/1) (closed, 76 comments; top issue by comments) — plugin architecture. Not specified. Do not adopt a plugin host for the gate.
7. [reg-suit #108](https://github.com/reg-viz/reg-suit/pull/108) (merged, 7 comments; top PR by comments) — take AWS credentials from the EC2 metadata service. The metadata-address escape probe is P7-T12. The plan does not use reg-suit or its S3 publisher.
8. [reg-suit #203](https://github.com/reg-viz/reg-suit/issues/203) (open, 11 reactions; top by reactions) — approve or reject snapshot changes from the report and update a GitHub check. Not specified. P4's gate is the deterministic verdict, not a human click that accepts a diff.
9. [Argos #429](https://github.com/argos-ci/argos/issues/429) (closed, 21 comments; top issue by comments) — `argos-ci upload` dies with socket hang up. Not specified. P4-T23 uses stored screenshots in the repo and does not upload to Argos.
10. [Argos #1319](https://github.com/argos-ci/argos/pull/1319) (merged, 17 comments; top PR by comments) — comment id widened to a bigint. Not specified. Product UI, outside the diff path.
11. [Argos #1152](https://github.com/argos-ci/argos/issues/1152) (closed, 10 reactions; top by reactions) — several screenshots can all be valid, to quiet flake. Not specified as a feature. P0-T09 requires two shots of a route to be byte-identical, which is the opposite policy (T3-11).
12. [promptfoo #8964](https://github.com/promptfoo/promptfoo/pull/8964) (open, 127 comments; top PR by comments, and the highest comment count in this track) — adaptive coding-agent red-team plugins, MCP trace evidence, local verifier receipts. Not specified. T3-15 keeps P7 on static cases. Threat model and rubric stay [ME].
13. [promptfoo #1876](https://github.com/promptfoo/promptfoo/issues/1876) and [promptfoo #657](https://github.com/promptfoo/promptfoo/issues/657) (both closed, 19 comments; tied at the top of the issue comment rank, GraphQL returned #1876 then #657) — Gemini 1.5 Flash provider failure, and a request for bias and fairness detection. Judge family bias is P4-T17 and ADR-013, which stay [ME]. A promptfoo bias plugin is not specified.
14. [promptfoo #1395](https://github.com/promptfoo/promptfoo/issues/1395) (open, 11 reactions; top by reactions) — compare this run with a previous run across several configs. Guarded: P5-T05 phase-over-phase report and P5-T16 gate against a stored baseline.
15. [FastChat #170](https://github.com/lm-sys/FastChat/issues/170) (closed, 38 comments; top issue by comments) — a 30B model. Not specified. Stale repo; the judge in the plan is local Gemma, P4-T11.
16. [FastChat #2622](https://github.com/lm-sys/FastChat/pull/2622) (merged, 27 comments; top PR by comments) — ChatGLM3 conversation template. Not specified. Outside `llm_judge/`.
17. [FastChat #90](https://github.com/lm-sys/FastChat/issues/90) (closed, 36 reactions; top by reactions) — release the ShareGPT dataset. Not specified. Calibration data is the 100 pairs in P4-T10, labelled by hand.
18. [odiff #112](https://github.com/dmtrKovalenko/odiff/pull/112) (merged, 19 comments; top PR by comments) — comparison can skip writing a diff image. Partial: P4-T06 requires a structured verdict, so a missing diff file can still be a fail. The plan does not require a diff-image artifact.
19. [odiff #53](https://github.com/dmtrKovalenko/odiff/issues/53) (closed, 17 comments, 7 reactions; top issue by comments and top by reactions) — accept image buffers, not only files. Not specified. File paths are enough for the fixture job in P4-T23.

Reaction search also returned, below the leaders and not re-ranked here: odiff [#2](https://github.com/dmtrKovalenko/odiff/issues/2) "Add ignore regions" and [#3](https://github.com/dmtrKovalenko/odiff/issues/3) "Anti-aliasing support" (4 reactions each). Those requests are already the behaviour in `cli.zig` at this SHA (T3-08, T3-10). SWE-bench [#621](https://github.com/SWE-bench/SWE-bench/issues/621) (11 comments, 0 reactions; not a leader) asks for confidence intervals on the leaderboard. Argus already requires a Wilson interval in `PLAN.md` Metrics contract.
