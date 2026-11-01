# P4 runtime judge

Checked 2026-10-31.

## Local

The Ollama library page lists `gemma4:e4b` and the command `ollama run gemma4:e4b`. The "E" is effective parameters. The tag is the cross-family judge. This machine does not have the `ollama` command on `PATH`, so the weight file was not pulled. The download cited on the Gemma Ollama page is about 9.6 GB, and the plan's machine is 16 GB with no discrete GPU. Pulling it was not part of this pass.

The runner is `ollama_backend` in `packages/verify/src/verify/judge.py`. It posts the rubric prompt and both PNGs to `http://127.0.0.1:11434/api/chat`. A unit test checks the request body. No pair was judged on CPU. No seconds-per-pair number is recorded from a live call.

## Hosted

A directory page, [llmperks.com/gemma/gemma-4-e4b](https://llmperks.com/gemma/gemma-4-e4b), updated 2026-10-18, lists one free route: Together AI, model id `google/gemma-4-E4B-it`, fair use that depends on server load, and an API key. This pass did not call that API and did not read a quota off a provider console. `docs/quotas.md` has no Together row. A key-gated fair-use listing is not a measured free quota.

## Decision

Runtime judging stays local Ollama `gemma4:e4b`. Hosted Gemma is not selected. Until a person labels the 100 pairs and a local run produces an α, the judge is advisory (ADR-013).

Update 2026-10-31: Ollama 0.40.13 is installed and `gemma4:e4b` was pulled (6.6 GB on disk, about 2 GB resident on CPU). A pair of two 1280x800 screenshots takes about 72 s. See `docs/notes/p4-finish.md`.
