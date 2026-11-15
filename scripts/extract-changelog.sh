#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
set -euo pipefail
VERSION="${1:?Usage: $0 <version>}"
awk "/^## \\[${VERSION}\\]/{found=1; next} found && /^## \\[/{exit} found{print}" CHANGELOG.md
