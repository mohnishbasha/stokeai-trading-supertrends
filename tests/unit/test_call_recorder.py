# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Provider call sanitizing: no secret reaches a provider_calls row (TS-ING-013)."""

from supertrends.data.call_recorder import REDACTED, sanitize


def test_unit_provider_calls_sanitize_strips_query_string_and_credential_params() -> None:
    path, params = sanitize(
        "/v2/aggs/ticker/FXA/range/1/day/2026-01-01/2026-02-01?apiKey=FAKE-VALUE",
        {
            "adjusted": "true",
            "apiKey": "FAKE-VALUE",
            "api_key": "FAKE-VALUE",
            "Authorization": "Bearer FAKE-VALUE",
            "token": "FAKE-VALUE",
            "limit": "50000",
        },
    )
    assert path == "/v2/aggs/ticker/FXA/range/1/day/2026-01-01/2026-02-01"
    assert params == {"adjusted": "true", "limit": "50000"}
    assert "FAKE-VALUE" not in repr((path, params))


def test_unit_provider_calls_sanitize_redacts_bearer_in_values() -> None:
    _, params = sanitize("/x", {"note": "sent Bearer abc123 header"})
    assert params == {"note": f"sent {REDACTED} header"}
