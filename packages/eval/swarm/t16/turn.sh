#!/bin/bash
# Driver wrapper for the P5.5-T16 stale-skill run. usage: turn.sh show|answer|status|start ... (see eval.t16_turn)
# The file `active` next to this script names the fixture (natural|insistent); the subagents run this script without env.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
: "${ARGUS_PLATFORM_REPO:=C:/Users/vibha/Downloads/data/dcortex/dcortex_claude/dcortex-platform}"
export ARGUS_PLATFORM_REPO
export T16_VARIANT="$(cat "$HERE/active")"
cd "$ROOT" && exec uv run --frozen --all-packages python -m eval.t16_turn "$@"
