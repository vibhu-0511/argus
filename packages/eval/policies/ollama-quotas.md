# Quota row for the local model in the P8-T12 ablation

Ollama publishes no cap. The ledger refuses a model that has no row, so this file gives `gemma4:e4b` a self-imposed budget that
is far above what 20 tasks need. It is NOT a provider limit. The ablation table's quota-share cell reads `docs/quotas.md`,
which has no row for this model, so that cell stays a dash.

```yaml
measured: none
method: self-imposed
models:
  gemma4:e4b:
    requests_per_day: 1000000
    tokens_per_day: 1000000000
    requests_per_minute: 100000
    tokens_per_minute: 1000000000
    cached_counts: false
```
