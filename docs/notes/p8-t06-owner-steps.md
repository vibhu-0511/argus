# P8-T06 target-agnostic runner: what was shown, what was not, owner steps

Date: 2026-11-03. **Not run against the real dcortex repo. The box stays unticked.** No dcortex checkout (`ARGUS_PLATFORM_REPO`) was used, and no real fix agent, model or GitHub run was involved. No model was called: the tests fake the fix agent.

## Shown locally (`uv run --all-packages python -m pytest packages/app/tests -q`: 85 passed)

| Claim | Evidence |
|---|---|
| The runner takes start, test, routes and budget from `.argus.yml` | `test_runner.py`; `plan` prints them for two configs with the same code |
| The same runner works on a second repo with a different layout, no code change | `packages/app/tests/fixtures/second-repo` (flat Python package, stdlib server on 127.0.0.1:18765, `unittest`): repro (`exited 1`, routes answered), fix (fake agent, real patch), verify (`exited 0`). Also as a folder of a bigger repo, and with CRLF files |
| No target is written into the runner | a test reads the string literals of `runner.py` for dcortex, canvas, vite, pnpm, npm, docker, the five flows, both ports |
| The dcortex repo can be described with it | `config/dcortex.argus.yml` loads, `plan` prints it, and a test checks its routes are the flows in `config/platform.md`. **Planned, not run** |
| Typed config errors reach the result | a missing test command ends as `MissingFieldError: .argus.yml: missing required field 'test' (the test command)` in `result.json` (the text P8-T22 expects) |

## Not shown

- A run on the dcortex repo. The commands in `config/dcortex.argus.yml` (`docker compose --profile copa-local up --build`, `cd apps/canvas && npm run test`, console on port 19080, the five flows) come from `config/platform.md` and `packages/fix-loop/AGENTS.md`. They were not run. Known problems: the compose start takes minutes (set `ARGUS_START_TIMEOUT`, default 120 s), the app needs a sign-in the routes do not do (they only check that the page answers), and killing the start command does not stop the containers.
- The default fix agent (`argus_app.runner._fix_agent`): wired from `run_fix`, `agent_job._router` and `_execute`, never run. It needs the Docker sandbox image and a model key.
- Install on a bare runner: a tenant's `start` and `test` run on a clean checkout, so their dependencies must be installed by the command itself (`npm ci && npm test`); there is no `setup` field. The onboarding doc says so.
- The sandbox for the fix step is the small no-network image with no toolchain: the model can read and edit files there but cannot run the tenant's tests. The prompt says so; only verify runs them.
- A patch that edits test files could make the tests pass without fixing the bug. Nothing checks for it (a later task).
- `subset install`: `uv sync --package argus-app --locked` is what the workflow runs. A throwaway env (`uv run --isolated --package argus-app --locked`) imported the runner and the fix loop; the workflow itself never ran.

## Owner steps (real dcortex run)

1. Have the dcortex checkout, Docker running, Node 24 and pnpm as in `packages/fix-loop/AGENTS.md`. Set `ARGUS_PLATFORM_REPO` to it.
2. See what would run: `uv run --all-packages python -m argus_app.runner plan config/dcortex.argus.yml`.
3. Copy `config/dcortex.argus.yml` to the repo root as `.argus.yml` in a scratch clone (do not commit it to the private repo). Run the baseline: `ARGUS_TARGET_REPO=<clone> ARGUS_OUT=<empty folder> ARGUS_STEP=repro ARGUS_TICKET_ID=owner/repo#1 ARGUS_RUN_KEY=argus:local:1 ARGUS_START_TIMEOUT=600 uv run --all-packages python -m argus_app.runner`. Read `<folder>/repro/result.json`, then `docker compose --profile copa-local down`.
4. If the commands or routes are wrong, change `config/dcortex.argus.yml` and record what was wrong here. Tick the box only if the baseline and verify (`ARGUS_STEP=verify`, no patch) ran on that clone.
