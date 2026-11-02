#!/bin/bash
# usage: repro-rig.sh up|down|status. Canvas (Vite on 127.0.0.1) + the sandbox network for the repro stage. Start it once, before any run.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
: "${ARGUS_PLATFORM_REPO:=C:/Users/vibha/Downloads/data/dcortex/dcortex_claude/dcortex-platform}"
export ARGUS_PLATFORM_REPO
cd "$ROOT" && exec uv run --frozen --all-packages python -m repro_agent.trees "$@"
