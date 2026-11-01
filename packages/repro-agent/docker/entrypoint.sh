#!/bin/sh
set -eu
dir=$(mktemp -d /tmp/argus-user-data.XXXXXX)
export ARGUS_USER_DATA_DIR="$dir"
printf 'user-data-dir=%s\n' "$dir"
script=${1:-sample.mjs}
case "$script" in
  sample.mjs|probe-net.mjs|probe-app.mjs) ;;
  *) echo "not-allowed" >&2; exit 2 ;;
esac
exec node "/opt/argus-repro/$script"
