#!/usr/bin/env bash
set -euo pipefail

REGISTRY="us-docker.pkg.dev"
IMAGE="apigee-release/apigee-hybrid-helm-charts/apigee-operator"

line="${1:?support line X.Y required}"

# Validate X.Y input.
if [[ ! "$line" =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid support line: $line" >&2
  exit 1
fi

# Manual test override.
if [[ -n "${SIMULATED_UPSTREAM_VERSION:-}" ]]; then
  version="${SIMULATED_UPSTREAM_VERSION}"

  if [[ "$version" != "$line".* ]]; then
    echo "Version $version does not belong to support line $line" >&2
    echo "version=" >> "$GITHUB_OUTPUT"
    exit 0
  fi

  echo "version=$version" >> "$GITHUB_OUTPUT"
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

latest="$(
  python - "$TMP_FILE" "$line" <<'PY'
import re
import sys

filename = sys.argv[1]
support_line = sys.argv[2]

wanted_major, wanted_minor = map(int, support_line.split("."))

pattern = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:hotfix\.(\d+))?$"
)

versions = []

with open(filename) as f:
    for line in f:
        version = line.strip()
        match = pattern.match(version)

        if not match:
            continue

        major, minor, patch, hotfix = match.groups()

        major = int(major)
        minor = int(minor)

        if (major, minor) != (wanted_major, wanted_minor):
            continue

        key = (
            major,
            minor,
            int(patch),
            int(hotfix or 0),
        )

        versions.append((key, version))

if versions:
    print(max(versions)[1])
PY
)"

echo "Latest Apigee ${line}.x version: ${latest}"
echo "version=${latest}" >> "$GITHUB_OUTPUT"