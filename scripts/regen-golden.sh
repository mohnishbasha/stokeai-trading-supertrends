#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# Regenerates the derived golden hashes (tests/golden/*.sha256) under the golden policy
# (TEST_PLAN 5.5 item 3). It never touches tests/golden/tradingview or tests/golden/handcomputed.
# Usage: regen-golden.sh --reason "why the output legitimately changed" [--check]
#   --check   recompute and compare with the committed hashes; write nothing (exit 1 on drift)
# Put the reason in the PR body (section "Golden regeneration").
set -euo pipefail
cd "$(dirname "$0")/.."

reason=""
check=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reason)
      if [[ $# -lt 2 ]]; then
        echo "x --reason needs a value" >&2
        exit 2
      fi
      reason="$2"
      shift 2
      ;;
    --check)
      check=1
      shift
      ;;
    *)
      echo "x unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${reason//[[:space:]]/}" ]]; then
  echo "x refusing to run without --reason \"...\" (golden policy, TEST_PLAN 5.5)" >&2
  exit 2
fi

if [[ $check -eq 1 ]]; then
  status=0
  while read -r name value; do
    committed="$(tr -d '[:space:]' <"tests/golden/${name}.sha256")"
    if [[ "$committed" == "$value" ]]; then
      echo "ok $name $value"
    else
      echo "x $name drifted: committed $committed, computed $value"
      status=1
    fi
  done < <(uv run python -m tests.golden.determinism)
  exit "$status"
fi

uv run python -m tests.golden.determinism --write
echo "regenerated golden hashes. Reason: $reason"
echo "Add this reason to the PR body under 'Golden regeneration'."
