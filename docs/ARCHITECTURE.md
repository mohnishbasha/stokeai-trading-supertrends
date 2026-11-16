# Super Trends Market Agent: Architecture

| Field | Value |
|---|---|
| Document | `docs/ARCHITECTURE.md` |
| Version | 1.0.0 |
| Date | 2026-11-14 |
| Product | Super Trends Market Agent (short form: Super Trends) |
| Owner | Serverless Ventures LLC |
| License of the project | Super Trends Community License (PolyForm Noncommercial 1.0.0, SPDX `PolyForm-Noncommercial-1.0.0`). Source-available, free for noncommercial use. |

**Status of this document.** This document is the source of truth for the structure and the contracts of Super Trends: components, decisions, data flows, database schema, HTTP API, CLI, MCP tools, provider interfaces, the run state machine, the security model, build and deployment, observability, repository layout, and configuration. `docs/PRD.md` is the source of truth for product behavior and carries the Signal Engine Specification formulas verbatim; this document references those formulas and does not restate them in full except where a contract depends on them. Any change to a contract defined here (API, CLI, MCP, schema, provider interface, state machine, deployment shape, configuration schema) follows the Spec Change Protocol: option A (internal only, stated in the PR), option B (this document updated in the same PR), or option C (a spec issue filed, scheduled, and closed in the same sprint). A change to any scoring formula, weight, or threshold is always option B and bumps `scoring.version` in `config/scoring.yaml`.

**Conventions used in this document.**
- "Session" means a regular XNYS trading session. "Trade date" is the session date in America/New_York.
- All timestamps stored in the database are `timestamptz` in UTC. All trade dates are `date` values in exchange time.
- Placeholders that must never be replaced with real values in this public repository are written as `REPLACE_...` or `<...>`.
- Section numbers are stable. Other documents cross-reference them (for example "ARCHITECTURE section 6.1").

---

## 1. System Overview

Super Trends is a CPU-only, single-owner server product. A scheduled job ingests end-of-day market data for a watchlist, computes indicators, scores eleven factors per ticker, combines them into a composite score, selects at most 3 buys and at most 2 sells, writes a justification per pick, and publishes the result atomically. A stateless API serves the published results to a browser UI, a CLI, and an MCP server. An LLM is used only to word the narrative, never to score.

```
                                   Owner (browser, terminal, AI agent)
                                                 |
                       tailnet or private cluster ingress (no public LoadBalancer)
                                                 |
 +--------------------------------------------------------------------------------------------+
 | Kubernetes namespace: supertrends (prod) or supertrends-stage (stage)                       |
 |                                                                                            |
 |   +-------------------------------+        +-----------------------------------------+     |
 |   | API Deployment                |        | CronJob: daily run                      |     |
 |   | `supertrends serve`           |        | `supertrends run daily`                 |     |
 |   |  - FastAPI /api/v1/*          |        | 30 17 * * 1-5 America/New_York          |     |
 |   |  - UI static files (ui/dist)  |        | concurrencyPolicy: Forbid               |     |
 |   |  - MCP streamable HTTP /mcp   |        +-------------------+---------------------+     |
 |   |  - /healthz /readyz /metrics  |                            |                           |
 |   +---------------+---------------+        +-------------------+---------------------+     |
 |                   |                        | Worker Deployment (ADR-020)             |     |
 |                   | read; enqueue manual   | `supertrends worker`                    |     |
 |                   | runs; watchlist writes | executes queued manual runs             |     |
 |                   |                        +-------------------+---------------------+     |
 |                   v                                            v                           |
 |   +--------------------------------------------------------------------------------+      |
 |   | PostgreSQL 17 (bundled StatefulSet + PVC, or external)                          |      |
 |   | bars, fundamentals, runs, scores, append-only picks, outcomes, config versions  |      |
 |   +--------------------------------------------------------------------------------+      |
 |                                                                                            |
 |   Job (Helm hook): `supertrends db migrate` (pre-install, pre-upgrade)                     |
 +-------------------------------+--------------------------------+---------------------------+
                                 | egress 443 only                | egress in-cluster
                                 v                                v
               +-----------------------------------+   +---------------------------------+
               | Market data / fundamentals vendor |   | LLM gateway (OpenAI-compatible) |
               | Massive (formerly Polygon.io),    |   | Stoke: existing gateway in      |
               | alternate adapter, or fixture     |   | front of vLLM. Optional.        |
               +-----------------------------------+   +---------------------------------+

 Daily run pipeline inside the job or worker process (one code path, also used by backtests):

   providers -> ingest + data quality -> indicators -> factors (11) -> regime + weights
     -> composite, display score, band, confidence -> selection (candidates, ranking,
     correlation guard) -> evidence documents -> narrative (LLM with numeric guard, or
     template) -> atomic publication -> outcome tracking for earlier picks -> retention
```

Surfaces and who uses them:

| Surface | Transport | Users | Writes allowed |
|---|---|---|---|
| Web UI | HTTPS through tailnet or private ingress, same origin as the API | trader | run trigger and watchlist edits with the bearer token |
| HTTP API | JSON over HTTP, `/api/v1` | UI, CLI remote mode, Pi extension, smoke tests | `POST /api/v1/runs`, watchlist writes (token) |
| CLI | local process; local mode talks to Postgres, remote mode talks to the API | trader, operator, CronJob | local mode: all; remote mode: token-gated writes |
| MCP | stdio (`supertrends mcp`) or streamable HTTP (`/mcp`, token) | Goose, OpenCode, Claude Code, other MCP clients | `supertrends_run`, `supertrends_watchlist` add and remove |
| Prometheus | `/metrics` scrape | operator | none |

Hard boundaries that the architecture enforces:
- No brokerage integration, no order placement, no brokerage credentials, no personal financial data.
- No GPU requests, no model deployment, no cluster-wide components installed on Stoke.
- No outbound traffic except the configured market data provider, fundamentals provider, and LLM endpoint. No telemetry.
- The LLM never influences a score, a rank, or a selection.
- Published picks are never edited or deleted.

---

## 2. Component Responsibilities

Module paths are relative to `src/supertrends/` unless stated otherwise. The import rules in the last column are enforced by an import-linter contract in CI (Appendix I principle 1).

| Component | Path | Responsibility | Inputs | Outputs | Import rules and invariants |
|---|---|---|---|---|---|
| Settings | `settings.py` | Load environment settings with the `SUPERTRENDS_` prefix into a pydantic-settings model; validate at startup | environment, `.env` (dev only) | `Settings` object | Unknown provider name fails startup with a message naming the variable. Secret fields are `SecretStr` and never rendered. |
| Errors | `errors.py` | Domain error hierarchy rooted at `SuperTrendsError` | none | exception classes | Every `except` handles, re-raises, or records and fails the run cleanly. |
| Logging | `logging.py` | structlog JSON configuration, request ID binding, secret redaction processor | settings | JSON log lines on stdout | No `print` anywhere. Redaction is unit-tested. |
| Version | `version.py` | Version and commit from `SUPERTRENDS_VERSION` / `SUPERTRENDS_COMMIT` (image) or package metadata (wheel) | build args | `VERSION`, `COMMIT` | `supertrends --version` prints `supertrends {VERSION} ({commit})`. |
| Indicator engine | `indicators/` | Pure, vectorized indicator functions: primitives, Supertrend, SMA, MACD, ADX, divergences, mean reversion, volatility, Fibonacci, levels, volume, estimated order flow; a registry of every public indicator | numpy arrays or pandas frames, parameters | arrays of the same length with NaN during warm-up; typed records for pivots, divergences, legs, levels | Imports nothing from `api`, `cli`, `mcp`, `data`, `runs`. No I/O, clock, randomness, or globals. Every public function is registered with the no-look-ahead harness. |
| Scoring | `scoring/` | `Factor` protocol and registry, the eleven factor modules, regime detection, weight adjustment and renormalization, composite, display score, band, confidence, the scoring config model and `config_hash` | indicator snapshot, context (benchmarks, fundamentals, earnings), scoring config | `FactorResult` per factor, `TickerScore` per ticker | Same import rules as indicators. Factor scores validated in [-100, 100]. Every factor ID in `config/scoring.yaml` maps to a registered factor and the reverse. |
| Selection | `selection/` | Candidate rules, ranking with the tie-breaker chain, max counts, correlation guard, "also qualified" list, nearest-miss record | `TickerScore` list, return series for correlation, config | `Selection` (buys, sells, also qualified, nearest misses) | Same import rules. Never pads a side. |
| Narrative | `narrative/` | Evidence document builder, deterministic template narrative, `NarrativeProvider` implementations (`template`, `openai_compatible`), numeric guard, banned-phrase and sentence-count checks, versioned prompts | evidence document | `Narrative` (text, source, model, prompt version, tokens) | The prompt contains only numbers and enumerated labels from the evidence document. Output treated as untrusted plain text. Never changes a score. |
| Data layer | `data/` | SQLAlchemy 2 models, repository functions, ingestion, trading calendar (XNYS via `exchange_calendars`), data-quality pass, provider protocols, adapters, and registry | provider responses, database | rows in Postgres, typed frames for the engine | Providers are selected only from settings. Base URLs never come from request input. |
| Providers | `data/providers/` | `base.py` protocols and models, `fixture.py` synthetic generator, `massive.py` REST adapter, `alternate.py` second vendor, `registry.py` | settings | typed bars, corporate actions, financials, earnings dates | Every vendor call is recorded in `provider_calls` without secrets. No test touches the network. |
| Run orchestrator | `runs/` | `state.py` state machine, `orchestrator.py` daily loop, `publish.py` atomic publication, abandoned-run reaping, worker loop | trade date, trigger, settings | `runs` rows, transitions, published picks | One run at a time (advisory lock and partial unique index). A failed run never replaces the last good published run. |
| Track record | `trackrecord/` | Outcome tracker (entry prices, forward returns), statistics service, backtest engine | published picks, bars, config | `outcomes` rows, statistics, backtest results in the `backtests` schema | The backtest calls the same factor, composite, and selection code as live runs; there is no second scoring path. |
| HTTP API | `api/` | FastAPI app factory, routes, pydantic schemas, bearer auth, Host allowlist, security headers, rate limiting of writes, RFC 9457 problems, static UI serving with SPA fallback, MCP HTTP mount | HTTP requests, database | JSON responses, UI assets | Stateless; can scale horizontally. Reads never recompute scores; they render stored evidence. |
| MCP server | `mcp/` | Official Python MCP SDK server with seven tools; stdio and streamable HTTP transports | tool calls | structured JSON tool results with disclaimer | Thin adapter over the same service functions and schemas as the API. |
| CLI | `cli/` | Typer application `supertrends` with all commands in section 6.2; local mode (database) and remote mode (`--api-url`) | arguments, environment | text or `--json` output, exit codes 0, 1, 2, 3 | Thin adapter over service functions; `--json` output validates against the API schemas. |
| Observability | `observability/` | Prometheus metric definitions, the database-backed collector for job metrics (ADR-023), counter persistence helpers | runtime events, database | `/metrics` exposition | No metric label carries a secret or an unbounded value (no ticker labels). |
| Web UI | `ui/` | Vite, React 19, TypeScript strict SPA: Today, Ticker, Watchlist, Track Record, Runs, Settings, date browsing, demo tour; typed client generated from `docs/openapi.json` | API JSON | screens | No hand-written fetch calls. Every number formatted through `ui/src/lib/format.ts`. Disclaimer on every screen with a recommendation. |
| Daily CronJob | Helm `cronjob-daily-run.yaml` | Runs `supertrends run daily` at 17:30 America/New_York on weekdays | schedule | a run | `concurrencyPolicy: Forbid`, `startingDeadlineSeconds: 3600`, exits 0 with "market closed" on non-trading days. |
| Worker | Helm `deployment-worker.yaml`, Compose `worker` service | Executes manual runs queued by `POST /api/v1/runs` or `supertrends_run` (ADR-020) | `runs` rows in state `queued` | runs | Single replica; uses the same orchestrator and lock as the CronJob. |
| Migration Job | Helm `job-migrate.yaml` | `supertrends db migrate` as a `pre-install,pre-upgrade` hook | Alembic revisions | schema at head | Migrations are backward compatible for one version so rollback works. |
| PostgreSQL | Helm `statefulset-postgres.yaml` or external | System of record | SQL | rows | Append-only triggers on published history (section 5). |
| LLM gateway | external to Super Trends | Serves an OpenAI-compatible chat completions endpoint | rendered prompt | completion | Optional. On Stoke it is in-cluster so evidence never leaves the cluster. |
| Integrations | `integrations/` | Pi extension (`@stokeai-supertrends/pi-extension`), Goose toolkit, OpenCode and Claude Code config snippets | API or MCP | agent tools and slash commands | Call the HTTP API or the MCP server only. |

Service functions shared by all surfaces (in `api/` service layer imported by `cli/` and `mcp/`; the names are normative):

| Function | Used by |
|---|---|
| `get_latest_recommendations() -> RecommendationsResponse` | `GET /api/v1/recommendations/latest`, `supertrends today`, `supertrends_recommend` |
| `get_recommendations(date) -> RecommendationsResponse` | `GET /api/v1/recommendations`, `supertrends_recommend` with date |
| `get_rankings(date, limit, offset, group) -> RankingsResponse` | `GET /api/v1/rankings`, `supertrends rank`, `supertrends_rank` |
| `get_analysis(symbol, date) -> AnalysisResponse` | `GET /api/v1/tickers/{symbol}/analysis`, `supertrends analyze`, `supertrends_analyze` |
| `get_watchlist() / add_watchlist_item() / remove_watchlist_item()` | watchlist endpoints, `supertrends watchlist`, `supertrends_watchlist` |
| `enqueue_run(date, trigger) -> RunTriggerResponse` | `POST /api/v1/runs`, `supertrends run daily --api-url`, `supertrends_run` |
| `get_track_record(filters) -> TrackRecordResponse` | `GET /api/v1/track-record`, `supertrends track-record`, `supertrends_track_record` |
| `get_status() -> StatusResponse` | `GET /api/v1/status`, `supertrends status`, `supertrends_status` |

---

## 3. Decision Log

ADRs are numbered and never renumbered. A superseded ADR stays in the log with status "Superseded by ADR-NNN". New ADRs are appended here; long-form supporting notes may live in `docs/adr/` and are linked from the ADR. ADR-001 to ADR-016 are seeded from BUILD_PROMPT Appendix A. ADR-017 onward record ambiguities resolved while writing the specification.

### ADR-001: Web service with a browser UI, not a desktop app
- **Context:** The product's heartbeat is a scheduled end-of-day run. The owner reaches it from several devices over a tailnet.
- **Decision:** Build a web service with a browser UI, deployed on the Stoke k3s cluster.
- **Alternatives rejected:** Tauri desktop app: no server to schedule runs, harder to reach from a phone.
- **Consequences:** Needs a server, a database, and a deployment path; gains scheduling, one source of truth, and access from any device on the tailnet.
- **Status:** Accepted.

### ADR-002: Python 3.12 for the backend
- **Context:** The core work is numeric indicator math that must be verifiable against golden fixtures. The owner's general language preference ranks Go and Rust first for services.
- **Decision:** Python 3.12 for the engine, API, CLI, and MCP server, with numpy and pandas.
- **Alternatives rejected:** Go (matches other Stoke tools, but a weaker numeric ecosystem and more code for the same math); Rust (highest effort for no user-visible gain at this scale).
- **Consequences:** One language for every backend surface. Runtime cost is acceptable: one daily batch for about 200 tickers and a low-traffic read API. Hot loops are limited to recursive indicators and are covered by a benchmark test (NFR-001).
- **Status:** Accepted.

### ADR-003: Indicators implemented in-house, no TA library at runtime
- **Context:** Supertrend must match TradingView within 0.01 per bar; warm-up and look-ahead behavior must be explicit.
- **Decision:** Implement every indicator in `src/supertrends/indicators/`. A TA library may be used in tests only, as an independent cross-check.
- **Alternatives rejected:** TA-Lib (native build on ARM64, formulas differ in seeding); pandas-ta (maintenance risk).
- **Consequences:** More code to write and test (95 percent coverage target for indicators); exact parity and clean ARM64 builds.
- **Status:** Accepted.

### ADR-004: PostgreSQL, bundled single instance by default
- **Context:** The CronJob, the worker, and the API access the same data concurrently; history is append-only and evidence is JSON.
- **Decision:** PostgreSQL 17. The chart bundles a single-replica StatefulSet; an external database is supported.
- **Alternatives rejected:** SQLite on a PVC (blocks the CronJob and API from sharing safely); TimescaleDB (not needed at this volume).
- **Consequences:** JSONB evidence, triggers for append-only rules, advisory locks for run concurrency. Backup is `pg_dump` (`supertrends db backup`).
- **Status:** Accepted.

### ADR-005: Daily run as a Kubernetes CronJob calling the CLI
- **Context:** The run must survive API restarts and must not run twice when the API has several replicas.
- **Decision:** A CronJob runs `supertrends run daily` at `30 17 * * 1-5` in America/New_York with `concurrencyPolicy: Forbid`.
- **Alternatives rejected:** In-process scheduler (ties run lifetime to the API pod, breaks with replicas).
- **Consequences:** The API is stateless and can scale. Run metrics must reach Prometheus from a short-lived pod (see ADR-023). Manual runs need an executor outside the API (see ADR-020).
- **Status:** Accepted.

### ADR-006: One image, several commands
- **Context:** Every artifact must be built, signed, scanned, and mirrored for two architectures.
- **Decision:** One OCI image with entrypoint `supertrends`; commands `serve`, `run daily`, `worker`, `db migrate`, `mcp`, `healthcheck`.
- **Alternatives rejected:** Separate API, worker, and UI images (more supply chain surface for no benefit).
- **Consequences:** The image contains the UI bundle even for the job; size cost is small.
- **Status:** Accepted.

### ADR-007: UI served by the API
- **Context:** A single owner, a strict CSP, one hostname.
- **Decision:** FastAPI serves `ui/dist` with SPA fallback and cache headers.
- **Alternatives rejected:** A separate nginx image.
- **Consequences:** Single origin (`connect-src 'self'`), no CORS, one Service and one route.
- **Status:** Accepted.

### ADR-008: LLM used only for narrative, through an OpenAI-compatible endpoint, with a numeric guard and template fallback
- **Context:** Plain-language explanations help, but a model must not invent numbers or move scores, and the product must work with no LLM.
- **Decision:** The LLM writes 3 to 5 sentences from the evidence document only. A numeric guard rejects any number not in the evidence. On rejection, timeout (8 s), or error: retry once at temperature 0, then fall back to the template.
- **Alternatives rejected:** LLM-in-the-loop scoring (non-deterministic, unverifiable); no LLM (drier justifications).
- **Consequences:** Narrative source is recorded (`llm` or `template`) with the model name and prompt version. Scores are deterministic (NFR-002).
- **Status:** Accepted.

### ADR-009: Pluggable market data and fundamentals providers; Massive (formerly Polygon.io) as the first adapter
- **Context:** Vendors change endpoints, limits, and names; the product should not depend on one vendor.
- **Decision:** `MarketDataProvider` and `FundamentalsProvider` protocols with a registry; Massive is the first real adapter; a synthetic fixture provider powers dev, CI, kind, demo, and smoke.
- **Alternatives rejected:** Unofficial scraping libraries (unreliable, terms risk).
- **Consequences:** Adding a vendor is one module and one registry line. Market data and fundamentals may come from different vendors.
- **Status:** Accepted.
- **Vendor verification (verified 2026-11-15, S1-T04):** Massive docs (massive.com/docs/rest) confirm aggregates `GET /v2/aggs/ticker/{ticker}/range/{mult}/{timespan}/{from}/{to}` (fields `t,o,h,l,c,v,vw,n`, `limit` max 50000), grouped daily `GET /v2/aggs/grouped/locale/us/market/stocks/{date}` (fields `T,t,o,h,l,c,v,vw`; all Stocks plans), and `GET /v3/reference/tickers/{ticker}`. Differences from section 7.6: splits and dividends are now `GET /stocks/v1/splits` (`execution_date`, `split_from`, `split_to`) and `GET /stocks/v1/dividends` (`ex_dividend_date`, `cash_amount`) with `ticker` and date-comparator filters; financials are `GET /stocks/financials/v1/income-statements` (`tickers`, `timeframe=quarterly`, `period_end`, `filing_date`; Stocks Advanced or Financials expansion plans only), so `fcf` and `net_debt` are `None` until balance-sheet and cash-flow endpoints are added; the docs list no earnings calendar endpoint, so `earnings_dates` raises `CapabilityNotSupported`. The docs state no free-tier rate limit; the default of 5 calls per minute is kept and configurable. Both 401 and 403 map to `ProviderUnconfigured` (the vendor also uses 403 for plan gating, which the adapter cannot distinguish). Retries are hand-rolled (full jitter, base 1 s, cap 30 s, 5 attempts, `Retry-After` honored) rather than `tenacity`, which is not a dependency. Grouped daily bars take the requested session as the bar date; the vendor `t` is ignored for them.

### ADR-010: Estimated order flow from 5-minute bars
- **Context:** True order flow needs L2 and tick data that v1 does not buy.
- **Decision:** Estimate buy and sell volume from 5-minute bars (close location in range), with a daily-bar fallback at weight x 0.6, labeled "estimated order flow" with its quality level. A `trades` capability flag leaves room for tick-rule classification later.
- **Alternatives rejected:** Skip the factor (loses the volume-pressure read the owner relies on); buy tick data (cost).
- **Consequences:** The UI never claims to see the order book. Intraday bars are retained for 90 days.
- **Status:** Accepted.

### ADR-011: Rule-based, transparent scoring with a versioned config
- **Context:** Every pick must be explainable and reproducible; there is no track record yet to learn from.
- **Decision:** Fixed rules from the Signal Engine Specification, parameters in `config/scoring.yaml`, every result tagged with `config_hash`.
- **Alternatives rejected:** Learned weights (no track record yet to train on).
- **Consequences:** Tuning is manual and versioned; backtests let the owner test a config before trusting it.
- **Status:** Accepted.

### ADR-012: Flux HelmRelease from a signed OCI chart for Stoke
- **Context:** Stoke deploys everything through Flux; CI must not hold cluster credentials.
- **Decision:** Publish a cosign-signed OCI chart to GHCR; Flux `OCIRepository` verifies it and a `HelmRelease` installs it with the image by digest.
- **Alternatives rejected:** `helm install` from CI (credentials in CI); Argo CD (not what Stoke runs).
- **Consequences:** Promotion and rollback are pull requests to the owner's Stoke GitOps repository.
- **Status:** Accepted.

### ADR-013: MCP server (stdio and HTTP) as the main agent interface, plus a thin Pi extension
- **Context:** Several agent harnesses need the same answers as the UI.
- **Decision:** One MCP server with seven tools over stdio and streamable HTTP; a Pi extension that calls the HTTP API for slash commands and streaming run progress.
- **Alternatives rejected:** Per-harness plugins (duplicated work).
- **Consequences:** Goose, OpenCode, and Claude Code need only config snippets.
- **Status:** Accepted.

### ADR-014: CLI in Python (Typer), not a separate Bun binary
- **Context:** The CLI needs the engine for local mode (ingest, run, backtest).
- **Decision:** Typer CLI in the same package; the wheel is the "local binary".
- **Alternatives rejected:** TypeScript CLI compiled with bun.
- **Consequences:** One language, one release artifact for the CLI.
- **Status:** Accepted.

### ADR-015: Deployments private by default, token on writes, no user accounts
- **Context:** One owner on a tailnet; public access and accounts need legal review first.
- **Decision:** The code is public; an instance is private. Reads are open inside the network boundary; writes require a bearer token from a Kubernetes Secret; no accounts.
- **Alternatives rejected:** Clerk auth now (unneeded complexity).
- **Consequences:** The Host allowlist and NetworkPolicy matter (section 9). Multi-user features are out of scope for v1.
- **Status:** Accepted.

### ADR-016: Community license: PolyForm Noncommercial 1.0.0, with a CLA
- **Context:** The owner wants public source, no commercial use by others, and all rights kept by Serverless Ventures LLC.
- **Decision:** The unmodified PolyForm Noncommercial License 1.0.0 with the Required Notice line, plus a Contributor License Agreement enforced in CI. The project is described as source-available and free for noncommercial use.
- **Alternatives rejected:** AGPL-3.0 (allows commercial use); Apache-2.0 or MIT (allow everything); a custom-written license (untested wording); BUSL (time-limited, converts later).
- **Consequences:** Dependency licenses are restricted to a permissive allowlist (LGPL only for unmodified libraries such as psycopg; Zlib and CC0-1.0 are also accepted, added 2026-11-15 because numpy 2.5, pulled in by `exchange_calendars`, is `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`); GPL, AGPL, SSPL, and unknown licenses fail CI. The license notice appears in the UI footer, `supertrends --version`, and `GET /api/v1/status`.
- **Status:** Accepted.

### ADR-017: GitHub repository name
- **Context:** BUILD_PROMPT.md names the GitHub repository `stokeai-supertrends`. The owner provisioned the repository as `mohnishbasha/stokeai-trading-supertrends`. BUILD_PROMPT.md Step 2 says an existing repository is not recreated: add the remote and continue.
- **Decision:** Use the existing repository `mohnishbasha/stokeai-trading-supertrends`. Every other identifier keeps the name from Project Identity: Python package `supertrends`, CLI `supertrends`, image `ghcr.io/mohnishbasha/stokeai-supertrends`, chart `oci://ghcr.io/mohnishbasha/charts/stokeai-supertrends`, npm scope `@stokeai-supertrends`, chart directory `deploy/helm/stokeai-supertrends/`, namespaces `supertrends` and `supertrends-stage`, metric prefix `supertrends_`.
- **Alternatives rejected:** Renaming the repository (an owner action, breaks links already shared); renaming the image, chart, and package to match the repository (churn across every artifact and document).
- **Consequences:** Places that reference the GitHub repository itself use `stokeai-trading-supertrends`: `gh` commands, `SUPERTRENDS_SOURCE_URL` default `https://github.com/mohnishbasha/stokeai-trading-supertrends`, the OCI label `org.opencontainers.image.source`, cosign identity regexps (`^https://github.com/mohnishbasha/stokeai-trading-supertrends/`), and the Flux `matchOIDCIdentity.subject`. Keyless signatures are issued for the workflow identity of the repository that runs the workflow, so the verification regexps must name the real repository or verification fails. Artifact names (image, chart) are unchanged. GHCR packages are linked to the repository through the OCI source label.
- **Status:** Accepted.

### ADR-018: Tables and columns added beyond the Appendix D seed
- **Context:** The seed schema does not hold everything the specified behavior needs: rankings for every ticker, per-ticker exclusions, persisted state transitions, corporate-action detection, job metrics from a short-lived pod, and group membership.
- **Decision:** Add `ticker_scores`, `run_transitions`, `corporate_actions`, `watchlist_groups`, `watchlist_group_members`, and `metric_counters`; add a `backtests` schema (ADR-029). Rename the seed column `outcomes.return` to `pick_return` (avoids a keyword-like identifier in SQL and in pydantic). Remove `group_name` from `watchlist_items` in favor of the many-to-many tables (ADR-019).
- **Alternatives rejected:** Storing rankings and exclusions inside `runs.summary` JSONB only (no indexes, slow history queries, NFR-004 risk); recomputing rankings on read (violates "evidence is the contract").
- **Consequences:** Section 5 is the complete schema. `ticker_scores` and the existing append-only tables are protected by triggers.
- **Status:** Accepted.

### ADR-019: Watchlist groups are many-to-many
- **Context:** The seed has 14 groups and 200 unique symbols; a symbol may belong to several groups and must be scored once. Appendix D placed `group_name` on `watchlist_items`, which would duplicate a symbol per group.
- **Decision:** `watchlist_items` holds one row per (watchlist, symbol). `watchlist_groups` holds groups; `watchlist_group_members` links groups to items. Add group endpoints (ADR-025).
- **Alternatives rejected:** A `group_name` column with one row per membership (duplicates and makes the 300 cap ambiguous); a text array column (no referential integrity).
- **Consequences:** The 300-ticker cap counts `watchlist_items` rows. A symbol in three groups is stored once with three memberships (S1-T07 acceptance).
- **Status:** Accepted.

### ADR-020: Manual runs are executed by a worker process, not the API
- **Context:** `POST /api/v1/runs` and the MCP `supertrends_run` tool trigger runs. The API pod has a 512 MiB ceiling and a run needs up to 1.5 GiB (NFR-010). The API pod has no Kubernetes API access (`automountServiceAccountToken: false`), so it cannot create Jobs. ADR-005 rejects tying run lifetime to API pods.
- **Decision:** The API inserts a `runs` row in state `queued` and returns 202. A single-replica worker (`supertrends worker`, chart `deployment-worker.yaml`, Compose `worker` service) polls for queued runs every `SUPERTRENDS_WORKER_POLL_SECONDS` (default 5) and executes them through the same orchestrator as the CronJob. Local-mode CLI (`supertrends run daily`) executes inline. The CronJob keeps calling `supertrends run daily` directly.
- **Alternatives rejected:** Running the job inside the API process (breaks NFR-010 and ADR-005); a dispatcher CronJob every minute (1440 pods per day of noise); giving the API RBAC to create Jobs (Kubernetes API access the product otherwise does not need).
- **Consequences:** One more Deployment (`worker.enabled`, default true; replicas follow `replicaCount`, so stage at 0 has no worker). The worker requests little when idle; its limit equals the run job limit. Queued rows not picked up within `SUPERTRENDS_QUEUED_RUN_TIMEOUT_SECONDS` (default 600) are failed with reason `not_picked_up`.
- **Status:** Accepted.

### ADR-021: Run concurrency, abandoned runs, and "already running" semantics
- **Context:** S3-T07 requires an advisory lock and "two simultaneous triggers produce one run and one already running response". A killed process leaves a non-terminal row behind.
- **Decision:** Two layers. (1) A partial unique index allows at most one non-terminal run row (`state NOT IN ('published','failed')`). Inserting a second one fails, which yields HTTP 409 or the CLI "already running" result. (2) The executing process holds the session-level advisory lock `pg_try_advisory_lock(hashtext('supertrends.run'))` for the whole run. Before inserting or claiming a run, an executor that obtains the lock marks any non-terminal row that is not `queued` as `failed` with reason `abandoned` (no live process can be holding it). CLI result for `supertrends run daily` when another run is active: exit 0 with "already running for {date}" when the active run is for the same trade date (the work is in progress), exit 3 when it is for a different date.
- **Alternatives rejected:** Advisory lock only (a crash between insert and lock leaves no trace for the UI); row lock only (`SELECT ... FOR UPDATE` would hold a transaction open for minutes).
- **Consequences:** Killing a run mid-flight leaves the previous published run as latest; the next run reaps the abandoned row.
- **Status:** Accepted.

### ADR-022: Default trade date and "market closed" semantics
- **Context:** The CronJob fires on weekdays, including holidays. Manual triggers can arrive at any time. The spec says the command exits 0 with "market closed" on non-trading days and publishes nothing.
- **Decision:** Without `--date` (or `date` in the request), the trade date is today in America/New_York. If today is not an XNYS session: result `market_closed`, exit 0, no `runs` row, HTTP 200 `{"run_id": null, "state": "market_closed"}`. If today is a session that has not closed plus 30 minutes (half days use their early close): result `session_not_complete`, exit 3, HTTP 409 problem `session-not-complete`. An explicit date must be an XNYS session on or before the last completed session, else exit 2 or HTTP 422 `not-a-trading-date` / `date-in-future`.
- **Alternatives rejected:** Defaulting to the last completed session (a holiday CronJob would rerun the previous day and supersede it every holiday).
- **Consequences:** Holidays produce no run rows; the smoke suite accepts `market_closed`.
- **Status:** Accepted.

### ADR-023: Job metrics are persisted in Postgres and exposed by the API
- **Context:** The CronJob and worker pods are short-lived or idle; Prometheus scraping them is unreliable. Installing a Pushgateway would add a component on Stoke, which the project avoids.
- **Decision:** Run-side counters (`supertrends_run_state_total`, `supertrends_provider_requests_total`, `supertrends_provider_rate_limited_total`, `supertrends_narrative_total`) are incremented in the `metric_counters` table inside the run's transactions. Run-side gauges are derived from the latest runs at scrape time. The API's `/metrics` exposes both through a custom collector, alongside its own in-process HTTP metrics.
- **Alternatives rejected:** Pushgateway (new component); scraping job pods (missed scrapes); deriving counters from `provider_calls` row counts (30-day retention would make counters decrease).
- **Consequences:** Metrics survive pod restarts. Counter values are monotonic because `metric_counters` is never pruned. With several API replicas every replica exposes the same database values; dashboards use `max by (...)` for these series.
- **Status:** Accepted.

### ADR-024: Host allowlist exemptions for probes and in-cluster callers
- **Context:** The API rejects requests whose `Host` is not in `SUPERTRENDS_ALLOWED_HOSTS`. Kubelet probes send the pod IP; Helm tests and Prometheus use the Service DNS name.
- **Decision:** `/healthz`, `/readyz`, and `/metrics` are exempt from the Host check. The chart appends the Service names (`<fullname>`, `<fullname>.<namespace>`, `<fullname>.<namespace>.svc`, `<fullname>.<namespace>.svc.cluster.local`) to the allowlist automatically. A request with a disallowed Host gets 421 Misdirected Request as a problem response.
- **Alternatives rejected:** Disabling the check in cluster (weakens DNS-rebinding protection); a wildcard (same).
- **Consequences:** Helm tests and the smoke suite work by Service name; external hostnames must be listed.
- **Status:** Accepted.

### ADR-025: HTTP endpoints added beyond the Appendix C seed
- **Context:** Specified features need reads and writes the seed table omits: grouping tickers (US-004), the "Backtest (hypothetical)" tab (S6-T04), and showing the exact config that produced any past pick (US-012, S5-T07).
- **Decision:** Add `POST /api/v1/watchlist/groups`, `DELETE /api/v1/watchlist/groups/{slug}`, `PUT /api/v1/watchlist/items/{symbol}/groups` (all token), `GET /api/v1/backtests`, `GET /api/v1/backtests/{id}`, and `GET /api/v1/config/scoring/{hash}`. Backtests are started only from the CLI.
- **Alternatives rejected:** Embedding backtests in the track-record response (mixes hypothetical and real results, which the honesty rules forbid); a backtest trigger endpoint (long CPU work on the API pod).
- **Consequences:** Section 6.1 lists 27 HTTP operations.
- **Status:** Accepted.

### ADR-026: Rule point values are named constants; `scoring.version` is part of the hash
- **Context:** Appendix E exposes periods, thresholds, and weights, but not every rule's point value (for example SMA +30 / +25 / +20). NFR-002 promises identical output for the same bars and config hash.
- **Decision:** Rule point values and clip bounds stay as named constants in each factor module (part of the formula). `config_hash` is computed over the whole validated document including `scoring.version`. Changing a named scoring constant is a formula change: it bumps `scoring.version` (option B), which changes the hash. Golden factor fixtures fail on any constant change, and the golden-fixture policy requires a version bump in the same PR.
- **Alternatives rejected:** Moving every point value into YAML (a large, fragile config surface the owner did not ask for); leaving constants out of versioning (same hash, different scores).
- **Consequences:** `config_hash` plus code version identifies a scoring behavior; `runs.code_version` records the code version too.
- **Status:** Accepted.

### ADR-027: Valuation input when forward estimates are unavailable
- **Context:** Factor 11 valuation uses forward P/E (or EV/Sales when earnings are negative) percentile versus the ticker's own 3-year history. Forward estimates are "if available" from the provider, and a point-in-time history of forward estimates may not exist.
- **Decision:** Most literal reading first: when the provider reports `forward_estimates` capability and point-in-time estimates exist, use forward P/E. Otherwise compute the percentile on trailing twelve-month P/E (or EV/Sales when TTM earnings are negative) built daily from `bars_daily` closes and point-in-time `fundamentals`, and record the evidence item `valuation_basis` = `trailing_pe` or `ev_sales`. Factor quality is not degraded by this substitution alone. An owner checklist entry asks the owner to confirm.
- **Alternatives rejected:** Scoring the valuation sub-score as 0 when forward data is missing (silently changes the factor's range); marking the factor `degraded` for every ticker (a systemic -10 confidence penalty).
- **Consequences:** The basis is visible in the evidence and the UI.
- **Status:** Accepted, pending owner confirmation.

### ADR-028: Fixture provider calendar anchoring
- **Context:** The synthetic dataset must be deterministic for tests yet produce a "latest" session that the demo and smoke runs can publish.
- **Decision:** The fixture provider generates bars on the XNYS calendar ending at `SUPERTRENDS_FIXTURE_END_DATE`. Default: the last completed session at process start. Determinism tests and golden hashes pin `SUPERTRENDS_FIXTURE_END_DATE=2026-11-13` and `SUPERTRENDS_FIXTURE_SEED=20261114`. Bar values depend only on the seed and the session index counted back from the end date, so shapes are identical for any end date.
- **Alternatives rejected:** A fixed historic window (the demo would show stale dates and the data-quality pass would mark everything `stale`).
- **Consequences:** Demo and smoke runs always have a current session; CI determinism is preserved.
- **Status:** Accepted.

### ADR-029: Backtest results live in a separate `backtests` schema
- **Context:** S6-T03 says backtests write to a separate `backtests` schema and never touch published recommendations.
- **Decision:** A Postgres schema `backtests` with tables `backtests.backtest_runs`, `backtests.picks`, `backtests.outcomes`, and `backtests.equity_curve`, created by the same Alembic migrations. The backtest engine never writes to `public.recommendations`, `public.runs`, or `public.outcomes`.
- **Alternatives rejected:** A `kind` column on `runs` (risk of a hypothetical result appearing as real).
- **Consequences:** Every API payload from the `backtests` schema carries `"hypothetical": true`.
- **Status:** Accepted.

### ADR-030: Rounding and presentation boundaries; disclaimer on every score-bearing payload
- **Context:** The coding standard rounds scores to 1 decimal at the API boundary; the example payload shows `confidence` as an integer. Appendix C requires the disclaimer on every payload containing picks.
- **Decision:** All logic (thresholds, ranking, tie-breakers) uses unrounded values except the display score, which the formula itself rounds to 1 decimal. API, CLI, and MCP present `display_score`, `composite`, scores, weights, and contributions at 1 decimal and `confidence` as an integer (round half away from zero). The `disclaimer` field is included on every payload that carries a pick, a score, a ranking, an analysis, or track-record or backtest statistics.
- **Alternatives rejected:** Rounding before comparison (a 49.6 confidence would pass the 50 floor).
- **Consequences:** Stored values keep full precision (`double precision`), except `display_score` which is `numeric(4,1)`.
- **Status:** Accepted.

### ADR-031: Data retention runs as a post-publication step and as a command
- **Context:** S6-T06 requires deleting intraday bars older than 90 days and `provider_calls` older than 30 days, never deleting rows referenced by a pick's evidence window. No schedule is specified.
- **Decision:** `supertrends db prune` performs retention. The daily run calls the same function after publication; a failure there is logged and counted but does not fail the run. Intraday rows needed by any pick published in the last 10 sessions (the flow window) are kept regardless of age.
- **Alternatives rejected:** A second CronJob (more objects for a few deletes).
- **Consequences:** Daily bars, recommendations, narratives, outcomes, and config versions are kept forever.
- **Status:** Accepted.

### ADR-032: Alternate market data provider selection
- **Context:** S1-T05 requires a second provider behind the same interface, chosen between Alpaca Market Data and Tiingo after reading their current docs and terms (verified 2026-11-15).
- **Decision:** Alpaca Market Data. The registry name is `alternate` and the module is `data/providers/alternate.py`.
  - Auth: headers `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY` against `https://data.alpaca.markets`. Alpaca uses a key pair, so `SUPERTRENDS_ALTERNATE_API_KEY` holds `KEY_ID:SECRET`; a value without both parts reports `unconfigured`.
  - Endpoints: `GET /v2/stocks/bars` (`timeframe=1Day` or `5Min`, `adjustment=all`, `feed=iex`, `limit` up to 10000, `page_token` pagination, response `bars.{symbol}[]` with `t o h l c v n vw`) and `GET /v1/corporate-actions` (`forward_splits`, `reverse_splits` with `new_rate` and `old_rate`, `cash_dividends` with `rate`, `ex_date`).
  - Plan: the free Basic plan allows 200 calls per minute, the IEX feed only for equities, and history since 2016; Algo Trader Plus (about $99 per month) has 10,000 calls per minute and the full SIP feed. Intraday 5-minute bars and adjusted daily bars are available on the free plan, so `intraday=True` and `adjusted=True`.
  - Capabilities: `grouped_daily=False` (no whole-market endpoint) and `trades=False` raise `CapabilityNotSupported`. `resolve_symbol` is a recent-bar lookup (the asset catalog is on the trading API host and does not distinguish ETFs), so it returns type `stock` and no name.
  - Terms: market data is licensed under the NASDAQ and NYSE subscriber agreements, which restrict republishing or reselling data. The product publishes derived picks, not raw quotes, but the owner must review the terms before production use (OWNER_CHECKLIST row 20).
- **Why Alpaca over Tiingo:** The free Tiingo plan allows 50 requests per hour and 1,000 per day (a 200-symbol backfill is impractical), and limits use to personal use with no display or sharing of data (the paid personal plan is $30 per month). Alpaca's 200 calls per minute and multi-symbol bars fit the daily run, and header-key auth matches ADR-035. Tiingo remains a documented fallback: its single-token header auth (`Authorization: Token`), `/tiingo/daily/{ticker}/prices` (with `divCash` and `splitFactor`), and a per-ticker `adj*` series would also fit the interface.
- **Alternatives rejected:** Tiingo (rate limits and personal-use terms above); choosing without reading current terms.
- **Consequences:** Settings keys `SUPERTRENDS_ALTERNATE_API_KEY` and `SUPERTRENDS_ALTERNATE_BASE_URL` (added in S1-T02). On the free plan, volume comes from IEX only, so volume-based factors differ from the primary vendor; `feed="sip"` is a constructor option for a paid plan. The adapter has its own retry loop; consolidate with the Massive adapter into one shared HTTP helper (token bucket, per-run cache, `provider_calls` recording) when S1-T04 lands.
- **Status:** Accepted (verified 2026-11-15).

### ADR-033: Weekly bars are resampled in memory, not persisted
- **Context:** Weekly bars are resampled from daily bars (week ending Friday) for Supertrend, MACD, and divergences.
- **Decision:** `indicators.primitives.resample_weekly` computes weekly bars on demand from `bars_daily`; there is no weekly table. A partial current week is included only through bar t (no look-ahead); a holiday Friday ends the week on the last session of that week.
- **Alternatives rejected:** A `bars_weekly` table (a second copy to keep consistent after split refetches).
- **Consequences:** One source of truth for prices.
- **Status:** Accepted.

### ADR-034: Definition of "day N on the list"
- **Context:** The UI shows "day N on the list"; the spec does not define gaps or side changes.
- **Decision:** `days_on_list` = 1 + the number of consecutive immediately preceding sessions on which the same symbol was published on the same side in the published run of that session. A session with no published run breaks the streak. Computed at publication and stored in the evidence document.
- **Alternatives rejected:** Counting any side (a flip from buy to sell is a new view).
- **Consequences:** Deterministic and reproducible from stored runs.
- **Status:** Accepted.

### ADR-035: Massive authentication by header, never by query string
- **Context:** Massive accepts the API key as a query parameter or an `Authorization: Bearer` header. Query-string keys leak into logs and URLs.
- **Decision:** The adapter sends the key only in the `Authorization` header. `provider_calls.endpoint` stores the path template and `params` stores non-secret parameters. Logged URLs are built without the key.
- **Alternatives rejected:** Query parameter (`apiKey=`) with a scrubber (one missed path leaks the key).
- **Consequences:** If the vendor stops accepting the header, the adapter fails with `ProviderUnconfigured` rather than silently switching to the query parameter; the fix requires a reviewed change.
- **Status:** Accepted. Verified 2026-11-15 (S1-T04): the Massive quickstart documents both `?apiKey=` and `Authorization: Bearer <key>`; the adapter uses only the header, strips any `apiKey` from vendor `next_url` values, scrubs the key from vendor text it quotes, and discards transport exception text (which can echo the URL).

### ADR-036: Forward-return horizon definition
- **Context:** The track record measures forward returns "at 1, 5, 10, and 20 trading days" from an entry at the next session's open; the exit point is not defined.
- **Decision:** The entry session (the first session after the trade date) counts as session 1. The horizon-h exit is the adjusted close of session h. So the 1-day return is the entry session's close over its open. SPY uses the same entry open and exit close sessions. A sell pick's `pick_return` is the raw price return (a sell hit is a negative excess return); returns are never sign-flipped.
- **Alternatives rejected:** Exit at the close h sessions after the trade date (mixes the gap before entry into the result, which the pick could not capture).
- **Consequences:** An outcome for horizon h is computable after session h closes and its bar is stored. Backtests use the identical definition.
- **Status:** Accepted.

### ADR-037: Omitted regime multipliers default to 1.00 inside the validated document
- **Context:** The seed `config/scoring.yaml` lists regime multipliers only for factors whose value differs from 1.00 and sets `transitional: {}`. The schema rule "no silent defaults" would reject the seed as written.
- **Decision:** The pydantic model fills omitted multipliers with 1.00 during validation, so the validated document (the input to `config_hash`) always holds all 33 cells. Writing a cell as 1.00 explicitly or omitting it yields the same hash.
- **Alternatives rejected:** Requiring all 33 cells in YAML (changes the seed file the owner wrote); filling defaults at use time (the hash would not describe the effective values).
- **Consequences:** `GET /api/v1/config/scoring` returns the full table. The PRD multiplier table and the validated config agree cell by cell (tested).
- **Status:** Accepted.

### ADR-038: Weight pipeline order (PRD A-01)
- **Context:** The Signal Engine Specification applies regime multipliers to base weights and places event adjustments "after regime multipliers, before renormalizing", but does not place the quality multipliers (`daily_estimate` x 0.6, fundamentals older than 120 days x 0.5) or the removal of `missing` factors.
- **Decision:** Order: base weights, regime multipliers, event multiplier (`days_to_earnings <= 5`: fundamentals x 1.5), quality multipliers, drop factors with quality `missing`, renormalize the remaining weights to sum 100. Contributions (`weight * score / 100`) then sum to the composite.
- **Alternatives rejected:** Renormalizing after each step (multiplication is commutative, but intermediate renormalization makes the stored adjustment trail harder to audit); applying quality multipliers before regime multipliers (same result, but less literal against the stated sequence).
- **Consequences:** Every multiplier is a product on the base weight before a single renormalization, so the final weights do not depend on the order of the multiplicative steps; the order fixes how the adjustment trail is recorded and shown. Covered by unit tests on the weight pipeline.
- **Status:** Accepted pending owner confirmation.

### ADR-039: Display score rounding mode (PRD A-02)
- **Context:** `display = round((composite + 100) / 2, 1)` does not name a rounding mode. Python's built-in `round` rounds half to even on the binary float, so 78.45 can display as 78.4. ADR-030 covers presentation rounding of other fields but not the display formula itself.
- **Decision:** Compute the display score with `decimal` round half up (`ROUND_HALF_UP`) on the exact composite, quantized to 0.1. Because the display score is never negative, this equals round half away from zero, consistent with ADR-030.
- **Alternatives rejected:** Python built-in `round` (half to even and binary float artifacts make boundary cases such as 64.95 vs a 65 threshold depend on float representation).
- **Consequences:** A boundary test asserts composite 56.9 displays 78.5 (not 78.4). Selection compares the rounded display score with thresholds, as the formula states.
- **Status:** Accepted pending owner confirmation.

### ADR-040: Divergence weekly multiplier scope (PRD A-03)
- **Context:** "If the same divergence type also exists on weekly bars: multiply the total by 1.25" could apply per divergence or to the whole sum, and bullish and bearish divergences can coexist.
- **Decision:** Bullish and bearish points are summed with their signs (hidden at half value). The 1.25 multiplier applies once to that total when at least one counted daily divergence has a weekly divergence (pivot width 3) of the same type (regular or hidden, same direction) on the same oscillator. Then `clip(sum, -100, 100)`.
- **Alternatives rejected:** Per-divergence multiplier (reads "the total" as something other than the total).
- **Consequences:** Weekly confirmation is recorded as an evidence item naming the confirming oscillator.
- **Status:** Accepted pending owner confirmation.

### ADR-041: Fibonacci rule precedence (PRD A-04)
- **Context:** More than one Fibonacci rule can match at once (for example near 61.8 and near 50.0 when ATR is large relative to the leg); the specification gives no precedence.
- **Decision:** Evaluate in this order and take the first match: close above B (+20), close below 78.6 (-50), near 61.8 and holding (+80), near 50.0 and holding (+70), near 38.2 and holding (+60), otherwise 0. Mirrored with flipped signs for a down leg.
- **Alternatives rejected:** Summing matched rules (not stated, and could exceed the listed values); nearest level wins (adds an unstated distance rule).
- **Consequences:** Structural states (leg resumed, swing failed) override retracement holds; the deepest held level wins among holds. Unit tests cover each overlap.
- **Status:** Accepted pending owner confirmation.

### ADR-042: Confidence when the composite is exactly 0 (PRD A-05)
- **Context:** `agreement` counts weight held by factors "whose score has the same sign as composite", which is undefined when the composite is exactly 0.
- **Decision:** When the composite is 0, agreement = 0, so confidence starts at 0 before deductions. Factors with score exactly 0 never count toward agreement.
- **Alternatives rejected:** Treating 0 as positive (biases toward buys); agreement = 1 (overstates confidence).
- **Consequences:** Such a ticker has display 50.0 and cannot be a candidate under any threshold.
- **Status:** Accepted pending owner confirmation.

### ADR-043: Bollinger Bands use population standard deviation (PRD A-06)
- **Context:** The mean-reversion z-score names population stdev; Bollinger Bands (used for `pct_b` and `bbw`) do not state which.
- **Decision:** Population stdev (ddof = 0) for both, matching TradingView's `ta.bb`.
- **Alternatives rejected:** Sample stdev for Bollinger (inconsistent with the z-score and with TradingView).
- **Consequences:** Golden tests compare against TradingView-convention values.
- **Status:** Accepted pending owner confirmation.

### ADR-044: Order flow `daily_estimate` on daily bars (PRD A-07)
- **Context:** The zero-range rule uses `prev_close`; on daily bars `delta_pct_10` becomes the mean of the daily `delta_pct` values.
- **Decision:** Apply the classification formula per daily bar with the prior daily close as `prev_close`, compute `delta_pct` per session, and average over the last 10 sessions. Quality `daily_estimate`, weight x 0.6 (ADR-038 order).
- **Alternatives rejected:** A single 10-day aggregate bar (loses the per-session mean the formula defines).
- **Consequences:** The same code path serves intraday and daily inputs; only the bar source differs.
- **Status:** Accepted pending owner confirmation.

### ADR-045: Stale check kept at selection (PRD A-08)
- **Context:** Selection requires "data quality not `stale`", but stale tickers are already excluded before scoring.
- **Decision:** Both checks stay (defense in depth). A stale ticker never reaches selection; the selection check is asserted by a unit test that injects a stale score directly.
- **Alternatives rejected:** Dropping the selection check (weakens a literal selection rule, Implementation Note 5).
- **Consequences:** None at runtime; one extra guard.
- **Status:** Accepted pending owner confirmation.

### ADR-046: NFR-001 is measured on the full seed ingestion set (PRD A-09)
- **Context:** NFR-001 cites the 200-symbol seed, but VIX is never scored and some `needs_review` symbols start excluded.
- **Decision:** NFR-001 is measured on the full seed ingestion set (up to 200 symbols plus benchmarks). The scored count is lower and reported in the run summary.
- **Alternatives rejected:** Measuring only scored tickers (understates ingestion cost).
- **Consequences:** The benchmark test fixture uses the full seed list.
- **Status:** Accepted pending owner confirmation.

### ADR-047: Bands evaluated on the rounded display score (PRD A-11)
- **Context:** Bands are stated at one decimal (79.9, 35.1). An unrounded value such as 79.95 would fall in no band.
- **Decision:** Bands are evaluated on the rounded display score (ADR-039), so the band table has no gaps.
- **Alternatives rejected:** Evaluating on the unrounded value with half-open intervals (adds boundaries the table does not state).
- **Consequences:** Boundary tests cover 80.0, 79.9, 65.0, 64.9, 50.0, 49.9, 35.1, 35.0, 20.1, 20.0.
- **Status:** Accepted pending owner confirmation.

### ADR-048: Correlation guard return definition (PRD A-12)
- **Context:** "60-day return correlation" does not name the return type or how missing sessions are handled.
- **Decision:** Pearson correlation of daily close-to-close simple returns over the last 60 sessions both tickers traded.
- **Alternatives rejected:** Log returns (near-identical at daily scale, less common in the stated domain); price-level correlation (spurious for trending series).
- **Consequences:** Unit tests with known correlations; the correlation value is shown with each "also qualified" entry.
- **Status:** Accepted pending owner confirmation.

### ADR-049: Fundamentals provider is an allowed outbound destination (PRD A-14)
- **Context:** NFR-008 allows outbound calls only to the market data provider and the LLM endpoint; the Security Guidelines also allow the fundamentals provider, which may be a different vendor.
- **Decision:** The configured fundamentals provider is an allowed destination (FR-916); NFR-008 is read as covering it. The egress allowlist (section 9) lists market data provider, fundamentals provider, LLM gateway, Postgres, and DNS.
- **Alternatives rejected:** Forcing one vendor for both (removes pluggability, ADR-009).
- **Consequences:** The egress-blocked integration test permits exactly these destinations.
- **Status:** Accepted pending owner confirmation.

### ADR-050: Nearest miss selection (PRD A-15)
- **Context:** "The nearest candidate" is not defined when several tickers miss for different reasons.
- **Decision:** Per side, the nearest miss is the scored, non-excluded ticker with the smallest distance between its display score and that side's adjusted threshold; ties use the selection tie-breakers. The reason names the first failing rule in the order of the selection rules (PRD section 7.15).
- **Alternatives rejected:** Counting failed rules (less intuitive, needs its own tie rule).
- **Consequences:** `nearest_miss` (section 6.1) carries `ticker`, `display_score`, and `reason`; present only when that side has fewer picks than the max.
- **Status:** Accepted pending owner confirmation.

### ADR-051: CLA enforced without `pull_request_target`
- **Context:** S0-T08 needs a CLA check that blocks unsigned PRs from other accounts. Common CLA actions run on `pull_request_target`, which section 9 forbids, because it runs with a write token in the context of untrusted PR code.
- **Decision:** Two workflows. `cla.yml` runs on `pull_request` with a read-only token, checks out the base commit (never the PR head), reads `signatures/cla.json` from the `cla-signatures` branch, and runs `scripts/cla.py check`; the owner, `dependabot[bot]`, and `github-actions[bot]` are exempt. `cla-sign.yml` runs on `issue_comment`, never checks out PR code, records a signature when the comment is exactly "I have read the CLA Document and I hereby sign the CLA" (creating the `cla-signatures` branch on first use), and re-runs the `cla` check for that PR.
- **Alternatives rejected:** A hosted CLA bot (third-party write access to the repo); `pull_request_target` actions (forbidden); signatures committed to `develop` (every signature would need a protected-branch PR).
- **Consequences:** The check is merge-blocking only when `cla` is a required status check (owner checklist #18). A fork PR runs workflows from its own head, so a PR that edits `cla.yml` is visible in review and fork PRs from first-time contributors need approval before workflows run.
- **Status:** Accepted.

### ADR-052: Reviewed dev-only license exceptions
- **Context:** The license allowlist (ADR-016) rejects every license outside MIT, BSD, Apache-2.0, ISC, PSF, MPL-2.0, and LGPL. Four npm packages that only the UI toolchain uses carry other permissive licenses: `caniuse-lite` (CC-BY-4.0, browser data used by the build), `minimatch`, `lru-cache`, and `@isaacs/nonrecursive-glob-match` (BlueOak-1.0.0).
- **Decision:** `scripts/gen_third_party_licenses.py` keeps a named list of reviewed exceptions that applies only to dev-only npm packages. The same license on a runtime dependency still fails CI, as does GPL, AGPL, SSPL, or unknown anywhere.
- **Alternatives rejected:** Widening the allowlist for all dependencies (silently admits these licenses at runtime); dropping the tools (not possible without dropping Vite and ESLint).
- **Consequences:** Adding an exception is a reviewed code change with a test. `THIRD_PARTY_LICENSES.md` still lists these packages with their licenses.
- **Status:** Accepted.

### ADR-053: Indicator primitive definitions and package aggregation
- **Context:** S2-T01 needs exact definitions the spec leaves open, and later Sprint 2 tasks must add indicators in parallel without merge conflicts in `indicators/__init__.py`.
- **Decision:** `percentile_rank` is the share of the window's earlier n-1 values strictly below the current value, times 100. RSI of a flat window is 50 (all gains 100, all losses 0). ZigZag runs on closes; a swing is confirmed on the first close reversing by at least the threshold (per-bar array allowed, value at the reversal bar), and the running extreme is returned separately as tentative. `zigzag_threshold` uses the 8% floor while ATR is in warm-up. Pivots are reported only when `p + width <= last index`, with `confirmed_at = p + width`. `resample_weekly` works on numpy arrays and does not import `supertrends.data`; tests assert equality with `data/resample.py`. `indicators/__init__.py` star-imports every module and concatenates their `__all__`; tasks add names only to their own module's `__all__` (ruff `F401`/`F403` are ignored for that one file).
- **Alternatives rejected:** Dynamic `globals()` re-export (mypy cannot see the names); hand-edited `__init__.py` (conflicts across parallel tasks).
- **Consequences:** The number may need renumbering at merge. A new indicator module needs a one-line change here.
- **Status:** Accepted.

### ADR-054: Trend and momentum indicator definitions
- **Context:** Factor 2, Factor 3, and the regime ADX leave several details open (S2-T03).
- **Decision:** ADX uses Wilder: `+DM = up if up > down and up > 0 else 0`, `-DM = down if down > up and down > 0 else 0` (`up = high[t] - high[t-1]`, `down = low[t-1] - low[t]`), TR, +DM, and -DM smoothed with the Wilder RMA over bars 1..14, `+DI = 100 * RMA(+DM) / RMA(TR)`, `DX = 100 * |+DI - -DI| / (+DI + -DI)`, `ADX = RMA(DX, 14)`; any zero denominator yields 0, so a flat series gives DI = DX = ADX = 0. A cross at t needs the prior bar on the other side or equal (`a[t-1] <= b[t-1]` and `a[t] > b[t]` for golden); `last_cross` looks at the last N bars including the latest. Slope is `sma[t] - sma[t-5]`. Weekly MACD is evaluated as of each day from the completed weekly EMA state plus the in-progress week closed at that day's close, so it equals the finished weekly bar's MACD on the last session of a week and never uses later bars. A histogram run is 3 consecutive strict changes.
- **Alternatives rejected:** Forward-filling the last completed weekly MACD (stale by up to 4 days); recomputing the whole weekly series per day (O(n^2)).
- **Consequences:** The number may need renumbering at merge.
- **Status:** Accepted.

### ADR-055: Support and resistance clustering, strength, and Fibonacci projection

- **Context:** Factors 6 and 7 leave the clustering rule, the strength weighting, the "intact yesterday" test, and the extension anchor open.
- **Decision:** Pivot prices are sorted and clusters are anchored on their lowest price (a pivot joins while within `0.5 * atr14` of the anchor); the level is the mean price. Strength is the sum of per-touch weights `1 - 0.7 * age / 250` (identical to `touches * mean weight`). The 52-week high and low are extra levels (touches 1) on top of the 4 strongest per side. Breakout and breakdown use the levels computed as of the previous bar, so the flag appears only on the crossing bar. Fibonacci extensions are `A + ratio * (B - A)`; the ZigZag threshold is the scalar at the as-of bar. Both functions are as-of-last-bar: callers pass `bars[:t+1]`.
- **Alternatives rejected:** Single-linkage chaining (clusters can grow without bound); per-cluster mean weight times touches (same value, less clear).
- **Consequences:** The number may need renumbering at merge. See PRD A-22.
- **Status:** Accepted.

### ADR-056: Indicator registry and the determinism harness

- **Context:** NFR-007 needs every public indicator under the no-look-ahead property, and NFR-002 needs a committed determinism hash.
- **Decision:** `supertrends.indicators.registry` lists every public indicator with an adapter, its kind (series or as-of) and `confirm_lag`; non-indicator public names are exempt with a reason, and a test fails on any name in `indicators.__all__` that is neither. Hypothesis draws only generator parameters and numpy builds the bars. Weekly values are checked as of completed weeks (ADR-033). Hashes of the synthetic dataset and of all indicator outputs (canonical JSON, NaN as null, floats rounded to 10 significant digits by `round_significant`, because full-precision `repr` differed between macOS arm64 and Linux amd64 CI in the last bits of a few recursive indicators) live in `tests/golden/*.sha256` and change only through `scripts/regen-golden.sh --reason`. The package aggregator imports modules under `_m_` aliases so the `supertrend` function can be exported next to the module of the same name.
- **Alternatives rejected:** Registry under `tests/` (the snapshot task needs it too); drawing raw floats in hypothesis (slow shrinking).
- **Consequences:** `indicators.supertrend` is the function, so use `importlib` for the module. Profiles `ci` (100, derandomized) and `nightly` (1000) come from `HYPOTHESIS_PROFILE`.
- **Status:** Accepted.

### ADR-057: Indicator snapshot document and persistence

- **Context:** S2-T09 stores the `computing` output per ticker. The table key is (`run_id`, `symbol`) and has no date or hash column.
- **Decision:** `scoring.snapshot.compute_snapshot(bundle, cfg, as_of)` is pure: it drops bars after `as_of`, computes every registered per-bar indicator at the last bar with parameters from the config (registry defaults where the config has none: BBW rank window 126, ATR% rank window 252, relative volume 20, HV20), and returns canonical JSON (NaN null, floats to 10 significant digits via `indicators.registry.round_significant`, sorted keys in `snapshot_bytes`). It lives in `scoring/` because it reads the config; `indicators/` stays free of it. `data.snapshots.write_snapshot` is `INSERT ... ON CONFLICT DO NOTHING`; on conflict it compares the stored document and returns `unchanged` when equal, else raises `SnapshotConflictError`. `compute_and_store` refuses a config whose hash differs from `runs.config_hash`. No migration: date and hash come from the run row.
- **Alternatives rejected:** Adding `trade_date` and `config_hash` columns (duplicates `runs`, needs a migration); upsert (the table is append-only).
- **Consequences:** A retry of `computing` is safe. Changing bars or config means a new run.
- **Status:** Accepted.

---

## 4. Data Flows

Each flow lists its trigger, its steps in order, the tables read and written, and its failure behavior. Formulas referenced here are defined in `docs/PRD.md` (Signal Engine Specification).

### 4.1 Daily run (scheduled)

Trigger: CronJob at 17:30 America/New_York, Monday to Friday, `supertrends run daily` with no `--date`.

```
CronJob pod                     PostgreSQL                         Providers / LLM
-----------                     ----------                         ---------------
resolve trade date (ADR-022)
  not a session -> log "market closed", exit 0 (no row)
  session not closed + 30 min -> exit 3
pg_try_advisory_lock ---------> lock held for the run
reap abandoned runs (ADR-021) -> UPDATE runs SET state=failed
INSERT runs(state=queued) ----> partial unique index guards concurrency
transition ingesting ---------> run_transitions
  incremental ingest -----------------------------------------------> grouped daily bars (1 call/date)
                                                                     per-ticker backfill, splits,
                                                                     dividends, 5-min bars, financials,
                                                                     earnings dates
  upsert bars, actions, -------> bars_daily, bars_intraday, corporate_actions,
  fundamentals (known_at)        fundamentals, earnings_calendar, provider_calls
  new split -> full refetch of that ticker's adjusted history
  data-quality pass: ok | degraded | stale | insufficient_history
transition computing
  indicators on daily + weekly (resampled in memory, ADR-033) + intraday
  -------------------------------> indicator_snapshots
transition scoring
  11 factors, ticker regime, market regime, weight multipliers,
  event and fundamentals adjustments, renormalize, composite,
  display, band, confidence
  -------------------------------> factor_scores, ticker_scores (scored and excluded rows)
transition selecting
  candidates, ranking, tie-breakers, correlation guard (60 d, 0.9),
  max 3 buys / 2 sells, also qualified, nearest misses
  evidence documents, days_on_list (ADR-034)
transition narrating
  per pick: LLM with numeric guard (8 s timeout, one retry at T=0) ----> LLM gateway
            or template fallback
publish (one transaction, section 8)
  -------------------------------> recommendations, narratives, runs.published_at,
                                   runs.superseded_by on the prior published run, metric_counters
post-publication (failures logged, never fail the run)
  outcome tracking (4.5) --------> recommendations.entry_price (once), outcomes
  retention (ADR-031) -----------> DELETE old bars_intraday, provider_calls
release advisory lock, exit 0
```

Exclusions: tickers with quality `stale` or `insufficient_history` get a `ticker_scores` row with `status = 'excluded'` and `exclusion_reason`, are not scored, and are listed in `runs.summary.excluded`. Tickers below the liquidity floor are scored (they appear in rankings) but are never candidates. VIX-style index symbols and crypto entries from the seed are not ingested or scored.

Failure: any unhandled error in states `ingesting` through `narrating` moves the run to `failed` with `error_code` and `error_detail`; nothing from that run is visible as published; the previous published run remains latest. Narrative failures never fail the run (fallback to template). Provider rate limits wait inside the token bucket; persistent provider failure for a ticker degrades or excludes that ticker; failure of the benchmark data (SPY or QQQ) fails the run with `error_code = 'benchmark_unavailable'`, because market regime and outcomes depend on it.

### 4.2 Manual run

Trigger: `POST /api/v1/runs` (token), MCP `supertrends_run` (token), `supertrends run daily --api-url ...` (remote), or `supertrends run daily [--date]` (local).

1. Validate the date (ADR-022). Market closed returns 200 with `state: "market_closed"`.
2. Remote paths: the API inserts `runs(state='queued', trigger='api'|'mcp'|'cli')`. A unique violation on the active-run index returns 409 `run-in-progress` with the active `run_id`. Otherwise 202 with `run_id`, `state: "queued"`, and `Location: /api/v1/runs/{id}`.
3. The worker polls every `SUPERTRENDS_WORKER_POLL_SECONDS`, claims the oldest queued row with `SELECT ... FOR UPDATE SKIP LOCKED` inside a short transaction after acquiring the advisory lock, and runs the same orchestrator as 4.1 from `ingesting` onward.
4. Clients follow progress by polling `GET /api/v1/runs/{id}` (the UI polls every 2 s; the Pi extension streams `onUpdate` from the same polling). The response includes the transition list.
5. Local CLI mode runs inline in the CLI process and prints one line per transition.

Rerun for a date that already has a published run: a new run row is created; on success it is published and the previous run gets `superseded_by = new_run_id`; on failure the previous run stays published. Both rows remain.

### 4.3 UI read

1. Browser loads `/` from the API pod (static `ui/dist`, `index.html` with `Cache-Control: no-cache`, hashed assets with `max-age=31536000, immutable`).
2. The Today screen calls `GET /api/v1/recommendations/latest` and `GET /api/v1/status` through the generated typed client (TanStack Query).
3. The API resolves "latest" as the run with the greatest `trade_date` among runs where `published_at IS NOT NULL AND superseded_by IS NULL`, then reads `recommendations`, `narratives`, `ticker_scores` (also qualified, nearest miss, excluded), and `config_versions`. No score is recomputed; payloads are rendered from stored evidence.
4. Ticker screen: `GET /tickers/{symbol}/analysis?date=` (from `ticker_scores`, `factor_scores`, `indicator_snapshots`) and `GET /tickers/{symbol}/bars` (from `bars_daily` plus overlay series computed by the indicator registry on stored bars up to `to`; overlays are presentation only and never feed a score).
5. Date browsing uses `?date=`; when the date has no published run the API returns 404 `no-published-run` and the UI shows the nearest published dates.

### 4.4 Backtest

Trigger: `supertrends backtest --from --to --config` (CLI only, local mode).

1. Validate the config; compute its `config_hash`; insert into `config_versions` if new.
2. Insert `backtests.backtest_runs(state='running')`.
3. For each session t in range: load bars with `date <= t`, fundamentals with `known_at <= t` (end of session t), earnings calendar as known at t; run the same indicator, factor, composite, and selection functions as live runs; narratives are not generated (the template evidence is stored). Picks go to `backtests.picks`.
4. Entries at the open of t+1; forward returns at 1, 5, 10, 20 sessions for the pick and SPY into `backtests.outcomes`.
5. Equity curve "equal weight the daily buys, hold 5 days" versus SPY into `backtests.equity_curve`.
6. Mark the backtest `completed` (or `failed`), write JSON and a Markdown summary to `--out` (default `./backtest-{id}.json` and `.md`). Every artifact and payload carries `hypothetical: true` and the disclaimer.

Isolation: the backtest never writes to `public.runs`, `public.recommendations`, or `public.outcomes`, and does not take the run advisory lock (it can run alongside a daily run).

### 4.5 Outcome measurement

Runs as the post-publication step of every successful daily run (and is also callable through `supertrends track-record --refresh` in local mode).

1. Entry prices: for every recommendation with `entry_price IS NULL` whose next session after `trade_date` has a stored daily bar, set `entry_price` to that session's adjusted open. The trigger allows this single update from NULL to a value.
2. For each recommendation with an entry price and each horizon h in {1, 5, 10, 20}: if no outcome row exists and exit session h has closed and has a stored bar, compute `pick_return = close(exit) / entry_price - 1` with adjusted prices, where the entry session counts as session 1 and the exit session is session h (ADR-036), the same for SPY over the same sessions (SPY entry at the same open), and `excess_return = pick_return - benchmark_return`. Insert one `outcomes` row. Splits between entry and exit are handled because all bars are adjusted, and adjusted history is refetched on a new split.
3. Statistics (`GET /api/v1/track-record`) are computed on read from `recommendations` joined with `outcomes`: hit rate (buy hit when excess > 0, sell hit when excess < 0), mean and median excess, worst pick, sample size, `small_sample` when n < 20; per side, per horizon, overall and by band, filterable by config hash.

Entry price adjustment note: `entry_price` is stored as the adjusted open known at fill time. If a later split re-adjusts history, outcome computation uses the stored bar series consistently adjusted at computation time and rescales `entry_price` by the cumulative split factor between fill and computation, recorded in the outcome row (`adjustment_factor`).

---

## 5. Database Schema

PostgreSQL 17. Schema `public` for the live system and schema `backtests` for hypothetical results (ADR-029). Names are snake_case. All timestamps are `timestamptz` (UTC); trade dates are `date`. Prices are `double precision` (adjusted values are derived floats; exact decimal storage brings no benefit for computed indicators), volumes are `bigint`. IDs for runs, recommendations, and backtests are ULIDs stored as `text` with a `CHECK (length(id) = 26)`.

### 5.1 Live tables

#### `tickers`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `symbol` | `text` | no | | PK. `CHECK (symbol ~ '^[A-Z][A-Z0-9.\-]{0,9}$')` |
| `name` | `text` | yes | | from provider reference data; never placed in an LLM prompt |
| `type` | `text` | no | `'stock'` | `CHECK (type IN ('stock','etf','index','crypto'))` |
| `active` | `boolean` | no | `true` | |
| `is_benchmark` | `boolean` | no | `false` | true for SPY, QQQ |
| `resolution` | `text` | no | `'resolved'` | `CHECK (resolution IN ('resolved','unresolved','needs_review'))` |
| `resolution_reason` | `text` | yes | | |
| `avg_dollar_volume_20d` | `double precision` | yes | | updated each run |
| `created_at` | `timestamptz` | no | `now()` | |
| `updated_at` | `timestamptz` | no | `now()` | |

#### `watchlists`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `integer` | no | identity | PK |
| `name` | `text` | no | `'default'` | `UNIQUE` |
| `is_default` | `boolean` | no | `true` | partial unique index `WHERE is_default` |
| `created_at` | `timestamptz` | no | `now()` | |

#### `watchlist_items`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `watchlist_id` | `integer` | no | | FK `watchlists(id)` ON DELETE CASCADE |
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `added_at` | `timestamptz` | no | `now()` | |
| `source` | `text` | no | `'user'` | `CHECK (source IN ('seed','user','api','cli','mcp'))` |
| `scored` | `boolean` | no | `true` | false for index symbols such as VIX |

PK (`watchlist_id`, `symbol`). The 300-item cap is enforced in the service (422) and by a constraint trigger that counts rows per watchlist.

#### `watchlist_groups`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `integer` | no | identity | PK |
| `watchlist_id` | `integer` | no | | FK `watchlists(id)` ON DELETE CASCADE |
| `slug` | `text` | no | | `CHECK (slug ~ '^[a-z0-9][a-z0-9-]{0,47}$')` |
| `name` | `text` | no | | display name, max 64 chars |
| `position` | `integer` | no | `0` | display order |

`UNIQUE (watchlist_id, slug)`.

#### `watchlist_group_members`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `group_id` | `integer` | no | | FK `watchlist_groups(id)` ON DELETE CASCADE |
| `watchlist_id` | `integer` | no | | part of FK to items |
| `symbol` | `text` | no | | FK (`watchlist_id`, `symbol`) to `watchlist_items` ON DELETE CASCADE |

PK (`group_id`, `symbol`). Index on (`watchlist_id`, `symbol`).

#### `bars_daily`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `date` | `date` | no | | session date |
| `open`, `high`, `low`, `close` | `double precision` | no | | split and dividend adjusted per provider capability `adjusted` |
| `volume` | `bigint` | no | | `CHECK (volume >= 0)` |
| `vwap` | `double precision` | yes | | when provided |
| `adjusted_at` | `timestamptz` | no | `now()` | last adjustment refetch |
| `provider` | `text` | no | | registry name |

PK (`symbol`, `date`). Index `ix_bars_daily_date` on (`date`). `CHECK (high >= low)`.

#### `bars_intraday`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `ts` | `timestamptz` | no | | bar start, 5-minute bars |
| `open`, `high`, `low`, `close` | `double precision` | no | | |
| `volume` | `bigint` | no | | |
| `provider` | `text` | no | | |

PK (`symbol`, `ts`). Index on (`ts`) for retention. 90-day retention (ADR-031).

#### `corporate_actions`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `ex_date` | `date` | no | | |
| `kind` | `text` | no | | `CHECK (kind IN ('split','dividend'))` |
| `ratio` | `double precision` | yes | | split to/from ratio |
| `amount` | `double precision` | yes | | cash dividend |
| `first_seen_at` | `timestamptz` | no | `now()` | a new split row triggers a full refetch |

PK (`symbol`, `ex_date`, `kind`).

#### `fundamentals`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `period_end` | `date` | no | | fiscal quarter end |
| `known_at` | `timestamptz` | no | | filing or provider availability time; point-in-time key |
| `metrics` | `jsonb` | no | | revenue, eps, gross margin, operating margin, fcf, net debt, shares, estimates when available |
| `provider` | `text` | no | | |

PK (`symbol`, `period_end`, `known_at`). Index on (`symbol`, `known_at`).

#### `earnings_calendar`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `date` | `date` | no | | |
| `confirmed` | `boolean` | no | `false` | |
| `known_at` | `timestamptz` | no | `now()` | |

PK (`symbol`, `date`).

#### `config_versions`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `hash` | `text` | no | | PK, `sha256:<64 hex>` |
| `version` | `integer` | no | | `scoring.version` |
| `document` | `jsonb` | no | | full validated document |
| `first_seen_at` | `timestamptz` | no | `now()` | |

Insert-only (no updates; enforced by the append-only trigger).

#### `runs`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `text` | no | | PK, ULID |
| `trade_date` | `date` | no | | |
| `state` | `text` | no | `'queued'` | `CHECK (state IN ('queued','ingesting','computing','scoring','selecting','narrating','published','failed'))` |
| `trigger` | `text` | no | | `CHECK (trigger IN ('schedule','api','mcp','cli','demo'))` |
| `config_hash` | `text` | no | | FK `config_versions(hash)` |
| `code_version` | `text` | no | | `VERSION (commit)` |
| `market_regime` | `text` | yes | | `risk_on`, `risk_off`, `neutral` |
| `created_at` | `timestamptz` | no | `now()` | |
| `started_at` | `timestamptz` | yes | | first non-queued transition |
| `finished_at` | `timestamptz` | yes | | published or failed |
| `published_at` | `timestamptz` | yes | | set only in the publication transaction |
| `superseded_by` | `text` | yes | | FK `runs(id)` |
| `error_code` | `text` | yes | | `abandoned`, `not_picked_up`, `benchmark_unavailable`, `provider_unavailable`, `internal` |
| `error_detail` | `text` | yes | | secret-free message, max 2000 chars |
| `summary` | `jsonb` | no | `'{}'` | counts, exclusions, narrative sources, durations |

Indexes: `ix_runs_trade_date_published_at` on (`trade_date`, `published_at`); `ux_runs_one_active` UNIQUE on (`(1)`) `WHERE state NOT IN ('published','failed')` (ADR-021); `ux_runs_one_current_per_date` UNIQUE on (`trade_date`) `WHERE published_at IS NOT NULL AND superseded_by IS NULL`. `CHECK ((state = 'published') = (published_at IS NOT NULL))`. Update rules: a trigger allows only forward state transitions (section 8) and allows `superseded_by` to be set once, from NULL, on a published run.

#### `run_transitions`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `run_id` | `text` | no | | FK `runs(id)` |
| `seq` | `integer` | no | | 1, 2, 3, ... |
| `from_state` | `text` | yes | | NULL for the initial `queued` |
| `to_state` | `text` | no | | |
| `at` | `timestamptz` | no | `now()` | |
| `detail` | `jsonb` | no | `'{}'` | counts at the transition |

PK (`run_id`, `seq`). Append-only.

#### `indicator_snapshots`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `run_id` | `text` | no | | FK `runs(id)` |
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `values` | `jsonb` | no | | values at bar t for every registered indicator, daily and weekly |

PK (`run_id`, `symbol`). Append-only. The trade date and config hash are those of the `runs` row (the document repeats them as `as_of` and `config_hash`). `values` is the canonical snapshot of ADR-057: `daily`, `weekly`, `levels`, `fib`, `divergences`, `flow`. A write of an equal document for an existing key is skipped; a different one raises (no UPDATE ever).

#### `ticker_scores`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `run_id` | `text` | no | | FK `runs(id)` |
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `status` | `text` | no | | `CHECK (status IN ('scored','excluded'))` |
| `exclusion_reason` | `text` | yes | | `stale`, `insufficient_history`, `no_data`, `unresolved`; required when excluded |
| `data_quality` | `text` | no | | `ok`, `degraded`, `stale`, `insufficient_history` |
| `composite` | `double precision` | yes | | -100..100, NULL when excluded |
| `display_score` | `numeric(4,1)` | yes | | 0..100 |
| `band` | `text` | yes | | six bands |
| `confidence` | `double precision` | yes | | 0..100, full precision (ADR-030) |
| `regime` | `text` | yes | | `trending`, `ranging`, `transitional` |
| `st_dir_d`, `st_dir_w` | `smallint` | yes | | -1 or 1 |
| `bars_since_flip` | `integer` | yes | | |
| `st_line` | `double precision` | yes | | |
| `buy_threshold`, `sell_threshold` | `numeric(4,1)` | yes | | after adjustments |
| `candidate` | `text` | yes | | `buy`, `sell`, or NULL |
| `rank_overall` | `integer` | yes | | by display descending |
| `weights` | `jsonb` | yes | | base and final weight per factor |
| `adjustments` | `jsonb` | no | `'[]'` | adjustments that fired |
| `flags` | `jsonb` | no | `'[]'` | `event_risk`, `low_liquidity`, ... |
| `avg_dollar_volume_20d` | `double precision` | yes | | |
| `rel_volume` | `double precision` | yes | | tie-breaker input |

PK (`run_id`, `symbol`). Index on (`symbol`, `run_id`). `CHECK (status = 'scored' OR exclusion_reason IS NOT NULL)`. Append-only.

#### `factor_scores`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `run_id` | `text` | no | | FK `runs(id)` |
| `symbol` | `text` | no | | |
| `factor_id` | `text` | no | | one of the 11 factor IDs |
| `score` | `double precision` | yes | | `CHECK (score BETWEEN -100 AND 100)`; NULL when quality is missing |
| `weight` | `double precision` | no | | final weight after renormalization, 0..100 |
| `contribution` | `double precision` | no | | `weight * score / 100` |
| `quality` | `text` | no | | `ok`, `degraded`, `missing`, `daily_estimate` |
| `evidence` | `jsonb` | no | | reasons and inputs |

PK (`run_id`, `symbol`, `factor_id`). FK (`run_id`, `symbol`) to `ticker_scores`. Index `ix_factor_scores_symbol_run` on (`symbol`, `run_id`). Append-only.

#### `recommendations`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `text` | no | | PK, ULID |
| `run_id` | `text` | no | | FK `runs(id)` |
| `symbol` | `text` | no | | FK `tickers(symbol)` |
| `trade_date` | `date` | no | | denormalized from the run |
| `side` | `text` | no | | `CHECK (side IN ('buy','sell'))` |
| `rank` | `smallint` | no | | `CHECK (rank >= 1)` |
| `display_score` | `numeric(4,1)` | no | | |
| `confidence` | `double precision` | no | | |
| `band` | `text` | no | | |
| `evidence` | `jsonb` | no | | the evidence document (validated against the committed JSON schema): the section 7.16 shape plus required `expected_1d_move` (`atr14`) and flow quality |
| `entry_price` | `double precision` | yes | | filled once |
| `entry_date` | `date` | yes | | filled once with `entry_price` |
| `created_at` | `timestamptz` | no | `now()` | |

`UNIQUE (run_id, side, rank)` (also the required index `ix_recommendations_run_side_rank`). `UNIQUE (run_id, symbol)`. Index on (`symbol`, `trade_date`). Append-only except `entry_price` and `entry_date`, which may change once from NULL to a value.

#### `narratives`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `recommendation_id` | `text` | no | | PK, FK `recommendations(id)` |
| `text` | `text` | no | | plain text, max 1200 chars |
| `source` | `text` | no | | `CHECK (source IN ('llm','template'))` |
| `model` | `text` | yes | | model name for `llm` |
| `prompt_version` | `text` | no | | e.g. `narrative-v1` |
| `tokens_in`, `tokens_out` | `integer` | yes | | |
| `attempts` | `smallint` | no | `1` | 1 or 2 LLM attempts |
| `rejection_reasons` | `jsonb` | no | `'[]'` | `numeric_guard`, `banned_phrase`, `length`, `timeout`, `error` |

Append-only.

#### `outcomes`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `recommendation_id` | `text` | no | | FK `recommendations(id)` |
| `horizon_days` | `smallint` | no | | `CHECK (horizon_days IN (1,5,10,20))` |
| `exit_date` | `date` | no | | |
| `pick_return` | `double precision` | no | | renamed from seed `return` (ADR-018) |
| `benchmark_return` | `double precision` | no | | SPY over the same window |
| `excess_return` | `double precision` | no | | |
| `adjustment_factor` | `double precision` | no | `1.0` | split rescale of entry price |
| `computed_at` | `timestamptz` | no | `now()` | |

PK (`recommendation_id`, `horizon_days`). Append-only.

#### `provider_calls`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `bigint` | no | identity | PK |
| `run_id` | `text` | yes | | FK `runs(id)` ON DELETE SET NULL |
| `provider` | `text` | no | | registry name |
| `endpoint` | `text` | no | | path template only, never a URL with a key |
| `params` | `jsonb` | no | `'{}'` | non-secret params |
| `status` | `text` | no | | HTTP status code or `timeout`, `error` |
| `duration_ms` | `integer` | no | | |
| `cache_hit` | `boolean` | no | `false` | |
| `ts` | `timestamptz` | no | `now()` | |

Index on (`ts`), on (`provider`, `ts`). 30-day retention.

#### `metric_counters`
| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `name` | `text` | no | | metric name |
| `labels` | `jsonb` | no | `'{}'` | canonical sorted label set |
| `value` | `double precision` | no | `0` | monotonic |
| `updated_at` | `timestamptz` | no | `now()` | |

PK (`name`, `labels`). Updated with `INSERT ... ON CONFLICT DO UPDATE SET value = value + EXCLUDED.value`. Never pruned (ADR-023).

### 5.2 `backtests` schema

| Table | Columns (type, null) | Keys and notes |
|---|---|---|
| `backtests.backtest_runs` | `id text` no; `from_date date` no; `to_date date` no; `config_hash text` no FK `public.config_versions`; `code_version text` no; `state text` no (`running`, `completed`, `failed`); `created_at timestamptz` no default `now()`; `finished_at timestamptz` yes; `tickers integer` no; `summary jsonb` no default `'{}'`; `error_detail text` yes | PK `id`. `hypothetical` is implicit for every row and always emitted as true |
| `backtests.picks` | `backtest_id text` no FK; `trade_date date` no; `symbol text` no; `side text` no; `rank smallint` no; `display_score numeric(4,1)` no; `confidence double precision` no; `band text` no; `evidence jsonb` no; `entry_price double precision` yes; `entry_date date` yes | PK (`backtest_id`, `trade_date`, `side`, `rank`) |
| `backtests.outcomes` | `backtest_id text` no; `trade_date date` no; `side text` no; `rank smallint` no; `horizon_days smallint` no; `pick_return`, `benchmark_return`, `excess_return double precision` no | PK (`backtest_id`, `trade_date`, `side`, `rank`, `horizon_days`), FK to `backtests.picks` |
| `backtests.equity_curve` | `backtest_id text` no; `date date` no; `strategy_equity double precision` no; `benchmark_equity double precision` no | PK (`backtest_id`, `date`) |

Backtest tables are deletable with `supertrends backtest --delete ID` (they are hypothetical and not part of the published record).

### 5.3 Append-only rules

A single trigger function `supertrends_reject_mutation()` raises `append_only_violation` (SQLSTATE `P0001`, message names the table) on `UPDATE` or `DELETE`. It is attached `BEFORE UPDATE OR DELETE` to: `config_versions`, `run_transitions`, `indicator_snapshots`, `ticker_scores`, `factor_scores`, `narratives`, `outcomes`.

`recommendations` uses `supertrends_recommendations_guard()`: DELETE always rejected; UPDATE allowed only when every column other than `entry_price` and `entry_date` is unchanged and `OLD.entry_price IS NULL AND NEW.entry_price IS NOT NULL`.

`runs` uses `supertrends_runs_guard()`: DELETE rejected; state may only move forward along section 8 edges; `published_at` may only be set together with `state = 'published'`; a run in a terminal state is immutable except `superseded_by` set once from NULL.

Retention deletes (`bars_intraday`, `provider_calls`) are on tables without the trigger. No migration may drop or weaken these triggers without an ADR.

### 5.4 Migrations

- Alembic, revisions in `migrations/versions/`, one revision per schema change, named `NNNN_short_description.py` with a sequential prefix.
- `supertrends db migrate` runs `alembic upgrade head` under the advisory lock `hashtext('supertrends.migrate')` so concurrent migration Jobs serialize.
- Expand and contract: a revision released in version N must leave the schema usable by version N-1 (add nullable columns or columns with defaults, add tables, backfill in a later release; drop or rename only one release after the code stopped using it). This makes `helm rollback` safe without a down migration.
- `downgrade` is implemented for every revision and tested (`upgrade head` then `downgrade base` on an empty database in CI), but production rollback never runs downgrades.
- `/readyz` returns 503 until the database revision equals the head revision bundled in the image.
- Triggers and the `backtests` schema are created in migrations, not by SQLAlchemy `create_all`.

---

## 6. API Contract

### 6.0 Common rules (all surfaces)

- **Disclaimer.** Every HTTP payload, CLI output (text and `--json`), and MCP result that carries a pick, a score, a ranking, an analysis, or track-record or backtest statistics includes the field `"disclaimer"` with the exact text below (ADR-030). In text CLI output it is printed as the last paragraph.

  > Super Trends output is general market analysis generated by an algorithm from technical and fundamental data. It is not investment advice, not a recommendation tailored to you, and not an offer to buy or sell any security. The algorithm can be and often is wrong. Past and backtested performance does not predict future results. You are responsible for your own decisions.

- **Hypothetical label.** Every backtest payload carries `"hypothetical": true` and a `"label": "Backtest (hypothetical)"`.
- **Rounding.** Scores, weights, contributions, and returns presented at 1 decimal (returns as percent with 2 decimals in `*_pct` fields); `confidence` as an integer (ADR-030).
- **Validation.** `symbol` path and body values are uppercased, then must match `^[A-Z][A-Z0-9.\-]{0,9}$`. `date` values are `YYYY-MM-DD`, must be an XNYS session, and must not be after the last completed session. Unknown query parameters are rejected with 422. Request bodies reject additional properties.
- **IDs.** Run, recommendation, and backtest IDs are 26-character ULIDs.
- **Content type.** `application/json; charset=utf-8`; errors use `application/problem+json`.
- **Request ID.** Every response carries `X-Request-ID` (echoed if the client sent a valid one, else generated); it appears in logs and problem bodies.

### 6.1 HTTP endpoints

Base URL: the instance origin (canonical `https://supertrends.openstoke.com` on Stoke, `http://127.0.0.1:8080` locally). JSON API under `/api/v1`. The OpenAPI 3.1 document is generated by `supertrends config export-openapi` into `docs/openapi.json` and diffed in CI; it must agree with this section.

**Authentication.** Read endpoints: none (protected by the network boundary and the Host allowlist). Write endpoints: `Authorization: Bearer <SUPERTRENDS_API_TOKEN>`, compared with `hmac.compare_digest`. Missing or wrong token: 401 `unauthorized` with `WWW-Authenticate: Bearer`. Writes are rate-limited per client IP to `SUPERTRENDS_WRITE_RATE_PER_MIN` (default 30) with a token bucket; excess returns 429 `rate-limited` with `Retry-After`.

**Errors (RFC 9457).** Body:

```json
{
  "type": "urn:supertrends:problem:run-in-progress",
  "title": "A run is already in progress",
  "status": 409,
  "detail": "Run 01JCX4... for 2026-11-13 is in state scoring.",
  "instance": "/api/v1/runs",
  "request_id": "6f1c2a7e9b8d4c55",
  "errors": [{"loc": ["body", "date"], "msg": "not a trading date"}]
}
```

`errors` is present only for 422. `detail` never contains a secret, a stack trace, or provider response bodies. Problem slugs:

| Status | Slug | When |
|---|---|---|
| 400 | `bad-request` | malformed JSON |
| 401 | `unauthorized` | missing or invalid bearer token on a write |
| 404 | `not-found` | unknown route, run, backtest, config hash |
| 404 | `no-published-run` | no published run for the requested date, or none yet |
| 404 | `ticker-not-found` | symbol not on the watchlist and not a benchmark |
| 405 | `method-not-allowed` | |
| 409 | `run-in-progress` | an active run exists; `detail` names it and the body adds `active_run_id` |
| 409 | `session-not-complete` | default date is a session not yet closed plus 30 minutes |
| 409 | `already-exists` | watchlist symbol or group slug exists |
| 421 | `misdirected-request` | `Host` not in the allowlist (ADR-024) |
| 422 | `validation-error` | invalid parameter or body |
| 422 | `not-a-trading-date` | date is not an XNYS session |
| 422 | `date-in-future` | date after the last completed session |
| 422 | `watchlist-full` | the 301st item |
| 422 | `symbol-unresolved` | provider reference data cannot resolve the symbol |
| 429 | `rate-limited` | write rate exceeded |
| 500 | `internal` | unhandled error (logged with request ID) |
| 503 | `not-ready` | database unreachable or migrations not at head |

Shared JSON objects (used below):

```json
// Pick (buys[], sells[]); also the item shape of also_qualified[] with "duplicates" added
{
  "rank": 1, "ticker": "ORCL", "display_score": 78.4, "band": "Buy", "confidence": 71,
  "supertrend": {"dir_d": 1, "dir_w": 1, "bars_since_flip": 3, "line": 212.4},
  "regime": "trending", "flags": [], "days_on_list": 1,
  "invalidation": {"level": 212.4, "rule": "daily close below the Supertrend line"},
  "expected_1d_move": 4.1,
  "top_factors": [{"id": "supertrend", "contribution": 23.4}, {"id": "macd", "contribution": 9.1}],
  "narrative": {"text": "...", "source": "llm", "model": "..."},
  "ribbon": "UUUUDDDUUU",
  "recommendation_id": "01JCX...",
  "entry_price": null
}

// AlsoQualified
{"ticker": "VOO", "side": "buy", "display_score": 77.9, "confidence": 70, "duplicates": "SPY", "correlation": 0.99}

// NearestMiss (per side, present only when that side has fewer picks than the max)
{"ticker": "XYZ", "display_score": 37.2, "reason": "score above the sell threshold of 35"}

// Excluded
{"ticker": "ABC", "reason": "stale"}
```

`expected_1d_move` is `atr14` in price units (Factor 8, "shown on every card"); it is always present on a Pick, never null, and is also stored in the pick's evidence document. `ribbon` is the last 10 daily Supertrend directions oldest first (`U` up, `D` down). `top_factors` has the 3 largest absolute contributions. `flags` values: `event_risk`, `weekly_disagrees`, `high_volatility`, `degraded_data`, `daily_estimate_flow`.

---

#### GET `/healthz`
Auth: none. Host check exempt. Liveness only (no database access).
Response 200:
```json
{"status": "ok", "version": "1.0.0", "commit": "abc1234"}
```

#### GET `/readyz`
Auth: none. Host check exempt.
Response 200 `{"status": "ready", "database": "ok", "migrations": "head", "revision": "0007"}`. Response 503 (problem `not-ready`) with the same fields set to `"unreachable"` or `"behind"`.

#### GET `/metrics`
Auth: none (cluster-internal; NetworkPolicy limits callers to the monitoring namespace). Host check exempt. Response 200 Prometheus text format 0.0.4 (section 11).

#### GET `/api/v1/recommendations/latest`
Auth: none. Returns the latest current published run (section 4.3).
Response 200:
```json
{
  "date": "2026-11-13",
  "run_id": "01JCX...",
  "published_at": "2026-11-13T22:34:10Z",
  "market_regime": "risk_on",
  "config": {"version": 1, "hash": "sha256:..."},
  "buys": [ /* Pick, max selection.max_buys */ ],
  "sells": [ /* Pick, max selection.max_sells */ ],
  "also_qualified": [ /* AlsoQualified */ ],
  "nearest_miss": {"buy": null, "sell": {"ticker": "XYZ", "display_score": 37.2, "reason": "score above the sell threshold of 35"}},
  "excluded": [{"ticker": "ABC", "reason": "stale"}],
  "summary": {"tickers_total": 200, "tickers_scored": 196, "tickers_excluded": 4, "narrative_llm": 4, "narrative_template": 1},
  "superseded_runs": [],
  "disclaimer": "Super Trends output is general market analysis ..."
}
```
Errors: 404 `no-published-run` (fresh install).

#### GET `/api/v1/recommendations?date=YYYY-MM-DD`
Auth: none. `date` required. Same response as `latest` for the current published run of that date; `superseded_runs` lists earlier published run IDs for the date with their `published_at`. Errors: 404 `no-published-run`, 422 `validation-error`, `not-a-trading-date`, `date-in-future`.

#### GET `/api/v1/rankings?date=&limit=&offset=&group=`
Auth: none. `date` optional (default latest published run date); `limit` 1..300 default 50; `offset` >= 0 default 0; `group` optional group slug.
Response 200:
```json
{
  "date": "2026-11-13", "run_id": "01JCX...", "config": {"version": 1, "hash": "sha256:..."},
  "total": 196, "limit": 50, "offset": 0,
  "items": [
    {"rank": 1, "ticker": "ORCL", "display_score": 78.4, "band": "Buy", "confidence": 71,
     "composite": 56.8, "regime": "trending", "st_dir_d": 1, "st_dir_w": 1, "bars_since_flip": 3,
     "candidate": "buy", "picked": "buy", "flags": [], "groups": ["ai-infra"]}
  ],
  "excluded": [{"ticker": "ABC", "reason": "stale"}],
  "disclaimer": "..."
}
```
`picked` is `buy`, `sell`, `also_qualified`, or null. Errors: 404 `no-published-run`, 404 `not-found` (group), 422.

#### GET `/api/v1/tickers/{symbol}/analysis?date=`
Auth: none. `date` optional (default latest published run date).
Response 200:
```json
{
  "ticker": "ORCL", "name": "Oracle Corp", "date": "2026-11-13", "run_id": "01JCX...",
  "status": "scored", "data_quality": "ok",
  "display_score": 78.4, "composite": 56.8, "band": "Buy", "confidence": 71,
  "regime": "trending", "market_regime": "risk_on",
  "supertrend": {"dir_d": 1, "dir_w": 1, "bars_since_flip": 3, "line": 212.4, "distance_atr": 1.2},
  "thresholds": {"buy": 65.0, "sell": 30.0},
  "candidate": "buy", "picked": {"side": "buy", "rank": 1, "recommendation_id": "01JCX..."},
  "factors": [
    {"id": "supertrend", "score": 100.0, "base_weight": 20.0, "weight": 23.4, "contribution": 23.4,
     "quality": "ok", "reasons": ["Daily Supertrend flipped up 3 bars ago", "Weekly Supertrend agrees"]}
  ],
  "adjustments": ["trending regime"],
  "flags": [],
  "levels": {"support": [215.1, 208.7], "resistance": [229.5, 236.0], "fib": {"61.8": 214.2}, "next_target": 236.0},
  "invalidation": {"level": 212.4, "rule": "daily close below the Supertrend line"},
  "expected_1d_move": 4.1,
  "fundamentals": {"quality": "ok", "valuation_basis": "trailing_pe", "days_to_earnings": 12, "sub_scores": {}},
  "order_flow": {"label": "estimated order flow", "quality": "intraday_estimate"},
  "narrative": {"text": "...", "source": "template", "model": null},
  "config": {"version": 1, "hash": "sha256:..."},
  "disclaimer": "..."
}
```
For an excluded ticker: `status: "excluded"`, `exclusion_reason`, and score fields null. `narrative` is present only for picks. Errors: 404 `ticker-not-found`, 404 `no-published-run`, 422.

#### GET `/api/v1/tickers/{symbol}/bars?tf=1d&from=&to=`
Auth: none. `tf` is `1d` (default), `1w`, or `5m`; `from`, `to` dates (default: last 252 sessions ending at the latest stored bar; max span 1260 sessions for `1d`/`1w`, 30 sessions for `5m`).
Response 200:
```json
{
  "ticker": "ORCL", "tf": "1d", "from": "2025-11-13", "to": "2026-11-13",
  "bars": [{"t": "2026-11-13", "o": 220.1, "h": 224.0, "l": 219.2, "c": 223.5, "v": 9123000}],
  "overlays": {
    "supertrend": [{"t": "2026-11-13", "value": 212.4, "dir": 1}],
    "sma_20": [{"t": "2026-11-13", "value": 218.0}], "sma_50": [], "sma_200": []
  }
}
```
Overlay values are NaN-free (warm-up points omitted). No disclaimer (no pick or score). Errors: 404 `ticker-not-found`, 422.

#### GET `/api/v1/tickers/{symbol}/history?from=&to=&limit=`
Auth: none. `limit` 1..500 default 120 (most recent first).
Response 200:
```json
{
  "ticker": "ORCL",
  "scores": [{"date": "2026-11-13", "run_id": "01JCX...", "display_score": 78.4, "band": "Buy", "confidence": 71, "regime": "trending", "status": "scored"}],
  "picks": [{"date": "2026-11-13", "side": "buy", "rank": 1, "recommendation_id": "01JCX...", "entry_price": null, "outcomes": {"1": null, "5": null, "10": null, "20": null}}],
  "disclaimer": "..."
}
```
Only current published runs are included. Errors: 404 `ticker-not-found`, 422.

#### GET `/api/v1/watchlist`
Auth: none.
Response 200:
```json
{
  "id": 1, "name": "default", "count": 200, "max": 300,
  "groups": [{"slug": "ai-infra", "name": "AI Infra", "position": 0, "symbols": ["NVDA", "ORCL"]}],
  "items": [{"symbol": "ORCL", "name": "Oracle Corp", "type": "stock", "scored": true, "resolution": "resolved", "resolution_reason": null, "added_at": "2026-11-01T12:00:00Z", "groups": ["ai-infra"]}],
  "benchmarks": ["SPY", "QQQ"]
}
```

#### POST `/api/v1/watchlist/items`
Auth: token. Body `{"symbol": "ORCL", "groups": ["ai-infra"]}` (`groups` optional, existing slugs).
Response 201 with the item object and `Location: /api/v1/watchlist`. Errors: 401, 409 `already-exists`, 422 `validation-error`, `watchlist-full`, `symbol-unresolved`, 429.

#### DELETE `/api/v1/watchlist/items/{symbol}`
Auth: token. Removes the item and its memberships; history is kept. Removing SPY or QQQ removes them from the watchlist only (they stay ingested as benchmarks). Response 204. Errors: 401, 404 `not-found`, 429.

#### PUT `/api/v1/watchlist/items/{symbol}/groups` (ADR-025)
Auth: token. Body `{"groups": ["ai-infra", "megacap"]}` replaces the item's memberships (empty list allowed). Response 200 item object. Errors: 401, 404, 422 (unknown slug), 429.

#### POST `/api/v1/watchlist/groups` (ADR-025)
Auth: token. Body `{"slug": "ai-infra", "name": "AI Infra", "position": 0}`. Response 201 group object. Errors: 401, 409 `already-exists`, 422, 429.

#### DELETE `/api/v1/watchlist/groups/{slug}` (ADR-025)
Auth: token. Deletes the group and memberships, never the items. Response 204. Errors: 401, 404, 429.

#### GET `/api/v1/runs?limit=&before=`
Auth: none. `limit` 1..200 default 30; `before` optional run ID cursor.
Response 200:
```json
{
  "items": [{"id": "01JCX...", "trade_date": "2026-11-13", "state": "published", "trigger": "schedule",
             "created_at": "...", "started_at": "...", "finished_at": "...", "published_at": "...",
             "superseded_by": null, "config_hash": "sha256:...", "duration_seconds": 312.4,
             "error_code": null, "picks": {"buy": 3, "sell": 1}}],
  "next_before": "01JCW..."
}
```

#### GET `/api/v1/runs/{id}`
Auth: none.
Response 200: the list item fields plus
```json
{
  "transitions": [{"seq": 1, "from": null, "to": "queued", "at": "..."}, {"seq": 2, "from": "queued", "to": "ingesting", "at": "..."}],
  "summary": {"tickers_total": 200, "tickers_scored": 196, "excluded": [{"ticker": "ABC", "reason": "stale"}],
              "narrative": {"llm": 4, "template": 1}, "provider_calls": 214, "rate_limit_waits_seconds": 0.0},
  "error_detail": null,
  "code_version": "1.0.0 (abc1234)"
}
```
No disclaimer (no picks). Errors: 404 `not-found`.

#### POST `/api/v1/runs`
Auth: token. Body `{"date": "2026-11-13"}` (optional; `{}` allowed).
Responses: 202 `{"run_id": "01JCX...", "state": "queued", "trade_date": "2026-11-13"}` with `Location`; 200 `{"run_id": null, "state": "market_closed", "trade_date": "2026-11-14"}` (ADR-022). Errors: 401, 409 `run-in-progress` (body includes `active_run_id`), 409 `session-not-complete`, 422 `not-a-trading-date` / `date-in-future`, 429.

#### GET `/api/v1/track-record?from=&to=&side=&band=&config=`
Auth: none. `side` `buy` | `sell` (default both); `band` one of the six band names; `config` a config hash; `from`/`to` dates on `trade_date` (default all).
Response 200:
```json
{
  "filters": {"from": null, "to": null, "side": null, "band": null, "config": null},
  "benchmark": "SPY",
  "stats": [
    {"side": "buy", "horizon_days": 5, "band": null, "n": 42, "small_sample": false,
     "hit_rate": 0.548, "mean_excess_pct": 0.41, "median_excess_pct": 0.22,
     "worst": {"ticker": "XYZ", "date": "2026-10-02", "excess_pct": -9.81, "recommendation_id": "01J..."}}
  ],
  "picks": [{"recommendation_id": "01J...", "date": "2026-10-02", "ticker": "XYZ", "side": "buy", "band": "Buy",
             "display_score": 71.2, "confidence": 58, "config_hash": "sha256:...", "entry_price": 51.2,
             "outcomes": {"1": {"pick_pct": -1.2, "benchmark_pct": 0.1, "excess_pct": -1.3}, "5": null, "10": null, "20": null}}],
  "disclaimer": "..."
}
```
`stats` contains one row per side x horizon overall, then per band. Empty ranges return `n: 0` and null statistics, not an error. Errors: 422.

#### GET `/api/v1/backtests?limit=` (ADR-025)
Auth: none. `limit` 1..100 default 20. Response 200 `{"items": [{"id", "from_date", "to_date", "config_hash", "state", "created_at", "finished_at", "tickers"}], "hypothetical": true, "label": "Backtest (hypothetical)", "disclaimer": "..."}`.

#### GET `/api/v1/backtests/{id}` (ADR-025)
Auth: none. Response 200 `{"id", "from_date", "to_date", "config": {"version", "hash"}, "state", "stats": [ /* same shape as track-record stats */ ], "equity_curve": [{"date", "strategy", "benchmark"}], "picks_count": 0, "hypothetical": true, "label": "Backtest (hypothetical)", "disclaimer": "..."}`. Errors: 404.

#### GET `/api/v1/config/scoring`
Auth: none. Response 200 `{"version": 1, "hash": "sha256:...", "document": { /* validated scoring.yaml as JSON */ }, "loaded_at": "..."}`.

#### GET `/api/v1/config/scoring/{hash}` (ADR-025)
Auth: none. `hash` is `sha256:<64 hex>`. Response 200 `{"version", "hash", "document", "first_seen_at"}`. Errors: 404, 422.

#### GET `/api/v1/status`
Auth: none.
Response 200:
```json
{
  "version": "1.0.0", "commit": "abc1234", "env": "prod",
  "license": {"notice": "Copyright Serverless Ventures LLC. Noncommercial use only.", "spdx": "PolyForm-Noncommercial-1.0.0", "source_url": "https://github.com/mohnishbasha/stokeai-trading-supertrends"},
  "demo": false,
  "latest_run": {"id": "01JCX...", "trade_date": "2026-11-13", "state": "published", "published_at": "..."},
  "active_run": null,
  "last_completed_session": "2026-11-13",
  "data_freshness": {"latest_bar_date": "2026-11-13", "stale_tickers": 0, "seconds_since_session_close": 6010},
  "providers": {"market": {"name": "massive", "status": "ok", "last_success_at": "2026-11-13T22:31:02Z", "capabilities": {"intraday": true, "trades": false, "adjusted": true}},
                "fundamentals": {"name": "massive", "status": "ok", "last_success_at": "2026-11-13T22:31:40Z"}},
  "llm": {"provider": "openai_compatible", "model": "...", "status": "ok", "last_success_at": "2026-11-13T22:33:58Z", "template_fallback_last_run": 0.2},
  "scoring": {"version": 1, "hash": "sha256:..."},
  "next_scheduled_run": "2026-11-16T17:30:00-05:00"
}
```
Field semantics used by clients for freshness and stale detection (docs/DESIGN.md StaleBanner and ProviderStatus read exactly these names):
- `latest_run`: the most recent run in any state (`id`, `trade_date`, `state`, `published_at`, null until published); `state: "failed"` drives the `run_failed` banner. null on a fresh install.
- `active_run`: null, or `{"id", "trade_date", "state"}` for the run currently queued or executing (`state` is the current step, for example `scoring`); drives the `run_in_progress` banner.
- `last_completed_session`: the latest XNYS session that closed at least 30 minutes ago. A page payload whose `date` (or `trade_date`) is earlier than this value is stale (`behind` banner).
- `data_freshness.latest_bar_date`: the latest stored daily bar date across scored tickers; `data_freshness.stale_tickers`: tickers with data quality `stale` in the latest run; `data_freshness.seconds_since_session_close`: seconds since `last_completed_session` closed.
- `providers.market.status`, `providers.fundamentals.status`, `llm.status`: health (values below); `last_success_at`: timestamp of the last successful call, null if none recorded; `llm.template_fallback_last_run`: share of picks in the latest run whose narrative fell back to the template (0..1), null if no run.

Provider and LLM `status` values: `ok`, `degraded`, `unconfigured`, `unreachable`. Status checks are cached for 60 s and never send secrets in the response. No disclaimer (no pick).

#### POST `/mcp`
Auth: token for every request on HTTP (read and write tools alike, per the security guidelines). MCP streamable HTTP transport in stateless JSON-response mode. `GET /mcp` and `DELETE /mcp` return 405. Unauthenticated calls return 401 before any MCP processing. Tools in section 6.3.

#### Static UI routes
- GET `/assets/{file}`: hashed bundle files, `Cache-Control: public, max-age=31536000, immutable`; 404 problem if missing.
- GET `/{path}` (any path not starting with `api/`, `mcp`, `assets/`, `healthz`, `readyz`, `metrics`): `index.html` with `Cache-Control: no-cache` (SPA fallback).
- Security headers on every response: `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`. HSTS is added by the ingress where TLS terminates.

Endpoint count: 19 from Appendix C, 6 added by ADR-025, 2 static routes: 27 operations.

### 6.2 CLI commands

Program: `supertrends` (Typer), entry point `supertrends.cli.app:main`. Every command has `--help`. Output is human-readable text by default; commands marked `--json` print exactly one JSON document to stdout that validates against the corresponding API response schema (the same pydantic model). Logs go to stderr as JSON lines; stdout carries only results.

**Global options** (before the command): `--version` (prints `supertrends {VERSION} ({commit})` and the line `Copyright Serverless Ventures LLC. Noncommercial use only. {SUPERTRENDS_SOURCE_URL}`, exit 0), `--api-url URL` (remote mode; env `SUPERTRENDS_API_URL`), `--log-level LEVEL` (env `SUPERTRENDS_LOG_LEVEL`), `--config PATH` (scoring config, env `SUPERTRENDS_SCORING_CONFIG`).

**Modes.** Local mode (no `--api-url`): talks to Postgres through `SUPERTRENDS_DATABASE_URL` and calls the service functions directly. Remote mode (`--api-url`): calls the HTTP API; write commands send `Authorization: Bearer $SUPERTRENDS_API_TOKEN`. Commands marked "local only" exit 2 with a message in remote mode.

**Exit codes** (all commands):

| Code | Meaning |
|---|---|
| 0 | success (including "market closed" and "already running for the same date") |
| 1 | error: unhandled failure, run failed, API 5xx, authentication failure |
| 2 | usage: invalid flag, argument, symbol, or date; command not available in this mode |
| 3 | not ready: database unreachable or migrations behind, no published run yet, session not complete, API not ready, active run for a different date |

| Command | Flags and arguments | Mode | Output | Notes |
|---|---|---|---|---|
| `today` | `[--date D] [--json]` | both | cards: rank, ticker, score, band, confidence, Supertrend state, invalidation, expected 1-day move, narrative; also qualified; nearest miss; disclaimer | exit 3 if no published run |
| `analyze TICKER` | `[--date D] [--json]` | both | factor table (score, weight, contribution, quality, reasons), levels, regime, adjustments, disclaimer | exit 2 invalid symbol; exit 1 on 404 with message |
| `rank` | `[--date D] [--top N] [--group SLUG] [--json]` | both | ranked table; `--top` default 20, max 300 | |
| `watchlist list` | `[--json]` | both | groups and items | |
| `watchlist add SYMBOL` | `[--group SLUG]...` | both | confirmation | remote mode needs the token |
| `watchlist remove SYMBOL` | | both | confirmation | remote mode needs the token |
| `run daily` | `[--date D] [--json] [--no-wait]` | both | local: one line per state transition, then the summary; remote: enqueues, then polls `GET /runs/{id}` every 2 s and prints transitions unless `--no-wait` | exit 0 published, market closed, or already running for the same date; exit 1 failed; exit 3 session not complete or active run for another date |
| `worker` | `[--poll-seconds N] [--once]` | local only | logs | ADR-020; `--once` processes at most one queued run then exits (tests) |
| `ingest` | `[--date D] [--symbols A,B] [--full]` | local only | per-ticker summary and data-quality counts | idempotent; `--full` refetches full adjusted history |
| `backtest` | `--from D --to D [--config PATH] [--out PREFIX] [--json]` ; `--list` ; `--delete ID` | local only | statistics table, equity summary, "Backtest (hypothetical)" header, disclaimer; files `PREFIX.json` and `PREFIX.md` | |
| `track-record` | `[--from D] [--to D] [--side buy|sell] [--band B] [--config HASH] [--refresh] [--json]` | both (`--refresh` local only) | stats table with sample sizes and "small sample" labels, disclaimer | `--refresh` runs outcome measurement (4.5) |
| `status` | `[--json]` | both | version, license notice, latest run, freshness, provider and LLM health | exit 3 if not ready |
| `serve` | `[--bind HOST:PORT] [--workers N]` | local only | logs | default bind `SUPERTRENDS_BIND`; runs uvicorn with the app factory; serves UI from `SUPERTRENDS_UI_DIR` |
| `mcp` | | both | MCP over stdio | local mode uses the database; remote mode proxies to the HTTP API with the token |
| `healthcheck` | `--url URL [--timeout S]` | n/a | `ok` or reason | GET `{url}/readyz`; exit 0 ready, 3 not ready, 1 unreachable; default timeout 3 s; used by Compose health checks |
| `db migrate` | `[--revision REV]` | local only | revision applied | advisory-locked (5.4) |
| `db backup` | `--out PATH` | local only | file path and size | wraps `pg_dump --format=custom`; file mode 0600 |
| `db prune` | `[--dry-run]` | local only | rows deleted per table | ADR-031 |
| `config show` | `[--json]` | both | active scoring config, version, hash | |
| `config validate` | `[PATH]` | n/a | `valid sha256:...` or errors | exit 2 on invalid (weights not summing to 100, unknown factor ID, missing factor) |
| `config export-openapi` | `[--out PATH]` | n/a | OpenAPI 3.1 JSON to stdout or file | used by `make openapi` |
| `config export-schema` | `[--out DIR]` | n/a | JSON schemas: evidence document, scoring config, MCP tool schemas | committed under `docs/schemas/` and diffed in CI |

CLI command count: 23 (counting each subcommand of `watchlist`, `db`, and `config` separately).

Text output for picks always ends with the disclaimer paragraph. Colors are optional (`NO_COLOR` respected); buy and sell are labeled with words and arrows, never color alone.

### 6.3 MCP tools

Server name `supertrends`, version = product version. Transports: stdio (`supertrends mcp`) and streamable HTTP at `/mcp` (token). Every tool `inputSchema` and `outputSchema` is JSON Schema 2020-12 with `"additionalProperties": false` at every object level. Results are returned as `structuredContent` plus a single text content item holding the same JSON. Every tool description ends with: "Informational market analysis only. Super Trends places no trades and gives no personalized advice."

Shared definitions: `date` = `{"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"}`; `ticker` = `{"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9.\\-]{0,9}$"}` (uppercased server-side); `disclaimer` = `{"type": "string", "const": "<disclaimer text>"}`.

| Tool | Input schema | Output schema | Auth on HTTP |
|---|---|---|---|
| `supertrends_recommend` | `{"date"?: date}` | `RecommendationsResponse` (6.1 `recommendations/latest`), includes `disclaimer` | token (transport) |
| `supertrends_analyze` | `{"ticker": ticker, "date"?: date}` required `ticker` | `AnalysisResponse` (6.1 analysis), includes `disclaimer` | token |
| `supertrends_rank` | `{"date"?: date, "top"?: integer 1..300 default 20}` | `RankingsResponse` with `limit = top`, includes `disclaimer` | token |
| `supertrends_watchlist` | `{"action": "list"|"add"|"remove", "ticker"?: ticker, "groups"?: [slug]}`; `ticker` required when action is add or remove (`if/then` in schema) | `{"action", "ok": boolean, "watchlist": WatchlistResponse}` | token; add and remove are write operations and also require the token on stdio when the stdio server runs in remote mode |
| `supertrends_status` | `{}` | `StatusResponse` | token |
| `supertrends_track_record` | `{"from"?: date, "to"?: date, "side"?: "buy"|"sell"}` | `TrackRecordResponse`, includes `disclaimer` | token |
| `supertrends_run` | `{"date"?: date}` | `{"run_id": string|null, "state": "queued"|"market_closed"|"already_running", "trade_date": date, "active_run_id"?: string}` (an active run is reported as `already_running`, not as an error) | token (write) |

Error semantics: validation failures and domain errors (no published run, ticker not found, session not complete) return a tool result with `isError: true` and a text item holding the RFC 9457 problem JSON. Missing token on HTTP returns HTTP 401 before MCP processing. On stdio in local mode, write tools are allowed without a token (the caller already has database access); in remote mode the token from `SUPERTRENDS_API_TOKEN` is forwarded.

Tool count: 7.

---

## 7. Provider Interfaces

All provider code lives in `src/supertrends/data/providers/` (market and fundamentals) and `src/supertrends/narrative/` (narrative). Protocols use `typing.Protocol`; result types are frozen pydantic v2 models or frozen dataclasses. Providers are synchronous from the orchestrator's point of view (internally they may use `httpx.Client`); ingestion parallelism is bounded by the rate limiter, not by threads.

### 7.1 Types (`data/providers/base.py`)

```python
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol, Sequence

@dataclass(frozen=True)
class ProviderCapabilities:
    intraday: bool          # 5-minute bars available on this plan
    trades: bool            # tick trades available (reserved for tick-rule flow, ADR-010)
    adjusted: bool          # bars are split and dividend adjusted by the vendor
    grouped_daily: bool     # whole-market daily bars in one call
    reference: bool         # symbol resolution and names

@dataclass(frozen=True)
class Bar:
    symbol: str
    ts: datetime            # session date at 00:00 America/New_York for daily, bar start (UTC) for intraday
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None

@dataclass(frozen=True)
class CorporateAction:
    symbol: str
    ex_date: date
    kind: Literal["split", "dividend"]
    ratio: float | None     # split: new shares per old share
    amount: float | None    # dividend cash amount

@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    name: str | None
    type: Literal["stock", "etf", "index", "crypto"]
    active: bool

@dataclass(frozen=True)
class QuarterlyFinancials:
    symbol: str
    period_end: date
    known_at: datetime      # point-in-time availability (filing date or vendor timestamp)
    metrics: dict[str, float | None]   # revenue, eps_diluted, gross_margin, operating_margin, fcf, net_debt, shares

@dataclass(frozen=True)
class ForwardEstimate:
    symbol: str
    as_of: datetime
    eps_next_12m: float | None
    revenue_next_12m: float | None

@dataclass(frozen=True)
class EarningsDate:
    symbol: str
    date: date
    confirmed: bool

ProviderHealth = Literal["ok", "degraded", "unconfigured", "unreachable"]

@dataclass(frozen=True)
class ProviderStatus:
    name: str
    health: ProviderHealth
    detail: str | None      # never contains a secret
```

### 7.2 Protocols

```python
class MarketDataProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Bar]: ...
    def grouped_daily(self, session: date) -> Sequence[Bar]: ...                 # requires capabilities.grouped_daily
    def intraday_bars(self, symbol: str, start: date, end: date,
                      minutes: Literal[5] = 5) -> Sequence[Bar]: ...             # requires capabilities.intraday
    def corporate_actions(self, symbol: str, start: date, end: date) -> Sequence[CorporateAction]: ...
    def resolve_symbol(self, symbol: str) -> SymbolInfo | None: ...              # None when unknown
    def trades(self, symbol: str, session: date) -> Sequence[object]: ...        # requires capabilities.trades; unused in v1
    def status(self) -> ProviderStatus: ...

class FundamentalsProvider(Protocol):
    name: str
    supports_forward_estimates: bool

    def quarterly_financials(self, symbol: str, since: date) -> Sequence[QuarterlyFinancials]: ...
    def forward_estimates(self, symbol: str) -> Sequence[ForwardEstimate]: ...   # [] or CapabilityNotSupported
    def earnings_dates(self, symbol: str, start: date, end: date) -> Sequence[EarningsDate]: ...
    def status(self) -> ProviderStatus: ...
```

Return contracts: sequences are sorted by time ascending, contain no duplicates, and contain only bars within [start, end] inclusive. Empty results are valid (holidays, new listings). Values are validated by the adapter (`high >= max(open, close)`, `low <= min(open, close)`, `volume >= 0`); a violating row raises `ProviderDataError`. Calling a method whose capability flag is false raises `CapabilityNotSupported` without network I/O.

### 7.3 Error semantics (`errors.py`)

| Exception | Raised when | Orchestrator behavior |
|---|---|---|
| `ProviderUnconfigured` | no API key, or the vendor rejects the key (401/403) | fatal at run start for the market provider (`error_code = provider_unavailable`); startup still succeeds and status shows `unconfigured` |
| `ProviderRateLimited(retry_after: float | None)` | 429 after the retry budget is spent | counted in `supertrends_provider_rate_limited_total`; the ticker is retried later in the same run once; then treated as `ProviderUnavailable` for that ticker |
| `ProviderUnavailable` | 5xx, timeout, connection error after retries | the ticker keeps its stored bars; quality becomes `stale` if the latest session is missing; benchmark failure fails the run |
| `ProviderDataError` | malformed or invalid payload | the ticker is excluded with reason `no_data`; logged with endpoint template and request ID |
| `CapabilityNotSupported` | method needs a capability the plan lacks | caller falls back (flow uses daily estimate; valuation uses trailing P/E, ADR-027) |

All derive from `ProviderError(SuperTrendsError)`. Messages never include the key, the full URL with query, or response bodies longer than 200 characters.

Retries: `tenacity` with exponential backoff and full jitter (base 1 s, cap 30 s, max 5 attempts) on 429 and 5xx and transport errors; `Retry-After` honored when present. Timeouts: connect 5 s, read 30 s.

Rate limiting: a process-wide token bucket of `SUPERTRENDS_PROVIDER_RATE_PER_MIN` calls per minute per provider. Waiting time is recorded in the run summary (`rate_limit_waits_seconds`) and excluded from NFR-001.

Caching: responses are cached in memory per run by (endpoint template, params) so repeated reads in one run do not spend calls.

Recording: every outbound call writes a `provider_calls` row (provider, endpoint template, non-secret params, status, duration, cache hit, run ID).

### 7.4 Registry (`data/providers/registry.py`)

```python
MARKET_PROVIDERS: dict[str, Callable[[Settings], MarketDataProvider]] = {
    "fixture": FixtureProvider.from_settings,
    "massive": MassiveProvider.from_settings,
    "alternate": AlternateProvider.from_settings,      # ADR-032
}
FUNDAMENTALS_PROVIDERS: dict[str, Callable[[Settings], FundamentalsProvider]] = {
    "fixture": FixtureFundamentals.from_settings,
    "massive": MassiveFundamentals.from_settings,
}
def market_provider(settings: Settings) -> MarketDataProvider: ...
def fundamentals_provider(settings: Settings) -> FundamentalsProvider: ...
```

The tables hold lazy `"module:attribute"` targets (or registered factories via `register_market_provider` and `register_fundamentals_provider`) so each adapter module is imported only when selected and the S1-T03, S1-T04, and S1-T05 adapters plug in independently; a name whose module does not exist yet raises `ConfigError` ("has no implementation yet"). The market and fundamentals providers are chosen independently and may come from different vendors. An unknown name raises `ConfigError("SUPERTRENDS_MARKET_PROVIDER='x' is not one of: fixture, massive, alternate")` at startup. `SUPERTRENDS_DEMO=1` with a non-fixture market provider is a startup error.

### 7.5 Fixture provider (`data/providers/fixture.py`)

- Deterministic synthetic generator: seeded geometric Brownian motion with regime switches, overnight gaps, one 4:1 split, and volume patterns. Seed `SUPERTRENDS_FIXTURE_SEED` (default `20261114`); calendar anchored at `SUPERTRENDS_FIXTURE_END_DATE` (default last completed session) per ADR-028.
- Universe: 12 synthetic tickers (`FXA` to `FXL`, type `stock` or `etf`) plus `SPY` and `QQQ` stand-ins. By construction: at least one trending, one ranging, one reversing ticker; for demo mode, a latest session with 3 buys and 2 sells, one fresh flip, one divergence, one Fibonacci hold, one breakout, one `event_risk` pick (earnings in 3 sessions), one excluded (stale) ticker, and a correlated pair that exercises the correlation guard.
- History: 3 years of daily bars and 30 sessions of 5-minute bars. Capabilities: all true except `trades`.
- Fundamentals: synthetic quarterly financials with `known_at` 30 days after period end; earnings dates; ETFs return no financials (quality `missing`).
- Any symbol outside the universe resolves to `None` (watchlist add returns `symbol-unresolved`), except that the permissive mode `SUPERTRENDS_FIXTURE_PERMISSIVE=1` (tests) accepts any regex-valid symbol and generates bars for it from a hash of the symbol.
- No network I/O, ever; still writes `provider_calls` rows with provider `fixture` so metrics and the run summary are exercised.

### 7.6 Massive adapter (`data/providers/massive.py`)

Massive was formerly Polygon.io. Endpoint paths below follow the vendor's documented REST layout at the time of writing and must be verified against current vendor documentation at implementation time (S1-T04); the adapter keeps every path in one table so a change is one edit.

| Method | Endpoint (relative to `SUPERTRENDS_MASSIVE_BASE_URL`) | Notes |
|---|---|---|
| `grouped_daily(session)` | `GET /v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true` | one call per session for the whole market; used for daily updates |
| `daily_bars(symbol, start, end)` | `GET /v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}?adjusted=true&sort=asc&limit=50000` | backfill and split refetch |
| `intraday_bars(symbol, start, end)` | `GET /v2/aggs/ticker/{symbol}/range/5/minute/{start}/{end}?adjusted=true&sort=asc&limit=50000` | likely needs a paid plan for 200 symbols (owner checklist) |
| `corporate_actions` | `GET /v3/reference/splits?ticker={symbol}`, `GET /v3/reference/dividends?ticker={symbol}` | paginated via `next_url` (host is checked to equal the configured base URL host before following) |
| `resolve_symbol` | `GET /v3/reference/tickers/{symbol}` | name and type |
| `quarterly_financials` | vendor financials endpoint (verify current path) | `known_at` from filing date |
| `earnings_dates` | vendor earnings or events endpoint if available on the plan, else `CapabilityNotSupported` | |

- Authentication: `Authorization: Bearer <SUPERTRENDS_MASSIVE_API_KEY>` only (ADR-035).
- Base URL default `https://api.massive.com`; the legacy host `https://api.polygon.io` is accepted. Base URL comes only from settings (SSRF rule); pagination URLs from responses are followed only when their scheme and host match the configured base URL.
- Rate: default 5 calls per minute (free tier); set `SUPERTRENDS_PROVIDER_RATE_PER_MIN` to the purchased plan.
- Bars timestamps from the vendor (epoch milliseconds) are converted to session dates in America/New_York.
- Tests use recorded, scrubbed, synthetic-valued fixtures in `tests/fixtures/providers/massive/`; no test calls the network.

### 7.7 Alternate provider (`data/providers/alternate.py`)

Implements `MarketDataProvider` for Alpaca Market Data (chosen over Tiingo, ADR-032, verified 2026-11-15). Header auth only, with the key pair in `SUPERTRENDS_ALTERNATE_API_KEY` as `KEY_ID:SECRET`; retry on 429, 5xx, and transport errors per 7.3. Daily bars are adjusted; intraday is 5-minute regular-session bars; `grouped_daily` and `trades` raise `CapabilityNotSupported`. Tested by the shared contract suite (`tests/contract/provider_contract.py`) against recorded fixtures in `tests/fixtures/providers/alpaca/`. The rate-limit token bucket, per-run cache, and `provider_calls` recording land with the shared HTTP helper (see ADR-032 consequences).

### 7.8 Narrative provider (`narrative/`)

```python
@dataclass(frozen=True)
class NarrativeDraft:
    text: str
    model: str | None
    tokens_in: int | None
    tokens_out: int | None

class NarrativeProvider(Protocol):
    name: Literal["template", "openai_compatible"]
    def generate(self, evidence: EvidenceDocument, *, temperature: float, timeout_s: float) -> NarrativeDraft: ...
    def status(self) -> ProviderStatus: ...

def write_narrative(evidence: EvidenceDocument, provider: NarrativeProvider, settings: Settings) -> Narrative:
    """Attempt 1 at temperature 0.3, attempt 2 at 0.0, then template. Never raises."""
```

- `openai_compatible`: `POST {SUPERTRENDS_LLM_BASE_URL}/chat/completions` with `model`, `messages` (versioned system prompt plus compact evidence rendering), `max_tokens = 220`, `temperature`. Optional `Authorization: Bearer <SUPERTRENDS_LLM_API_KEY>`. Timeout `SUPERTRENDS_LLM_TIMEOUT_SECONDS` (default 8).
- Prompt budget: the rendered prompt must be at most 900 tokens (counted with a fixed tokenizer approximation in code, tested in CI on the fixture set); if over budget, lower-ranked factor reasons are dropped from the rendering until it fits.
- Validation chain on every draft: plain text only (no Markdown links, no HTML), 3 to 5 sentences, max 1200 characters, banned phrases ("guaranteed", "will", "can't lose", position size, options, leverage terms), numeric guard (every number in the text matches an evidence value within rounding to the displayed precision). Rejection reasons are recorded in `narratives.rejection_reasons`.
- `template`: deterministic, built from the evidence document in the required order (Supertrend state, two largest positive contributions, largest opposing factor, invalidation level); always passes the numeric guard (tested).
- Errors and timeouts never propagate; `write_narrative` always returns a `Narrative`.

---

## 8. Run State Machine and Atomic Publication

### 8.1 States and transitions

```
                 +---------+
   insert ------>| queued  |-----------------------------+
                 +----+----+                             |
                      | claimed by executor (lock held)  |
                      v                                  |
                 +-----------+                           |
                 | ingesting |------------------------+  |
                 +-----+-----+                        |  |
                       v                              |  |
                 +-----------+                        |  |
                 | computing |----------------------+ |  |
                 +-----+-----+                      | |  |
                       v                            | |  |
                 +-----------+                      | |  |
                 |  scoring  |--------------------+ | |  |
                 +-----+-----+                    | | |  |
                       v                          v v v  v
                 +-----------+               +-----------+
                 | selecting |-------------->|  failed   | (terminal)
                 +-----+-----+               +-----------+
                       v                          ^
                 +-----------+                    |
                 | narrating |--------------------+  (publication transaction error)
                 +-----+-----+
                       v
                 +-----------+
                 | published | (terminal)
                 +-----------+
```

Allowed edges: `queued -> ingesting`, `ingesting -> computing`, `computing -> scoring`, `scoring -> selecting`, `selecting -> narrating`, `narrating -> published`, and any non-terminal state `-> failed`. No other edge exists; the `runs` trigger rejects others. Every transition inserts a `run_transitions` row in the same transaction as the `runs.state` update, and increments `supertrends_run_state_total{state}` in `metric_counters`.

| State | Work | Writes |
|---|---|---|
| `queued` | waiting for an executor | `runs` |
| `ingesting` | incremental ingest, corporate actions, fundamentals, earnings, data-quality pass | bars, actions, fundamentals, calendar, `provider_calls` |
| `computing` | indicators daily, weekly, intraday | `indicator_snapshots` |
| `scoring` | factors, regimes, weights, composite, display, band, confidence; exclusions | `ticker_scores`, `factor_scores` |
| `selecting` | candidates, ranking, correlation guard, also qualified, nearest misses, evidence documents, `days_on_list` | in memory, plus `runs.summary` |
| `narrating` | narrative per pick | in memory |
| `published` | publication transaction committed | `recommendations`, `narratives`, `runs` |
| `failed` | `error_code`, `error_detail` set | `runs` |

Rows written in `ingesting` through `scoring` belong to the run (`run_id`) but are invisible to readers until the run is published, because every read path joins through a current published run. Bars and fundamentals are shared data and are visible immediately; they are facts, not output.

### 8.2 Atomic publication

One database transaction, `SERIALIZABLE` isolation, retried up to 3 times on serialization failure:

1. `SELECT ... FROM runs WHERE id = :run_id FOR UPDATE`; assert `state = 'narrating'`.
2. `INSERT` all `recommendations` (with evidence documents) and their `narratives`.
3. Find the current published run for `trade_date` (`published_at IS NOT NULL AND superseded_by IS NULL`), lock it, set its `superseded_by = :run_id`.
4. `UPDATE runs SET state = 'published', published_at = now(), finished_at = now(), summary = :summary WHERE id = :run_id`; insert the `run_transitions` row.
5. Increment `metric_counters` for `run_state_total{state="published"}` and narrative counters.
6. `COMMIT`.

If any step fails, the transaction rolls back, the run moves to `failed` in a new transaction with `error_code = 'internal'`, and the previously published run is unchanged. The partial unique index `ux_runs_one_current_per_date` guarantees at most one current run per date even under a race.

### 8.3 Concurrency and recovery

- At most one active run (partial unique index `ux_runs_one_active`) and one executing process (advisory lock), per ADR-021.
- Reaping: executors reap abandoned non-queued runs on start; queued runs older than `SUPERTRENDS_QUEUED_RUN_TIMEOUT_SECONDS` are failed with `not_picked_up`. The API also reaps stale queued rows when handling `POST /api/v1/runs`, so a missing worker cannot block triggers forever.
- Process signals: on SIGTERM the executor finishes the current database statement, moves the run to `failed` with `error_code = 'internal'` and detail `terminated`, releases the lock, and exits 1. The CronJob `activeDeadlineSeconds` is 3600.
- Determinism: the same bars and config hash produce byte-identical `factor_scores`, `ticker_scores`, and selection (NFR-002); no clock or randomness reaches the engine; the run's "as of" is the trade date.

---

## 9. Security Model and Trust Boundaries

### 9.1 Trust boundaries

```
 [Owner devices] --(tailnet / private ingress, TLS)--> [Ingress or tailnet proxy]
        TB1: network boundary. Reads open inside; writes need the bearer token.
 [Ingress] --> [API pod]   Host allowlist (421), CSP, input validation, write rate limit
        TB2: API process. Untrusted: every request field, every header.
 [API pod, Worker, CronJob] --> [PostgreSQL]   password from Secret, in-namespace only (NetworkPolicy)
        TB3: data store. Trusted, but append-only triggers protect published history from code bugs.
 [Worker, CronJob] --443--> [Market data / fundamentals vendor]
        TB4: vendor responses are untrusted data: schema-validated, numeric-validated, names never reach the LLM.
 [Worker, CronJob] --> [LLM gateway]
        TB5: LLM output is untrusted text: validated, numeric-guarded, length-limited, rendered as plain text.
 [MCP clients] --stdio--> [supertrends mcp]   local process trust (same user)
 [MCP clients] --HTTP /mcp + token--> [API pod]
```

### 9.2 Threats and controls

| Threat | Control |
|---|---|
| Unauthorized writes (runs, watchlist) | Bearer token from a Kubernetes Secret, constant-time compare, write rate limit, 401 without detail |
| DNS rebinding or misrouted traffic | `SUPERTRENDS_ALLOWED_HOSTS` check (421), with probe exemptions only for `/healthz`, `/readyz`, `/metrics` (ADR-024) |
| XSS through narrative or names | LLM output and provider strings rendered as text nodes only; strict CSP with no inline script or style; no Markdown rendering |
| Prompt injection | Provider strings (names, descriptions, news) never enter the prompt; prompt contains only numbers and enumerated labels |
| Fabricated numbers in narrative | Numeric guard, banned phrases, sentence count; template fallback |
| SSRF | LLM and provider base URLs only from settings; pagination URLs must match the configured host; no URL parameters on any endpoint |
| Secret leakage | `SecretStr` settings, structlog redaction processor (unit-tested), `provider_calls` stores path templates only, header auth (ADR-035), problem details never echo upstream bodies, gitleaks in CI |
| Tampering with published history | Append-only triggers; publication is one transaction; reruns supersede without editing |
| Injection through parameters | Symbol regex, trading-date validation, bounded pagination, SQLAlchemy bound parameters only (no string SQL) |
| Supply chain | Locked installs, pip-audit, npm audit, Trivy, Dependabot, digest-pinned base images, Actions pinned by SHA, cosign keyless signing, SBOM and provenance, Flux signature verification, license allowlist |
| Container escape and lateral movement | UID 10001, read-only root FS, all capabilities dropped, no privilege escalation, `seccompProfile: RuntimeDefault`, `automountServiceAccountToken: false`, default-deny NetworkPolicy |
| Data exfiltration and telemetry | Egress only to provider hosts on 443, the LLM gateway, Postgres, DNS; egress-blocked integration test |
| Regulatory misuse | Disclaimer on every pick-bearing payload; no holdings, sizes, strikes, leverage, or orders; private deployment by default; owner checklist item to consult a securities lawyer before sharing |

### 9.3 Secrets

| Secret | Env var | Source on Kubernetes | Consumers |
|---|---|---|---|
| Database URL / password | `SUPERTRENDS_DATABASE_URL` | `existingSecret` key `database-url` (or bundled Postgres secret) | API, worker, CronJob, migrate Job |
| API bearer token | `SUPERTRENDS_API_TOKEN` | `existingSecret` key `api-token` | API |
| Market data key | `SUPERTRENDS_MASSIVE_API_KEY` | `existingSecret` key `massive-api-key` | worker, CronJob, API (status check only) |
| Fundamentals key (when a different vendor) | `SUPERTRENDS_FUNDAMENTALS_API_KEY` | `existingSecret` key `fundamentals-api-key` | worker, CronJob |
| LLM key (if the gateway needs one) | `SUPERTRENDS_LLM_API_KEY` | `existingSecret` key `llm-api-key` | worker, CronJob |

Secret values never appear in values files, ConfigMaps, logs, metrics, API responses, the run summary, or `provider_calls`. `.env.example` lists names with empty values.

### 9.4 Network policy

Default deny for all pods in the release. Allowed: ingress to the API on 8080 from the ingress controller or tailnet proxy namespace (`networkPolicy.ingressFrom`) and from Prometheus (`networkPolicy.metricsFrom`); egress from API, worker, CronJob, and migrate Job to Postgres 5432 (in-release or `externalDatabase` CIDR), to kube-dns 53 UDP/TCP, to the LLM gateway (`networkPolicy.llmEgress` namespace and pod selector), and to `networkPolicy.providerEgressCIDRs` on 443 (default `0.0.0.0/0` on 443 because vendor IPs are not stable; tighten with an egress gateway if available). Postgres accepts ingress only from release pods.

---

## 10. Build and Deployment

This section mirrors the Build and Deployment, Versioning, Environment Model, and Dependency Versions sections of `BUILD_PROMPT.md` in full. Subsections 10.1 to 10.23 are carried over verbatim except for the deltas listed in 10.0 (the repository-name substitutions of ADR-017 are applied in place; the other deltas are additive and listed here rather than edited into the copied text, except the chart tree, which shows the added templates). `docs/DEPLOYMENT.md` (Sprint 8) is produced from this section.

### 10.0 Deltas from BUILD_PROMPT (each backed by an ADR)

| Delta | Where | ADR |
|---|---|---|
| GitHub repository references (OCI `source` label, cosign identity regexps, Flux `matchOIDCIdentity.subject`, `git clone` URL, `SUPERTRENDS_SOURCE_URL`) use `mohnishbasha/stokeai-trading-supertrends`. Image, chart, package, CLI, chart directory, and namespaces keep `stokeai-supertrends` / `supertrends`. | Makefile `image-verify`, Path 1, Dockerfile label, Path 3 verify, Flux `OCIRepository` | ADR-017 |
| Worker Deployment for manual runs: chart template `deployment-worker.yaml`, values key `worker`, Compose service `worker` in `docker-compose.local.yml`, `docker-compose.demo.yml`, `docker-compose.prod.yml`, and `docker-compose.dev.yml` (dev runs it on the host with `uv run supertrends worker`). Stage at `replicaCount: 0` also runs zero workers. | chart tree, values, Compose | ADR-020 |
| Chart appends the in-cluster Service DNS names to `SUPERTRENDS_ALLOWED_HOSTS`; probes and `/metrics` are exempt from the Host check. | `_helpers.tpl`, `deployment-api.yaml` | ADR-024 |
| Values keys named in the profile table but missing from the seed values are defined: `llmMock` (template `deployment-llm-mock.yaml`, kind only), `seed` (post-install Job `job-seed.yaml`, kind only), `global.imageRegistry` (air-gap). | values, chart tree | ADR-020 (worker), this section |
| Secret keys: the chart reads the `existingSecret` keys exactly as named in the seed values and owner commands (`SUPERTRENDS_API_TOKEN`, `SUPERTRENDS_MASSIVE_API_KEY`, `SUPERTRENDS_LLM_API_KEY`, `SUPERTRENDS_DATABASE_URL`, optional `SUPERTRENDS_FUNDAMENTALS_API_KEY`) via `envFrom`. Section 9.3 lists logical key names; the env var names are authoritative. | `deployment-*.yaml`, `cronjob-daily-run.yaml` | none (clarification) |
| Make target `narrative-eval` (S5-T03): `uv run python scripts/narrative_eval.py --report docs/NARRATIVE_EVAL.md`, needs `SUPERTRENDS_LLM_BASE_URL`. | Makefile | none (named by S5-T03) |
| Retention runs after each daily run (no extra CronJob). | none | ADR-031 |
| Metrics from the CronJob and worker are persisted to Postgres and exposed by the API, so ServiceMonitor targets only the API Service. | `servicemonitor.yaml` | ADR-023 |
| Root `Makefile` adds `export IMAGE VERSION` so Compose can substitute `${IMAGE}:${VERSION}`. | Makefile | none (needed for Compose) |
| The local Compose host port is `${SUPERTRENDS_HOST_PORT:-8080}`, still bound to 127.0.0.1, so a machine where 8080 is taken can run `make up` and `make smoke` (set `SMOKE_BASE_URL` to match). | `docker-compose.local.yml` | none (default unchanged) |
| Until Sprint 1 adds Alembic, the Dockerfile build stage copies `README.md`, `src/`, and `config/` and runs `uv sync --locked --no-dev --no-editable`; base images are pinned by digest. | Dockerfile | none (staged delivery) |
| The required jobs carry the display names `ci / lint-and-typecheck` and `ci / unit-tests`, which are the check contexts branch protection requires. | `ci.yml` | none (alignment) |
| Ruff excludes `*.md`: ruff 0.17 formats Python code blocks inside Markdown, and the spec documents are not reformatted by tools. | `pyproject.toml` | none (tooling) |
| Ingestion (S1-T06): `ingest()` returns per-ticker data quality (`ok`, `stale`, `degraded`, `insufficient_history`) and the daily run stores it in `ticker_scores.data_quality`; weekly resample is in memory in `data/resample.py` (ADR-033); fundamentals refresh when empty, on the first session of the ISO week, after an earnings date, or with `--full`; the default universe is the resolved watchlist plus SPY and QQQ (TODO(#17)); `data/call_recorder.py` uses the same `CallRecord` shape as the Massive recorder; per-ticker daily bars are used (grouped daily is S1-T04). | `data/ingest.py`, `data/quality.py`, `data/resample.py` | none (implementation detail) |
| CLA check and signer workflows. | `cla.yml`, `cla-sign.yml` | ADR-051 |
| Massive adapter endpoint paths follow the 2026-11-15 vendor docs where they differ from section 7.6 (`/stocks/v1/splits`, `/stocks/v1/dividends`, `/stocks/financials/v1/income-statements`); no earnings endpoint, so `earnings_dates` is `CapabilityNotSupported`; retries are hand-rolled instead of `tenacity`. | `data/providers/massive.py` (`ENDPOINTS`) | ADR-009 |
| Network is blocked for tests: `pytest-socket` (MIT) with `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1` in pytest `addopts`, so unit and integration tests reach only loopback (local Postgres) and a stray outbound call fails the test. | `pyproject.toml` | none (Sprint 1 checklist) |
| Dev-only npm license exceptions in the license script. | `scripts/gen_third_party_licenses.py` | ADR-052 |
| Watchlist item objects add a nullable `resolution_reason` (PRD FR-007 requires the reason on the Watchlist screen). The seed symbol `000660` fails the `tickers.symbol` format CHECK, so it is reported by the seed loader but cannot be stored; it stays in `docs/OWNER_CHECKLIST.md` row 13. Watchlist routes render problem+json through a route class until S1-T08 adds app-wide handlers. | `api/routes/watchlist.py`, `data/watchlist.py` | none (S1-T07) |

Additional values (merged into the seed `values.yaml` in 10.6):

```yaml
global:
  imageRegistry: ""        # air-gap: prefix for every image (app, postgres, llm mock)

worker:
  enabled: true            # replicas follow replicaCount capped at 1 (0 when replicaCount is 0)
  pollSeconds: 5
  queuedRunTimeoutSeconds: 600
  resources:
    requests: { cpu: 50m, memory: 192Mi }
    limits: { cpu: "2", memory: 1536Mi }

llmMock:
  enabled: false           # kind profile only: OpenAI-compatible mock for narratives
  image: { repository: ghcr.io/mohnishbasha/stokeai-supertrends, tag: "", digest: "" }   # same image, command: supertrends-llm-mock

seed:
  enabled: false           # kind profile only: post-install Job runs fixture ingest and one run
```

Additional chart templates: `deployment-worker.yaml`, `deployment-llm-mock.yaml` (when `llmMock.enabled`), `service-llm-mock.yaml`, `job-seed.yaml` (post-install hook, when `seed.enabled`). The llm mock is a console script `supertrends-llm-mock` shipped in the same wheel (dev-only behavior, deterministic canned responses that pass the numeric guard plus one forced-failure mode for fallback tests).

### 10.1 Overview
This section is mandatory and explicit. `docs/ARCHITECTURE.md` must mirror it, and Sprint 8 produces `docs/DEPLOYMENT.md` from it. The root `Makefile` is the only documented way to build and deploy.

Super Trends is a CPU-only product. There are no GPU requests, no NVIDIA device plugin dependencies, and no model storage. It reaches an LLM over HTTP through the gateway Stoke already runs. Everything GPU-related in the general deployment template is intentionally dropped.

Super Trends is a server product with a web UI, not a desktop app. "Local binary" for Super Trends means the `supertrends` CLI installed from the built wheel.
### 10.2 Single entry point: root Makefile

Create this in Sprint 0 (S0-T03). Targets not yet implementable print a notice and exit 0 until their sprint.

```makefile
SHELL := /bin/bash
GH_OWNER ?= mohnishbasha
VERSION  := $(shell tr -d '[:space:]' < VERSION)
COMMIT   := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
CREATED  := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
IMAGE    ?= ghcr.io/$(GH_OWNER)/stokeai-supertrends
CHART    := deploy/helm/stokeai-supertrends
CHART_REPO ?= oci://ghcr.io/$(GH_OWNER)/charts
KIND_CLUSTER ?= supertrends
NAMESPACE ?= supertrends
PROFILE  ?= kind
SMOKE_BASE_URL ?= http://localhost:8080
PLATFORMS ?= linux/amd64,linux/arm64
BUILD_ARGS := --build-arg VERSION=$(VERSION) --build-arg COMMIT=$(COMMIT) --build-arg CREATED=$(CREATED)

.DEFAULT_GOAL := help
.PHONY: help setup build build-release check test coverage dev up down smoke demo demo-verify demo-down run-daily openapi \
        version-sync image image-multiarch image-push image-scan image-verify \
        helm-lint helm-package helm-push kind-up kind-load helm-install helm-test helm-uninstall kind-down

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup: ## Check prerequisites and install dependencies
	@./scripts/check-prereqs.sh
	uv sync --locked
	npm --prefix ui ci

build: ## Build the UI and the Python wheel
	npm --prefix ui run build
	uv build --wheel

build-release: ## Reproducible release build (locked, clean)
	rm -rf dist ui/dist
	npm --prefix ui ci && npm --prefix ui run build
	uv sync --locked --no-dev && uv build --wheel

check: ## Lint, format check, type-check (Python and TypeScript)
	uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src
	npm --prefix ui run lint && npm --prefix ui run type-check
	./scripts/check-versions.sh

test: ## Unit tests
	uv run pytest tests/unit -q
	npm --prefix ui run test -- --run

coverage: ## Coverage with thresholds
	uv run pytest tests/unit tests/integration --cov=src/supertrends --cov-report=term --cov-report=xml
	npm --prefix ui run test -- --run --coverage
	uv run python scripts/check_coverage.py .coverage-thresholds.toml

dev: ## Native dev: Postgres in Compose, API and UI on the host with reload
	docker compose -f deploy/compose/docker-compose.dev.yml up -d postgres llm-mock
	uv run supertrends db migrate
	( uv run uvicorn supertrends.api.app:create_app --factory --reload --port 8080 & \
	  npm --prefix ui run dev ; kill %1 )

up: ## Run the built image with Compose
	docker compose -f deploy/compose/docker-compose.local.yml up -d --wait

down: ## Stop Compose and remove volumes
	docker compose -f deploy/compose/docker-compose.local.yml down -v

smoke: ## Smoke suite against SMOKE_BASE_URL
	SMOKE_BASE_URL=$(SMOKE_BASE_URL) uv run pytest tests/smoke -q

demo: image ## Local demo: full product on synthetic data, no keys needed
	SUPERTRENDS_DEMO=1 docker compose -f deploy/compose/docker-compose.demo.yml up -d --wait
	@echo "Demo ready: http://localhost:8080   tour: http://localhost:8080/demo   (make demo-verify to check every function)"

demo-verify: ## Check every product function against the running demo, write demo-report/
	SMOKE_BASE_URL=http://localhost:8080 uv run python scripts/demo_verify.py --report demo-report

demo-down: ## Stop the demo and remove its data
	docker compose -f deploy/compose/docker-compose.demo.yml down -v

run-daily: ## Trigger the daily run locally
	uv run supertrends run daily

openapi: ## Regenerate docs/openapi.json and the UI client
	uv run supertrends config export-openapi > docs/openapi.json
	npm --prefix ui run gen:api

version-sync: ## Write VERSION into the checked files
	./scripts/version-sync.sh

image: ## Build the image for the local architecture
	docker buildx build $(BUILD_ARGS) -t $(IMAGE):$(VERSION) -t $(IMAGE):sha-$(COMMIT) --load .

image-multiarch: ## Build for linux/amd64 and linux/arm64 (no push)
	docker buildx build $(BUILD_ARGS) --platform $(PLATFORMS) -t $(IMAGE):$(VERSION) .

image-push: ## Build multi-arch, push, sign, attach SBOM and provenance
	docker buildx build $(BUILD_ARGS) --platform $(PLATFORMS) \
	  --sbom=true --provenance=mode=max \
	  -t $(IMAGE):$(VERSION) -t $(IMAGE):sha-$(COMMIT) --push .
	cosign sign --yes $(IMAGE)@$$(docker buildx imagetools inspect $(IMAGE):$(VERSION) --format '{{json .Manifest.Digest}}' | tr -d '"')

image-scan: ## Vulnerability scan, fails on HIGH or CRITICAL
	trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed $(IMAGE):$(VERSION)

image-verify: ## Verify the image signature
	cosign verify $(IMAGE):$(VERSION) \
	  --certificate-identity-regexp '^https://github.com/$(GH_OWNER)/stokeai-trading-supertrends/' \
	  --certificate-oidc-issuer https://token.actions.githubusercontent.com

helm-lint: ## Lint and template every profile
	@for p in kind stoke selfhost hosted; do \
	  helm lint $(CHART) -f $(CHART)/values-$$p.yaml || exit 1; \
	  helm template supertrends $(CHART) -f $(CHART)/values-$$p.yaml > /dev/null || exit 1; \
	done

helm-package: ## Package the chart at the current version
	helm package $(CHART) --version $(VERSION) --app-version $(VERSION) -d dist/charts

helm-push: helm-package ## Push the chart to the OCI registry
	helm push dist/charts/stokeai-supertrends-$(VERSION).tgz $(CHART_REPO)

kind-up: ## Create the local kind cluster
	kind create cluster --name $(KIND_CLUSTER) --config deploy/kind/cluster.yaml

kind-load: ## Load the local image into kind
	kind load docker-image $(IMAGE):$(VERSION) --name $(KIND_CLUSTER)

helm-install: ## Install or upgrade the chart with PROFILE (default kind)
	helm upgrade --install supertrends $(CHART) -n $(NAMESPACE) --create-namespace \
	  -f $(CHART)/values-$(PROFILE).yaml \
	  --set image.repository=$(IMAGE) --set image.tag=$(VERSION) \
	  --atomic --wait --timeout 5m

helm-test: ## Run Helm tests
	helm test supertrends -n $(NAMESPACE) --logs

helm-uninstall: ## Uninstall the release
	helm uninstall supertrends -n $(NAMESPACE)

kind-down: ## Delete the kind cluster
	kind delete cluster --name $(KIND_CLUSTER)
```

### 10.3 Path 1: Local build

Prerequisites, checked by `scripts/check-prereqs.sh` (called from `make setup`; prints what is missing and how to install it):

| Tool | Minimum | Used for |
|---|---|---|
| Python | 3.12 | backend |
| uv | 0.5 | Python env and lock |
| Node.js | 22 LTS | UI build |
| Docker with buildx | 27 | images, Compose |
| make, jq, git | any recent | tooling |
| kind, kubectl, helm | kind 0.24, kubectl 1.31, helm 3.16 | cluster paths |
| cosign, trivy | current | release paths only |

Verify the latest stable versions at implementation time and pin what you use in `docs/ARCHITECTURE.md`.

```bash
git clone git@github.com:mohnishbasha/stokeai-trading-supertrends.git && cd stokeai-trading-supertrends
make setup
make build
```

Build outputs:

| Output | Path | Built by |
|---|---|---|
| Python wheel (includes the CLI) | `dist/supertrends-{VERSION}-py3-none-any.whl` | `uv build --wheel` |
| UI bundle | `ui/dist/` | `npm --prefix ui run build` |
| Container image | `ghcr.io/mohnishbasha/stokeai-supertrends:{VERSION}` | `make image` |
| Helm chart package | `dist/charts/stokeai-supertrends-{VERSION}.tgz` | `make helm-package` |
| Pi extension | `integrations/pi/dist/` | `npm --prefix integrations/pi run build` |

Rules: a clean clone must build with `make setup && make build`, and CI proves it on every PR. Release builds use `make build-release` (locked dependencies, pinned toolchain through `.python-version` and `.nvmrc`). The CLI and `/healthz` report version and commit.

Verification:

```bash
uv run supertrends --version          # supertrends 0.1.0 (abc1234)
make check && make test
```

### 10.4 Path 2: Local deploy

**Native run for development**

```bash
make dev                         # Postgres and an LLM mock in Compose, API on :8080 with reload, UI on :5173
uv run supertrends ingest              # fixture provider by default
uv run supertrends run daily
curl -fsS localhost:8080/api/v1/recommendations/latest | jq '.buys[].ticker, .sells[].ticker'
uv run supertrends today
```

**Native install of the release CLI**

```bash
make build-release
uv tool install dist/supertrends-*.whl
supertrends --version
SUPERTRENDS_DATABASE_URL=postgresql+psycopg://... supertrends db migrate
supertrends serve --bind 127.0.0.1:8080 &
supertrends healthcheck --url http://127.0.0.1:8080     # exit 0 when ready
```

Provide `deploy/systemd/supertrends.service` and `deploy/systemd/supertrends-daily.timer` (17:30 America/New_York, weekdays) for a single-host install without Kubernetes, with `scripts/install.sh` that installs the wheel into `/opt/supertrends`, writes an environment file with mode 0600, and enables the units.

**Compose run from the built image**

```bash
make image
make up                          # app + Postgres from deploy/compose/docker-compose.local.yml
make smoke                       # same suite as kind and Stoke
make down
```

**Demo mode (local run to see and verify the product)**

```bash
make demo           # builds the image, starts everything, seeds data, prints the URL
make demo-verify    # one PASS / FAIL line per function, plus demo-report/index.html with screenshots
make demo-down
```

Demo mode exists so the owner can look at the product and confirm it works without API keys, a cluster, or real market data. Requirements:
- `deploy/compose/docker-compose.demo.yml`: the app, Postgres, and the LLM mock, with `SUPERTRENDS_DEMO=1`, the fixture provider, and a one-shot seed service.
- The seed loads the synthetic dataset, then replays the last 60 trading days through the real run orchestrator, so the Today screen, date browsing, rankings, and the Track Record all have data. The synthetic tickers are constructed so the latest run has 3 buys and 2 sells, one ticker in each regime, a fresh Supertrend flip, a divergence, a Fibonacci hold, a breakout, an `event_risk` pick, and one excluded ticker.
- Every screen shows the banner "DEMO DATA: synthetic prices, not real markets". Demo mode cannot be enabled together with a real provider.
- The `/demo` tour lists each function, links to where it is shown, and displays its status.
- `scripts/demo_verify.py` checks the demo matrix below through the API, the CLI, MCP, and (from Sprint 4) the UI with Playwright, prints a table, writes `demo-report/index.html` with one screenshot per screen, and exits non-zero on any FAIL.
- `make demo` followed by `make demo-verify` runs in CI on every PR from Sprint 3 on.

Demo matrix (extend it in the same PR as any new function):

| Function | Verified by | Added in |
|---|---|---|
| Ingest and data quality flags | API status, excluded ticker shown with reason | 3 |
| All 11 factors scored, contributions sum to the composite | analysis endpoint for 3 tickers | 3 (fundamentals and regimes in 5) |
| Top 3 buys and top 2 sells, duplicate guard | latest recommendations | 3 |
| Supertrend line, direction, flip age | bars endpoint and chart overlay | 3, chart in 4 |
| Today, Ticker, Watchlist, Runs, Settings screens | Playwright screenshots | 4 |
| Narrative with numeric guard and template fallback | one LLM-mock narrative, one forced fallback | 5 |
| Dynamic weights and event risk | a trending and a ranging ticker, an earnings-window pick | 5 |
| Track record and backtest | statistics for the 60 replayed days | 6 |
| CLI and MCP parity with the API | `supertrends today --json`, MCP tool calls | 7 |
| Watchlist groups and add / remove | API round trip and UI | 3, UI in 4 |

`docker-compose.local.yml`: the app image (read-only root filesystem, non-root, health check using `supertrends healthcheck`), Postgres with a named volume and health check, a one-shot `migrate` service, a one-shot `seed` service (fixture ingest and one run), and an LLM mock. `docker-compose.prod.yml`: pinned image digests, resource limits, no published database port, an internal network, and secrets from an env file outside the repository.

### 10.5 Path 3: Containerization using OCI

One deployable, one multi-stage Dockerfile. The same image runs the API (`supertrends serve`), the daily job (`supertrends run daily`), migrations (`supertrends db migrate`), and the stdio MCP server (`supertrends mcp`).

Dockerfile shape (pin every `FROM` by digest when you write it):

```dockerfile
# syntax=docker/dockerfile:1

# ---- stage 1: UI dependencies and build ----
FROM --platform=$BUILDPLATFORM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY ui/ ./
RUN npm run build

# ---- stage 2: Python dependencies (cached layer) ----
FROM python:3.12-slim-bookworm AS deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock VERSION ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

# ---- stage 3: build and install the project ----
FROM deps AS build
COPY src/ ./src/
COPY config/ ./config/
COPY alembic.ini ./
COPY migrations/ ./migrations/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

# ---- stage 4: minimal runtime ----
FROM python:3.12-slim-bookworm AS runtime
ARG VERSION=0.0.0
ARG COMMIT=unknown
ARG CREATED=unknown
LABEL org.opencontainers.image.title="Super Trends Market Agent" \
      org.opencontainers.image.description="Supertrend market agent: daily top buys and sells with justification" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT}" \
      org.opencontainers.image.created="${CREATED}" \
      org.opencontainers.image.source="https://github.com/mohnishbasha/stokeai-trading-supertrends" \
      org.opencontainers.image.vendor="Serverless Ventures LLC" \
      org.opencontainers.image.licenses="PolyForm-Noncommercial-1.0.0"
RUN groupadd -g 10001 supertrends && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin supertrends
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    SUPERTRENDS_VERSION=${VERSION} SUPERTRENDS_COMMIT=${COMMIT} SUPERTRENDS_UI_DIR=/app/ui
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /app/src /app/src
COPY --from=build /app/config /app/config
COPY --from=build /app/alembic.ini /app/alembic.ini
COPY --from=build /app/migrations /app/migrations
COPY --from=ui /ui/dist /app/ui
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["supertrends", "healthcheck", "--url", "http://127.0.0.1:8080"]
ENTRYPOINT ["supertrends"]
CMD ["serve", "--bind", "0.0.0.0:8080"]
```

Requirements:
- OCI image format, multi-arch `linux/amd64` and `linux/arm64` through buildx. ARM64 is the production architecture (DGX Spark). Confirm that every wheel in `uv.lock` has an `aarch64` build (numpy, pandas, psycopg binary); if one does not, build it in the `deps` stage and record it in an ADR. CI runs the unit test suite inside the ARM64 image under QEMU at least on `staging`.
- Replace `ghcr.io/astral-sh/uv:latest` and both base images with digest-pinned references. Evaluate a distroless or Chainguard Python runtime; adopt it if numpy and pandas run on it for both architectures, otherwise keep slim and record why.
- Non-root, read-only root filesystem (the app writes only to `/tmp`, mounted as `emptyDir`), a health check that needs no shell (exec form of the CLI).
- Standard `org.opencontainers.image.*` labels wired to `VERSION` and the commit, as above.
- Tagging: immutable `{VERSION}` on release, `sha-{short}` on every merge to `staging`, never `latest`. Deployments reference the digest.
- Registry: GHCR.
- Signing and supply chain: cosign keyless, SBOM (SPDX) and SLSA provenance attached by buildx, Trivy failing on high or critical.
- Non-image OCI artifacts: the Helm chart is pushed with `helm push` to `oci://ghcr.io/mohnishbasha/charts`. Super Trends ships no models or large assets, so `oras` is used only in the air-gap mirror procedure.

Commands:

```bash
make image                 # local arch, loaded into Docker
make image-multiarch       # both arches, proves the build
make image-scan
make image-push            # CI only: build, push, SBOM, provenance, cosign sign
make image-verify          # what a consumer runs:
cosign verify ghcr.io/mohnishbasha/stokeai-supertrends:1.0.0 \
  --certificate-identity-regexp '^https://github.com/mohnishbasha/stokeai-trading-supertrends/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

### 10.6 Path 4: Helm chart for a Kubernetes cluster

Chart tree:

```
deploy/helm/stokeai-supertrends/
  Chart.yaml
  values.yaml
  values.schema.json
  values-kind.yaml          # local kind, bundled Postgres, fixture provider, LLM mock
  values-stoke.yaml         # existing k3s ARM64 cluster on DGX Spark (stage and prod)
  values-selfhost.yaml      # any single cluster, bundled Postgres, template narratives by default
  values-hosted.yaml        # AWS: external Postgres, ALB ingress, External Secrets
  templates/
    _helpers.tpl
    configmap-scoring.yaml
    deployment-api.yaml
    deployment-worker.yaml        # manual-run worker (ADR-020)
    deployment-llm-mock.yaml      # when llmMock.enabled (kind)
    service-llm-mock.yaml         # when llmMock.enabled (kind)
    service.yaml
    cronjob-daily-run.yaml
    job-migrate.yaml              # pre-install, pre-upgrade hook
    job-seed.yaml                 # post-install hook when seed.enabled (kind)
    statefulset-postgres.yaml     # when postgres.enabled
    service-postgres.yaml
    pvc.yaml
    ingress.yaml
    hpa.yaml
    pdb.yaml
    networkpolicy.yaml
    serviceaccount.yaml
    servicemonitor.yaml
    prometheusrule.yaml
    configmap-dashboard.yaml
    externalsecret.yaml           # when externalSecrets.enabled
    NOTES.txt
    tests/
      test-health.yaml
      test-api.yaml
```

Seed `values.yaml` (no secret values in any committed file):

```yaml
image:
  repository: ghcr.io/mohnishbasha/stokeai-supertrends
  tag: ""            # defaults to .Chart.AppVersion
  digest: ""         # when set, wins over tag
  pullPolicy: IfNotPresent
imagePullSecrets: []

replicaCount: 1
env: prod

api:
  port: 8080
  resources:
    requests: { cpu: 100m, memory: 256Mi }
    limits: { cpu: "1", memory: 512Mi }
  terminationGracePeriodSeconds: 30

dailyRun:
  enabled: true
  schedule: "30 17 * * 1-5"
  timeZone: America/New_York
  suspend: false
  activeDeadlineSeconds: 3600
  backoffLimit: 1
  resources:
    requests: { cpu: 500m, memory: 512Mi }
    limits: { cpu: "2", memory: 1536Mi }

providers:
  market: massive          # fixture | massive | alternate
  fundamentals: massive
  massiveBaseUrl: https://api.massive.com
  ratePerMinute: 5

llm:
  narrativeProvider: openai_compatible   # template | openai_compatible
  baseUrl: ""              # set per profile; empty means template narratives
  model: ""
  timeoutSeconds: 8

secrets:
  existingSecret: supertrends-secrets   # keys: SUPERTRENDS_API_TOKEN, SUPERTRENDS_MASSIVE_API_KEY, SUPERTRENDS_LLM_API_KEY, SUPERTRENDS_DATABASE_URL
externalSecrets:
  enabled: false
  secretStoreRef: { name: "", kind: ClusterSecretStore }

postgres:
  enabled: true            # bundled single-instance Postgres
  image: { repository: postgres, tag: "17", digest: "" }
  storage: { size: 10Gi, storageClass: "" }
  resources:
    requests: { cpu: 100m, memory: 256Mi }
    limits: { cpu: "1", memory: 1Gi }
  existingSecret: supertrends-postgres   # key: POSTGRES_PASSWORD
externalDatabase:
  enabled: false           # when true, SUPERTRENDS_DATABASE_URL comes from secrets.existingSecret

scoring:
  config: {}               # empty means the default config baked into the image; otherwise rendered to a ConfigMap

ingress:
  enabled: false
  className: ""
  host: ""                 # Stoke profile: supertrends.openstoke.com (stage: supertrends-stage.openstoke.com)
  annotations: {}
  tls: []

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 3
  targetCPUUtilizationPercentage: 70

pdb:
  enabled: false
  minAvailable: 1

networkPolicy:
  enabled: true
  ingressFrom: []          # namespace and pod selectors allowed to reach the API
  llmEgress: []            # selectors for the LLM gateway
  providerEgressCIDRs: ["0.0.0.0/0"]   # 443 only; narrow where the CNI supports FQDN policy

metrics:
  serviceMonitor: { enabled: false, labels: {} }
  prometheusRule: { enabled: false, labels: {} }
  dashboard: { enabled: false, labels: { grafana_dashboard: "1" } }

nodeSelector: {}
tolerations: []
affinity: {}

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  fsGroup: 10001
  seccompProfile: { type: RuntimeDefault }
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities: { drop: ["ALL"] }
```

Chart rules:
- `Chart.yaml` `version` and `appVersion` equal `VERSION` (checked by `check-versions.sh`).
- `values.schema.json` validates every key, rejects unknown keys, rejects any key named `password`, `token`, or `apiKey` that carries a literal value, and validates the cron expression format.
- API Deployment: `RollingUpdate` with `maxUnavailable: 0`, `maxSurge: 1`; startup, readiness (`/readyz`), and liveness (`/healthz`) probes; `preStop` sleep of 5 seconds and SIGTERM handling so in-flight requests finish; `/tmp` as `emptyDir`.
- The daily run is a CronJob with `concurrencyPolicy: Forbid`, `timeZone`, `startingDeadlineSeconds: 3600`, and history limits. Because the run is a CronJob, the API is stateless and can scale horizontally.
- Migration Job runs as a `pre-install,pre-upgrade` hook with `hook-delete-policy: before-hook-creation,hook-succeeded`. Migrations are backward compatible for one version so rollback works.
- Bundled Postgres is a single-replica StatefulSet with a PVC. With `externalDatabase.enabled` it is not rendered.
- PodDisruptionBudget and HPA are rendered only when enabled and only make sense with more than one replica; the hosted profile enables both.
- NetworkPolicy default deny with the allowances listed in Security Guidelines.
- Helm tests: `test-health` (calls `/readyz`), `test-api` (calls `/api/v1/recommendations/latest` and accepts 200 or a well-formed 404 "no run yet").

Profiles:

| Profile | Database | Provider | LLM | Exposure | Notes |
|---|---|---|---|---|---|
| `values-kind.yaml` | bundled | fixture | in-chart mock (`llmMock.enabled`) | port-forward | CI and local loop; seeds data and triggers a run with a post-install Job |
| `values-stoke.yaml` | bundled on `local-path` (or the class found in the inventory) | massive | Stoke gateway | `supertrends.openstoke.com` (stage: `supertrends-stage.openstoke.com`) through the tailnet service or the existing ingress found in the inventory; reachable only privately | `nodeSelector: {kubernetes.io/arch: arm64}`, ServiceMonitor and dashboard on, no GPU |
| `values-selfhost.yaml` | bundled | massive | template (LLM optional) | ingress off by default | air-gap friendly: `global.imageRegistry` override |
| `values-hosted.yaml` | external (AWS RDS Postgres) | massive | any OpenAI-compatible endpoint | ALB ingress with TLS | External Secrets from AWS Secrets Manager, HPA 2 to 3, PDB on, amd64 or arm64 (Graviton) |

**Stoke profile and inventory.** Stoke already runs a platform. Super Trends reuses it and installs nothing cluster-wide. `scripts/stoke-inventory.sh` (read-only) writes `private/STOKE_INVENTORY.md` (git-ignored) with one row per dependency:

| Component | Expected on Stoke | Super Trends needs | Expected class |
|---|---|---|---|
| Kubernetes (k3s, ARM64) | yes | a namespace | REUSE |
| Flux v2 (source, helm, kustomize controllers) | yes | OCIRepository, HelmRelease, Kustomization | REUSE |
| LLM gateway in front of vLLM (AIBrix) | yes | an OpenAI-compatible base URL and a model name | REUSE |
| kube-prometheus-stack | yes | ServiceMonitor, PrometheusRule, dashboard ConfigMap | REUSE |
| Storage class | k3s `local-path` or other | a 10Gi PVC for Postgres | REUSE |
| Ingress or tailnet exposure | Traefik (k3s default) and Tailscale | one HTTP route, private | REUSE |
| Secret management (SOPS or External Secrets) | find out | 2 Secrets per namespace | REUSE if present, else plain Secrets created by the owner |
| NetworkPolicy enforcement | depends on CNI | default deny plus allowances | REUSE if enforced, else document the gap |
| Postgres operator | probably none | none: the bundled StatefulSet is enough | NOT NEEDED |
| GPU Operator, KubeRay | yes | nothing | NOT NEEDED |

The script records the gateway's in-cluster service URL and the served model names (from the gateway's `/v1/models`) so `values-stoke.yaml` can be filled without guessing. If a model must be chosen, prefer a small instruct model already served; Super Trends's narrative task is short and structured. Record the choice and the measured acceptance rate in `docs/NARRATIVE_EVAL.md`. Do not deploy a model for Super Trends.

Local cluster loop:

```bash
make kind-up
make image
make kind-load
make helm-install                 # PROFILE=kind
make helm-test
kubectl -n supertrends port-forward svc/supertrends 8080:8080 &
make smoke
make helm-uninstall && make kind-down
```

Remote install from the OCI chart (any cluster, without Flux):

```bash
helm upgrade --install supertrends oci://ghcr.io/mohnishbasha/charts/stokeai-supertrends \
  --version 1.0.0 -n supertrends --create-namespace \
  -f values-stoke.yaml \
  --set image.digest=sha256:<digest-from-release> \
  --atomic --wait --timeout 10m
helm test supertrends -n supertrends --logs
helm history supertrends -n supertrends
helm rollback supertrends <revision> -n supertrends --wait
```

Secrets the owner creates once per namespace (values never enter git):

```bash
kubectl -n supertrends create secret generic supertrends-postgres --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 24)"
kubectl -n supertrends create secret generic supertrends-secrets \
  --from-literal=SUPERTRENDS_API_TOKEN="$(openssl rand -hex 32)" \
  --from-literal=SUPERTRENDS_MASSIVE_API_KEY="<key>" \
  --from-literal=SUPERTRENDS_LLM_API_KEY="" \
  --from-literal=SUPERTRENDS_DATABASE_URL="postgresql+psycopg://supertrends:<same password>@supertrends-postgres:5432/supertrends"
```

**Stoke through Flux (the production path).** Stoke uses Flux for GitOps. Super Trends ships manifests that the Stoke GitOps repository references:

```
deploy/flux/
  base/
    namespace.yaml
    ocirepository.yaml      # chart source, cosign-verified
    helmrelease.yaml
    kustomization.yaml
  overlays/
    stage/                  # namespace supertrends-stage, sha- chart or prerelease, replicas may be 0
      kustomization.yaml
      patch-helmrelease.yaml
    prod/                   # namespace supertrends, released chart version, image by digest
      kustomization.yaml
      patch-helmrelease.yaml
```

Shape of the two key objects (confirm API versions against the Flux version found in the inventory):

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: stokeai-supertrends
  namespace: supertrends
spec:
  interval: 10m
  url: oci://ghcr.io/mohnishbasha/charts/stokeai-supertrends
  ref:
    semver: "1.x"
  verify:
    provider: cosign
    matchOIDCIdentity:
      - issuer: "^https://token.actions.githubusercontent.com$"
        subject: "^https://github.com/mohnishbasha/stokeai-trading-supertrends/.*$"
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: supertrends
  namespace: supertrends
spec:
  interval: 10m
  chartRef:
    kind: OCIRepository
    name: stokeai-supertrends
  install:
    remediation: { retries: 2 }
  upgrade:
    remediation: { retries: 2, strategy: rollback }
  test:
    enable: true
  rollback:
    cleanupOnFail: true
  values:
    env: prod
    image:
      digest: sha256:REPLACE_WITH_RELEASE_DIGEST
    nodeSelector:
      kubernetes.io/arch: arm64
    llm:
      baseUrl: REPLACE_FROM_STOKE_INVENTORY
      model: REPLACE_FROM_STOKE_INVENTORY
    metrics:
      serviceMonitor: { enabled: true }
      prometheusRule: { enabled: true }
      dashboard: { enabled: true }
```

The GHCR image and chart packages are public, so no pull secret is needed; after the first publish, record in the owner checklist that the package visibility must be set to public. The manifests in this public repository keep the `REPLACE_` placeholders; real cluster values are patched in the Stoke GitOps repository. Promotion is a pull request to the Stoke GitOps repository that changes the chart version and image digest in the overlay. Rollback is reverting that pull request, or in an emergency:

```bash
flux suspend helmrelease supertrends -n supertrends
helm rollback supertrends <revision> -n supertrends --wait
# fix forward in git, then
flux resume helmrelease supertrends -n supertrends
```

Chart verification in CI:
- `helm lint` and `helm template` for every profile (`make helm-lint`), output validated with `kubeconform`.
- Schema negative tests: a values file with a literal secret, an invalid cron, and an unknown key must each fail.
- `kind-e2e`: kind install with the kind profile, post-install seed and run, Helm tests, smoke suite.
- Upgrade and rollback test: previous released chart to current, smoke, rollback, smoke.
- `kustomize build` and schema validation for both Flux overlays.

Air-gapped install (self-host profile): mirror the image and chart into a private registry with `oras copy` or `skopeo copy --all`, set `global.imageRegistry` and the chart URL, and use the `fixture` or an internally reachable provider. `DEPLOYMENT.md` carries the exact commands.

### 10.7 CI and CD pipeline map

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | PR and push to `develop`, `staging`, `main` | lint, type-check, unit, coverage thresholds, integration (Postgres service), e2e (Playwright on Compose), image build for both architectures, `helm-lint`, version and changelog checks, gitleaks, audits |
| `kind-e2e.yml` | PR touching `src/`, `deploy/`, `Dockerfile`; push to `staging` | kind install, Helm tests, smoke suite, upgrade and rollback test |
| `release-images.yml` | push to `staging` (sha tag), tag `v*` (version tag) | multi-arch build, Trivy, push to GHCR, cosign sign, SBOM and provenance |
| `release-chart.yml` | same as above | `helm package`, `helm push` to OCI, cosign sign |
| `release.yml` | tag `v*` | version check, full suite, calls the two workflows above, creates the GitHub Release |
| `harness-smoke.yml` | push to `staging`, tag `v*` | MCP client against the API with fixture data |
| `flux-validate.yml` | PR touching `deploy/flux/` | `kustomize build`, schema validation |
| `nightly.yml` | schedule | full suite inside the ARM64 image under QEMU, dependency audit, determinism hash check |

Deployment to Stoke is pull-based through Flux. CI never holds cluster credentials.

### 10.8 Which sprint delivers which part

| Sprint | Build and deployment deliverable |
|---|---|
| 0 | Makefile, prerequisites script, Dockerfile skeleton, Compose, CI building both architectures, inventory script |
| 1 | Compose with Postgres and migrations, smoke suite skeleton |
| 3 | Real image, minimal chart, kind loop, `kind-e2e` in CI, CronJob, full smoke suite |
| 3 to 9 | Demo mode (`make demo`, `make demo-verify`), extended every sprint |
| 4 to 7 | Every sprint checklist: image builds, chart installs on kind, smoke suite passes against it |
| 6 | ServiceMonitor, PrometheusRule, dashboard |
| 8 | Complete chart and schema, four profiles, signed `sha-` images and OCI chart, Flux overlays, staging on Stoke, upgrade and rollback test, air-gap notes, `docs/DEPLOYMENT.md` |
| 9 | Signed multi-arch `1.0.0` image and chart, production on Stoke by digest |


### 10.9 Semantic versioning

`MAJOR.MINOR.PATCH`. MAJOR: breaking change to the HTTP API, MCP tool schemas, CLI flags, database schema without an automatic migration, or the meaning of a score. MINOR: new capability, backward compatible. PATCH: fixes only. Pre-1.0 versions are `0.{sprint}.{patch}` and carry no compatibility promise.

The scoring config has its own integer `scoring.version`. Any change to weights, thresholds, or formulas bumps it and is called out in the changelog under a "Scoring" heading, because it changes what the picks mean.

### 10.10 Version source of truth

The root `VERSION` file (one line, no `v` prefix). Everything else derives from it or is checked against it:

| File | Field | How |
|---|---|---|
| `pyproject.toml` | `project.version` | dynamic, read from `VERSION` by the build backend |
| `ui/package.json` | `version` | checked |
| `integrations/pi/package.json` | `version` | checked |
| `deploy/helm/stokeai-supertrends/Chart.yaml` | `version` and `appVersion` | checked |
| Container labels | `org.opencontainers.image.version` | build arg from `VERSION` |
| `supertrends --version`, `/healthz` | version, commit | read at build time |

### 10.11 scripts/check-versions.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CANONICAL="$(tr -d '[:space:]' < VERSION)"
if ! [[ "$CANONICAL" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]]; then
  echo "x VERSION is not semver: '$CANONICAL'"; exit 1
fi
check() {
  local actual="$1" file="$2"
  if [[ "$actual" != "$CANONICAL" ]]; then
    echo "x Version mismatch in $file: expected $CANONICAL, got $actual"
    exit 1
  fi
  echo "ok $file: $CANONICAL"
}
check "$(jq -r .version ui/package.json)" "ui/package.json"
check "$(jq -r .version integrations/pi/package.json)" "integrations/pi/package.json"
check "$(awk '/^version:/{print $2}' deploy/helm/stokeai-supertrends/Chart.yaml | tr -d '"')" "Chart.yaml version"
check "$(awk '/^appVersion:/{print $2}' deploy/helm/stokeai-supertrends/Chart.yaml | tr -d '"')" "Chart.yaml appVersion"
echo "All versions consistent: $CANONICAL"
```

Runs in CI on every PR to `staging` and `main`. Files that do not exist yet in early sprints are skipped with a guard you add, and the guard is removed in the sprint that creates the file.

### 10.12 Version bump process

1. On a branch off `develop`: edit `VERSION`, then run `make version-sync` (writes the checked files).
2. Move the `[Unreleased]` changelog entries under a new `## [X.Y.Z] - YYYY-MM-DD` heading and leave an empty `[Unreleased]`.
3. Run `scripts/check-versions.sh` and `make check`.
4. Commit as `chore: release X.Y.Z`, open the PR.

### 10.13 Changelog protocol

`CHANGELOG.md` follows Keep a Changelog. `[Unreleased]` is always present. Every PR that changes behavior adds a line under Added, Changed, Deprecated, Removed, Fixed, Security, or Scoring. CI fails a PR labeled `type:feature` or `type:bug` that does not touch `CHANGELOG.md`.

### 10.14 scripts/extract-changelog.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:?Usage: $0 <version>}"
awk "/^## \\[${VERSION}\\]/{found=1; next} found && /^## \\[/{exit} found{print}" CHANGELOG.md
```

### 10.15 Git tagging strategy

- Releases: annotated tags on `main`: `git tag -a vX.Y.Z -m "Super Trends vX.Y.Z"`.
- Sprints: lightweight tags on `staging`: `sprint-N-complete`. The runner depends on these.
- Never move or delete a pushed tag.

### 10.16 Release workflow (CI)

```
tag vX.Y.Z pushed
  -> check-versions (tag must equal VERSION)
  -> full test suite
  -> build images linux/amd64 + linux/arm64 (buildx)
  -> Trivy scan (fail on HIGH, CRITICAL)
  -> push ghcr.io/mohnishbasha/stokeai-supertrends:X.Y.Z and :sha-<short>
  -> cosign sign (keyless), attach SBOM (SPDX) and SLSA provenance
  -> helm package (version X.Y.Z, appVersion X.Y.Z), helm push to oci://ghcr.io/mohnishbasha/charts, cosign sign
  -> create GitHub Release, body from scripts/extract-changelog.sh, attach SBOM and image digests
```

### 10.17 Release checklist

Pre-release
- [ ] Final Gate green (all sprint checklists checked, `docs/GATE_DEBT.md` empty); no open `priority:p0` or `priority:p1` issues in the milestone
- [ ] `scripts/check-versions.sh` passes; changelog section written
- [ ] Security review complete

Staging validation
- [ ] `sha-` image and chart deployed to `supertrends-stage` on Stoke by digest
- [ ] Helm tests and smoke suite pass on staging
- [ ] One full real-provider run reviewed by the owner

Release
- [ ] PR `staging` to `main` approved by the owner and merged
- [ ] Annotated tag pushed; release workflow green
- [ ] `cosign verify` succeeds for the image and the chart
- [ ] Production overlay updated to the new chart version and image digest

### 10.18 Post-release actions

- Back-merge `main` into `develop`.
- Bump `VERSION` on `develop` to the next patch with a `-dev` suffix.
- Confirm the first scheduled production run published.
- Close the milestone; open the next one.
- Record the release in `docs/RETROSPECTIVES.md`.

### 10.19 Environment Model

| Environment | Where | Data provider | LLM | Purpose |
|---|---|---|---|---|
| dev | Host or Compose | fixture (default) or real | mock or any OpenAI-compatible endpoint | Daily development |
| ci | GitHub Actions, kind | fixture | mock | Tests, chart install |
| stage | Stoke, namespace `supertrends-stage` | real | Stoke gateway | Pre-release validation |
| prod | Stoke, namespace `supertrends` | real | Stoke gateway | The owner's daily use |

On Stoke, stage and prod are two namespaces on the same cluster. Super Trends is CPU-only and small, so this costs no GPU capacity. Stage scales to zero replicas outside release weeks (`replicaCount: 0`, CronJob suspended).

### 10.20 Environment variables

| Name | dev | stage | prod | Notes |
|---|---|---|---|---|
| `SUPERTRENDS_ENV` | `dev` | `stage` | `prod` | |
| `SUPERTRENDS_DATABASE_URL` | `postgresql+psycopg://supertrends:supertrends@localhost:5432/supertrends` | from Secret | from Secret | |
| `SUPERTRENDS_MARKET_PROVIDER` | `fixture` | `massive` | `massive` | `fixture`, `massive`, or the alternate |
| `SUPERTRENDS_FUNDAMENTALS_PROVIDER` | `fixture` | `massive` | `massive` | may differ from the market provider |
| `SUPERTRENDS_MASSIVE_API_KEY` | empty | from Secret | from Secret | |
| `SUPERTRENDS_MASSIVE_BASE_URL` | `https://api.massive.com` | same | same | legacy host also works |
| `SUPERTRENDS_PROVIDER_RATE_PER_MIN` | `5` | per plan | per plan | match the purchased plan |
| `SUPERTRENDS_LLM_BASE_URL` | `http://localhost:8089/v1` (mock) | gateway URL from inventory | same | OpenAI-compatible |
| `SUPERTRENDS_LLM_MODEL` | `mock` | model served on Stoke | same | |
| `SUPERTRENDS_LLM_API_KEY` | empty | from Secret if required | same | |
| `SUPERTRENDS_NARRATIVE_PROVIDER` | `template` | `openai_compatible` | `openai_compatible` | falls back to template |
| `SUPERTRENDS_API_TOKEN` | `dev-token` | from Secret | from Secret | write endpoints |
| `SUPERTRENDS_SCORING_CONFIG` | `config/scoring.yaml` | mounted ConfigMap | mounted ConfigMap | |
| `SUPERTRENDS_RUN_CRON` | n/a | `30 17 * * 1-5` | `30 17 * * 1-5` | America/New_York |
| `SUPERTRENDS_LOG_LEVEL` | `debug` | `info` | `info` | |
| `SUPERTRENDS_SOURCE_URL` | repo URL | repo URL at commit | repo URL at commit | license and source link shown in the UI |
| `SUPERTRENDS_ALLOWED_HOSTS` | `localhost` | `supertrends-stage.openstoke.com` | `supertrends.openstoke.com` | Host header allowlist |
| `SUPERTRENDS_BIND` | `127.0.0.1:8080` | `0.0.0.0:8080` | `0.0.0.0:8080` | |


Verify the latest stable version of each at implementation time, pin exact versions in the lock files, and record them in `docs/ARCHITECTURE.md`. The constraints below are floors, not targets.

### 10.21 Dependency versions: Python (pyproject.toml)

| Package | Constraint | Purpose |
|---|---|---|
| python | `>=3.12,<3.13` | runtime |
| fastapi | `>=0.115` | HTTP API |
| uvicorn[standard] | `>=0.32` | ASGI server |
| pydantic, pydantic-settings | `>=2.9` | models and settings |
| sqlalchemy | `>=2.0.36` | ORM and queries |
| alembic | `>=1.14` | migrations |
| psycopg[binary] | `>=3.2` | Postgres driver |
| numpy | `>=2.1` | numeric core |
| pandas | `>=2.2` | bar frames, resampling |
| exchange-calendars | `>=4.5` | trading calendar |
| httpx | `>=0.27` | provider and LLM clients |
| tenacity | `>=9.0` | retries |
| typer | `>=0.13` | CLI |
| structlog | `>=24.4` | logging |
| prometheus-client | `>=0.21` | metrics |
| mcp | current stable | MCP server SDK |
| pyyaml | `>=6.0` | config |
| dev: pytest, pytest-cov, pytest-asyncio, hypothesis, respx, ruff, mypy, pip-audit, testcontainers | current stable | tests and tooling |

Do not add a technical-analysis library (TA-Lib, pandas-ta) as a runtime dependency. The indicators are implemented in-house so the formulas match the specification and TradingView exactly, and so the ARM64 image has no native build surprises. A TA library may be used in tests only, as an independent cross-check.

### 10.22 Dependency versions: TypeScript (ui/package.json)

| Package | Constraint | Purpose |
|---|---|---|
| react, react-dom | `^19` | UI |
| vite | `^6` | build |
| typescript | `^5.6` | language |
| react-router | `^7` | routing |
| @tanstack/react-query | `^5` | server state |
| zustand | `^5` | UI state |
| lightweight-charts | `^5` | financial charts (Apache-2.0, by TradingView) |
| openapi-typescript, openapi-fetch | current stable | generated API client |
| vitest, @testing-library/react, @axe-core/playwright, @playwright/test, eslint | current stable | tests and lint |

`integrations/pi`: `pi-agent-core` and `@sinclair/typebox`, current stable; confirm package names at implementation time.

### 10.23 Dependency versions: Infrastructure

| Component | Version |
|---|---|
| PostgreSQL | 17 |
| Helm | 3.16 or later |
| kind node image | match the Stoke k3s minor version found in the inventory |
| Flux | the version running on Stoke |


---

## 11. Observability

### 11.1 Metrics

All metrics are exposed at `GET /metrics` on the API (port 8080). Run-side metrics come from Postgres through a custom collector (ADR-023); HTTP metrics are in-process. No label carries a ticker, a run ID, a user value, or a secret. "Source" says where the value comes from.

| Metric | Type | Labels | Source | Meaning |
|---|---|---|---|---|
| `supertrends_run_duration_seconds` | gauge | none | DB: last finished run | `finished_at - started_at` of the most recent published or failed run |
| `supertrends_run_state_total` | counter | `state` (8 values) | DB `metric_counters` | state transitions entered |
| `supertrends_tickers_scored` | gauge | none | DB: latest published run | tickers with `status = 'scored'` |
| `supertrends_tickers_excluded` | gauge | `reason` (`stale`, `insufficient_history`, `no_data`, `unresolved`) | DB: latest published run | excluded tickers by reason |
| `supertrends_data_freshness_seconds` | gauge | none | DB | seconds between the close of the last completed session and now if the latest stored benchmark bar is older than that session, else 0 |
| `supertrends_provider_requests_total` | counter | `provider`, `status` (`2xx`, `4xx`, `429`, `5xx`, `timeout`, `error`, `cache`) | DB `metric_counters` | outbound provider calls |
| `supertrends_provider_rate_limited_total` | counter | `provider` | DB `metric_counters` | 429 responses and local token-bucket waits that exceeded 1 s |
| `supertrends_narrative_total` | counter | `source` (`llm`, `template`), `result` (`accepted`, `rejected`, `timeout`, `error`, `fallback`) | DB `metric_counters` | narrative attempts and outcomes |
| `supertrends_narrative_tokens` | gauge | `kind` (`prompt`, `completion`) | DB: latest published run | max per-pick tokens in the latest run (budget 900 / 220) |
| `supertrends_picks_published` | gauge | `side` (`buy`, `sell`) | DB: latest published run | picks in the latest published run |
| `supertrends_run_narrative_fallback_ratio` | gauge | none | DB: latest published run | template narratives divided by picks (0 when no picks) |
| `supertrends_last_published_run_timestamp_seconds` | gauge | none | DB | `published_at` of the latest current run, Unix seconds |
| `supertrends_publication_overdue` | gauge | none | DB plus calendar | 1 when the last completed session has no published run and the time in America/New_York is past `SUPERTRENDS_PUBLICATION_DEADLINE` (default `19:00`) on that session's date or later, else 0 |
| `supertrends_build_info` | gauge (always 1) | `version`, `commit` | process | build identity |
| `supertrends_http_requests_total` | counter | `method`, `route` (route template), `status` | process | HTTP requests |
| `supertrends_http_request_duration_seconds` | histogram | `method`, `route` | process | buckets 0.005 to 2.5 s |

The collector runs at most one set of database queries per scrape, cached for 10 s, with a 2 s statement timeout; a database error yields `supertrends_collector_errors_total` (counter, no labels) and omits the database-sourced series rather than failing the scrape.

### 11.2 Logs

JSON lines on stdout via structlog. Required fields on every line: `ts` (RFC 3339 UTC), `level`, `event` (snake_case message key), `logger`, `version`, `env`. Context fields when applicable: `request_id`, `method`, `route`, `status`, `duration_ms` (HTTP); `run_id`, `trade_date`, `state`, `trigger` (runs); `symbol` (per-ticker events, allowed in logs, never in metric labels); `provider`, `endpoint` (template), `attempt`, `retry_after` (providers); `narrative_source`, `tokens_in`, `tokens_out`, `rejection_reason` (narratives); `error_code`, `exc_type` (errors; stack traces only at `debug`). The redaction processor removes values of keys matching `(?i)(token|api[_-]?key|password|secret|authorization|database_url)` and masks bearer strings in any value; a unit test asserts no configured secret appears in captured logs. Levels: `debug` dev, `info` stage and prod.

Key events: `run_transition`, `run_published`, `run_failed`, `ticker_excluded`, `provider_call`, `provider_rate_limited`, `narrative_rejected`, `narrative_fallback`, `split_detected_refetch`, `retention_pruned`, `http_request`, `auth_failed`, `host_rejected`.

### 11.3 Dashboard

`deploy/dashboards/supertrends.json` (Grafana, schema version current at implementation, datasource as a variable `${DS_PROMETHEUS}`), shipped as a ConfigMap with label `grafana_dashboard: "1"` when `metrics.dashboard.enabled`. Rows and panels:

1. **Today:** last published time, publication overdue (stat, red at 1), picks published by side, tickers scored and excluded, data freshness.
2. **Runs:** run duration (time series), run state transitions rate by state, failed runs in 7 days.
3. **Providers:** request rate by provider and status, error ratio, rate-limited total.
4. **Narrative:** narrative results by source and result, fallback ratio, prompt and completion tokens versus budget lines (900, 220).
5. **API:** request rate by route and status, p50 / p95 latency (NFR-004 target line at 200 ms), build info.

Series sourced from the database use `max by (...)` so several API replicas do not double count.

### 11.4 Alerts (`prometheusrule.yaml`)

| Alert | Expression (shape) | For | Severity |
|---|---|---|---|
| `SuperTrendsNoPublishedRun` | `max(supertrends_publication_overdue) == 1` | 5m | warning |
| `SuperTrendsDataStale` | `max(supertrends_data_freshness_seconds) > 0` and `max(supertrends_publication_overdue) == 1` | 15m | warning |
| `SuperTrendsProviderErrorRate` | `sum(rate(supertrends_provider_requests_total{status=~"5xx|timeout|error|429"}[15m])) / sum(rate(supertrends_provider_requests_total{status!="cache"}[15m])) > 0.2` | 15m | warning |
| `SuperTrendsNarrativeFallbackHigh` | `max(supertrends_run_narrative_fallback_ratio) > 0.5` | 0m | info |
| `SuperTrendsRunFailed` | `increase(max(supertrends_run_state_total{state="failed"})[1h:]) > 0` | 0m | warning |
| `SuperTrendsMetricsCollectorErrors` | `increase(supertrends_collector_errors_total[15m]) > 0` | 15m | info |

The provider error-rate alert uses counters, which are monotonic across pods because they are stored in Postgres. Rules are checked by `promtool check rules` in CI. Alerts carry `summary` and `runbook_url` annotations pointing to sections of `docs/RUNBOOK.md`.

---

## 12. Repository Structure

Seeded from BUILD_PROMPT Appendix B. The top-level directory is the clone of `mohnishbasha/stokeai-trading-supertrends` (ADR-017). Items marked `(+)` are added by this document's ADRs or contracts.

```
stokeai-trading-supertrends/
  BUILD_PROMPT.md
  VERSION
  Makefile
  Dockerfile
  pyproject.toml
  uv.lock
  alembic.ini
  README.md  CHANGELOG.md  LICENSE  COPYRIGHT  COMMERCIAL.md  CLA.md  DISCLAIMER.md  THIRD_PARTY_LICENSES.md
  CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md
  private/                                            # git-ignored: Stoke inventory and cluster values
  AGENTS.md  CLAUDE.md  SKILLS.md  SOUL.md
  .gitignore  .python-version  .nvmrc  .coverage-thresholds.toml  .env.example
  runner.mk  run-supertrends.sh  run-supertrends-status.sh        # operator files, do not edit
  .agent/skills/
    run-tests/      SKILL.md  run.sh
    check-types/    SKILL.md  run.sh
    daily-brief/    SKILL.md  run.sh
  .github/
    workflows/      ci.yml  kind-e2e.yml  release.yml  release-images.yml  release-chart.yml
                    harness-smoke.yml  flux-validate.yml  nightly.yml
    ISSUE_TEMPLATE/ task.md  bug_report.md
    pull_request_template.md  dependabot.yml
  config/
    scoring.yaml
    watchlist.seed.yaml
  docs/
    PRD.md  ARCHITECTURE.md  DESIGN.md  SPRINT_PLAN.md  TEST_PLAN.md
    RETROSPECTIVES.md  OWNER_CHECKLIST.md  GATE_DEBT.md  DEPLOYMENT.md
    USER_GUIDE.md  RUNBOOK.md  SECURITY_REVIEW.md  PERFORMANCE.md  NARRATIVE_EVAL.md
    openapi.json
    schemas/        evidence.schema.json  scoring.schema.json  mcp-tools.schema.json   (+)
    adr/
  migrations/
    env.py  script.py.mako  versions/                                   (+ layout)
  src/supertrends/
    __init__.py  version.py  settings.py  errors.py  logging.py
    indicators/     primitives.py  supertrend.py  trend.py  momentum.py  divergence.py
                    meanrev.py  volatility.py  fibonacci.py  levels.py  volume.py  flow.py  registry.py
    scoring/        factor.py  factors/ (one module per factor)  regime.py  weights.py
                    composite.py  confidence.py  config.py
    selection/      candidates.py  ranking.py  correlation.py
    narrative/      evidence.py  template.py  llm.py  guard.py  prompts/
                    mock_server.py  (+ supertrends-llm-mock, dev and kind only)
    data/           models.py  repo.py  ingest.py  calendar.py  quality.py  retention.py (+)
                    providers/  base.py  fixture.py  massive.py  alternate.py  registry.py
    runs/           orchestrator.py  state.py  publish.py  worker.py (+)  reaper.py (+)
    trackrecord/    outcomes.py  stats.py  backtest.py
    api/            app.py  deps.py  routes/  schemas.py  security.py  static.py
                    services.py (+ shared service functions, section 2)  problems.py (+)
    mcp/            server.py  tools.py
    cli/            main.py  commands/
    observability/  metrics.py  collector.py (+ ADR-023)
  ui/
    package.json  vite.config.ts  tsconfig.json  index.html
    src/  main.tsx  routes/  components/  store/  lib/  api/ (generated)  styles/tokens.css
    tests/  e2e/
  integrations/
    pi/  goose/  opencode/  claude-code/
  deploy/
    compose/   docker-compose.dev.yml  docker-compose.local.yml  docker-compose.prod.yml
               docker-compose.demo.yml (+ named in Path 2)
    helm/stokeai-supertrends/
    flux/      base/  overlays/stage/  overlays/prod/
    kind/      cluster.yaml
    systemd/   supertrends.service  supertrends-daily.timer
    dashboards/ supertrends.json
  scripts/
    check-prereqs.sh  check-versions.sh  version-sync.sh  extract-changelog.sh
    check_coverage.py  gen-third-party-licenses.sh  stoke-inventory.sh  validate-fixtures.sh  install.sh
    demo_verify.py (+ named in Path 2)  narrative_eval.py (+ S5-T03)  check_scoring_version.py (+ S5-T07)
  tests/
    unit/  integration/  smoke/  regression/  golden/  narrative_eval/  fixtures/
    contract/ (+ provider contract suites and API contract tests)
```

Rules: `private/`, `logs/`, `.env`, `demo-report/`, `dist/`, and `ui/dist/` are git-ignored. Every source file carries the SPDX and copyright header. Import boundaries from section 2 are enforced by an import-linter contract in `pyproject.toml`.

---

## 13. Configuration

Three layers: the scoring config (`config/scoring.yaml`, versioned and hashed), environment settings (`SUPERTRENDS_*`, pydantic-settings), and Helm values (section 10.6) that render settings and the scoring ConfigMap.

### 13.1 `config/scoring.yaml` (seed, verbatim from BUILD_PROMPT Appendix E)

```yaml
scoring:
  version: 1
min_history_bars: 250
liquidity:
  min_avg_dollar_volume_20d: 20000000
supertrend:
  atr_length: 10
  factor: 3.0
  fresh_flip_bars: 5
  stretch_atr: 4.0
sma:
  periods: [20, 50, 200]
  slope_bars: 5
  cross_lookback: 10
macd:
  fast: 12
  slow: 26
  signal: 9
  cross_lookback: 3
  weekly_disagree_multiplier: 0.75
divergence:
  pivot_width_daily: 5
  pivot_width_weekly: 3
  window_bars: 60
  recency_bars: 15
  points: { rsi: 40, macd_hist: 35, obv: 25 }
  hidden_multiplier: 0.5
  weekly_confirm_multiplier: 1.25
mean_reversion:
  window: 20
  z_cap: 2.5
  rsi_length: 14
  rsi_low: 30
  rsi_high: 70
fibonacci:
  lookback_bars: 120
  min_reversal_pct: 0.08
  min_reversal_atr: 3.0
  near_atr: 0.5
levels:
  lookback_bars: 250
  pivot_width: 5
  cluster_atr: 0.5
  breakout_rel_volume: 1.5
volatility:
  atr_length: 14
  bb_length: 20
  bb_mult: 2.0
  squeeze_rank: 15
  expansion_rank: 85
  extreme_atr_rank: 90
volume:
  osc_short: 5
  osc_long: 10
  obv_slope_bars: 20
flow:
  intraday_timeframe: 5m
  window_sessions: 10
  min_sessions_for_intraday: 8
  cmf_length: 20
  daily_estimate_weight_multiplier: 0.6
fundamentals:
  stale_days: 120
  stale_weight_multiplier: 0.5
weights:
  supertrend: 20
  sma: 10
  macd: 10
  divergence: 10
  mean_reversion: 8
  fibonacci: 6
  levels: 8
  volatility: 5
  volume_osc: 6
  flow: 9
  fundamentals: 8
regime:
  adx_length: 14
  trending_min: 25
  ranging_max: 20
  multipliers:
    trending:     { supertrend: 1.25, sma: 1.20, macd: 1.10, divergence: 0.90, mean_reversion: 0.50, fibonacci: 1.00, levels: 0.90 }
    ranging:      { supertrend: 0.70, sma: 0.70, macd: 0.90, divergence: 1.20, mean_reversion: 1.60, fibonacci: 1.10, levels: 1.40 }
    transitional: {}
events:
  earnings_window_days: 5
  earnings_fundamentals_multiplier: 1.5
thresholds:
  buy_display_min: 65
  sell_display_max: 35
  min_confidence: 50
  weak_fundamentals_score: -40
  strong_fundamentals_score: 40
  fundamentals_threshold_shift: 5
  market_regime_threshold_shift: 5
selection:
  max_buys: 3
  max_sells: 2
  correlation_window: 60
  correlation_max: 0.9
benchmarks: [SPY, QQQ]
track_record:
  horizons_days: [1, 5, 10, 20]
  small_sample: 20
```

### 13.2 Scoring config schema rules

The pydantic model `scoring.config.ScoringConfig` (exported as `docs/schemas/scoring.schema.json` by `supertrends config export-schema`) validates the document. Rules:

- Unknown keys at any level are rejected (`extra = "forbid"`). Every key in the seed is required; there are no silent defaults in code for values that the file defines (exception: omitted regime multipliers, below).
- `scoring.version` is an integer >= 1.
- `weights` has exactly the eleven factor IDs `supertrend`, `sma`, `macd`, `divergence`, `mean_reversion`, `fibonacci`, `levels`, `volatility`, `volume_osc`, `flow`, `fundamentals`; each weight is a number >= 0; the sum must equal 100 (tolerance 1e-9). Every weight key maps to a registered factor and every registered factor has a weight (S3-T01).
- `regime.multipliers` has exactly the three regimes `trending`, `ranging`, `transitional`; each maps a subset of the eleven factor IDs to a multiplier > 0. A factor omitted from a regime has multiplier 1.00, which matches the specification table (the seed lists only the cells that differ from 1.00, and `transitional: {}`). This is the one documented default; it is applied by the model, so it is part of the validated document and of the hash (ADR-037).
- Periods and lengths are positive integers; `regime.ranging_max <= regime.trending_min`; `thresholds.sell_display_max < thresholds.buy_display_min`; display thresholds are within 0..100; `min_confidence` within 0..100; `selection.max_buys` and `max_sells` are integers 0..10; `correlation_max` within (0, 1]; `track_record.horizons_days` is a non-empty ascending list of positive integers.
- `benchmarks` contains SPY and QQQ (the market regime rule is defined on both).
- `supertrends config validate [PATH]` prints `valid sha256:<hash>` or the list of errors and exits 2. The API and jobs refuse to start with an invalid config.

### 13.3 `config_hash`

```
config_hash = "sha256:" + sha256( canonical_json( validated_document ) ).hexdigest()
canonical_json = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
```

- Computed over the validated document after parsing YAML (comments, key order, and formatting do not change the hash), with numbers normalized by the pydantic model (`3` and `3.0` for a float field hash the same). `scoring.version` is part of the document and therefore of the hash (ADR-026).
- Each distinct hash is inserted into `config_versions` with the full document the first time it is used by a run or backtest.
- Every run, factor result (through `runs.config_hash`), recommendation evidence document, and backtest records the hash.
- CI check `scripts/check_scoring_version.py`: if the hash of `config/scoring.yaml` on the PR differs from `develop` and `scoring.version` did not increase, the check fails (S5-T07). Golden factor fixture changes without a version bump also fail (ADR-026).
- The active config source: `SUPERTRENDS_SCORING_CONFIG` path; on Kubernetes the chart renders `scoring.config` values into a ConfigMap mounted read-only at `/etc/supertrends/scoring.yaml` when non-empty, else the image default `/app/config/scoring.yaml` is used.

### 13.4 Environment settings

Settings model: `supertrends.settings.Settings` (pydantic-settings), prefix `SUPERTRENDS_`, `.env` loaded only when `SUPERTRENDS_ENV=dev`. Secrets are `SecretStr`. Invalid values fail startup with a message naming the variable.

| Variable | Type | Default | Used by | Notes |
|---|---|---|---|---|
| `SUPERTRENDS_ENV` | `dev`, `ci`, `stage`, `prod` | `dev` | all | |
| `SUPERTRENDS_DATABASE_URL` | secret URL | dev URL in 10.20 | all | `postgresql+psycopg://...` |
| `SUPERTRENDS_MARKET_PROVIDER` | `fixture`, `massive`, `alternate` | `fixture` | jobs, status | |
| `SUPERTRENDS_FUNDAMENTALS_PROVIDER` | `fixture`, `massive` (+ vendor added in S5) | `fixture` | jobs | may differ from market provider |
| `SUPERTRENDS_MASSIVE_API_KEY` | secret | empty | jobs, status | empty means `unconfigured` |
| `SUPERTRENDS_MASSIVE_BASE_URL` | URL | `https://api.massive.com` | jobs | legacy `https://api.polygon.io` accepted |
| `SUPERTRENDS_FUNDAMENTALS_API_KEY` | secret | empty | jobs | only when the fundamentals vendor differs (+) |
| `SUPERTRENDS_ALTERNATE_API_KEY`, `SUPERTRENDS_ALTERNATE_BASE_URL` | secret, URL | empty | jobs | added with S1-T05 (ADR-032) (+) |
| `SUPERTRENDS_PROVIDER_RATE_PER_MIN` | int > 0 | `5` | jobs | per provider |
| `SUPERTRENDS_NARRATIVE_PROVIDER` | `template`, `openai_compatible` | `template` | jobs | |
| `SUPERTRENDS_LLM_BASE_URL` | URL | `http://localhost:8089/v1` | jobs, status | configuration only (SSRF rule) |
| `SUPERTRENDS_LLM_MODEL` | string | `mock` | jobs | |
| `SUPERTRENDS_LLM_API_KEY` | secret | empty | jobs | |
| `SUPERTRENDS_LLM_TIMEOUT_SECONDS` | float > 0 | `8` | jobs | (+) |
| `SUPERTRENDS_API_TOKEN` | secret | `dev-token` in dev only; required in stage and prod | API, CLI remote | startup fails in stage and prod if empty or equal to `dev-token` |
| `SUPERTRENDS_API_URL` | URL | empty | CLI, MCP stdio | remote mode (+) |
| `SUPERTRENDS_SCORING_CONFIG` | path | `config/scoring.yaml` | all | |
| `SUPERTRENDS_RUN_CRON` | cron | `30 17 * * 1-5` | chart, status (`next_scheduled_run`) | America/New_York |
| `SUPERTRENDS_PUBLICATION_DEADLINE` | `HH:MM` | `19:00` | metrics | America/New_York (+) |
| `SUPERTRENDS_WORKER_POLL_SECONDS` | int > 0 | `5` | worker | (+) |
| `SUPERTRENDS_QUEUED_RUN_TIMEOUT_SECONDS` | int > 0 | `600` | worker, API | (+) |
| `SUPERTRENDS_WRITE_RATE_PER_MIN` | int > 0 | `30` | API | (+) |
| `SUPERTRENDS_LOG_LEVEL` | `debug`, `info`, `warning`, `error` | `debug` dev, `info` otherwise | all | |
| `SUPERTRENDS_SOURCE_URL` | URL | `https://github.com/mohnishbasha/stokeai-trading-supertrends` | API, CLI, UI | license link (ADR-017) |
| `SUPERTRENDS_ALLOWED_HOSTS` | comma list | `localhost,127.0.0.1` | API | chart appends Service names (ADR-024) |
| `SUPERTRENDS_BIND` | `HOST:PORT` | `127.0.0.1:8080` | `serve` | `0.0.0.0:8080` in containers |
| `SUPERTRENDS_UI_DIR` | path | `/app/ui/dist` in image, `ui/dist` otherwise | API | (+) |
| `SUPERTRENDS_DEMO` | bool | `0` | all | demo banner; requires fixture provider (+) |
| `SUPERTRENDS_FIXTURE_SEED` | int | `20261114` | fixture provider | ADR-028 (+) |
| `SUPERTRENDS_FIXTURE_END_DATE` | date | last completed session | fixture provider | ADR-028 (+) |
| `SUPERTRENDS_FIXTURE_PERMISSIVE` | bool | `0` | fixture provider | tests only (+) |
| `SUPERTRENDS_VERSION`, `SUPERTRENDS_COMMIT` | string | set by the image build args | version | (+) |

`(+)` marks variables added by this document beyond the BUILD_PROMPT environment table. `.env.example` lists every variable with an empty value or the dev default.

### 13.5 Helm values to settings mapping

| Values key | Setting |
|---|---|
| `env` | `SUPERTRENDS_ENV` |
| `providers.market`, `providers.fundamentals` | `SUPERTRENDS_MARKET_PROVIDER`, `SUPERTRENDS_FUNDAMENTALS_PROVIDER` |
| `providers.massiveBaseUrl`, `providers.ratePerMinute` | `SUPERTRENDS_MASSIVE_BASE_URL`, `SUPERTRENDS_PROVIDER_RATE_PER_MIN` |
| `llm.narrativeProvider`, `llm.baseUrl`, `llm.model`, `llm.timeoutSeconds` | `SUPERTRENDS_NARRATIVE_PROVIDER` (forced to `template` when `baseUrl` is empty), `SUPERTRENDS_LLM_BASE_URL`, `SUPERTRENDS_LLM_MODEL`, `SUPERTRENDS_LLM_TIMEOUT_SECONDS` |
| `secrets.existingSecret` | `envFrom` for the secret variables |
| `dailyRun.schedule`, `dailyRun.timeZone` | CronJob spec and `SUPERTRENDS_RUN_CRON` |
| `worker.pollSeconds`, `worker.queuedRunTimeoutSeconds` | `SUPERTRENDS_WORKER_POLL_SECONDS`, `SUPERTRENDS_QUEUED_RUN_TIMEOUT_SECONDS` |
| `ingress.host` | added to `SUPERTRENDS_ALLOWED_HOSTS` |
| `scoring.config` | ConfigMap and `SUPERTRENDS_SCORING_CONFIG=/etc/supertrends/scoring.yaml` |
| `.Chart.AppVersion`, image build | `SUPERTRENDS_VERSION`, `SUPERTRENDS_COMMIT` (image env) |

---

End of document.
