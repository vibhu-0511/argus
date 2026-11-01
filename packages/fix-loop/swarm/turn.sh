#!/bin/bash
# Driver wrapper. usage: turn.sh start <task dir> <run id> <none|cap|offload|summary> | show <run id> | answer <run id> < reply
W=/c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29
export PYTHONPATH="$W/packages/fix-loop/src:$W/packages/argus-core/src:$W/packages/bench/src:$W/packages/verify/src"
cd "$W/packages/fix-loop"
exec /c/Users/vibha/Downloads/data/personal/argus/.venv/Scripts/python.exe -m fix_loop.turn "$@"
