# argus-workbench (P10)

Stub. P10-T16 completes this file.

A local web UI with five screens (Issue, Run, Review, PR, History) over scripted and replayed runs. It binds 127.0.0.1, has no login and calls no model. Every run it makes is SIMULATED or REPLAY and is in no aggregate.

- Start: `uv run --all-packages argus-workbench serve [--port N]` (127.0.0.1 only; there is no `--host`).
- Run folder layout: `docs/architecture/p10.md`, section "Run folder contract".
- Tests: `uv run --all-packages python -m pytest packages/workbench/tests -q`.
- Example run folders for every scenario: `argus_workbench.fixtures.write_all_fixtures(root=...)` (all SIMULATED).
