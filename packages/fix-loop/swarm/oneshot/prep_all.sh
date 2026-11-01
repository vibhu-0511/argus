#!/bin/bash
# usage: prep_all.sh <suffix>...  Prepares the runs one after another (worktree creation on the platform repo is not run in parallel). Use run_in_background.
D=$(dirname "$0")
for s in "$@"; do bash "$D/oneshot.sh" prep "$s" 2>&1 | tail -1 || echo "FAILED $s"; done
