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
