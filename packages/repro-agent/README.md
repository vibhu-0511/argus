# repro-agent

Turns a ticket into a Playwright script. The script is kept when it fails on the buggy tree and passes on the golden tree.

## Install

From the repo root, with Python 3.12:

```
uv sync
```

## Commands

```
uv run --package repro-agent python -m repro_agent.batch text-only
uv run --package repro-agent python -m repro_agent.batch text-plus-image
```

`text-only` writes `packages/repro-agent/runs/text-only/`. `text-plus-image` writes `packages/repro-agent/runs/text-plus-image/`. Each task directory gets `verdict.json` and `trajectory.jsonl`. The reply is recorded in the runner, so these commands do not call a model provider.
