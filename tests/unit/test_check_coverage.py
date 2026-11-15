# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""scripts/check_coverage.py: per-directory thresholds from .coverage-thresholds.toml."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_coverage", REPO / "scripts" / "check_coverage.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_coverage"] = module
    spec.loader.exec_module(module)
    return module


cc = _load()


def _write_xml(root: Path, lines: dict[str, tuple[int, int]]) -> None:
    """lines maps a path under src/pkg to (covered, total)."""
    classes = []
    for name, (covered, total) in lines.items():
        rows = "".join(
            f'<line number="{i}" hits="{1 if i <= covered else 0}"/>' for i in range(1, total + 1)
        )
        classes.append(f'<class filename="{name}"><lines>{rows}</lines></class>')
    xml = (
        f"<coverage><sources><source>{root / 'src' / 'pkg'}</source></sources>"
        f"<packages><package><classes>{''.join(classes)}</classes></package></packages></coverage>"
    )
    (root / "coverage.xml").write_text(xml)


def _setup(tmp_path: Path, threshold: int, covered: int) -> Path:
    (tmp_path / "src" / "pkg" / "core").mkdir(parents=True)
    _write_xml(tmp_path, {"core/a.py": (covered, 10)})
    toml = tmp_path / "t.toml"
    toml.write_text(f'[python]\n"src/pkg/core" = {threshold}\n"src/pkg/later" = 99\n')
    return toml


def test_passes_when_directory_meets_threshold(tmp_path: Path) -> None:
    toml = _setup(tmp_path, threshold=80, covered=9)
    assert cc.check(toml, tmp_path) == []


def test_fails_naming_the_directory_below_threshold(tmp_path: Path) -> None:
    toml = _setup(tmp_path, threshold=95, covered=9)
    failures = cc.check(toml, tmp_path)
    assert len(failures) == 1
    assert "src/pkg/core" in failures[0]
    assert "90.0" in failures[0]


def test_skips_directories_that_do_not_exist_yet(tmp_path: Path) -> None:
    toml = _setup(tmp_path, threshold=50, covered=9)
    assert not any("later" in f for f in cc.check(toml, tmp_path))


def test_typescript_thresholds_read_the_vitest_summary(tmp_path: Path) -> None:
    lib = tmp_path / "ui" / "src" / "lib"
    lib.mkdir(parents=True)
    summary = {
        "total": {"lines": {"total": 10, "covered": 5}},
        str(lib / "x.ts"): {"lines": {"total": 10, "covered": 5}},
    }
    (tmp_path / "ui" / "coverage").mkdir()
    (tmp_path / "ui" / "coverage" / "coverage-summary.json").write_text(json.dumps(summary))
    toml = tmp_path / "t.toml"
    toml.write_text('[typescript]\n"ui/src/lib" = 85\n"ui/src/store" = 85\n')
    failures = cc.check(toml, tmp_path)
    assert failures == ["ui/src/lib: 50.0% < 85%"]


def test_missing_report_for_an_existing_directory_fails(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg" / "core").mkdir(parents=True)
    toml = tmp_path / "t.toml"
    toml.write_text('[python]\n"src/pkg/core" = 80\n')
    with pytest.raises(FileNotFoundError):
        cc.check(toml, tmp_path)
