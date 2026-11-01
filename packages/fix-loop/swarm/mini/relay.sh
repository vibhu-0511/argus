#!/bin/bash
# usage: relay.sh [port]. One relay serves every variant E run. Run it with run_in_background.
A=/c/Users/vibha/Downloads/data/personal/argus
W=$A/.claude/worktrees/agent-swarm-calibration-1cdc29
export PYTHONPATH="$W/packages/fix-loop/src:$W/packages/argus-core/src:$W/packages/bench/src:$W/packages/verify/src"
cd "$W/packages/fix-loop"
exec $A/.venv/Scripts/python.exe swarm/mini/relay.py $1
