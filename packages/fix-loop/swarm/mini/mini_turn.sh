#!/bin/bash
# usage: mini_turn.sh show <run id> | answer <run id> < reply
A=/c/Users/vibha/Downloads/data/personal/argus
W=$A/.claude/worktrees/agent-swarm-calibration-1cdc29
exec $A/.venv/Scripts/python.exe "$W/packages/fix-loop/swarm/mini/mini_turn.py" "$@"
