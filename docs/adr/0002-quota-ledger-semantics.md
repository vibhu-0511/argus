# ADR-002: Quota ledger semantics

Status: accepted (P0-T08).

## Context

Every later phase calls a model through one client. A free-tier run that keeps going past the daily cap wastes the rest of the day and produces a partial result that looks like a model failure. Cached tokens are a separate number from fresh tokens. The ledger has to say what it counts, when the day rolls, and whether it warns or stops.

## Decision

The ledger hard-stops. `Ledger.call` checks the cap, and only then runs the function that performs the HTTP request. The call that would pass the cap raises `QuotaExceeded` and that function is not entered.

Counting is per model id, not per provider. Groq's published table gives each model its own requests and tokens. A model with no row in `docs/quotas.md` is refused. That is the stand-in for Mistral and hosted Gemma until a live probe fills a number. Inventing a cap would be a second, quieter bug.

The day boundary is UTC. The file stores that date. A process that starts the next UTC day begins at zero. Groq's own reset header was not read, because no API key was available (see `docs/quotas.md`). When a live header names a different reset, the boundary should follow the header.

Cached tokens are stored on their own counter. They are subtracted from the charged total only when that model's row says `cached_counts: false`. Groq's rate-limit page says cached tokens do not count, so those rows are false. Where the provider does not say, the row is absent and the call is refused, rather than guessed.

State is a JSON file. A new process loads it. The unit test covers the stop-before-HTTP case and the restart case.

## Alternatives

- Warn and continue. A warning does not keep the run inside the cap, which is the point of the ledger.
- One counter per provider. The published Groq rows are not one shared bucket, so a provider total would stop a second model that still had room, or let one model spend another's cap.
- A local midnight. The machine is in one timezone and the provider day may be another. UTC is one rule until a header is measured.
- Count every cached token, including Groq's. That would stop a run early against a page that says those tokens do not count.

## Consequences

`docs/quotas.md` wins over any number in `PROJECT.md`. The Groq integers in that file are the published Developer-plan table, and `measured: false` stays until a call with a key records the response headers. P0-T30 is the test that a tiny cap stops a run and keeps the partial result. P8 adds the tenant id to the key. Until then the file is one global day.
