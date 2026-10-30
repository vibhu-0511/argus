# Quotas

Checked on 2026-10-29.

Groq was probed with the user-level `ARGUS_MODEL_API_KEY`. One short chat completion was sent per model to `https://api.groq.com/openai/v1/chat/completions`. The key is not stored here. Mistral has no key on the Free plan, so it was not probed.

## Groq

Method: response headers from those calls, on 2026-10-29. Each of `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, and `qwen/qwen3.8-27b` returned `x-ratelimit-limit-requests: 1000` and `x-ratelimit-limit-tokens: 8000`. Groq's [rate-limit page](https://console.groq.com/docs/rate-limits) says the requests header is requests per day and the tokens header is tokens per minute. Those two numbers match the published Developer-plan table (`1K` RPD, `8K` TPM). The page does not call this table a free tier.

Headers did not include requests per minute or tokens per day. The published table still says 30 RPM and 200K TPD. Those two stay published figures, not header measurements. `x-ratelimit-reset-requests` came back between about 1.5 and 3 minutes, so that header is not a calendar-day boundary.

Cached tokens: the same page says cached tokens do not count towards rate limits. The usage objects on these calls had no cached-token field, so this probe did not observe a cache hit. `cached_counts` stays false because of the page.

| Model | Requests/day | Tokens/day | RPM | TPM | Cached tokens count |
|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | 1000, header | 200000, published only | 30, published only | 8000, header | no, from the page; no cache field in usage |
| `openai/gpt-oss-120b` | 1000, header | 200000, published only | 30, published only | 8000, header | no, from the page; no cache field in usage |
| `qwen/qwen3.8-27b` | 1000, header | 200000, published only | 30, published only | 8000, header | no, from the page; no cache field in usage |

## Mistral

Checked on 2026-10-29 in the signed-in console at `console.mistral.ai/api-keys`. The organization is on the Free plan. The page says "Upgrade to use your API keys" and "Upgrade to activate your API keys and access the full API." **New key** is disabled. There is no key to measure, so requests/day, tokens/day, rate limits, and cached-token behaviour are not measured.

The [activate guide](https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key) still says Free mode enables API access with no credit card. That page does not match this console. The console wins. No Mistral row is in the machine-readable block, so the ledger refuses a Mistral model rather than inventing a cap.

## Hosted Gemma

A free hosted Gemma exists. The [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing) page, read 2026-10-29, lists Gemma 4 with free-tier input and output "Free of charge", and the paid column "Not available". Requests/day and tokens/day are not stated on that page. Context caching is "Free of charge" on the free tier. Whether cached tokens count against a cap is not stated. No Gemma row is in the machine-readable block.

The local judge stays Ollama `gemma4:e4b`. That host has no published daily cap in this file.

## Machine-readable limits

The ledger reads this block. `requests_per_day` and `tokens_per_minute` are the header values from 2026-10-29. `tokens_per_day` and `requests_per_minute` are the published table, because those headers were absent.

```yaml
measured: partial
checked: 2026-10-29
method: groq-response-headers-plus-published-table
models:
  openai/gpt-oss-20b:
    requests_per_day: 1000
    tokens_per_day: 200000
    requests_per_minute: 30
    tokens_per_minute: 8000
    cached_counts: false
  openai/gpt-oss-120b:
    requests_per_day: 1000
    tokens_per_day: 200000
    requests_per_minute: 30
    tokens_per_minute: 8000
    cached_counts: false
  qwen/qwen3.8-27b:
    requests_per_day: 1000
    tokens_per_day: 200000
    requests_per_minute: 30
    tokens_per_minute: 8000
    cached_counts: false
```
