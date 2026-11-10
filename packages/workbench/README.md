# argus-workbench (P10)

Stub. P10-T16 completes this file.

A local web UI with five screens (Issue, Run, Review, PR, History) over scripted and replayed runs. It binds 127.0.0.1, has no login and calls no model. Every run it makes is SIMULATED or REPLAY and is in no aggregate.

- Start: `uv run --all-packages argus-workbench serve [--port N]` (127.0.0.1 only; there is no `--host`).
- Run folder layout: `docs/architecture/p10.md`, section "Run folder contract".
- Tests: `uv run --all-packages python -m pytest packages/workbench/tests -q`.
- Example run folders for every scenario: `argus_workbench.fixtures.write_all_fixtures(root=...)` (all SIMULATED).
- Runners (`runner.py`): `ScriptedRunner` plays the five scenarios and `ReplayRunner` plays a stored trajectory; `RunManager` starts, stops and retries runs (`POST /api/runs/{id}/start|stop|retry`).
- `FixLoopRunner` (`fixloop_runner.py`) wraps `fix_loop.run_fix`. **Never run against a real model**: it needs a scripted model function passed in (no default), reads no key, URL or model name, and builds no client. It is not reachable from the HTTP API; only tests and local scripts construct it.
