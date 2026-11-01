# Profiles

The active profile is the block whose `name` matches `active` below. `personal` is the default. Phase files, `PROJECT.md` model and infrastructure tables, and the HTML pages describe `personal`. They are not a second copy of this file.

`argus-core` reads `base_url`, `hosts`, `key_env`, and `wire_format` from the active block (P0-T05). A profile is configuration only while `wire_format` is `openai-compatible`. Anything else is a task rewrite, listed at the bottom.

Do not put a secret in this file. `key_env` is the variable name. Hours and task counts stay 556 h / 255 tasks. A company run does not add a task and does not replace the [ME] loop with a vendor agent product.

The system under test is not a profile switch. Both profiles use [`platform.md`](platform.md): the dcortex Canvas and its Postgres. `database` in the blocks below is Argus's own workflow store at P6, not the airline data.

```yaml
active: personal
```

## personal

The $0 profile. Values below are the ones already stated in `PROJECT.md`. Host URLs were filled by P0-T05 on 2026-10-29 from each provider's docs: [Groq](https://console.groq.com/docs/openai), [Mistral](https://docs.mistral.ai/resources/migration-guides), [Ollama local](https://docs.ollama.com/api/openai-compatibility). The default `base_url` is the cheap-tier host. Point the same client at another host by changing `base_url` and the key.

```yaml
name: personal
spend: "0"
wire_format: openai-compatible
base_url: "https://api.groq.com/openai/v1"
key_env: ARGUS_MODEL_API_KEY
hosts:
  groq: "https://api.groq.com/openai/v1"
  mistral: "https://api.mistral.ai/v1"
  ollama: "http://localhost:11434/v1"
data_policy: free-tier-prompts-may-be-used-for-training
roles:
  fixer: "Devstral 2 / Devstral Small 2"   # Mistral free tier
  cheap: "openai/gpt-oss-20b | qwen/qwen3.8-27b"  # Groq Developer-plan org limits
  judge_cross: "Gemma 4"                   # local Ollama gemma4:e4b
  judge_same: "a Mistral vision model"
  embeddings: "local open model"           # Ollama or sentence-transformers
quotas_file: docs/quotas.md                # P0-T06 measures this; that file wins
prices_file: prices.json                   # does not exist until P5-T11
control_plane: "Render free + FastAPI/DBOS"
database: "Neon free Postgres"
execution_plane: "GitHub Actions"
trace_backend: "OTLP to Langfuse Cloud Hobby"
dashboard: "GitHub Pages"
sandbox_network: none
secrets: "outside the repo (P7-T03). Render environment variables at P6-T12"
system_under_test: config/platform.md
```

## company

Paid model API and paid hosting are allowed only in this block. Leave a field empty until you have a source. Do not copy a personal quota, a personal price, or a Render/Neon measurement into it.

```yaml
name: company
spend: paid
wire_format: ""       # openai-compatible (config-only) or anthropic-messages (rewrites P0-T05)
base_url: ""
key_env: ARGUS_MODEL_API_KEY
data_policy: ""       # re-read the provider's data policy; do not reuse the free-tier sentence
roles:
  fixer: ""
  cheap: ""
  judge_cross: ""     # must be a different family from fixer if ADR-013's self-preference check stays
  judge_same: ""      # empty means that ablation is not run
  embeddings: ""
quotas_file: docs/quotas.company.md   # do not overwrite docs/quotas.md
prices_file: prices.json              # P5-T11 errors on an unknown model id
control_plane: ""     # FastAPI + DBOS can move; the host name is not chosen here
database: ""          # Postgres URL env name, not the URL
execution_plane: "GitHub Actions"  # change only if you mean to leave Actions
trace_backend: ""     # OTLP endpoint; P5-T09 already swaps the exporter endpoint
dashboard: ""
sandbox_network: none # stays none; the model call is outside the container
secrets: ""           # P7-T03 table; never a value in this file
system_under_test: config/platform.md
```

## What a profile switch does not touch

GitHub stays the source of truth (ADR-021). The state machine stays repro → fix → verify → PR → awaiting-qa → done. Checks stay pixel, overflow, axe, console, then the judge. The judge still does not override a passed check run. The sandbox stays `--network none`. Replay still uses the stored Trajectory, not a second live call.

## Where a company value is not a setting

These acceptance lines name the personal profile. A company run does not edit them. It fails the line until the line is rewritten, which this file does not do.

| Id | Why a setting is not enough |
|---|---|
| P0-T05 | Passes only if the same client reaches a mock, Groq, Mistral, and Ollama by `base_url` and key. `wire_format: anthropic-messages` fails that sentence. |
| P0-T06 | `docs/quotas.md` is Groq, Mistral, and a hosted-Gemma check. Company limits go in `docs/quotas.company.md`. |
| P0-T07 | The hard stop stays. Cached-token fields follow whatever `docs/quotas.md` measured. A different cache shape is a ledger change. |
| P3-T17 | mini-swe-agent is pointed at an OpenAI-compatible endpoint. The env var name is not stated in the plan. |
| P4-T11 | The cross-family judge runner is local Gemma on CPU. |
| P4-T16 | The same-family judge is a Mistral vision model. If the fixer is not Mistral, this control is the wrong family. |
| P5-T11 | Unknown model id in `prices.json` is an error. No price is invented here. |
| P5-T15 / ADR-016 | Which stage uses which tier is decided after the routing ablation, not before. |
| P6-T11, P6-T12, P6-T13, P6-T14, P6-T17 / ADR-022 | These measure Render sleep and Neon 100 CU-hours/project. An AWS host makes the numbers inapplicable. The webhook-as-hint design (ADR-021) can stay. |
| P6-T24 | Suspends Neon mid-run. |
| ADR-014 | Best-of-k cost cap. k = 5 multiplies fixer calls. On a paid profile that cap is spend, and the plan does not state a dollar cap. |

P5-T09 is a setting: the same run is viewable in a second OTLP backend by changing the exporter endpoint and the normalizer profile.

## Adding a profile

Copy the `company` block, change `name`, and set `active` to that name. Leave unknown fields empty. Do not add hours.
