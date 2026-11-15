# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Persistence of indicator snapshots (S2-T09). Stub; implemented next."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from supertrends.scoring.config import ScoringConfig

__all__ = [
    "SnapshotConflictError",
    "SnapshotSummary",
    "compute_and_store",
    "read_snapshot",
    "write_snapshot",
]


class SnapshotConflictError(Exception):
    """A different snapshot already exists for the run and symbol."""


class SnapshotSummary:
    stored: list[str]
    unchanged: list[str]
    skipped: dict[str, str]


def write_snapshot(session: Session, run_id: str, symbol: str, doc: dict[str, Any]) -> str:
    raise NotImplementedError


def read_snapshot(session: Session, run_id: str, symbol: str) -> dict[str, Any] | None:
    raise NotImplementedError


def compute_and_store(
    session: Session, run_id: str, symbols: Sequence[str], cfg: ScoringConfig, as_of: date
) -> SnapshotSummary:
    raise NotImplementedError
