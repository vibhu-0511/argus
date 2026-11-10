# P10-T10 break it: script and markup render inert

Status: tests written and shown to fail on three mutated builds. The TASKS.md box is NOT ticked: the PR body and the Run, PR and History screens do not exist in this branch (see "Gap"). Test module: `packages/workbench/tests/test_break_it_t10.py`.

## Induced failure

Put markup in every place a person or a run can put text:

- ticket text: `<script>window.__pwned=1</script>`, `<img src=x onerror=...>`, `$(touch /tmp/pwned) \`id\` ${7*7}`, `"><svg onload=...>`, `</script><script>...`, `javascript:...`, `{{7*7}} <iframe srcdoc=...>`
- run id: the same strings, plus `a/b`, `..`, `UPPER`, 65 characters, `con`
- reviewer note and reason (Approve with a reason, Request changes with a note)
- judge note, check reason, check route and patch file name inside `verdict.json` and `patch.diff`
- `report.html` (a page with `<script>` and an `onerror` image)
- PR body (`pr.json`), only once T08 exists (see Gap)

## Expected signal

Each one shows as plain text on every screen, and nothing runs.

## How the test proves it (no browser needed)

| Layer | What is asserted | Tests |
|---|---|---|
| Source | no script uses `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`, string `setTimeout`, `srcdoc`, `DOMParser`, `createContextualFragment`, handler properties (`.onclick =`), `.href =` / `.src =`, `window.open`, `location` writes, or `setAttribute` with a name that is not an `aria-*`/`role` literal (only `dom.js` may, and it has a deny list); `index.html` has one external module script, no inline handler, no inline style; the review screen's report frame is `<iframe sandbox="">` with no `allow-` token anywhere; the hash router turns a non-matching run id into `null` | `test_no_script_turns_text_into_markup_or_code` (one per JS file), `test_the_report_frame_is_sandboxed_with_no_allow_tokens`, `test_index_html_has_one_external_script_and_no_inline_code`, `test_run_id_rule_in_the_router_matches_the_store_rule`, `test_dom_helper_keeps_its_deny_list` |
| Headers | every response (pages, static files, JSON, 404, a refused POST) has a CSP whose script source is exactly `'self'`, with no `unsafe-*` keyword, no wildcard, no scheme source; the report is served with `default-src 'none'` and a bare `sandbox` directive (no `allow-*`), unchanged, with `nosniff` and no CORS header | `test_every_response_has_a_csp_with_scripts_from_self_only`, `test_a_refused_post_also_carries_the_csp`, `test_every_html_response_is_checked_and_has_no_inline_script_allowed`, `test_the_report_is_served_with_the_sandbox_csp_and_unchanged` |
| Data | hostile ticket text, reviewer note, reason, judge note, check reason, route and patch file names come back from the JSON API byte for byte, as `application/json` with `nosniff` (escaping is the page's job and the page only uses `textContent`); a hostile query string or path is never echoed into an HTML response; a run id with markup is refused by the id rule (`bad_run_id` or `not_found`), the error is JSON and does not echo the markup, and no folder or file is created | `test_ticket_text_comes_back_unchanged_as_json`, `test_reviewer_note_and_reason_come_back_unchanged`, `test_judge_and_check_text_from_the_verdict_come_back_unchanged`, `test_patch_file_names_come_back_unchanged`, `test_query_strings_and_paths_are_never_echoed_into_html`, `test_a_run_id_with_markup_is_refused_by_the_id_rule_and_creates_nothing`, `test_the_store_itself_refuses_a_run_id_with_markup` |

The expected values (`script-src` is `'self'`, the report has `sandbox`, the ids rule) are written in the test, not imported from the code under test, so a weakened build fails.

Command: `uv run --all-packages python -m pytest packages/workbench/tests/test_break_it_t10.py -q`

Observed on the fixed build: `58 passed, 1 skipped` (the skip is the PR body test, see Gap). Whole package: `330 passed, 1 skipped` (this includes the T11 module).

## A real bug the test found (fixed)

First run, before any mutation:

```
FAILED packages/workbench/tests/test_break_it_t10.py::test_query_strings_and_paths_are_never_echoed_into_html
.venv\Lib\site-packages\starlette\staticfiles.py:176: OSError
E   OSError: [WinError 123] The filename, directory name, or volume label syntax is incorrect: '...\\static\\<script>window.__pwned=1<\\script>'
1 failed, 57 passed, 1 skipped
```

`GET /static/<script>...` made Starlette's `StaticFiles` raise an `OSError` on Windows (`<`, `>`, `|`, `"`, `?` cannot be in a file name). The result is an untyped 500 outside the security middleware (no CSP header, no typed error body). Nothing was echoed, but it breaks the rule that every error is typed.

Fix: `server.py` mounts `SafeStaticFiles`, a small subclass of `StaticFiles` that turns an `OSError` from `lookup_path` into a 404, which the existing handler makes a typed `not_found`. After the fix: `58 passed, 1 skipped`.

## Mutation proof

Each mutation was made on the real file, the tests were run, and the file was restored with `git checkout -- <file>`. After the last revert the module passed again (`58 passed, 1 skipped`).

| # | Mutation | T10 result | Existing tests that also fail |
|---|---|---|---|
| 1 | `static/screens/issue.js`: `preview.textContent = JSON.stringify(ticket, null, 2);` became `preview.innerHTML = ...` (ticket text rendered as markup) | `1 failed, 57 passed, 1 skipped`: `test_no_script_turns_text_into_markup_or_code[screens/issue.js]`, message `assert not <re.Match object; span=(8147, 8156), match='innerHTML'>` | `test_static.py::test_no_markup_building_apis_in_any_script` |
| 2 | `security.py`: `script-src 'self'` became `script-src 'self' 'unsafe-inline'` in `CSP` | `3 failed, 55 passed, 1 skipped`: `test_every_response_has_a_csp_with_scripts_from_self_only`, `test_a_refused_post_also_carries_the_csp`, `test_every_html_response_is_checked_and_has_no_inline_script_allowed` | `test_security.py::test_csp_is_default_src_self_with_no_inline_or_eval_and_frame_rules` |
| 3 | `routes/review.py`: the report response loses its header (`return HTMLResponse(html)` instead of `HTMLResponse(html, headers={"Content-Security-Policy": REPORT_CSP})`); the page CSP then applies, which has no `sandbox` | `1 failed, 57 passed, 1 skipped`: `test_the_report_is_served_with_the_sandbox_csp_and_unchanged` (`d.get("sandbox") == []` fails, the CSP is the page one) | `test_review.py::test_report_response_is_sandboxed_by_its_own_csp`, `test_report_with_script_is_served_with_the_inert_csp_unchanged` |
| 4 (extra) | `static/screens/review.js`: `sandbox: ''` removed from the report `iframe` | `1 failed, 57 passed, 1 skipped`: `test_the_report_frame_is_sandboxed_with_no_allow_tokens` | none |

## Browser check (done by hand, not part of the tests)

The built-in browser pane, a local server on `127.0.0.1:8793` (started with `python -m argus_workbench.cli serve --port 8793`, then stopped; the `argus-workbench.exe` launcher is blocked on this machine by Application Control), and a throwaway run store holding one SIMULATED fixture run `run-hostile` whose judge note, check reason, patch file name and report held markup that sets `window.__pwned`:

| Page | Observed |
|---|---|
| `#/review/run-hostile` | judge note, check reason and patch file name each shown as literal text (`<script>window.__pwned=1</script>` visible as text); `#screen img, #screen svg` count 0; `window.__pwned` stays `null`; one `<script>` element in the document; the report frame has `sandbox=""` and its content is not reachable from the page (`contentDocument` is `null`) |
| `#/issue`, hostile text typed into the ticket field | the JSON preview `<pre>` shows the text; it has 0 child elements; no `img` in `#screen`; `window.__pwned` stays `null` |
| `#/review/<img src=x onerror=window.__pwned=1>` | the Review screen opened with its heading (the id did not match the rule, so the screen got no run id); 0 `img` in the document; `window.__pwned` stays `null` |
| direct visit `/api/runs/run-hostile/report` | heading `REPORT-VISIBLE` shows; the report's own `<script>` did not run (`window.__pwned` and `window.top.__pwned` both `null`). Its CSP, read with `fetch`, is `sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'`. `location.origin` printed `http://127.0.0.1:8793` in that pane, so I did not use the origin as evidence; the evidence is that the script did not run |

One note about the tool: the Browser pane is shared with other agents. My first tab was navigated away by someone else mid-script (to another server on port 8761), so I opened my own tab for the rest and closed it afterwards. Nothing on port 8761 was touched.

## Gap (why the box is not ticked)

The acceptance row says "on every screen" and names the PR body.

- `routes/pr.py` and the PR screen (T08) are in `p10/pr`, which is not one of the branches this group depends on. In this branch `run.js`, `pr.js` and `history.js` are still placeholders with static text. The source scan covers every file in `static/` (so it covers the real screens once they are merged), but the PR body itself could not be served and checked.
- `test_pr_body_hostile_text_is_inert_on_the_pr_routes` is written and skipped (`routes/pr.py (T08) is not in this branch`). It starts to run by itself when `routes/pr.py` exists: it writes a `pr.json` with hostile `title` and `body`, then calls every GET route of that module that has `{run_id}` in its path, and asserts JSON bodies carry the text unchanged under a script-src-`'self'` CSP, and any HTML response carries a `sandbox` CSP.
- The Run (T06) and History (T09) screens are not built here, so the live trajectory text and the history list cannot be checked in a browser. The same source scan applies to them when they land.

Owner/integrator steps after the groups are merged:

1. `uv run --all-packages python -m pytest packages/workbench/tests/test_break_it_t10.py -q` and confirm `0 skipped` (the PR test ran) and no failure. If the PR test fails because the T08 routes need a different fixture (for example a different `pr.json` shape), fix the fixture in that one test.
2. Repeat the browser check above on the Run, PR and History screens with a hostile ticket text, run note and PR body.
3. Then tick `P10-T10` in `TASKS.md`.
