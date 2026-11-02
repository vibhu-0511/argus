#!/bin/bash
# Driver wrapper for the P5.5-T15 break-it runs. usage: turn_t15.sh <real5|plus-any> start T <task id> | show <run id> | answer <run id> < reply | status <run id>
# Like turn.sh, but with skills on (eval.t15_turn). run id = T-<task id>; the arm picks the run folder and the skills directory.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
: "${ARGUS_PLATFORM_REPO:=C:/Users/vibha/Downloads/data/dcortex/dcortex_claude/dcortex-platform}"
export ARGUS_PLATFORM_REPO
export T15_ARM="$1"; shift
cd "$ROOT" && exec uv run --frozen --all-packages python -m eval.t15_turn "$@"
