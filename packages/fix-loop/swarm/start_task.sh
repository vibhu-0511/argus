#!/bin/bash
# usage: start_task.sh <task suffix, e.g. h05>. Creates the four runs p4b-full-{none,cap,offload,summary}-<suffix>. Slow when the machine is loaded: run it with run_in_background.
D=/c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/swarm
cd /c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop
for s in none cap offload summary; do r=p4b-full-$s-$1; "$D/turn.sh" start ../bench/tasks/seeded/seed-$1 $r $s > /dev/null 2>&1 && echo -n "$r " || echo "FAILED $r"; done; echo
