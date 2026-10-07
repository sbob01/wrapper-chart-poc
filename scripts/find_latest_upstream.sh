#!/usr/bin/env bash
set -euo pipefail

# This is deliberately a replaceable adapter.
# Later, replace this file with the real lookup against the Apigee Hybrid
# upstream source (Helm repo, OCI registry, GitHub releases, Google endpoint...).
#
# For now the workflow can be tested by passing SIMULATED_UPSTREAM_VERSION via
# workflow_dispatch. A scheduled run without that value reports no candidate.

if [[ -n "${SIMULATED_UPSTREAM_VERSION:-}" ]]; then
  echo "version=${SIMULATED_UPSTREAM_VERSION}" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo "version=" >> "$GITHUB_OUTPUT"
