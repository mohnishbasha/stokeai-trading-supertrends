#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# Writes VERSION into every checked file that exists (see ARCHITECTURE, Versioning).
set -euo pipefail
cd "$(dirname "$0")/.."
CANONICAL="$(tr -d '[:space:]' < VERSION)"
set_json_version() {
  local file="$1" tmp
  [[ -f "$file" ]] || return 0
  tmp="$(mktemp)"
  jq --arg v "$CANONICAL" '.version = $v' "$file" > "$tmp" && mv "$tmp" "$file"
  echo "wrote $file: $CANONICAL"
}
set_json_version ui/package.json
set_json_version integrations/pi/package.json
if [[ -f ui/package-lock.json ]]; then
  tmp="$(mktemp)"
  jq --arg v "$CANONICAL" '.version = $v | .packages[""].version = $v' ui/package-lock.json > "$tmp" \
    && mv "$tmp" ui/package-lock.json
  echo "wrote ui/package-lock.json: $CANONICAL"
fi
CHART_YAML="deploy/helm/stokeai-supertrends/Chart.yaml"
if [[ -f "$CHART_YAML" ]]; then
  tmp="$(mktemp)"
  sed -e "s/^version:.*/version: ${CANONICAL}/" -e "s/^appVersion:.*/appVersion: \"${CANONICAL}\"/" \
    "$CHART_YAML" > "$tmp" && mv "$tmp" "$CHART_YAML"
  echo "wrote $CHART_YAML: $CANONICAL"
fi
