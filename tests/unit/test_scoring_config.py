# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Scoring config schema and hash (S0-T09, ARCHITECTURE section 13)."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from supertrends.cli.main import app
from supertrends.errors import ConfigError
from supertrends.scoring.config import (
    FACTOR_IDS,
    ScoringConfig,
    config_hash,
    json_schema,
    load_scoring_config,
    parse_scoring_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "config" / "scoring.yaml"


@pytest.fixture
def raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(DEFAULT_PATH.read_text())
    return data


def _reverse_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _reverse_keys(value[k]) for k in reversed(list(value))}
    return value


def test_config_load_default_file_succeeds() -> None:
    cfg = load_scoring_config(DEFAULT_PATH)
    assert isinstance(cfg, ScoringConfig)
    assert cfg.scoring.version == 2
    assert cfg.supertrend.atr_length == 10
    assert cfg.supertrend.factor == 3.0
    assert sum(cfg.weights.as_dict().values()) == pytest.approx(100)


def test_config_default_matches_appendix_e_values() -> None:
    cfg = load_scoring_config(DEFAULT_PATH)
    assert cfg.weights.as_dict() == {
        "supertrend": 20,
        "sma": 7,
        "macd": 8,
        "divergence": 9,
        "mean_reversion": 7,
        "fibonacci": 5,
        "levels": 7,
        "volatility": 4,
        "volume_osc": 6,
        "flow": 9,
        "fundamentals": 8,
        "ripster": 10,
    }
    assert cfg.thresholds.buy_display_min == 65
    assert cfg.thresholds.sell_display_max == 35
    assert cfg.selection.max_buys == 3
    assert cfg.selection.max_sells == 2
    assert cfg.benchmarks == ["SPY", "QQQ"]
    assert cfg.track_record.horizons_days == [1, 5, 10, 20]


def test_config_unknown_top_level_key_fails_naming_key(raw: dict[str, Any]) -> None:
    raw["surprise"] = 1
    with pytest.raises(ConfigError, match="surprise"):
        parse_scoring_config(raw)


def test_config_unknown_nested_key_fails_naming_key(raw: dict[str, Any]) -> None:
    raw["supertrend"]["atr_lenght"] = 10
    with pytest.raises(ConfigError, match=r"supertrend\.atr_lenght"):
        parse_scoring_config(raw)


def test_config_negative_weight_fails_naming_key(raw: dict[str, Any]) -> None:
    raw["weights"]["sma"] = -5
    raw["weights"]["supertrend"] = 32
    with pytest.raises(ConfigError, match=r"weights\.sma"):
        parse_scoring_config(raw)


def test_config_weights_not_summing_to_100_fails_validation_naming_key(
    raw: dict[str, Any],
) -> None:
    """TS-REG-006: weights that do not sum to 100 are rejected, naming the key."""
    raw["weights"]["sma"] = 11
    with pytest.raises(ConfigError, match="weights"):
        parse_scoring_config(raw)


def test_config_missing_required_key_fails_naming_key(raw: dict[str, Any]) -> None:
    del raw["macd"]["signal"]
    with pytest.raises(ConfigError, match=r"macd\.signal"):
        parse_scoring_config(raw)


def test_config_unknown_regime_multiplier_factor_fails(raw: dict[str, Any]) -> None:
    raw["regime"]["multipliers"]["trending"]["vibes"] = 1.1
    with pytest.raises(ConfigError, match="vibes"):
        parse_scoring_config(raw)


def test_config_thresholds_sell_not_below_buy_fails(raw: dict[str, Any]) -> None:
    raw["thresholds"]["sell_display_max"] = 70
    with pytest.raises(ConfigError, match="sell_display_max"):
        parse_scoring_config(raw)


def test_config_ranging_max_above_trending_min_fails(raw: dict[str, Any]) -> None:
    raw["regime"]["ranging_max"] = 30
    with pytest.raises(ConfigError, match="ranging_max"):
        parse_scoring_config(raw)


def test_config_benchmarks_must_include_spy_and_qqq(raw: dict[str, Any]) -> None:
    raw["benchmarks"] = ["SPY"]
    with pytest.raises(ConfigError, match="benchmarks"):
        parse_scoring_config(raw)


def test_config_horizons_must_ascend(raw: dict[str, Any]) -> None:
    raw["track_record"]["horizons_days"] = [5, 1]
    with pytest.raises(ConfigError, match="horizons_days"):
        parse_scoring_config(raw)


def test_config_omitted_regime_multipliers_default_to_one() -> None:
    cfg = load_scoring_config(DEFAULT_PATH)
    trending = cfg.regime.multipliers["trending"]
    assert set(trending) == set(FACTOR_IDS)
    assert trending["supertrend"] == 1.25
    assert trending["flow"] == 1.0
    assert all(v == 1.0 for v in cfg.regime.multipliers["transitional"].values())


def test_config_hash_has_sha256_prefix_and_64_hex() -> None:
    digest = config_hash(load_scoring_config(DEFAULT_PATH))
    assert digest.startswith("sha256:")
    assert len(digest.removeprefix("sha256:")) == 64


def test_config_hash_stable_across_key_order(raw: dict[str, Any]) -> None:
    reordered = _reverse_keys(copy.deepcopy(raw))
    assert list(reordered) != list(raw)
    assert config_hash(parse_scoring_config(raw)) == config_hash(parse_scoring_config(reordered))


def test_config_hash_int_and_float_normalized(raw: dict[str, Any]) -> None:
    as_float = copy.deepcopy(raw)
    as_float["supertrend"]["factor"] = 3
    assert config_hash(parse_scoring_config(raw)) == config_hash(parse_scoring_config(as_float))


def test_config_hash_changes_with_scoring_version(raw: dict[str, Any]) -> None:
    bumped = copy.deepcopy(raw)
    bumped["scoring"]["version"] = raw["scoring"]["version"] + 1
    assert config_hash(parse_scoring_config(raw)) != config_hash(parse_scoring_config(bumped))


def test_config_json_schema_forbids_extra_keys() -> None:
    schema = json_schema()
    assert schema["additionalProperties"] is False
    assert "weights" in schema["properties"]
    json.dumps(schema)


def test_config_load_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_scoring_config(tmp_path / "nope.yaml")


def test_config_load_non_mapping_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- 1\n- 2\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_scoring_config(path)


def test_cli_config_validate_default_prints_valid_and_hash() -> None:
    result = CliRunner().invoke(app, ["config", "validate", str(DEFAULT_PATH)])
    assert result.exit_code == 0
    assert result.output.startswith("valid sha256:")


def test_cli_config_show_and_validate_unknown_key_fails_naming_key(
    raw: dict[str, Any], tmp_path: Path
) -> None:
    raw["supertrend"]["bogus"] = 1
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(raw))
    result = CliRunner().invoke(app, ["config", "validate", str(path)])
    assert result.exit_code == 2
    assert "supertrend.bogus" in result.output


def test_cli_config_show_prints_hash_and_document() -> None:
    result = CliRunner().invoke(app, ["config", "show", "--path", str(DEFAULT_PATH)])
    assert result.exit_code == 0
    assert result.output.splitlines()[0].startswith("# config_hash: sha256:")
    assert "supertrend:" in result.output


def test_cli_config_export_schema_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "schema.json"
    result = CliRunner().invoke(app, ["config", "export-schema", "--output", str(out)])
    assert result.exit_code == 0
    assert json.loads(out.read_text())["title"] == "ScoringConfig"


def test_config_committed_schema_matches_model() -> None:
    committed = json.loads((REPO_ROOT / "docs" / "schemas" / "scoring.schema.json").read_text())
    assert committed == json_schema()
