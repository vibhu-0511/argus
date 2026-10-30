# argus-core

Shared types, the OpenAI-compatible model client, and the quota ledger. Every other package builds on it.

## Install

From the repo root, with Python 3.12:

```
uv sync
```

## What is in `src/argus_core/`

| File | Holds |
|---|---|
| `types.py` | `Ticket`, `Task`, `Trajectory` (ADR-001), their JSONL round trip, and `dump_schemas` |
| `client.py` | `ModelClient`: one OpenAI-compatible `complete(model, messages)` call. The host is `base_url`, not a code branch |
| `profile.py` | `load_profiles` and `client_from_profile`: read the active block in `config/profiles.md`. A wire format that is not OpenAI-compatible is refused |
| `ledger.py` | `Ledger` and `QuotaExceeded` (ADR-002): refuses a call before the request when it would cross a measured cap. Cached tokens are counted apart |

`schemas/` holds the JSON schemas written by `dump_schemas`: `ticket`, `task`, and `trajectory`.

## Tests

```
uv run pytest packages/argus-core/tests
```
