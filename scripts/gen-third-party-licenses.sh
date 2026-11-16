#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# Writes THIRD_PARTY_LICENSES.md and fails on a license outside the allowlist.
# Needs the environment from "uv sync --locked" (pip-licenses is a dev dependency).
set -euo pipefail
cd "$(dirname "$0")/.."

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

uv run --locked pip-licenses --from=mixed --format=json > "$tmp/python.json"
uv export --locked --no-dev --no-hashes --no-emit-project --format requirements-txt > "$tmp/runtime.txt"
uv run --locked python scripts/gen_third_party_licenses.py \
  --python-json "$tmp/python.json" \
  --python-runtime "$tmp/runtime.txt" \
  --npm-lock ui/package-lock.json \
  --output THIRD_PARTY_LICENSES.md
