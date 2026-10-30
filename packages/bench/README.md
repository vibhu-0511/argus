# bench

## Install

From the repo root, with Python 3.12:

```
uv sync
```

The Playwright package in this directory uses pnpm 10.12.1, the version pinned in the root `package.json`.

## Commands

`uv run bench` from the repo root. The subcommands below are the ones in `src/argus_bench/cli.py`.

| Command | What it does |
|---|---|
| `bench validate <directory>` | Check a task directory against the Task schema |
| `bench score <task> --tree <path>` | Run that task's checks against a checkout |
| `bench golden --all` | Apply each golden patch and score it |
| `bench flake --all` | Repeat checks and quarantine mixed results |
| `bench baseline <task> --tree <path>` | One model call from the ticket and file text |
| `bench mutate --seed <int>` | Write validated CSS mutants for one seed |

`bench score` exits 0 when every check passes, 1 when a check fails, and 2 when the task or tree is missing or the runner crashes.

The mutated task-set hash and seed are in `docs/notes/p0-t26.md`.

Task directories live under `tasks/seeded/` and `tasks/mutated/`.

A task directory contains:

| File | Contents |
|---|---|
| `ticket.json` | Ticket: `id`, `text`, optional `screenshot` (`media_type`, `path` relative to this directory) |
| `bug.patch` | Unified diff that turns the fixed tree into the buggy tree |
| `golden.patch` | Unified diff that turns the buggy tree into the fixed tree |
| `checks.json` | List of checks. Each has `type` (`pixel_diff`, `bounding_box`, `computed_style`) and `params` |
| `meta.json` | `source` (`seeded` or `mutated`), `archetype`, `tier` (`easy`, `medium`, `hard`), optional `seed` |

`bench validate <dir>` exits 0 when the directory matches the Task schema. It exits 1 when a file is missing, empty, or rejected by the schema. `bench golden --all` applies every golden patch on a worktree of the platform repo and scores it. It prints `passed/total` and exits 0 only when every task passes.

`tasks/seeded/bug-17` is BUG-17 from the dcortex bug report: text under 12 px. The patches touch `apps/canvas/src/ops/radar.css` only.

`src/checks.ts` is the Playwright check library: computed style, bounding box, and pixel diff. `pnpm test` runs `tests/checks.spec.ts`, which checks out a clean worktree of the dcortex repo and a second worktree with `.radar-clock-time` changed from 20px to 64px. The same three checks pass on the clean tree and fail on the broken one. Both trees serve the five flows from `config/platform.md`.
