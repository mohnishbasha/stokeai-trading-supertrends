# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Enforce per-directory line coverage thresholds from .coverage-thresholds.toml.

Python coverage comes from coverage.xml (pytest-cov), TypeScript from
ui/coverage/coverage-summary.json (Vitest json-summary). Directories that do not
exist yet are skipped, so thresholds for later sprints can live in the file now.
"""

from __future__ import annotations

import json
import sys
import tomllib
import xml.etree.ElementTree as ET  # parses our own coverage report, not untrusted input
from collections.abc import Callable
from pathlib import Path

Lines = dict[str, tuple[int, int]]

TS_SUMMARY = Path("ui/coverage/coverage-summary.json")


def _python_lines(root: Path) -> Lines:
    tree = ET.parse(root / "coverage.xml")  # noqa: S314
    sources = [Path(s.text or "") for s in tree.iter("source")]
    result: Lines = {}
    for cls in tree.iter("class"):
        filename = cls.get("filename", "")
        path = next(
            (s / filename for s in sources if (s / filename).exists()),
            sources[0] / filename if sources else Path(filename),
        )
        lines = list(cls.iter("line"))
        covered = sum(1 for line in lines if int(line.get("hits", "0")) > 0)
        result[_rel(path, root)] = (covered, len(lines))
    return result


def _ts_lines(root: Path, summary: Path) -> Lines:
    data = json.loads((root / summary).read_text())
    result: Lines = {}
    for key, value in data.items():
        if key == "total":
            continue
        lines = value["lines"]
        result[_rel(Path(key), root)] = (int(lines["covered"]), int(lines["total"]))
    return result


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _evaluate(
    thresholds: dict[str, int], root: Path, load: Callable[[], Lines], failures: list[str]
) -> None:
    present = {d: t for d, t in thresholds.items() if (root / d).is_dir()}
    if not present:
        return
    lines = load()
    for directory, threshold in present.items():
        prefix = directory.rstrip("/") + "/"
        covered = sum(c for f, (c, _) in lines.items() if f.startswith(prefix))
        total = sum(t for f, (_, t) in lines.items() if f.startswith(prefix))
        if total == 0:
            continue
        percent = 100.0 * covered / total
        if percent < threshold:
            failures.append(f"{directory}: {percent:.1f}% < {threshold}%")


def check(config: Path, root: Path) -> list[str]:
    """Return one message per directory below its threshold."""
    thresholds = tomllib.loads(config.read_text())
    failures: list[str] = []
    _evaluate(thresholds.get("python", {}), root, lambda: _python_lines(root), failures)
    ts = thresholds.get("typescript", {})
    ui = {d: t for d, t in ts.items() if d.startswith("ui/")}
    pi = {d: t for d, t in ts.items() if d.startswith("integrations/pi/")}
    _evaluate(ui, root, lambda: _ts_lines(root, TS_SUMMARY), failures)
    _evaluate(
        pi,
        root,
        lambda: _ts_lines(root, Path("integrations/pi/coverage/coverage-summary.json")),
        failures,
    )
    return failures


def main(argv: list[str]) -> int:
    config = Path(argv[1] if len(argv) > 1 else ".coverage-thresholds.toml")
    failures = check(config, Path.cwd())
    for failure in failures:
        print(f"x coverage below threshold: {failure}")  # noqa: T201
    if not failures:
        print("ok coverage thresholds met")  # noqa: T201
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
