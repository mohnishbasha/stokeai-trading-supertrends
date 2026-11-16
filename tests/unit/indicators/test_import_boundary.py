# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Indicators are pure: they import nothing from api, cli, mcp, data, or runs (ARCHITECTURE 2)."""

import ast
from pathlib import Path

from supertrends import indicators

FORBIDDEN = ("api", "cli", "mcp", "data", "runs")
ROOT = Path(indicators.__file__).parent


def _imported_modules(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.append(base)
            names += [f"{base}.{alias.name}" for alias in node.names]
    return names


def test_unit_indicators_import_boundary_no_api_cli_mcp_data_runs() -> None:
    """TS-IND-018: no module under supertrends.indicators imports a forbidden package."""
    files = sorted(ROOT.rglob("*.py"))
    assert len(files) >= 12
    offenders: list[str] = []
    for path in files:
        for name in _imported_modules(ast.parse(path.read_text(encoding="utf-8"))):
            parts = name.split(".")
            if parts[0] == "supertrends" and len(parts) > 1 and parts[1] in FORBIDDEN:
                offenders.append(f"{path.name}: {name}")
    assert offenders == []
