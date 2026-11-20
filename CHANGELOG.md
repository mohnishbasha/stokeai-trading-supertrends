# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Composite and confidence (S3-T05): `scoring.regime` (ADX regimes and the multiplier table), `scoring.weights` (base x regime x earnings x quality, missing factors dropped and renormalized to 100), `scoring.composite` (composite, contributions, display score, bands, and the frozen `ScoreCard` from `score_ticker`), and `scoring.confidence` (agreement and the five deductions, with reasons) (ADR-064).
- Factor 12, Ripster EMA Clouds (S3-T14): the score rules (bias, trend, stacking, mid, long, pullback), and the pure helpers `confidence_stack_penalty`, `selection_bias_gate` and `ripster_evidence` in `scoring/ripster_rules.py` for the composite, selection and evidence tasks (ADR-063, PRD A-31).
- Factors 9 and 10 (S3-T04): `volume_osc` (vo part by the sign of the 5-bar return plus the OBV slope part) and `flow` (order flow delta plus CMF; `daily_estimate` quality returns the 0.6 weight multiplier from config; accumulation and distribution days as evidence) (PRD A-30).
- Factors 5 to 8 (S3-T03): Mean reversion, Fibonacci, Support and resistance, and Volatility scores with evidence and reasons from reason templates (ADR-061, PRD A-28 and A-29).
- Scoring factors 1 to 4 (S3-T02): Supertrend, SMA stack and slope, MACD, and RSI, MACD and OBV divergence, with evidence and reasons, table-driven tests for every rule line, and window-boundary tests on real snapshots (ADR-060).
- Factor framework (S3-T01): `FactorResult`, `EvidenceItem`, `FactorContext`, the quality vocabulary, reason templates, and the factor registry in `scoring.factor`; twelve stub modules under `scoring/factors/`; snapshot schema 2 with `prev_close`, `high`, `low`, `close_lag_3`, `ret_5`, `avg_dollar_volume_20d`, the `ripster` block, and `daily.sma_cross` fixed to SMA50 against SMA200 (ADR-059).
- Indicator snapshots: `scoring.snapshot.compute_snapshot` (every per-bar indicator daily and weekly, levels, Fibonacci, divergences, flow; canonical JSON, NaN as null, no look-ahead), insert-only persistence with idempotent retry and conflict detection in `data.snapshots`, and `compute_and_store` for the `computing` step; the 10-digit canonicalizer moved into `indicators.registry` (S2-T09).
- No-look-ahead and determinism harness: indicator registry, truncation and perturbation property tests with a negative control, determinism and synthetic dataset hashes, `scripts/regen-golden.sh`, `scripts/validate-fixtures.sh`, the 200-ticker compute benchmark, and unique-ID checks for specs; `supertrends.indicators.supertrend` is now the function (S2-T08).
- Volume indicators (`volume_oscillator`, `relative_volume`, `obv_slope_sign`, `cmf`, `accumulation_distribution_days`) and estimated order flow (`split_volume`, `estimate_order_flow` with `intraday`, `daily_estimate`, and `trades` quality) (S2-T07).
- Mean reversion and volatility indicators: Bollinger (20, 2), %B, z-score, bandwidth and rank, ATR% and rank, HV20, squeeze and expansion flags (S2-T05).
- Divergence detector: regular and hidden, bullish and bearish divergences for RSI, MACD histogram, and OBV on confirmed pivots (daily width 5, weekly width 3), with typed records and a per-bar series form (S2-T04).
- Trend and momentum indicators: SMA 20/50/200 with slope and cross detection, MACD (12, 26, 9) daily and weekly (as-of, no look-ahead), histogram run and signal cross helpers, and ADX(14) with +DI/-DI (S2-T03).
- Supertrend with TradingView semantics (`supertrend`, `bars_since_flip`, `distance_atr`, `supertrend_weekly_direction`), a hand-computed 40-bar fixture, and the TradingView parity harness (skipped until the owner provides exports) (S2-T02).
- Fibonacci legs, retracements and extensions, and support/resistance level clustering with breakout and breakdown flags (S2-T06).
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

### Fixed

- UI: TypeScript back to ^5.9.3, since typescript-eslint 8 supports only TypeScript <6.1 and the Dependabot bump to 7.0.2 broke `npm ci`.

### Scoring

- `config/scoring.yaml` adopts spec 1.1.0 (BUILD_PROMPT Appendix E): the Factor 12 Ripster weight 10, the `ripster` block, regime multipliers for it, and the other weights adjusted; `scoring.version` is 2 (S3-T01).
- `config/scoring.yaml` seeded with every default from the Signal Engine Specification (`scoring.version` 1), with a JSON schema and a stable `config_hash`.
