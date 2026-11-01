# P5-T06 notes

- Unpriced model: `argus.usage.cost_usd` is left off the span (no error, no zero). `dollar_equivalent` raises `UnknownModelPrice`; the span code catches it and `ValueError` (cached tokens above prompt tokens).
- Not set, as the semconv note says: `gen_ai.request.max_tokens/temperature/seed` (the client sends none), `gen_ai.usage.cache_write.input_tokens`, message content. `argus.tier` is T12's.
- Finish reason is read from the live reply only; a replayed trajectory has none.
- A `ModelClient.complete` inside a loop's `chat` span joins it. If the router (T12) retries on the other host inside one `_ask`, those attempts share one span and the last attempt's response attributes win. If per-attempt spans are wanted, the router should open its own `chat` span per attempt outside the loop's.
- `start_tracing` keeps the provider in the module and does not call `trace.set_tracer_provider`, so tests can start one per test. Third-party instrumentation will not see it until T07 decides to set the global.
- Only `opentelemetry-api` and `opentelemetry-sdk` (1.45.2) were added. The OTLP HTTP exporter belongs to T07.
- Console exporter uses a simple (synchronous) processor. T25 asks for batch export with a bounded queue for the real exporter.
- `uv run pytest packages/fix-loop/tests` fails at collection (`jsonschema` is not a declared dependency of fix-loop; only dom2src-mcp has it). Run with `--package fix-loop --with jsonschema`. With that, 55 pass and `test_ast_grep.py::test_pattern_returns_file_and_line_and_a_bad_pattern_is_typed` fails ("src/main.tsx is not in the worktree"); it only touches `fix_loop.tools`, which this task did not change. Not checked on the base commit.
