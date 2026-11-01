#!/bin/bash
# Driver wrapper for the P5-T14 Claude-session run. usage: turn.sh start <A|B> <task id> | show <run id> | answer <run id> < reply
# run id = <variant>-<task id>, e.g. B-seed-h05. Needs the repro rig up (repro-rig.sh up) and node_modules in the repo root.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# this machine's platform checkout (config/platform.md names the repo; the path is local)
: "${ARGUS_PLATFORM_REPO:=C:/Users/vibha/Downloads/data/dcortex/dcortex_claude/dcortex-platform}"
export ARGUS_PLATFORM_REPO
cd "$ROOT" && exec uv run --frozen --all-packages python -m eval.t14_turn "$@"
