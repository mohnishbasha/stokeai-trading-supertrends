#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
set -euo pipefail
cd "$(dirname "$0")/.."
CANONICAL="$(tr -d '[:space:]' < VERSION)"
if ! [[ "$CANONICAL" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]]; then
  echo "x VERSION is not semver: '$CANONICAL'"; exit 1
fi
check() {
  local actual="$1" file="$2"
  if [[ "$actual" != "$CANONICAL" ]]; then
    echo "x Version mismatch in $file: expected $CANONICAL, got $actual"
    exit 1
  fi
  echo "ok $file: $CANONICAL"
}
CHART_YAML="deploy/helm/stokeai-supertrends/Chart.yaml"
check "$(jq -r .version ui/package.json)" "ui/package.json"
# Guard: integrations/pi arrives in Sprint 7. Remove the guard in that sprint.
if [[ -f integrations/pi/package.json ]]; then
  check "$(jq -r .version integrations/pi/package.json)" "integrations/pi/package.json"
fi
# Guard: the chart arrives in Sprint 3. Remove the guard in that sprint.
if [[ -f "$CHART_YAML" ]]; then
  check "$(awk '/^version:/{print $2}' "$CHART_YAML" | tr -d '"')" "Chart.yaml version"
  check "$(awk '/^appVersion:/{print $2}' "$CHART_YAML" | tr -d '"')" "Chart.yaml appVersion"
fi
echo "All versions consistent: $CANONICAL"
