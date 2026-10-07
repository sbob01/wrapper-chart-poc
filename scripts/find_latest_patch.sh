#!/usr/bin/env bash
set -euo pipefail

# Replace later with a real query that returns the highest upstream X.Y.Z
# matching the requested X.Y support line.
#
# For manual tests you can pass SIMULATED_UPSTREAM_VERSION. The script rejects
# versions outside the requested support line.

line="${1:?support line X.Y required}"
version="${SIMULATED_UPSTREAM_VERSION:-}"

if [[ -z "$version" ]]; then
  echo "version=" >> "$GITHUB_OUTPUT"
  exit 0
fi

if [[ "$version" != "$line".* ]]; then
  echo "Simulated version $version does not belong to support line $line" >&2
  echo "version=" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo "version=$version" >> "$GITHUB_OUTPUT"
