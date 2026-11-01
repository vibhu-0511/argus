#!/bin/bash
# Light status: finished runs per task and verdict counts. usage: status.sh
cd /c/Users/vibha/Downloads/data/personal/argus/.claude/worktrees/agent-swarm-calibration-1cdc29/packages/fix-loop/runs
fin=0
for d in p4b-full-*/; do [ -f $d/verdict.json ] && fin=$((fin+1)); done
echo "runs with a verdict: $fin"
for t in e01 e02 e03 e04 e06 e09 e10 m01 m02 m03 m04 m05 m06 m07 m08 m09 h01 h02 h03 h04 h05 h06 h07 h08 h09 h10; do n=0; for s in none cap offload summary; do [ -f p4b-full-$s-$t/verdict.json ] && n=$((n+1)); done; echo -n "$t:$n/4 "; done; echo
for d in p4b-full-*/; do [ -f $d/verdict.json ] && tr -d '\n ' < $d/verdict.json | sed -E 's/.*"verdict":"([^"]*)".*/\1/' && echo; done | sort | uniq -c
