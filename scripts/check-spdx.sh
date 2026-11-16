#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# Fails when a source file lacks the SPDX header in its first 5 lines.
# Usage: check-spdx.sh [FILE...]   (default: every tracked or new, non-ignored source file)
set -euo pipefail
cd "$(dirname "$0")/.."

LICENSE_LINE="SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0"
COPYRIGHT_LINE="Copyright 2026 Serverless Ventures LLC"

# Owner and runner files are never touched by this project.
EXCLUDE_RE='^(runner\.mk|run-supertrends\.sh|run-supertrends-status\.sh|1|supertrends-build-prompt\.md|logs/.*)$'
SOURCE_RE='(\.(py|ts|tsx|js|mjs|cjs|sh|toml|ya?ml|css|html)|(^|/)(Makefile|Dockerfile[^/]*))$'

files=()
if [[ $# -gt 0 ]]; then
  files=("$@")
else
  while IFS= read -r f; do
    files+=("$f")
  done < <(git ls-files --cached --others --exclude-standard | grep -Ev "$EXCLUDE_RE" | grep -E "$SOURCE_RE" || true)
fi

bad=0
for f in "${files[@]}"; do
  [[ -f "$f" ]] || continue
  head_lines="$(head -n 5 "$f")"
  if [[ "$head_lines" != *"$LICENSE_LINE"* || "$head_lines" != *"$COPYRIGHT_LINE"* ]]; then
    echo "x missing SPDX header: $f"
    bad=1
  fi
done

if [[ "$bad" -ne 0 ]]; then
  echo "Add these two lines as comments at the top of each file:"
  echo "  $LICENSE_LINE"
  echo "  $COPYRIGHT_LINE"
  exit 1
fi
echo "ok SPDX headers present in ${#files[@]} files"
