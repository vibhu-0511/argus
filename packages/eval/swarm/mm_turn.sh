#!/bin/bash
# Driver wrapper for the P5-T20 argus fix-loop run with Claude sessions as the model.
# usage: mm_turn.sh start <instance id> | show <id> | answer <id> < reply | status <id>
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# run folders (a checkout each) live outside the repo on a short path: wp-calypso paths are deep (this machine's folder; set MM_RUNS to move it)
: "${MM_RUNS:=C:/swebench-run/argus-run}"
export MM_RUNS PYTHONUTF8=1
cd "$ROOT" && exec uv run --frozen --all-packages python -m eval.mm_turn "$@"
