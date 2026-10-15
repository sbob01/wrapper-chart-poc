#!/usr/bin/env bash
set -euo pipefail

MAX_VERSIONS="${1:-12}"
MAX_LINES="${2:-5}"

if [[ -z "${SIMULATED_UPSTREAM_VERSIONS:-}" ]]; then
  echo "SIMULATED_UPSTREAM_VERSIONS is not set" >&2
  exit 1
fi

printf '%s\n' $SIMULATED_UPSTREAM_VERSIONS \
  | head -n "$MAX_VERSIONS" \
  | awk -F. 'NF >= 2 { print $1 "." $2 }' \
  | sort -Vu \
  | tail -n "$MAX_LINES" \
  | awk '
      BEGIN { print "[" }
      {
        if (NR > 1) print ","
        printf "  \"%s\"", $0
      }
      END {
        if (NR > 0) print ""
        print "]"
      }
    '