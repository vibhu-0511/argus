# P5 break-its

Each section is one induced failure, the signal it should give, what was observed, and the fix. None of the tests call a model or the network.

## P5-T26 cache-busting prefix

Test: `packages/fix-loop/tests/test_cache_busting_prefix.py`. The shipped prompt is not changed. The test wraps `fix_loop.loop.system_message` so that `Current time: <ISO time>` comes first, one second later on every call.

**Induced failure.** The current time is the first line of the system message. The AGENTS.md map and the tool list follow it, unchanged.

**Expected signal.** Two requests no longer share their system bytes, so the byte comparison in `test_cache_prefix.py` does not hold, and cached tokens per call are zero.

**Observed.**

- The same comparison as `test_cache_prefix.py` (first message of two runs, as bytes and as the wire form) comes out unequal, and unequal to `system_message(PROTOCOL)`. The "no run-specific text in the prefix" check would also fire, because the date is in it. The test asserts the inequality, so the suite stays green.
- A stub provider reports a request's system tokens as cached only when the same system bytes came in on an earlier request. Three fix-loop calls against one stub and one ledger (`PrefixCacheStub`, `Ledger` file read back after each call):

| Prefix | Cached tokens per call | Ledger `cached` | Ledger `fresh` |
|---|---|---|---|
| Stable (shipped) | 0, 680, 680 | 1360 | 722 |
| Timestamp at the top | 0, 0, 0 | 0 | 2112 |

The first call is cold in both rows. In the stable row the system message is cached from the second call on. With the timestamp it never is: the whole prompt is counted as fresh and the cached tokens go to zero.

**Not shown.** The drop is shown with a stub provider only. No real provider's cache was called. Groq's usage object had no cached-token field in the 2026-10-29 probe (`docs/quotas.md`), so no real cache hit was ever observed, and the effect of this change on a real provider is unmeasured.

**Fix.** Keep dynamic content after the stable prefix: the time, ticket and run id go in the first user turn, as `user_message` and `run_fix(user=...)` already do. `test_cache_prefix.py` stays as the guard.

Run: `uv run pytest packages/fix-loop/tests/test_cache_busting_prefix.py packages/fix-loop/tests/test_cache_prefix.py -q`

## P5-T24 attribute rename

Tests: the last four in `packages/argus-core/tests/test_trace_normalize.py` (`RENAMED`). The shipped code change is a strict switch in `trace_normalize.py`, off by default. The new name `gen_ai.usage.input_token_count` is made up; the GenAI spec has not renamed `gen_ai.usage.input_tokens`.

**Induced failure.** A fixture span carries `gen_ai.usage.input_token_count` where argus writes `gen_ai.usage.input_tokens`, as a semconv revision might. Argus code is unchanged, so this is what a backend would receive after such a revision.

**Expected signal.** The normalizer's mapping test fails on the unknown name, and `unmapped` is non-zero.

**Observed.**

- Before this task nothing could fail. An unknown name passed through unchanged, the counter went to 1 and one warning was logged (name only, never the value). The Phoenix profile did not rename it, so `llm.token_count.prompt` was missing and no test noticed.
- Now `NormalizingExporter(..., strict=True)` (or `ARGUS_TRACE_STRICT=1`) raises `UnmappedAttribute: trace attribute 'gen_ai.usage.input_token_count' is not one argus knows; add it to KNOWN and the profiles`. This holds for all three profiles (`none`, `langfuse`, `phoenix`). The counter is already `{name: 1}` when it raises. `test_mapped_attribute` now runs strict, so a rename in the argus side of the tables fails the suite too.
- Default (strict off) is unchanged: the span goes out with the new name, counter 1, warning logged. A production run is never stopped by a rename.
- Inside a real span processor the SDK catches the error and logs `Exception while exporting Span`; that span is not exported and the code that made it carries on. So strict mode is loud in a direct `normalize` call and in the log, not as a crash of the run. Use it in tests and CI only.

**Fix.** Add the new name to `KNOWN` and to each profile that maps the old one (Phoenix: `llm.token_count.prompt`), and keep `gen_ai.usage.input_tokens` as an alias so older spans still map. `test_adding_the_new_name_with_the_old_one_kept_as_alias_fixes_it` does this with `monkeypatch` and shows: new name mapped, old name mapped, `unmapped` empty, strict mode quiet. In the real fix a row for the new name also goes into `EXPECTED`, which `test_every_rule_has_a_test_row` requires. Langfuse maps neither name (it reads the GenAI names itself), so for that profile only `KNOWN` changes.

**Not shown.** No real backend was sent the renamed span.

Run: `uv run pytest packages/argus-core/tests/test_trace_normalize.py -q`

## P5-T25 backend unreachable

Test: `packages/fix-loop/tests/test_backend_unreachable.py`. It runs the T06 stubbed fix-loop run with `ARGUS_TRACE_BACKEND=otlp` pointed at a local port, with `EXPORT_TIMEOUT_S` set to 1 for speed, and compares it with the same run into an in-memory exporter. Two kinds of dead port: **closed** (connection refused) and **silent** (a socket that listens and never reads or answers, the slow failure).

**Induced failure.** The trace backend cannot be reached.

**Expected signal.** The run finishes normally, the exporter logs a drop after the timeout, and the run takes no longer than that timeout.

**Observed.**

- Before this task the only log lines were the OTLP library's `Failed to export spans batch due to timeout, max retries or shutdown.` It does not say spans were dropped or how many. Now `NormalizingExporter.export` logs `dropped 5 spans: the trace backend did not take them` (logger `argus.trace`) whenever the inner exporter does not return success. The line holds a count only: no endpoint, no header, no span content. The test sets a fake bearer token and checks it is absent from every log record.
- The run result is unchanged: same stop reason (`submit`) and a byte-identical trajectory file. Emitting spans never waits for the network; the wait is in the flush at `provider.shutdown()`.
- The delay is one export timeout for the one batch (agent, two model calls and two tool calls make 5 spans, a single batch). Measured here, stub run plus flush, baseline 0.09 s:

| Export timeout | Closed port: extra seconds | Silent port: extra seconds |
|---|---|---|
| 1 s | 1.45 (one run; 1.15 in the test run) | 0.94 |
| 3 s (shipped) | 2.92 | 2.92 |

  Closed ports on Windows overshoot a 1 s timeout by up to half a second (refused connects are retried by the OS); at 3 s both kinds end at the timeout. The test asserts extra time under `timeout + 2 s`. A queue over 512 spans keeps the first 512 and drops the rest, and `test_trace_export.py::test_unreachable_backend_does_not_hold_the_run` covers that case.

**Fix.** Already in `telemetry.start_tracing`: a batch processor with a bounded queue (512) and an export timeout (3 s) in place of a synchronous exporter. The only change here is the drop log line.

**Not shown.** The test uses localhost only. A backend that answers slowly byte by byte, or DNS that hangs, was not tried; the OTLP exporter's timeout is a total budget per export, but I did not measure those cases.

Run: `uv run --package fix-loop --with jsonschema pytest packages/fix-loop/tests/test_backend_unreachable.py -q`
