# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Indicator snapshot of one ticker as of one date (S2-T09). Stub; implemented next."""

from __future__ import annotations

from datetime import date
from typing import Any

from supertrends.indicators.registry import Bundle
from supertrends.scoring.config import ScoringConfig

__all__ = [
    "NOT_SNAPSHOTTED",
    "SCHEMA_VERSION",
    "SNAPSHOT_COVERS",
    "compute_snapshot",
    "snapshot_bytes",
]

SCHEMA_VERSION = 1
SNAPSHOT_COVERS: dict[str, str] = {}
NOT_SNAPSHOTTED: dict[str, str] = {}


def compute_snapshot(bundle: Bundle, cfg: ScoringConfig, as_of: date) -> dict[str, Any]:
    raise NotImplementedError


def snapshot_bytes(doc: dict[str, Any]) -> bytes:
    raise NotImplementedError
