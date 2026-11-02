#!/bin/bash
# usage: start_task.sh <A|B> <task id>... Creates the run(s) <variant>-<task id> and prints each one's first status line.
# Slow on a loaded machine (a platform worktree per run): run it with run_in_background.
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
v=$1; shift
for t in "$@"; do echo "$v-$t: $("$D/turn.sh" start "$v" "$t" 2>&1 | tail -1)"; done
