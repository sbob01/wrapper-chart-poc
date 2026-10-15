#!/usr/bin/env bash
set -euo pipefail

REGISTRY="us-docker.pkg.dev"
IMAGE="apigee-release/apigee-hybrid-helm-charts/apigee-operator"

MAX_LINES="${1:-5}"

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

# Manual test override.
if [[ -n "${SIMULATED_UPSTREAM_VERSIONS:-}" ]]; then
  printf '%s\n' $SIMULATED_UPSTREAM_VERSIONS > "$TMP_FILE"
else
  URL="https://${REGISTRY}/v2/${IMAGE}/tags/list?n=100"

  while [[ -n "$URL" ]]; do
    HEADERS="$(mktemp)"
    BODY="$(mktemp)"

    curl -fsSL \
      -D "$HEADERS" \
      -o "$BODY" \
      "$URL"

    python - "$BODY" >> "$TMP_FILE" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

for tag in data.get("tags", []):
    print(tag)
PY

    LINK="$(
      grep -i '^link:' "$HEADERS" \
        | sed -n 's/^[Ll]ink:[[:space:]]*<\([^>]*\)>.*/\1/p' \
        | tr -d '\r' \
        || true
    )"

    rm -f "$HEADERS" "$BODY"

    if [[ -z "$LINK" ]]; then
      URL=""
    elif [[ "$LINK" == http* ]]; then
      URL="$LINK"
    else
      URL="https://${REGISTRY}${LINK}"
    fi
  done
fi

python - "$TMP_FILE" "$MAX_LINES" <<'PY'
import json
import re
import sys

filename = sys.argv[1]
max_lines = int(sys.argv[2])

pattern = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:hotfix\.(\d+))?$"
)

lines = set()

with open(filename) as f:
    for raw_line in f:
        version = raw_line.strip()
        match = pattern.match(version)

        if not match:
            continue

        major, minor, patch, hotfix = match.groups()

        lines.add((int(major), int(minor)))

# Sort semantically and keep only the newest N support lines.
lines = sorted(lines)[-max_lines:]

result = [
    f"{major}.{minor}"
    for major, minor in lines
]

print(json.dumps(result, indent=2))
PY