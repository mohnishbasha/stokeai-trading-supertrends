# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""scripts/gen_third_party_licenses.py: allowlist gate and THIRD_PARTY_LICENSES.md output."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    path = REPO / "scripts" / "gen_third_party_licenses.py"
    spec = importlib.util.spec_from_file_location("gen_third_party_licenses", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_third_party_licenses"] = module
    spec.loader.exec_module(module)
    return module


gtl = _load()


@pytest.mark.parametrize(
    "license_text",
    [
        "MIT",
        "MIT License",
        "BSD-3-Clause",
        "BSD License",
        "0BSD",
        "Apache-2.0",
        "Apache Software License",
        "ISC License (ISCL)",
        "Python Software Foundation License",
        "PSF-2.0",
        "Mozilla Public License 2.0 (MPL 2.0)",
        "LGPL-3.0-or-later",
        "GNU Lesser General Public License v3 (LGPLv3)",
        "MIT OR Apache-2.0",
        "Apache Software License; MIT License",
        "(MIT OR GPL-3.0)",
    ],
)
def test_allowed_licenses(license_text: str) -> None:
    assert gtl.is_allowed(license_text)


@pytest.mark.parametrize(
    "license_text",
    [
        "GPL-3.0",
        "GNU General Public License v3 (GPLv3)",
        "AGPL-3.0-only",
        "SSPL-1.0",
        "UNKNOWN",
        "",
        "MIT AND GPL-2.0",
        "BlueOak-1.0.0",
        "CC-BY-4.0",
    ],
)
def test_denied_licenses(license_text: str) -> None:
    assert not gtl.is_allowed(license_text)


def _inputs(tmp_path: Path, py_license: str, npm_license: str) -> list[str]:
    py = tmp_path / "py.json"
    py.write_text(
        json.dumps(
            [
                {"Name": "fastapi", "Version": "1.0", "License": "MIT"},
                {"Name": "badlib", "Version": "2.0", "License": py_license},
            ]
        )
    )
    runtime = tmp_path / "runtime.txt"
    runtime.write_text("fastapi==1.0\n")
    lock = tmp_path / "package-lock.json"
    lock.write_text(
        json.dumps(
            {
                "packages": {
                    "": {"name": "ui"},
                    "node_modules/react": {"version": "19.0.0", "license": "MIT"},
                    "node_modules/tool": {"version": "1.0.0", "license": npm_license, "dev": True},
                }
            }
        )
    )
    out = tmp_path / "THIRD_PARTY_LICENSES.md"
    return [
        "--python-json",
        str(py),
        "--python-runtime",
        str(runtime),
        "--npm-lock",
        str(lock),
        "--output",
        str(out),
    ]


def test_writes_table_and_exits_zero_when_all_allowed(tmp_path: Path) -> None:
    args = _inputs(tmp_path, "BSD-3-Clause", "ISC")
    assert gtl.main(args) == 0
    text = (tmp_path / "THIRD_PARTY_LICENSES.md").read_text()
    assert "| fastapi | 1.0 | MIT | runtime |" in text
    assert "| badlib | 2.0 | BSD-3-Clause | dev |" in text
    assert "| react | 19.0.0 | MIT | runtime |" in text
    assert "| tool | 1.0.0 | ISC | dev |" in text


@pytest.mark.parametrize("bad", ["GPL-3.0", "AGPL-3.0-only", "SSPL-1.0", "UNKNOWN"])
def test_security_license_script_fails_on_gpl_agpl_sspl_or_unknown(
    bad: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """TS-SEC-017."""
    assert gtl.main(_inputs(tmp_path, bad, "MIT")) == 1
    assert f"badlib 2.0: {bad}" in capsys.readouterr().out


def test_fails_on_unknown_npm_license(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gtl.main(_inputs(tmp_path, "MIT", "UNKNOWN")) == 1
    assert "tool 1.0.0: UNKNOWN" in capsys.readouterr().out


def test_reviewed_exception_passes_only_for_dev_dependency(tmp_path: Path) -> None:
    args = _inputs(tmp_path, "MIT", "CC-BY-4.0")
    lock = json.loads(Path(args[5]).read_text())
    lock["packages"]["node_modules/caniuse-lite"] = lock["packages"].pop("node_modules/tool")
    Path(args[5]).write_text(json.dumps(lock))
    assert gtl.main(args) == 0
    lock["packages"]["node_modules/caniuse-lite"]["dev"] = False
    Path(args[5]).write_text(json.dumps(lock))
    assert gtl.main(args) == 1
