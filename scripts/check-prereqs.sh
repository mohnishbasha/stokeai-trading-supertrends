#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# Checks the local toolchain for "make setup". Prints what is missing and how to install it.
set -euo pipefail
missing=0

# version_ge A B: true when dotted version A >= B.
version_ge() {
  [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]
}

need() {
  local tool="$1" min="$2" actual="$3" hint="$4"
  if [[ -z "$actual" ]]; then
    echo "x $tool is missing (need >= $min). Install: $hint"
    missing=1
  elif [[ "$min" != "any" ]] && ! version_ge "$actual" "$min"; then
    echo "x $tool $actual is too old (need >= $min). Install: $hint"
    missing=1
  else
    echo "ok $tool $actual"
  fi
}

ver() {
  # First dotted number in the output of the given command, or empty if it fails.
  "$@" 2>/dev/null | grep -Eo '[0-9]+(\.[0-9]+)+' | head -n1 || true
}

need python3 3.12 "$(ver python3 --version)" "https://www.python.org/downloads/ or uv python install 3.12"
need uv 0.5 "$(ver uv --version)" "https://docs.astral.sh/uv/getting-started/installation/"
need node 22 "$(ver node --version)" "https://nodejs.org/ (22 LTS, see .nvmrc)"
need npm any "$(ver npm --version)" "ships with Node.js"
need docker 27 "$(ver docker version --format '{{.Client.Version}}')" "https://docs.docker.com/get-docker/"
need "docker buildx" any "$(ver docker buildx version)" "https://docs.docker.com/build/install-buildx/"
need make any "$(ver make --version)" "your OS package manager"
need jq any "$(ver jq --version)" "https://jqlang.org/download/"
need git any "$(ver git --version)" "https://git-scm.com/downloads"

if [[ "$missing" -ne 0 ]]; then
  echo "Prerequisites missing. kind, kubectl, helm, cosign, and trivy are only needed for cluster and release paths."
  exit 1
fi
echo "All prerequisites present."
