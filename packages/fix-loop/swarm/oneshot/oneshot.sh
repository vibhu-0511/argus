#!/bin/bash
# usage: oneshot.sh prep <suffix> | show <run id> | answer <run id> < reply
A=/c/Users/vibha/Downloads/data/personal/argus
W=$A/.claude/worktrees/agent-swarm-calibration-1cdc29
export PYTHONPATH="$W/packages/fix-loop/src:$W/packages/argus-core/src:$W/packages/bench/src:$W/packages/verify/src"
cd "$W/packages/fix-loop"
exec $A/.venv/Scripts/python.exe "$W/packages/fix-loop/swarm/oneshot/oneshot.py" "$@"
