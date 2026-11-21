# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Daily run orchestration: state machine, pipeline, atomic publication (FR-901 to FR-906).

Entry points:

* `orchestrator.execute_run`: run one trade date inline (CLI `supertrends run daily`).
* `service`: functions the API (S3-T09) and a worker call to trigger runs and read results.
"""
