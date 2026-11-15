# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Domain errors. Every error raised by Super Trends code subclasses SuperTrendsError."""


class SuperTrendsError(Exception):
    """Base class for Super Trends domain errors."""


class ConfigError(SuperTrendsError):
    """Invalid scoring config or environment settings. The message names the offending key."""
