# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Structured JSON logs and the secret scrubber (TS-API-027, TS-API-028, TS-SEC-003/004)."""

from __future__ import annotations

import io
import json

import structlog
from fastapi.testclient import TestClient

from supertrends.api.app import create_app
from supertrends.logs import configure_logging
from supertrends.settings import Settings

TOKEN = "tok-abcdef-123456"  # noqa: S105  # gitleaks:allow
PROVIDER_KEY = "pk_live_ZZZ987654321"  # gitleaks:allow
LLM_KEY = "llm-key-QQQ-424242"  # gitleaks:allow
DSN_PASSWORD = "dsnPassw0rdXYZ"  # noqa: S105  # gitleaks:allow
DSN = f"postgresql+psycopg://svc:{DSN_PASSWORD}@db.internal:5432/st"
JWT = "eyJhbGciOi.payload.sig-9999"  # gitleaks:allow
AUTH_VALUE = f"Bearer {JWT}"
SECRETS = [TOKEN, PROVIDER_KEY, LLM_KEY, DSN_PASSWORD, JWT]


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=DSN,  # type: ignore[arg-type]
        api_token=TOKEN,  # type: ignore[arg-type]
        massive_api_key=PROVIDER_KEY,  # type: ignore[arg-type]
        llm_api_key=LLM_KEY,  # type: ignore[arg-type]
    )


def test_logging_scrubber_secret_values_never_appear_in_log_output() -> None:
    stream = io.StringIO()
    configure_logging(_settings(), stream=stream)
    log = structlog.get_logger("test")
    log.info("provider_call", token=TOKEN, api_key=PROVIDER_KEY, note=f"used {PROVIDER_KEY}")
    log.info("db_connect", dsn=DSN, database_url=DSN, msg=f"connecting to {DSN}")
    log.info(
        "hdr", authorization=AUTH_VALUE, headers={"Authorization": AUTH_VALUE, "X": AUTH_VALUE}
    )
    log.info("url", url=f"https://api.example.com/v1/x?apiKey={PROVIDER_KEY}&token={TOKEN}&a=b")
    log.info("other_dsn", dsn="postgresql://u:otherSecretPw@h/db")
    log.info("nested", items=[{"k": LLM_KEY}, f"Bearer {TOKEN}"], tup=(DSN_PASSWORD,))
    try:
        raise RuntimeError(f"failed with {DSN} and {TOKEN}")
    except RuntimeError:
        log.exception("boom")
    out = stream.getvalue()
    assert out.strip()
    for secret in [*SECRETS, "otherSecretPw"]:
        assert secret not in out
    assert "a=b" in out


def test_logging_every_line_is_json_with_required_fields() -> None:
    stream = io.StringIO()
    configure_logging(_settings(), stream=stream)
    structlog.get_logger("x").info("hello_world", symbol="AAPL")
    lines = stream.getvalue().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "hello_world"
    assert record["level"] == "info"
    assert record["logger"] == "x"
    assert record["ts"].endswith("Z")
    assert {"version", "env"} <= record.keys()
    assert record["symbol"] == "AAPL"


def test_api_json_logs_valid_json_lines_with_request_id() -> None:
    stream = io.StringIO()
    app = create_app(settings=_settings(), log_stream=stream)
    client = TestClient(app, base_url="http://localhost")
    client.get("/healthz", headers={"X-Request-ID": "rid-42", "Authorization": AUTH_VALUE})
    client.get("/x", headers={"Host": "evil.example"})
    out = stream.getvalue()
    records = [json.loads(line) for line in out.strip().splitlines()]
    http = [r for r in records if r["event"] == "http_request"]
    assert http[0]["request_id"] == "rid-42"
    assert http[0]["route"] == "/healthz"
    assert http[0]["status"] == 200
    assert "duration_ms" in http[0]
    assert any(r["event"] == "host_rejected" for r in records)
    for secret in SECRETS:
        assert secret not in out
