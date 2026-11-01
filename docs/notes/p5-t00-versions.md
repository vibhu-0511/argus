# P5-T00 version re-check

Checked on 2026-11-01. Every row has the page it came from. "not confirmed" means the page did not say, or the page could not be read. No number below is from memory.

## Tracing stack

| Item | Value | Source | Notes |
|---|---|---|---|
| OTel GenAI semconv: status | `stability: development` in the manifest. Every GenAI docs page carries `Status: Development`. The attributes used in P5 are all badged Development, except `error.type`, `server.address` and `server.port`, which are Stable | [manifest.yaml](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/model/manifest.yaml), [gen-ai-spans.md](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md) | Unchanged since 2026-10-30 |
| OTel GenAI semconv: repo | `open-telemetry/semantic-conventions-genai` (Apache-2.0). The `opentelemetry.io/docs/specs/semconv/gen-ai/*` pages now return a "Moved" notice that points to this repo | [repo README](https://github.com/open-telemetry/semantic-conventions-genai), [old spec page](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/) | Use the repo's `docs/gen-ai/` files, not the old URLs |
| OTel GenAI semconv: schema | `schema_url: https://opentelemetry.io/schemas/gen-ai-dev/1.42.0-dev`. Core semconv dependency `v1.44.0`. README "Schema URL" section still reads `TODO` | manifest.yaml (above) | Unchanged |
| OTel GenAI semconv: releases | The GitHub releases API returns `[]`. No tagged release. Last commit touching the manifest: `b694ec3`, 2026-08-04, "Semconv to 1.44" | [releases API](https://api.github.com/repos/open-telemetry/semantic-conventions-genai/releases), [commits API](https://api.github.com/repos/open-telemetry/semantic-conventions-genai/commits?path=model/manifest.yaml&per_page=1) | Tags page not read |
| OTel GenAI semconv: opt-in env var | `OTEL_SEMCONV_STABILITY_OPT_IN` / `gen_ai_latest_experimental`: not found in the docs pages read. Content capture is `OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT` (`NO_CONTENT` default) | gen-ai-spans.md | Whether any other file in the repo mentions the first one is not confirmed (code search needs a sign-in) |
| Langfuse Cloud Hobby: units | 50k units / month included. A unit is a trace, an observation (span, event, generation) or a score | [pricing](https://langfuse.com/pricing), [billable units](https://langfuse.com/docs/administration/billable-units) | Hobby "Additional usage" is "--". What happens after 50k is not stated: not confirmed |
| Langfuse Cloud Hobby: retention | 30 days of data access | pricing | Traces linked from the dashboard expire after 30 days |
| Langfuse Cloud Hobby: users | 2 users. Community support via GitHub | pricing | |
| Langfuse Cloud Hobby: rates | Ingestion 1,000 req/min. General API 30 req/min, Datasets API 100 req/min, Metrics API v2 100 req/day, Observations API v2 30 req/min | pricing | |
| Langfuse licence | Pricing FAQ: "Langfuse is open source". Billable-units page: self-hosted Langfuse (OSS) is free under the MIT licence. PyPI `langfuse` 5.1.0 is MIT | pricing, billable units, PyPI | The Cloud service itself is not MIT; the self-hosted code is |
| Langfuse OTLP | Cloud EU `https://cloud.langfuse.com/api/public/otel`, US `https://us.cloud.langfuse.com/api/public/otel`. Auth `Authorization=Basic base64(pk-lf-...:sk-lf-...)`. HTTP/JSON and HTTP/protobuf only. "gRPC is not supported yet" | [OTel get started](https://langfuse.com/docs/opentelemetry/get-started) | Port 4317 cannot be used. Region of the project is not known: ask the owner in T07 |
| Langfuse attribute mapping | input from `gen_ai.prompt` (fallback `gen_ai.tool.call.arguments`), output from `gen_ai.completion` (fallback `gen_ai.tool.call.result`), model from `gen_ai.request.model` / `gen_ai.response.model`, usage from `gen_ai.usage.*`, cost from `gen_ai.usage.cost`, type from `gen_ai.operation.name`. Unrecognised attributes land under `metadata.attributes` | OTel get started | `gen_ai.prompt` and `gen_ai.completion` are not in the semconv registry any more. Whether Langfuse also reads `gen_ai.input.messages`: not confirmed. The normalizer (T08) must handle this |
| Phoenix licence | Elastic License 2.0 (ELv2). It bars offering the software to third parties as a hosted or managed service. PyPI `arize-phoenix` says `Elastic-2.0` | [LICENSE](https://github.com/Arize-ai/phoenix/blob/main/LICENSE), PyPI | Not OSI open source. Fine for local use |
| Phoenix local run | `pip install arize-phoenix` then `phoenix serve`, or `uvx arize-phoenix serve`. Docker: `docker run -p 6006:6006 -p 4317:4317 -i -t arizephoenix/phoenix:latest` | [README](https://github.com/Arize-ai/phoenix), [terminal guide](https://arizeai-433a7140.mintlify.site/docs/phoenix/self-hosting/deployment-options/terminal.md), [docker guide](https://arize.com/docs/phoenix/self-hosting/deployment-options/docker) | UI `http://localhost:6006`. OTLP HTTP (protobuf) `http://localhost:6006/v1/traces`. OTLP gRPC port 4317. Default host `127.0.0.1` |

## Python packages (PyPI `latest`)

| Package | Version | Python | Licence | Uploaded (UTC) | Source |
|---|---|---|---|---|---|
| `opentelemetry-api` | 1.45.2 | >=3.10 | Apache-2.0 | 2026-10-29 | [PyPI JSON](https://pypi.org/pypi/opentelemetry-api/json) |
| `opentelemetry-sdk` | 1.45.2 | >=3.10 | Apache-2.0 | 2026-10-29 | [PyPI JSON](https://pypi.org/pypi/opentelemetry-sdk/json) |
| `opentelemetry-exporter-otlp-proto-http` | 1.45.2 | >=3.10 | Apache-2.0 | 2026-10-29 | [PyPI JSON](https://pypi.org/pypi/opentelemetry-exporter-otlp-proto-http/json) |
| `langfuse` | 5.1.0 | >=3.11,<4.0 | MIT | 2026-10-30 | [PyPI JSON](https://pypi.org/pypi/langfuse/json) |
| `arize-phoenix` | 21.0.0 | >=3.11,<3.16 | Elastic-2.0 | 2026-10-30 | [PyPI JSON](https://pypi.org/pypi/arize-phoenix/json) |

All five fit the repo's Python 3.12. The three OTel packages are on the same version. `opentelemetry-semantic-conventions` is `0.66b2` (a beta tag); P5 writes the attribute names as string constants and does not depend on that package.

## Groq limits for the models in `config/` and `docs/quotas.md`

Source: [console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits), read 2026-11-01.

| Model | RPM | RPD | TPM | TPD |
|---|---|---|---|---|
| `openai/gpt-oss-20b` | 30 | 1K | 8K | 200K |
| `openai/gpt-oss-120b` | 30 | 1K | 8K | 200K |
| `qwen/qwen3.8-27b` | 30 | 1K | 8K | 200K |

- All three model ids are on the page.
- The page has two tab labels, "Free Plan Limits" and "Developer Plan Limits", and one table. The text above the table says "the limits shown below are the base limits for the Developer plan". The page does not label any table "free tier". Whether the Free tab shows different numbers: not confirmed.
- These numbers match `docs/quotas.md`, which was measured from response headers on 2026-10-29 (requests/day 1000 and tokens/minute 8000 from headers, the other two published only). No change.
- "Cached tokens do not count towards your rate limits" is still on the page.
- The page calls the table a high-level summary. The account's own limits page (`/settings/limits`) wins.

## Result

- Pins that changed since 2026-10-30: none in the OTel GenAI row. The five Python packages above are new rows (first check).
- Open items carried into later tasks: Langfuse behaviour after 50k units (T07, T25), Langfuse reading `gen_ai.input.messages` (T08), Groq free-tier labelling (T12).
