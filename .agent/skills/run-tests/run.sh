#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
set -euo pipefail
cd "$(dirname "$0")/../../.."
make test
