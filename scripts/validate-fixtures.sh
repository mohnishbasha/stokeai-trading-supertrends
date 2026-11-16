#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# Validates committed fixtures: the synthetic dataset hash (TS-ING-003) and the golden policy
# directories exist. Exits non-zero on any mismatch.
set -euo pipefail
cd "$(dirname "$0")/.."

for d in tests/golden/handcomputed tests/golden/tradingview; do
  if [[ ! -d "$d" ]]; then
    echo "x missing golden directory: $d" >&2
    exit 1
  fi
done

committed="$(tr -d '[:space:]' <tests/golden/synthetic_dataset.sha256)"
computed="$(uv run python -m tests.golden.determinism | awk '$1 == "synthetic_dataset" {print $2}')"
if [[ "$committed" != "$computed" ]]; then
  echo "x synthetic dataset hash drifted: committed $committed, computed $computed" >&2
  exit 1
fi
echo "ok synthetic dataset hash $computed"
