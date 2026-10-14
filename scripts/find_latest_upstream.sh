#!/usr/bin/env bash
set -euo pipefail

REGISTRY="us-docker.pkg.dev"
IMAGE="apigee-release/apigee-hybrid-helm-charts/apigee-operator"

# Manual test override.
if [[ -n "${SIMULATED_UPSTREAM_VERSION:-}" ]]; then
  echo "version=${SIMULATED_UPSTREAM_VERSION}" >> "$GITHUB_OUTPUT"
  exit 0
fi

URL="https://${REGISTRY}/v2/${IMAGE}/tags/list?n=100"
TMP_FILE="$(mktemp)"

trap 'rm -f "$TMP_FILE"' EXIT

while [[ -n "$URL" ]]; do
  HEADERS="$(mktemp)"
  BODY="$(mktemp)"

  curl -fsSL \
    -D "$HEADERS" \
    -o "$BODY" \
    "$URL"

  # Extract all tags returned by this page.
  python - "$BODY" >> "$TMP_FILE" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

for tag in data.get("tags", []):
    print(tag)
PY

  # OCI pagination uses the Link response header.
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

latest="$(
  python - "$TMP_FILE" <<'PY'
import re
import sys

pattern = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:hotfix\.(\d+))?$"
)

versions = []

with open(sys.argv[1]) as f:
    for line in f:
        version = line.strip()
        match = pattern.match(version)

        if not match:
            continue

        major, minor, patch, hotfix = match.groups()

        key = (
            int(major),
            int(minor),
            int(patch),
            int(hotfix or 0),
        )

        versions.append((key, version))

if versions:
    print(max(versions)[1])
PY
)"

echo "Latest upstream Apigee version: ${latest}"
echo "version=${latest}" >> "$GITHUB_OUTPUT"