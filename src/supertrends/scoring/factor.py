# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Factor framework skeleton (S3-T01). Replaced by the implementation in the next commit."""

from datetime import date
from typing import Any

CONFIDENCE_INPUT_PATHS: tuple[str, ...] = ()
REGIME_INPUT_PATHS: tuple[str, ...] = ()
SELECTION_INPUT_PATHS: tuple[str, ...] = ()


class Quality(str):  # noqa: SLOT000
    OK = "ok"


class EvidenceItem:
    def __init__(self, **kwargs: Any) -> None:
        raise NotImplementedError("S3-T01")


class FactorResult:
    def __init__(self, **kwargs: Any) -> None:
        raise NotImplementedError("S3-T01")


class FactorContext:
    def __init__(self, **kwargs: Any) -> None:
        raise NotImplementedError("S3-T01")


class Factor:
    pass


class FactorRegistry:
    def __init__(self) -> None:
        raise NotImplementedError("S3-T01")


class ReasonTemplate:
    def __init__(self, *args: Any) -> None:
        raise NotImplementedError("S3-T01")


def format_number(value: Any) -> str:
    raise NotImplementedError("S3-T01")


def expand_input_paths(paths: tuple[str, ...], config: Any) -> tuple[str, ...]:
    raise NotImplementedError("S3-T01")


def get_path(snapshot: Any, path: str) -> Any:
    raise NotImplementedError("S3-T01")


_ = date
