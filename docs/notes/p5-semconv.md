# P5 span and attribute names

Read on 2026-11-01. Wave 2 reads this file: T06 (spans) takes the names and where to set them, T08 (normalizer) takes the status column and the aliases. Versions and limits are in `docs/notes/p5-t00-versions.md`.

## What was read

| Source | What | Gaps |
|---|---|---|
| [OTel GenAI semconv repo](https://github.com/open-telemetry/semantic-conventions-genai), `main`, files under `docs/gen-ai/` and `docs/registry/attributes/gen-ai.md` | Inference span (`client-inference.md`), execute-tool span (`gen-ai-spans.md`), agent spans (`gen-ai-agent-spans.md`), token metrics (`gen-ai-token-metrics.md`), registry table | Registry footnotes were not all read. A repo-wide search for the stability opt-in variable was not possible (code search needs a sign-in) |
| [Langfuse OTel page](https://langfuse.com/docs/opentelemetry/get-started) | Which `gen_ai.*` names Langfuse reads | Whether it reads the newer message attributes: not confirmed |
| [arXiv 2608.13867](https://arxiv.org/abs/2608.13867), Jarmak, "Engineering Reliable Coding Agents: Evaluating and Operating the System Around the Model", v1, 14 Aug 2026, CC BY 4.0 | The HTML version, from the start to section 14.2, plus the abstract | The text stopped near character 578,850 of 613,420. **Chapters 15 to 20 were not read**, which includes Chapter 19 (allocation and cost, routing) and section 20.4 (limitations). The PDF gave no text. Chapter 4 reached me as a tool summary, not verbatim |

## Status of the GenAI conventions

- The whole set carries `Status: Development`. No tagged release exists. Names can still change.
- Development: `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.*`, `gen_ai.response.*`, `gen_ai.usage.*` (including the cache names), `gen_ai.tool.*`, `gen_ai.agent.*`, `gen_ai.conversation.id`, and every message-content attribute.
- Stable: only the general attributes `error.type`, `server.address`, `server.port`.
- So every name argus writes except those three is a moving target. That is the reason for the normalizer (T08) and the Break-it task T24.
- Message content (`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`) is **Opt-In** in the spec, and the spec's own switch `OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT` defaults to `NO_CONTENT`. Argus follows that default: no prompt or reply text on spans. Reasons: every span is a billable Langfuse unit regardless of size, Hobby keeps data 30 days only, and the full text already lives in the trajectory JSONL.

## Span tree argus will emit

| Span name (spec format) | Kind (spec) | One per | Argus example |
|---|---|---|---|
| `invoke_agent {gen_ai.agent.name}` | `INTERNAL` for an in-process agent (`CLIENT` is for a remote agent service) | run of the repro agent, the fix loop, or best-of-k | `invoke_agent fix-loop` |
| `chat {gen_ai.request.model}` | `CLIENT` (the spec allows `INTERNAL` only for a model in the same process; Groq and Ollama are over HTTP) | model call | `chat openai/gpt-oss-20b` |
| `execute_tool {gen_ai.tool.name}` | `INTERNAL` | tool call | `execute_tool submit` |

Parent and child: `chat` and `execute_tool` are children of the `invoke_agent` span of their run. The span name formats are "SHOULD" in the spec, so they are taken as written.

## Things T06 and T08 must not get wrong

1. **Two different "stop reasons".** The spec's `gen_ai.response.finish_reasons` is what the *model* reported for one generation (`stop`, `length`, `tool_calls`, a `string[]`). Argus's `StopReason` (`submit`, `step-cap`, `token-cap`, `QuotaExceeded`, `stuck`, `consecutive-timeout`, `retry-cap`, `tool-unavailable`, `summary`, `verify-reject`) is why the *loop* ended. They are not the same value and must not share an attribute. Argus sets the first from the model reply and the second as `argus.stop_reason` on the `invoke_agent` span (and on the last step's `chat` span, as the trajectory already does).
2. **The finish reason is not stored.** `Completion.raw` holds the reply, but `TrajectoryStep` has no finish-reason field. A span can read it live from `raw["choices"][0]["finish_reason"]`; a replayed trajectory cannot. T06 must treat it as absent on replay and must not invent it.
3. **`input_tokens` includes cached tokens.** The spec says `gen_ai.usage.input_tokens` "SHOULD include all types of input tokens, including cached tokens", and `gen_ai.usage.cache_read.input_tokens` "SHOULD be included in" it. Argus `tokens_in` is the provider's `prompt_tokens`, which already includes the cached part (the ledger subtracts `tokens_cached` when a quota does not count cached tokens, `argus_core/ledger.py:101-103`). So: `input_tokens = tokens_in`, `cache_read.input_tokens = tokens_cached`, and no subtraction.
4. **The cached-token name is `gen_ai.usage.cache_read.input_tokens`.** `gen_ai.usage.cached_input_tokens` does not exist in the registry. The spec says to send it only "when available and non-zero". There is also `gen_ai.usage.cache_write.input_tokens`; Groq reports no cache writes, so argus does not set it.
5. **Old names are gone from the registry.** `gen_ai.system`, `gen_ai.usage.prompt_tokens`, `gen_ai.usage.completion_tokens`, `gen_ai.prompt` and `gen_ai.completion` have no row in the current registry (no deprecation note was found either, so how they were retired is not confirmed). **Langfuse still reads `gen_ai.prompt` and `gen_ai.completion` for input and output, and `gen_ai.usage.cost` for cost; none of the three is in the registry.** That is the first real job for the normalizer profile: argus writes the spec names, and the Langfuse profile adds or renames to what Langfuse reads. T24 renames `gen_ai.usage.input_tokens` and expects the unmapped counter to rise.
6. **Provider names.** `groq` and `mistral` are on the well-known list. Ollama is not. The spec says to set the value from the instrumentation's best knowledge, so argus uses `ollama` and records that as its own choice. Whether the spec forbids values outside the list: not confirmed.
7. **Metrics are not needed.** The old histogram `gen_ai.client.token.usage` is not on the token-metrics page any more (the page has `gen_ai.client.inference.usage.*` counters). Argus computes its numbers from the stored JSONL (T02, T03), not from OTel metrics, so it emits none.
8. **Langfuse over OTLP is HTTP only.** The exporter is `opentelemetry-exporter-otlp-proto-http`. Phoenix accepts the same protocol at `/v1/traces`, which is what makes the swap proof (T09) a change of endpoint and profile.

## What the reliable-agents paper says that matters here

The paper is a review and engineering monograph (author-assigned evidence grades, no experiments of its own), so these are claims to check against our own runs, not facts about argus.

- **One run is one draw.** Across 60,000 SWE-bench-Verified trajectories, single-run pass@1 varied by 2.2 to 6.0 points, and a gain of 2 to 3 points fits inside that spread (section 1.1). A +0.054 advantage fell to +0.0035 after three repeats (same section). Use for: T04 (report intervals, not points), T16 and T18 (gate thresholds come from measured run-to-run noise).
- **Repeats and thresholds.** Three repeats per configuration is "a workable minimum"; set the engineering threshold before the run; size repeats from pilot variance; a difference smaller than the measured variation earns no credit; an underpowered test gives no verdict (1.4, 1.2). Use for: T14 and ADR-017.
- **Paired comparison.** Compare per-task differences (McNemar for pass/fail, paired bootstrap for other metrics), and keep each attempt's outcome with its task id (1.1, 1.3). The paper does not name Wilson intervals in the text I read; Wilson is our choice for a single resolve rate (T04). Use for: T05, T14.
- **Cluster warning.** A bootstrap interval that treats tasks as independent "likely understates uncertainty" when tasks cluster by repository (12.2). Our 30 tasks share one Canvas repo, so the intervals are optimistic. State this wherever an interval is shown.
- **Pass@k vs pass^k.** pass@k (at least one of k succeeds) fits workflows with selection, pass^k (all succeed) fits unattended runs (1.1 definitions; 4.3 is a summary). Best-of-k in P4 is the first kind.
- **Do not trust self-reports.** One model "submitted" in 100% of trials but resolved 44% under an external check (Figure 4.1 caption). Argus's `submit` stop reason is a claim; the resolve rate must come from the checks, not from `submit`.
- **Record cost parts separately.** Count all tokens including retries and discarded branches, and record cache quantities separately; keep a pricing snapshot beside the run (Introduction, 2.2). Matches the trajectory's in/out/cached split and the dated `prices.json` (T11).
- **Typed events and causality.** A trace is a stream of typed events: model call (input and output references, timing, tokens, completion status), tool call (dispatch, acknowledgment, result), state change. Each action carries an agent id, the step that chose it and the session. Use parent ids and sequence numbers, not wall-clock order, for causality. The schema records its own version, because a missing field can mean "did not happen", "not recorded" or "older schema" (10.1, 11.3). Use for: T06 (parent links, a schema version resource attribute), T08.
- **Gaps are data.** Record the time between `tool_call_dispatched` and `tool_result_persisted` rather than hiding it (10.1). Keep quarantined runs (timeouts, rate limits, infrastructure failures) with an exclusion reason and owner, because deleting them erases the line between apparatus failure and agent failure (11.3). Use for: T20 (no task silently dropped), T25.
- **Verify before finishing.** An unverified success gives no clean evidence; re-run the executable check against system state (11.4, Introduction). Supports a "verified before submit" trajectory metric.
- **Same instrumentation across arms.** Changing instrumentation between experimental arms changes the apparatus and breaks a paired comparison (11.3). T06 must not add spans to one arm of the T14 ablation only.
- **Routing.** The only routing text I could read says each component should run on the least expensive model that can reliably do its role, and that a multi-agent design should beat a single agent on the same tasks (Introduction). The detailed chapter (19.4, "cheapest and sufficient") was **not readable**. Read it before T14 and ADR-016.
- **Not in the readable text:** span structure, stop-reason logging, a tool-call error rate, a loop or repeated-action metric, tokens per resolved task, any prompt-caching metric. T02 defines these itself and must say so. The paper only mentions duration, variance and tool-call count as early signals, and attributes them to its companion catalog (11.3).
- **Authors' caveats that apply:** many results are from repositories of millions of lines (transfer to a small repo is "an assumption to test"); part of the cost chapter is a research agenda; typed traces are shown by demonstration and specification, not by a controlled study (Introduction, Method, Chapter 10).

## Names argus will use

Status is from the spec text read on 2026-11-01. "Dev" = badged Development. "Argus" = a name argus owns, with no semconv status. "Where set" gives the file and line at this commit; T06 may move the exact line but not the data source.

| Attribute | Meaning | Status | Where argus sets it |
|---|---|---|---|
| `gen_ai.operation.name` | Operation kind: `invoke_agent`, `chat`, `execute_tool` | Dev, Required | Span creation, every span (T06) |
| `gen_ai.provider.name` | Provider: `groq`, `mistral`, or `ollama` (argus choice, see note 6) | Dev, Required on `chat` and `invoke_agent` | `chat` span; derived from `base_url` in `argus_core/profile.py:43`, where `ModelClient` is built |
| `gen_ai.request.model` | Model id sent, e.g. `openai/gpt-oss-20b` | Dev, Conditionally Required | `chat` span; the `model` argument of `ModelClient.complete` (`argus_core/client.py`) and of `_ask` (`fix_loop/loop.py:223`, `repro_agent/loop.py:124`) |
| `gen_ai.response.model` | Model id the provider says it used | Dev, Recommended | `chat` span; `Completion.raw["model"]` when present |
| `gen_ai.response.id` | Provider completion id | Dev, Recommended | `chat` span; `Completion.raw["id"]` when present |
| `gen_ai.response.finish_reasons` | Why the model stopped this generation (`string[]`) | Dev, Recommended | `chat` span; `Completion.raw["choices"][0]["finish_reason"]`, live only (note 2) |
| `gen_ai.usage.input_tokens` | Input tokens, cached ones included | Dev, Recommended | `chat` span; `Completion.usage.tokens_in` (`client.py` `Usage`) |
| `gen_ai.usage.output_tokens` | Output tokens | Dev, Recommended | `chat` span; `Completion.usage.tokens_out` |
| `gen_ai.usage.cache_read.input_tokens` | Input tokens served from the provider's cache; set only when non-zero | Dev, Recommended | `chat` span; `Completion.usage.tokens_cached` (parsed from `prompt_tokens_details.cached_tokens`) |
| `gen_ai.request.max_tokens`, `gen_ai.request.temperature`, `gen_ai.request.seed` | Request settings | Dev, Recommended (seed: Conditionally Required) | `chat` span, only if the caller sends them. `ModelClient.complete` sends none today, so these are absent for now |
| `gen_ai.agent.name` | `repro-agent`, `fix-loop`, `best-of-k`, `judge` | Dev, Conditionally Required | `invoke_agent` span; `run_repro` (`repro_agent/loop.py:44`), `run_fix` (`fix_loop/loop.py:40`), and the verify entry points |
| `gen_ai.conversation.id` | Groups all spans of one run; argus uses `TrajectoryMeta.run_id` | Dev, Conditionally Required | `invoke_agent` and `execute_tool` spans; `run_id` argument of `run_fix` / `run_repro` |
| `gen_ai.tool.name` | Tool name, e.g. `submit`; for the repro agent the callable `run_trees` | Dev, Required on `execute_tool` | `execute_tool` span; `name` from `_parse` / `act(name, payload)` at `fix_loop/loop.py:126`, and the `_within(tool_timeout, run_trees, script)` call at `repro_agent/loop.py:99` |
| `gen_ai.tool.type` | `function` | Dev, Recommended | `execute_tool` span; constant |
| `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` | Tool input and output | Dev, **Opt-In** | Not set (content stays off, see above) |
| `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions` | Message content | Dev, **Opt-In** | Not set |
| `error.type` | Class of error: `timeout`, `failed`, `QuotaExceeded`, an HTTP status | **Stable**, Conditionally Required | `chat` and `execute_tool` spans when they end in an error; from `ToolError.error` and `QuotaExceeded` |
| `server.address`, `server.port` | Host and port of the model API | **Stable** (address Recommended; port Conditionally Required when address is set) | `chat` span; parsed from `ModelClient.base_url` |
| `argus.stop_reason` | Why the loop ended: a `StopReason` value | Argus | `invoke_agent` span, set at the end; `reason` in `run_fix` / `run_repro`; also `TrajectoryStep.stop_reason` |
| `argus.step.index` | Position of the step in the trajectory | Argus | `chat` and `execute_tool` spans; `index` in the `for index in range(step_cap)` loops |
| `argus.task.id` | Bench task id | Argus | `invoke_agent` span; `task_id` argument of `run_fix` |
| `argus.tool.error` | Tool error string from the trajectory (`failed`, `timeout`, `not-a-repro`, ...) | Argus | `execute_tool` span; `TrajectoryStep.tool_error` |
| `argus.usage.cost_usd` | List-price dollar equivalent of a call | Argus (proposal) | `chat` span, owned by T11. The Langfuse profile (T08) renames it to the `gen_ai.usage.cost` that Langfuse reads, so argus itself never writes a name that is not in the registry |
| `argus.tier` | `cheap` or `strong`, which tier served the call | Argus (proposal) | `chat` span, owned by T12 |
| `argus.trace.schema_version` | Version of this naming scheme, so a missing field can be told from an older schema (paper, 11.3) | Argus (proposal) | Resource attribute, set once by T06 |

## Open items

- Langfuse and `gen_ai.input.messages`: not confirmed. Matters only if content capture is ever turned on.
- What the spec does with a provider value outside its list: not confirmed (note 6).
- Paper chapters 15 to 20: unread. Chapter 19 (routing) is needed for T14 and ADR-016; the companion repo named on the arXiv page (`sjarmak/engineering-reliable-coding-agents`) or the TeX source is the way in.
- Whether the old `gen_ai.system` and `gen_ai.usage.prompt_tokens` were deprecated with a notice or removed outright: not confirmed. T08 keeps them as aliases either way.
