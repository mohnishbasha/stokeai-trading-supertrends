# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""`supertrends config show | validate | export-schema` (ARCHITECTURE section 6, CLI table)."""

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from supertrends.cli.main import CONFIG_INVALID_EXIT, app

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "scoring.yaml"

runner = CliRunner()


def test_cli_config_show_and_validate_unknown_key_fails_naming_key(tmp_path: Path) -> None:
    """TS-CLI-020: show and validate accept the default; an unknown key exits 2 naming it."""
    shown = runner.invoke(app, ["config", "show", "--path", str(DEFAULT_PATH)])
    assert shown.exit_code == 0, shown.output
    assert shown.output.startswith("# config_hash: sha256:")

    valid = runner.invoke(app, ["config", "validate", str(DEFAULT_PATH)])
    assert valid.exit_code == 0, valid.output
    assert valid.output.startswith("valid sha256:")

    raw = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
    raw["surprise"] = 1
    bad = tmp_path / "scoring.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")

    invalid = runner.invoke(app, ["config", "validate", str(bad)])
    assert invalid.exit_code == CONFIG_INVALID_EXIT
    assert "surprise" in invalid.output

    invalid_show = runner.invoke(app, ["config", "show", "--path", str(bad)])
    assert invalid_show.exit_code == CONFIG_INVALID_EXIT


def test_cli_config_export_schema_writes_json_schema(tmp_path: Path) -> None:
    out = tmp_path / "schema.json"
    result = runner.invoke(app, ["config", "export-schema", "--output", str(out)])
    assert result.exit_code == 0, result.output
    schema = json.loads(out.read_text(encoding="utf-8"))
    assert "properties" in schema
