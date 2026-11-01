#!/bin/bash
# usage: mini_run.sh <seeded task suffix, e.g. h05> <run id> [relay port]. Blocks until the run ends: use run_in_background.
A=/c/Users/vibha/Downloads/data/personal/argus
W=$A/.claude/worktrees/agent-swarm-calibration-1cdc29
export PYTHONPATH="$W/packages/fix-loop/src:$W/packages/argus-core/src:$W/packages/bench/src:$W/packages/verify/src"
export ARGUS_PYTHON=$A/.venv/Scripts/python.exe
cd "$W/packages/fix-loop"
exec $A/.local/mini-venv/Scripts/python.exe swarm/mini/mini_run.py "../bench/tasks/seeded/seed-$1" "$2" $3
