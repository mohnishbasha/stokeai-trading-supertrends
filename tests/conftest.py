# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Shared pytest configuration: hypothesis profiles (TEST_PLAN section 6.6).

Select a profile with the `HYPOTHESIS_PROFILE` environment variable:

* `ci`      100 examples per property, `derandomize=True` so failures reproduce. Set in CI.
* `nightly` 1000 examples (the nightly workflow).
* `dev`     15 examples, the default for local runs so the suite stays fast.

The deadline is disabled in every profile: the indicator properties recompute whole series.
"""

import os

from hypothesis import HealthCheck, settings

_COMMON = {
    "deadline": None,
    "suppress_health_check": [HealthCheck.too_slow, HealthCheck.data_too_large],
}
settings.register_profile("ci", max_examples=100, derandomize=True, **_COMMON)
settings.register_profile("nightly", max_examples=1000, **_COMMON)
settings.register_profile("dev", max_examples=15, **_COMMON)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
