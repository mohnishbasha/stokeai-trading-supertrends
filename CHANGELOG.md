# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Supertrend with TradingView semantics (`supertrend`, `bars_since_flip`, `distance_atr`, `supertrend_weekly_direction`), a hand-computed 40-bar fixture, and the TradingView parity harness (skipped until the owner provides exports) (S2-T02).
- Indicator primitives (`sma`, `ema`, `rma`, `stdev`, `true_range`, `atr`, `rsi`, `obv`, `percentile_rank`, `linreg_slope`, confirmed `pivots`, `zigzag`, array `resample_weekly`), the `supertrends.indicators` package skeleton with an aggregated `__all__`, and the `numpy` dependency (S2-T01).
- `database_call_recorder()` returns the Postgres-backed `DbCallRecorder`, and the shared Massive client uses it, so every Massive call writes a sanitized `provider_calls` row; `call_recorder` reuses the adapters' `CallRecord` type (S1-T04, S1-T06 follow-up).
- Deterministic fixture provider (synthetic bars, fundamentals, split) and XNYS calendar helpers (S1-T03).
- Python package and the `supertrends` CLI with `--version`, `serve`, and `healthcheck`; `/healthz` and `/readyz` (S0-T01).
- `supertrends config show | validate | export-schema` (S0-T09).
- UI project: Vite, React, TypeScript strict, ESLint, Vitest, and Playwright with a placeholder route (S0-T02).
- `VERSION` as the version source of truth, `scripts/check-versions.sh`, `scripts/version-sync.sh`, `scripts/extract-changelog.sh`, and this changelog (S0-T04).
- Root `Makefile` with `make help`; later-sprint targets print when they arrive (S0-T03).
- Multi-stage `Dockerfile` (non-root, read-only root filesystem) and `deploy/compose/docker-compose.local.yml` with Postgres (S0-T06).
- CI pipeline (lint and type-check, unit, coverage, integration, e2e placeholder, multi-arch image build, changelog rule) and Dependabot (S0-T05).
- Agent harness files: `AGENTS.md`, `CLAUDE.md`, `SKILLS.md`, `SOUL.md`, and the `run-tests` and `check-types` skills (S0-T07).
- License and community files, SPDX header check, dependency license check, and the CLA check (S0-T08).
- SQLAlchemy 2 models and Alembic migrations for the complete live schema and the `backtests` schema, append-only triggers, run state guard, `supertrends db migrate`, and `supertrends.data.db` helpers (S1-T01).
- Watchlist service and API: default watchlist with many-to-many groups, 300-ticker cap, bearer-token writes, seed from `config/watchlist.seed.yaml` (14 groups, 200 symbols), `config/watchlist.crypto.yaml`, `symbols_to_ingest`, and `supertrends watchlist seed | list | add | remove` (S1-T07).
- `scripts/stoke-inventory.sh`, a read-only Stoke cluster inventory written to git-ignored `private/` (S0-T10).
- Provider interfaces: `MarketDataProvider` and `FundamentalsProvider` Protocols with typed results, provider error types, a registry that selects providers from settings, and a shared provider contract test suite (S1-T02).
- Alternate market data provider: Alpaca Market Data adapter behind the `alternate` registry name, with daily and 5-minute bars, splits, dividends, header auth, and retry (S1-T05, ADR-032).
- Massive (formerly Polygon.io) market data and fundamentals adapter with header auth, a token-bucket rate limiter, retries with jittered backoff, response caching, and call recording (S1-T04).
- Unit tests run with outbound network blocked via `pytest-socket` (loopback only).
- API skeleton: `/readyz` checks database reachability and migrations at head (RFC 9457 503), `/metrics` Prometheus HTTP metrics, structlog JSON logs with request IDs and a secret scrubber, problem+json errors, Host allowlist with probe exemptions, and `require_write_token` (S1-T08).
- Local Compose runs a one-shot `migrate` service (`supertrends db migrate`) before the app starts, so `/readyz` reports ready after `make up` (S1-T08).
- Ingestion service and `supertrends ingest [--date] [--symbols] [--full]`: idempotent incremental daily, 5-minute, and fundamentals ingest, split-triggered full refetch, data quality classification, and `provider_calls` recording (S1-T06).

### Scoring

- `config/scoring.yaml` seeded with every default from the Signal Engine Specification (`scoring.version` 1), with a JSON schema and a stable `config_hash`.
