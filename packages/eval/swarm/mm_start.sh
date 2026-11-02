#!/bin/bash
# usage: mm_start.sh <instance id>... Prepares each run (one git fetch and the issue images: network) and prints its first status line.
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for t in "$@"; do echo "$t: $("$D/mm_turn.sh" start "$t" 2>&1 | tail -1)"; done
