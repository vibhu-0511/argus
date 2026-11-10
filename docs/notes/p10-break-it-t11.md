# P10-T11 break it: hostile uploads

Status: done. The test refuses every hostile upload through the real `POST /api/issues`, stores nothing, and fails on both mutated builds. Test module: `packages/workbench/tests/test_break_it_t11.py`.

## Induced failure

Upload these as the `screenshot` of a new issue:

| Upload | Why it is hostile |
|---|---|
| HTML bytes named `x.png` (and `x.jpg`) | script in a file that claims to be an image |
| SVG as `image/svg+xml` named `x.svg`, SVG named `x.png`, SVG with an `<?xml?>` prolog named `x.png` | SVG can carry script |
| a file of exactly 5 MB + 1 byte (valid PNG start, valid JPEG start), 6 MB of PNG, 6 MB of HTML | over the cap |
| HTML bytes with the client file name `../../evil.png`, `..\..\evil.png`, `..` | path traversal in the name |
| a GIF named `x.png`, a PNG signature cut short | wrong or broken type |
| zero bytes (also with a `..` name) | empty file |

Also, the other side: a real PNG and a real JPEG whose client file name is `../../evil.png`, `..\..\evil.jpg`, `..`, `a/b/../../c.png`, `evil name;rm -rf.exe` or 300 characters long, sent with a lying content type (`text/plain`).

How the brief's "a file name with `..`" is read: the name alone is not the reason for refusal (the server never reads it), so it is tested twice. With hostile bytes it is refused by the bytes. With a real image it is accepted and the name has no effect (second part of this table).

## Expected signal

- Each hostile upload: a typed error `{"error": {"code", "field": "screenshot", "message"}}` as JSON, and NOTHING stored: the run store root has no folder, `store.list_runs()` is empty, the temp folder is empty and every spooled upload is closed.
- Each real image: `201`, stored as `shots/screenshot.png` or `shots/screenshot.jpg` (chosen by the first bytes), the client name nowhere in the response or in any stored file name or file content, and nothing written outside the run store.

| Case | Code | HTTP |
|---|---|---|
| HTML, SVG, GIF, cut-short PNG signature (any name, any content type) | `unsupported_file_type` | 415 |
| zero bytes | `empty_file` | 400 |
| 5 MB + 1, 6 MB (any bytes) | `file_too_large` | 413 |

## How the test proves it

- The real route is called through the FastAPI test client with a real multipart body and the per-start test token. Nothing is mocked in the route.
- "No temp files": `tempfile.tempdir` is pointed at an empty folder of the test and Starlette's `SpooledTemporaryFile` is wrapped to remember every upload it created. After each request the folder must be empty and every upload must be closed. `test_a_big_upload_really_goes_through_the_spool` checks the check is not vacuous: a 5 MB + 1 body must have rolled over to a temp file.
- The limits are written in the test (5 MiB, the two signatures), not imported, so changing the code changes the result.
- 5 MiB exactly is accepted and 5 MiB + 1 is refused (`test_the_size_cap_is_exactly_5_mib`).

Command: `uv run --all-packages python -m pytest packages/workbench/tests/test_break_it_t11.py -q`

Observed on the unmodified build: `33 passed`. Whole package: `330 passed, 1 skipped` (the skip is the PR-body test of T10).

## Mutation proof

Each mutation was made on `routes/issues.py`, the tests were run, and the file was restored with `git checkout -- packages/workbench/src/argus_workbench/routes/issues.py`. After the revert the module passed again (`33 passed`).

| # | Mutation | T11 result | Existing `test_issues.py` |
|---|---|---|---|
| 1 | Magic bytes weakened to a name check: `kind = sniff(data[:8])` replaced by a lookup of `part.filename` (`.png` gives PNG, `.jpg` or `.jpeg` gives JPEG) | `18 failed, 15 passed`. For example `assert 201 >= 400` for HTML named `x.png`; also failing: html named x.jpg, svg named x.png, svg with an xml prolog, html with `..` names, gif named x.png, cut-short signature, every "real image with an odd name" case whose name does not match its bytes, `test_the_type_follows_the_bytes_not_the_name`, `test_a_refusal_after_a_good_upload_leaves_only_the_good_run` | `5 failed, 34 passed` |
| 2 | Size cap raised: `int(load_spec()["targets"]["maxFileMB"] * 1024 * 1024)` became `... * 4 * 1024 * 1024` (20 MiB) | `5 failed, 28 passed`: both `5 MB + 1` cases, `6 MB, valid png start`, `6 MB of html named x.png` (`assert 201 == 413` for the first three), `test_the_size_cap_is_exactly_5_mib` | `3 failed, 36 passed` |

## What was found

Nothing to fix. The route already did all of this (signature check, one cap, server-chosen stored name, all checks before anything is written). The new test pins it down: before this task the existing `test_issues.py` also covered these, but not the leftover temp files, the odd names on real images, the 6 MB path, or the exact boundary through a spool check.

## Known limits (not fixed, not hidden)

- The check is the signature only. A file that starts with a PNG header and holds junk or script after it is stored (documented as a `ponytail:` note in `routes/issues.py`). Nothing serves it back inline in this build; a screen that does must keep `nosniff` and the image type.
- A polyglot such as a valid PNG header followed by HTML is therefore accepted. This test does not claim otherwise.
