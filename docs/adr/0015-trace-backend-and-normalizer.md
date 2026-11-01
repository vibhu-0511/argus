# ADR-015: Trace backend and normalizer

Status: accepted (P5-T10). Part of the Langfuse side is built but not confirmed against a live project (see Consequences).

## Context

Argus spans (`invoke_agent`, `chat`, `execute_tool`) use the OpenTelemetry GenAI attribute names. That spec is still `Development` with no tagged release, so names can change under us (`docs/notes/p5-semconv.md`). Backends do not read the same names: Langfuse reads `gen_ai.usage.cost` and `langfuse.session.id`; Phoenix reads OpenInference names such as `llm.cost.total` and `openinference.span.kind`. We want one place to adapt, and a backend we can leave without touching the loops.

| | Langfuse Cloud Hobby | Phoenix, local |
|---|---|---|
| Licence | Self-hosted code is MIT. The Cloud service is a hosted product | Elastic License 2.0 (not OSI open source; bars offering it to others as a managed service; fine for local use) |
| Quota | 50,000 units a month (a trace, an observation or a score is a unit), 30 days of data, 2 users. What happens after 50,000 is not stated on the pricing page | None. It is a local process; the limit is the disk |
| Rate limits | Ingestion 1,000 requests a minute | Not stated in the notes read |
| Receives | OTLP over HTTP (protobuf or JSON) at `/api/public/otel/v1/traces`, Basic auth from the project's two keys. No gRPC | OTLP over HTTP at `/v1/traces`; gRPC on 4317 |
| Needs an account | Yes (project and keys) | No |
| Seen working here | No. Export is built and tested against a local fake receiver only | Yes: Phoenix 21.0.0, five spans with parent links (`docs/notes/p5-t09.md`) |

Sources for the Langfuse and Phoenix rows: `docs/notes/p5-t00-versions.md` (read 2026-11-01).

## Decision

1. Argus always writes the GenAI names. No loop or span helper knows a backend.
2. A normalizer (`argus_core/trace_normalize.py`) sits between the spans and the exporter. A profile (`langfuse`, `phoenix`, `none`) is a table of argus attribute to backend attribute. A mapped attribute is moved, not copied. The table is data in code, with one test per row.
3. Any attribute argus does not know passes through unchanged and is counted by name (`unmapped_attributes()`). A spec rename therefore shows as a number instead of a silent gap in the backend. The Break it task T24 tests this.
4. The backend is chosen by environment variables only: `ARGUS_TRACE_BACKEND` (`console`, `langfuse`, `otlp`), `ARGUS_TRACE_PROFILE`, and the keys or endpoint. Keys are read from the environment and never written to a file, log line or span.
5. Network export uses a batch processor with a queue of 512 spans and a 3-second export timeout. An unreachable backend drops spans; it does not hold the run. T25 breaks this on purpose.
6. Langfuse Cloud Hobby is the cloud target named in the phase plan. Phoenix is the local second backend and the proof that the swap works. Message text is never put on a span (content capture is off), so the 50,000-unit quota is spent on structure only.

### Swap procedure

From Langfuse to Phoenix, or any OTLP/HTTP receiver, with no code change:

1. Start the receiver. For Phoenix 21: `python -m phoenix.server.main serve` (UI `http://127.0.0.1:6006`).
2. Set `ARGUS_TRACE_BACKEND=otlp` and `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:6006/v1/traces`. Add `OTEL_EXPORTER_OTLP_TRACES_HEADERS=name=value` if the receiver needs a key.
3. Set `ARGUS_TRACE_PROFILE=phoenix`.
4. Run. Check `python -m argus_core.telemetry` prints `export=SUCCESS`, and after a real run read `unmapped_attributes()`: it should be empty.

To a backend with no profile: use `ARGUS_TRACE_PROFILE=none` first (names stay as argus wrote them), then add a table to `PROFILES` and a test row per attribute.

## Alternatives

- Use the Langfuse SDK. Rejected: it ties the loops to one vendor, and the task was to keep the backend swappable.
- Map attributes inside each span helper. Rejected: every backend or spec change would touch the loops, and T24 could not test one place.
- Copy mapped attributes instead of moving them. This keeps the original names in the backend as well. It doubles the attributes on every span, which in Langfuse land in `metadata.attributes`. Moving is the smaller payload; the cost is below.
- Phoenix as the only backend. It has no quota and no account. It is local, so a trace cannot be linked from a public dashboard, which the phase wants (T23).

## Consequences

- **The Langfuse path is not confirmed.** No Langfuse account or key was available. The endpoint form, Basic auth and headers follow the Langfuse OTel page (read 2026-11-01) and a test checks the request on the wire against a local server. Whether a project shows the trace is the T07 check that the owner still has to run (`docs/notes/p5-t07.md`). The `langfuse` profile's targets (`gen_ai.usage.cost`, `langfuse.session.id`, `langfuse.observation.metadata.*`) come from the same page and were not seen working.
- **The profile is not required for Phoenix 21 to type a trace.** With profile `none`, Phoenix 21 still showed the right kinds, model and token counts, because it reads the GenAI names. The `phoenix` profile adds the cost (`llm.cost.total`), agent and tool names. It also moves the `gen_ai.usage.*` names, and Phoenix then did not compute `llm.token_count.total` for that run (it did for the `none` run). Not fixed; the options are in `docs/notes/p5-t09.md`. Seen on Phoenix 21.0.0 only.
- **Phoenix could not be imported on this machine** because Windows Application Control blocks pandas' native DLL. The server ran from `python -m phoenix.server.main serve`. The `phoenix` command and the Python client were not usable here.
- **The unmapped counter sees only the argus side.** It counts names on our spans that the normalizer does not list, which is what a spec rename of our output looks like. If a backend changes the names it reads, the counter stays at zero; a new or updated backend still needs a look at its docs.
- Phoenix's licence limits how it can be shared as a service. Argus only runs it locally, so this does not bite.
- Hobby keeps data for 30 days. A trace linked from the dashboard expires after that.
