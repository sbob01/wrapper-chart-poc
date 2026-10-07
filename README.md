# Apigee Hybrid wrapper - workflow prototype

Minimal repository for testing two independent lifecycle workflows around an Apigee Hybrid wrapper chart.

## Repository layout

```text
.github/workflows/
  follow-latest.yml
  maintain-supported-lines.yml
chart-wrapper/
  Chart.yaml
  values.yaml
  values.schema.json
  templates/configmap.yaml
config/
  supported-lines.json
scripts/
  find_latest_upstream.sh
  find_latest_patch.sh
  version_logic.py
```

## Lifecycle model

`main` follows the newest upstream line:

- upstream patch -> wrapper patch +1
- upstream minor -> wrapper minor +1 and patch=0
- upstream major -> wrapper major +1, minor=0, patch=0

Support branches are named `release/apigee-X.Y` and may only consume newer patches from that same upstream `X.Y` line.

## Important prototype choice

Real upstream discovery is intentionally not implemented yet. The adapter scripts are the only files that need replacement when the real Apigee version source is decided:

- `scripts/find_latest_upstream.sh`
- `scripts/find_latest_patch.sh`

Until then, both workflows support `workflow_dispatch` with `simulated_upstream_version` so the versioning behaviour can be tested immediately.

## First test

1. Push the repository to GitHub.
2. Before testing the maintenance workflow, create branches matching `config/supported-lines.json`, for example:

```bash
git branch release/apigee-1.14
git branch release/apigee-1.15
git push origin release/apigee-1.14 release/apigee-1.15
```

3. Actions -> `Follow latest Apigee line` -> Run workflow.
4. Enter `1.15.1`: the wrapper changes from `1.15.0` to `1.15.1`.
5. Enter `1.16.0`: the wrapper changes from `1.15.0` to `1.16.0` in a clean checkout and reports that a support branch should be preserved.
6. Leave `persist_changes=false` for dry runs.

For support-line testing, run `Maintain supported Apigee lines`, select `support_line=1.15`, and simulate `1.15.1`.

## ECR

Publishing is deliberately simulated by:

```text
tratando de subir x.y.z
```

The workflows contain comments showing where `helm package`, AWS OIDC authentication, ECR login and `helm push` would eventually be placed.

## Notes

The dependency repository in `Chart.yaml` is a placeholder, so actual dependency download/lint is not expected to work until the real Apigee chart source is configured.
