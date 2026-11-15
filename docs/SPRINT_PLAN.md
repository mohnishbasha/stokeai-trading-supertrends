# Supertrends Sprint Plan

**Version:** 1.0.0
**Date:** 2026-11-14

This plan seeds all 10 sprints of the Supertrends build. Every task has an ID, title, labels, estimate (S / M / L), dependencies, spec references, description, and acceptance criteria. Each sprint ends with a non-blocking checklist, and the plan ends with the Final Gate. Tasks may be added; tasks and checklist items may not be removed.

## How to use this plan

- Each task becomes one GitHub issue titled `[S{n}-T{nn}] {title}` in the milestone named exactly like its sprint (for example "Sprint 0: Scaffold").
- Labels, estimate, dependencies, description, and acceptance criteria are copied into the issue body. Acceptance criteria become the issue checklist.
- The issue-creation script parses this file. Task headings are exactly `### S{n}-T{nn}: {title}`; do not add other `### S` headings.
- Size labels: S is up to half a day, M is about one to two days, L is about three to five days.
- Spec references point to PRD functional requirement groups (Watchlist FR-0xx, Ingestion FR-1xx, Indicators FR-2xx, Scoring FR-3xx, Selection FR-4xx, Justification FR-5xx, Track record and backtest FR-6xx, UI FR-7xx, API/CLI/MCP FR-8xx, Operations FR-9xx), NFR IDs, ARCHITECTURE section numbers, and TEST_PLAN feature areas.
- At each sprint end, tick the sprint checklist boxes that pass. Log each unmet item in `docs/GATE_DEBT.md` and carry on.

## Sprint Start Protocol

1. Move all sprint issues from Backlog to In Progress on the project board.
2. Assign issues to yourself.
3. Pull latest `develop` and verify it is up to date with `staging`.
4. Pick the highest-priority unblocked issue.
5. Read the relevant PRD, ARCHITECTURE, and TEST_PLAN sections before writing code.
6. Add test scenarios for this feature to `docs/TEST_PLAN.md` before writing code.
7. Create a branch: `git checkout -b feature/s{n}-t{nn}-{short-slug} develop`.
8. Write failing tests first (TDD) and confirm they fail for the right reason.
9. Implement until tests pass.
10. Update `docs/TEST_PLAN.md` to mark new scenarios as Automated.
11. Update the relevant spec doc in the same branch if behavior changed.
12. Open a PR against `develop`. The PR description must state which spec sections were updated.
13. Wait for CI (lint, type-check, unit, integration, coverage threshold).
14. Merge.
15. Add the implementation comment and close the issue.
16. Pick the next issue.

## Spec Change Protocol

Any PR that changes user-facing behavior, API contracts, database schema, scoring rules, or architectural decisions must satisfy one of:

- **A, no spec change:** the PR description explicitly states "internal only, no spec change".
- **B, spec updated in same PR:** the relevant `docs/` file is updated alongside the code.
- **C, spec issue filed:** a separate GitHub issue is created before the code PR merges, scheduled in the current sprint, and closed within the same sprint.

Option C is not a deferral mechanism. Any change to a scoring formula, weight, or threshold is always option B and also bumps `scoring.version` in `config/scoring.yaml`.

## Test Scenario Generation Protocol

1. Open `docs/TEST_PLAN.md` and add scenarios for the feature before writing code.
2. Use the naming convention: `{type}_{module}_{operation}_{scenario}_{outcome}`.
3. Mark new scenarios as Deferred until the test is written, then Automated.
4. Scenarios too hard to automate: Skipped, with a written reason and a manual step.
5. The test file must have a test for every Automated scenario when the feature PR merges.

## Sprint End Protocol

1. All sprint issues closed, or moved to the next sprint with an explanation.
2. Run the sprint checklist and check each box that passes in `docs/SPRINT_PLAN.md`. Log each unmet item in `docs/GATE_DEBT.md` and carry on; do not stop. In the last sprint this step is the Final Gate and every item, including all earlier debt, must be green.
3. Spec doc audit: review all five docs for stale sections and update before proceeding.
4. Coverage check: `make coverage`, confirm it meets `.coverage-thresholds.toml`.
5. Merge `develop` into `staging` via PR.
6. Run the manual smoke checklist from `docs/TEST_PLAN.md` against the staging build (`make up && make smoke`; from Sprint 8 on, also against the Stoke staging namespace).
7. Document the sprint retrospective in `docs/RETROSPECTIVES.md`: what was built (links to closed issues), spec sections updated, tests added (counts by type), coverage delta, what worked, what did not, what to change.
8. Tag the staging build and push the tag. The runner depends on this exact tag name: `git tag sprint-{n}-complete && git push origin sprint-{n}-complete`.

## Definition of Done

A task is done when:

- Code implemented; `make build` succeeds.
- Unit tests written first and passing.
- `make check` exits 0 (ruff, ruff format check, mypy strict, eslint, tsc, with 0 warnings).
- Coverage has not dropped below thresholds.
- PR opened against `develop` with the issue linked.
- CI green.
- Spec doc changes committed in the same PR (or option A / C confirmed).
- New test scenarios added to TEST_PLAN.md.
- Implementation comment added to the issue before closing.

### Coverage thresholds

```toml
# .coverage-thresholds.toml
[python]
"src/supertrends/indicators" = 95
"src/supertrends/scoring" = 92
"src/supertrends/selection" = 92
"src/supertrends/data" = 85
"src/supertrends/narrative" = 85
"src/supertrends/api" = 85
"src/supertrends/mcp" = 80
"src/supertrends/cli" = 80

[typescript]
"ui/src/components" = 75
"ui/src/store" = 85
"ui/src/lib" = 85
"integrations/pi/src" = 70
```

Indicator and scoring thresholds are high on purpose: a silent math error here produces confident wrong picks.

## Sprint Overview

| Sprint | Name | Duration | Goal |
|---|---|---|---|
| 0 | Scaffold | 1 week | Tooling, CI, empty shell, image skeleton, agent files |
| 1 | Data Layer | 1 week | Providers, storage, watchlist, ingestion |
| 2 | Indicator Engine | 1 week | Every indicator, golden-tested, no look-ahead |
| 3 | Scoring and Daily Picks | 2 weeks | The core feature: factors, composite, selection, daily run, API. First real image and chart |
| 4 | UI | 1 week | Design system and all screens on real data |
| 5 | Justification and Dynamic Weights | 1 week | Narratives, fundamentals overlay, regimes |
| 6 | Track Record and Backtest | 1 week | Outcomes, statistics, replay |
| 7 | CLI, MCP, Harnesses | 1 week | `supertrends` CLI, MCP server, Pi, Goose, OpenCode |
| 8 | Packaging and Stoke Deploy | 1 week | Full chart, OCI chart, Flux, staging on Stoke, deployment docs |
| 9 | Release v1.0.0 | 1 week | Hardening, QA, signed multi-arch release, production by digest |

---

## Sprint 0: Scaffold

**Milestone:** Sprint 0: Scaffold
**Duration:** 1 week
**Goal:** a repository where `make setup && make build && make check` passes on a clean clone, CI is green, and an empty image builds for both architectures.

### S0-T01: Repository layout and Python project

- **Labels:** `type:chore` `area:ci` `priority:p0` `size:M` `sprint:0`
- **Estimate:** M
- **Dependencies:** none
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 12 Repository Structure, section 10 Build and Deployment; TEST_PLAN: Build and tooling scenarios

**Description:**
Create the tree in Appendix B. `pyproject.toml` with uv, package `supertrends` under `src/`, Python 3.12, ruff, mypy strict, pytest, pytest-cov, hypothesis. A `supertrends` console entry point that prints version and commit.

**Acceptance criteria:**
- [x] `uv sync --locked` works on a clean clone
- [x] `supertrends --version` prints `supertrends {VERSION} ({commit})`
- [x] `mypy --strict src` passes on the empty package

### S0-T02: UI project

- **Labels:** `type:chore` `area:ui` `priority:p0` `size:S` `sprint:0`
- **Estimate:** S
- **Dependencies:** none
- **Spec references:** PRD: UI FR-7xx; ARCHITECTURE: section 12 Repository Structure, section 10 Build and Deployment; TEST_PLAN: UI scenarios

**Description:**
`ui/` with Vite, React, TypeScript strict, ESLint, Vitest, Playwright installed. A single placeholder route.

**Acceptance criteria:**
- [x] `npm --prefix ui ci && npm --prefix ui run build` produces `ui/dist`
- [x] `npm --prefix ui run lint` and `type-check` exit 0 with 0 warnings

### S0-T03: Root Makefile

- **Labels:** `type:chore` `area:ci` `priority:p0` `size:M` `sprint:0`
- **Estimate:** M
- **Dependencies:** S0-T01, S0-T02
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment; TEST_PLAN: Build and tooling scenarios

**Description:**
Create the root `Makefile` exactly as specified in Build and Deployment, with `make help`. Targets that depend on later sprints exist now and print "not available until Sprint N" with exit 0.

**Acceptance criteria:**
- [x] `make help` lists every required target
- [x] `make setup`, `make build`, `make check` pass on a clean clone

### S0-T04: Version source of truth and scripts

- **Labels:** `type:chore` `area:ci` `priority:p0` `size:S` `sprint:0`
- **Estimate:** S
- **Dependencies:** S0-T01, S0-T02
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment (Versioning); TEST_PLAN: Build and tooling scenarios

**Description:**
Root `VERSION` file containing `0.1.0`. `scripts/check-versions.sh`, `scripts/extract-changelog.sh`, `CHANGELOG.md` with an `[Unreleased]` section. See Versioning.

**Acceptance criteria:**
- [x] `scripts/check-versions.sh` exits 0
- [x] changing `ui/package.json` version alone makes it exit 1 naming that file

### S0-T05: CI pipeline

- **Labels:** `type:chore` `area:ci` `priority:p0` `size:M` `sprint:0`
- **Estimate:** M
- **Dependencies:** S0-T03
- **Spec references:** PRD: Operations FR-9xx; NFR: security and supply chain; ARCHITECTURE: section 10 Build and Deployment, section 9 Security Model; TEST_PLAN: CI scenarios

**Description:**
`.github/workflows/ci.yml` with jobs `lint-and-typecheck`, `unit-tests`, `coverage`, `integration-tests` (Postgres service container), `e2e-tests` (placeholder until Sprint 4), `build-image` (buildx, amd64 and arm64, no push on PRs). Dependabot for pip, npm, GitHub Actions, and Docker. `pip-audit` and `npm audit --audit-level=high` in CI.

**Acceptance criteria:**
- [x] CI is green on `develop`
- [x] a PR with a lint error fails `lint-and-typecheck`
- [x] the image job builds both architectures

### S0-T06: Dockerfile skeleton and Compose

- **Labels:** `type:chore` `area:deploy` `priority:p0` `size:M` `sprint:0`
- **Estimate:** M
- **Dependencies:** S0-T03
- **Spec references:** PRD: Operations FR-9xx; NFR: container hardening; ARCHITECTURE: section 10 Build and Deployment, section 9 Security Model; TEST_PLAN: Deployment and smoke scenarios

**Description:**
Multi-stage `Dockerfile` in the shape given in Build and Deployment, building the placeholder UI and the empty API. `deploy/compose/docker-compose.local.yml` with Postgres and the app.

**Acceptance criteria:**
- [x] `make image` builds
- [x] the container runs as non-root with a read-only root filesystem
- [x] `make up` then `curl -fsS localhost:8080/healthz` returns `{"status":"ok"}`
- [x] `make down` cleans up

### S0-T07: Agent harness files

- **Labels:** `type:docs` `area:ci` `priority:p1` `size:M` `sprint:0`
- **Estimate:** M
- **Dependencies:** S0-T03
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 12 Repository Structure; TEST_PLAN: Build and tooling scenarios

**Description:**
Generate `.gitignore`, `AGENTS.md`, `CLAUDE.md`, `SKILLS.md`, `SOUL.md`, `.agent/skills/run-tests/` and `.agent/skills/check-types/` (each with `SKILL.md` and `run.sh`), per Appendix J. `.gitignore` includes `logs/`.

**Acceptance criteria:**
- [x] each file contains every required section
- [x] both skill `run.sh` scripts exit 0
- [x] `runner.mk`, `run-supertrends.sh`, `run-supertrends-status.sh` are untouched and not ignored

### S0-T08: License and community files

- **Labels:** `type:docs` `area:ci` `priority:p1` `size:S` `sprint:0`
- **Estimate:** S
- **Dependencies:** S0-T01, S0-T02
- **Spec references:** PRD: Operations FR-9xx; NFR: licensing and compliance; ARCHITECTURE: section 9 Security Model, section 12 Repository Structure; TEST_PLAN: CI scenarios

**Description:**
`LICENSE` (the unmodified PolyForm Noncommercial License 1.0.0 text, fetched from polyformproject.org, never retyped or edited, preceded only by the line "Required Notice: Copyright 2026 Serverless Ventures LLC (https://serverlessvc.com)"), `COPYRIGHT` (Copyright 2026 Serverless Ventures LLC, a Delaware limited liability company formed on November 26, 2024; the copyright year is the year this software was first published, 2026, not the formation year; all rights reserved except as granted in LICENSE; noncommercial use only; commercial licenses from legal@serverlessvc.com), `COMMERCIAL.md` (plain-language summary: what counts as noncommercial, examples of commercial use that need a license, how to ask for one; states that commercial licenses are governed by Delaware law and that LICENSE controls if the two differ), `CLA.md` (governed by Delaware law; names the company as "Serverless Ventures LLC, a Delaware limited liability company formed on November 26, 2024"; individual contributor license agreement granting Serverless Ventures LLC the right to relicense; base it on a standard template such as the Apache ICLA adapted for this project and flag it in the owner checklist for legal review), a CLA check in CI, SPDX headers on every source file with `scripts/check-spdx.sh`, `CONTRIBUTING.md` (dev setup, TDD and spec rules, Conventional Commits, CLA requirement), `CODE_OF_CONDUCT.md` (Contributor Covenant), `SECURITY.md` (private vulnerability reporting through GitHub Security Advisories, contact legal@serverlessvc.com), `THIRD_PARTY_LICENSES.md` generated by `scripts/gen-third-party-licenses.sh` from the Python and npm lock files, `DISCLAIMER.md` with the text from Security Guidelines.

**Acceptance criteria:**
- [x] files exist
- [x] the license script runs in CI and fails if a dependency has a license outside the allowlist (MIT, BSD, Apache-2.0, ISC, PSF, MPL-2.0, and LGPL for unmodified libraries such as psycopg), and fails on GPL, AGPL, SSPL, or unknown, because strong-copyleft dependencies cannot be combined with a noncommercial license
- [x] `scripts/check-spdx.sh` fails on a source file without the SPDX header
- [ ] a PR from a non-owner account without a signed CLA is blocked (not met: the `cla` check fails such a PR but is not yet a required status check; owner checklist #18 and #19, docs/GATE_DEBT.md GD-001)

### S0-T09: Config and settings skeleton

- **Labels:** `type:feature` `area:scoring` `priority:p1` `size:S` `sprint:0`
- **Estimate:** S
- **Dependencies:** S0-T01
- **Spec references:** PRD: Scoring FR-3xx; ARCHITECTURE: section 13 Configuration, section 3 Decision Log; TEST_PLAN: Scoring configuration scenarios

**Description:**
`config/scoring.yaml` with every default from the Signal Engine Specification, a pydantic settings model, a JSON schema export, and a `config_hash` function (sha256 of the canonical JSON).

**Acceptance criteria:**
- [x] loading the default file succeeds
- [x] an unknown key or out-of-range weight fails with a message naming the key
- [x] the hash is stable across key order

### S0-T10: Stoke inventory script

- **Labels:** `type:chore` `area:deploy` `priority:p1` `size:S` `sprint:0`
- **Estimate:** S
- **Dependencies:** S0-T03
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment (Stoke profile), section 9 Security Model; TEST_PLAN: Deployment and smoke scenarios

**Description:**
`scripts/stoke-inventory.sh` that, given a kubeconfig, writes `private/STOKE_INVENTORY.md` (git-ignored: it describes a real cluster and must never be committed to this public repository) classifying each dependency as REUSE, UPGRADE, INSTALL, or NOT NEEDED (see Build and Deployment, Stoke profile). It is read-only: `kubectl get` and `flux get` only.

**Acceptance criteria:**
- [x] with no kubeconfig it writes the table with every row "UNKNOWN: run against the cluster" and exits 0
- [x] `shellcheck` passes
- [x] the owner checklist has an entry asking the owner to run it

### Sprint 0 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

- [x] `make setup && make build && make check` pass on a clean clone (proven in CI)
- [x] CI green on `develop` and `staging`
- [x] Image builds for `linux/amd64` and `linux/arm64` in CI
- [x] `make up`, `/healthz`, `make down` work
- [x] All agent harness files and legal files present
- [x] `scripts/check-versions.sh` passes
- [x] Five spec docs audited and current
- [x] Retrospective written; tag `sprint-0-complete` pushed

Checklist run 2026-11-15. All eight items pass. One task-level criterion is unmet and is logged in `docs/GATE_DEBT.md` (GD-001: S0-T08 CLA check not yet merge-blocking).

---

## Sprint 1: Data Layer

**Milestone:** Sprint 1: Data Layer
**Duration:** 1 week
**Goal:** bars and fundamentals for a watchlist land in Postgres, correctly adjusted, with quality flags, from a pluggable provider.

### S1-T01: Database schema and migrations

- **Labels:** `type:feature` `area:data` `priority:p0` `size:M` `sprint:1`
- **Estimate:** M
- **Dependencies:** S0-T01
- **Spec references:** PRD: Ingestion FR-1xx; ARCHITECTURE: section 5 Database Schema; TEST_PLAN: Data layer and schema scenarios

**Description:**
SQLAlchemy 2 models and Alembic migrations for: `tickers`, `watchlists`, `watchlist_items`, `bars_daily`, `bars_intraday`, `fundamentals`, `earnings_calendar`, `runs`, `indicator_snapshots`, `factor_scores`, `recommendations`, `narratives`, `outcomes`, `config_versions`, `provider_calls`. Composite primary keys on (ticker, ts) for bars. `recommendations` and `factor_scores` are append-only (enforced by a trigger that rejects UPDATE and DELETE).

**Acceptance criteria:**
- [x] `alembic upgrade head` and `downgrade base` both succeed on an empty database (#118)
- [x] the append-only trigger rejects an UPDATE in an integration test (#118)

### S1-T02: Provider interfaces

- **Labels:** `type:feature` `area:data` `priority:p0` `size:S` `sprint:1`
- **Estimate:** S
- **Dependencies:** S0-T09
- **Spec references:** PRD: Ingestion FR-1xx; ARCHITECTURE: section 7 Provider Interfaces; TEST_PLAN: Provider contract scenarios

**Description:**
`MarketDataProvider` (daily bars, intraday bars, splits and dividends, capability flags `intraday`, `trades`, `adjusted`), `FundamentalsProvider` (quarterly financials, forward estimates if available, earnings dates), both as Protocols with typed results. A registry selects providers from settings.

**Acceptance criteria:**
- [x] a fake provider passes the shared contract test suite (#117)
- [x] an unknown provider name fails at startup with a clear message (#117)

### S1-T03: Fixture provider

- **Labels:** `type:feature` `area:data` `priority:p0` `size:M` `sprint:1`
- **Estimate:** M
- **Dependencies:** S1-T02
- **Spec references:** PRD: Ingestion FR-1xx; ARCHITECTURE: section 7 Provider Interfaces; TEST_PLAN: Provider contract scenarios, Fixture dataset scenarios

**Description:**
A deterministic synthetic generator (seeded geometric Brownian motion with regime switches, gaps, a split, and volume patterns) that produces 3 years of daily and 30 days of 5-minute bars for 12 synthetic tickers plus `SPY` and `QQQ` stand-ins. No vendor data is committed to the repository. This provider powers dev, CI, kind, and the smoke suite.

**Acceptance criteria:**
- [x] same seed produces identical bars (#120)
- [x] the dataset includes at least one trending, one ranging, and one reversing ticker by construction, asserted in tests (#120)

### S1-T04: Massive (formerly Polygon.io) provider

- **Labels:** `type:feature` `area:data` `priority:p0` `size:L` `sprint:1`
- **Estimate:** L
- **Dependencies:** S1-T02
- **Spec references:** PRD: Ingestion FR-1xx; NFR: secrets handling, provider rate limits; ARCHITECTURE: section 7 Provider Interfaces, section 9 Security Model; TEST_PLAN: Provider contract scenarios

**Description:**
REST adapter for daily aggregates, 5-minute aggregates, splits, dividends, and financials. Base URL is configurable (`https://api.massive.com` default; `https://api.polygon.io` is the legacy host). Token-bucket rate limiter with a configurable calls-per-minute (default 5, the free-tier limit; verify the current plan limits at implementation time), exponential backoff with jitter on 429 and 5xx, response caching by (endpoint, params), and every call recorded in `provider_calls`. The seed watchlist has about 200 symbols, so daily updates must use the grouped daily bars endpoint (one call returns the whole market for a date) with per-ticker calls only for backfill, corporate actions, and intraday bars; record in the owner checklist that a paid plan is likely needed for 5-minute bars on 200 symbols. Tests use recorded, scrubbed fixtures; no test calls the network.

**Acceptance criteria:**
- [x] contract tests pass (#121)
- [x] a 429 sequence is retried and succeeds (#121)
- [x] the API key never appears in logs, errors, or `provider_calls` (#121; the key is never part of a `CallRecord`, but no provider writes `provider_calls` rows yet, see GD-007)
- [x] with no key configured the provider reports `unconfigured` and the app still starts on the fixture provider (#121)

### S1-T05: Second provider adapter

- **Labels:** `type:feature` `area:data` `priority:p2` `size:M` `sprint:1`
- **Estimate:** M
- **Dependencies:** S1-T02
- **Spec references:** PRD: Ingestion FR-1xx; ARCHITECTURE: section 7 Provider Interfaces, section 3 Decision Log; TEST_PLAN: Provider contract scenarios

**Description:**
One alternate provider behind the same interface so the product is not tied to a single vendor. Choose between Alpaca Market Data and Tiingo by reading their current docs and terms at implementation time; record the choice as an ADR. Fundamentals may come from a different vendor than bars (for example Financial Modeling Prep); the registry allows mixing.

**Acceptance criteria:**
- [x] contract tests pass with recorded fixtures (#119)
- [x] switching `SUPERTRENDS_MARKET_PROVIDER` changes the active provider with no code change (#119)

### S1-T06: Ingestion service

- **Labels:** `type:feature` `area:data` `priority:p0` `size:L` `sprint:1`
- **Estimate:** L
- **Dependencies:** S1-T01, S1-T03
- **Spec references:** PRD: Ingestion FR-1xx; ARCHITECTURE: section 4 Data Flows, section 5 Database Schema; TEST_PLAN: Ingestion scenarios

**Description:**
`supertrends ingest` and an internal function used by runs: incremental fetch per ticker (from last stored bar), upsert, corporate-action handling (on a new split, refetch the full adjusted history for that ticker), weekly resample, and a data-quality pass that sets `ok`, `degraded`, `stale` (latest daily bar older than the last completed session), or `insufficient_history`. Trading calendar from `exchange_calendars` (XNYS), including half days and holidays.

**Acceptance criteria:**
- [x] re-running ingestion is idempotent (#124)
- [x] a simulated split triggers a full refetch (#124)
- [x] a holiday does not mark tickers stale (#124)
- [x] a ticker with a gap of more than 3 sessions is flagged `degraded` (#124)

### S1-T07: Watchlist service and API

- **Labels:** `type:feature` `area:api` `area:data` `priority:p0` `size:M` `sprint:1`
- **Estimate:** M
- **Dependencies:** S1-T01
- **Spec references:** PRD: Watchlist FR-0xx, API FR-8xx; ARCHITECTURE: section 6.1 HTTP, section 5 Database Schema; TEST_PLAN: Watchlist scenarios

**Description:**
CRUD for one default watchlist plus named groups. Symbol validation against the provider's reference data (or a permissive regex on the fixture provider). Seed on first start: the 14 groups and 200 unique symbols in Appendix L, written to `config/watchlist.seed.yaml`, following the seed rules there (many-to-many group membership, provider validation, `unresolved` and `needs_review` handling, VIX not scored, crypto file kept but not ingested). Hard cap 300 tickers. `SPY` and `QQQ` are always ingested as benchmarks even if removed from the watchlist.

**Acceptance criteria:**
- [x] endpoints in the API contract behave as specified (#123)
- [x] adding ticker 301 returns 422 (#123)
- [x] the seed loads all 14 groups (#123)
- [x] a symbol in three groups is stored once with three memberships (#123)
- [ ] an unresolvable seed symbol is recorded as `unresolved` with a reason and excluded, never substituted. Not met: `000660` fails the `tickers.symbol` CHECK and is reported as "not storable" instead of being stored as `unresolved` (GD-005)
- [x] write endpoints require the bearer token; read endpoints do not (#123)

### S1-T08: API skeleton and observability base

- **Labels:** `type:feature` `area:api` `area:observability` `priority:p1` `size:M` `sprint:1`
- **Estimate:** M
- **Dependencies:** S1-T01
- **Spec references:** PRD: API FR-8xx, Operations FR-9xx; NFR: observability, secrets handling; ARCHITECTURE: section 6.1 HTTP, section 11 Observability, section 9 Security Model; TEST_PLAN: API and observability scenarios

**Description:**
FastAPI app with `/healthz` (process up), `/readyz` (database reachable, migrations at head), `/metrics` (Prometheus), structured JSON logs via structlog with a request ID, and RFC 9457 problem responses. Settings from environment with the `SUPERTRENDS_` prefix.

**Acceptance criteria:**
- [x] `/readyz` returns 503 when the database is down (#122)
- [x] logs are valid JSON lines (#122)
- [x] no log line contains a secret (tested by a log-scrubbing unit test) (#122)

### Sprint 1 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

All eight Sprint 1 tasks are implemented in open PRs #117 to #124 and are waiting on owner merges (docs/OWNER_CHECKLIST.md #21). The criteria ticked above are met on each PR's branch. "Integrated tree" below means a local merge of all eight branches on top of `develop`, made 2026-11-15 to check them together.

- [x] `supertrends ingest` on the fixture provider fills the database; a second run changes nothing (integrated tree: 5,292 daily, 16,380 intraday, and 1 corporate-action row for 7 symbols; the second run wrote 0 rows. Not on `develop` until #124 merges, GD-002)
- [x] Provider contract tests pass for fixture, Massive, and the alternate provider (#120, #121, #119, and the integrated tree)
- [x] Watchlist API works end to end against Postgres in CI (`integration-tests` job green on #123; the PR's red `lint-and-typecheck` is the cross-branch gitleaks finding, GD-011)
- [ ] No test touches the network (CI runs with outbound network blocked for the test step). Partly met: pytest-socket blocks every non-localhost socket in all test runs (#117), but the CI test step has no OS-level outbound block (GD-003)
- [ ] `make up && make smoke` pass. On the integrated tree they pass (3 smoke tests) only with the Compose `migrate` service pushed to #122 (7819b0f). Not run on `develop` or `staging` (GD-004)
- [x] Coverage thresholds met; spec docs audited (integrated tree: 91% line and branch, every per-directory threshold met; audit notes in docs/RETROSPECTIVES.md)
- [ ] Retrospective written; tag `sprint-1-complete` pushed. The retrospective is written; the tag waits on the merges and the `staging` promotion (GD-002)

Checklist run 2026-11-15. Four of seven items pass. One task criterion is unmet (S1-T07 unresolved seed symbols). Each unmet item has an entry in `docs/GATE_DEBT.md`, GD-002 to GD-012.

---

## Sprint 2: Indicator Engine

**Milestone:** Sprint 2: Indicator Engine
**Duration:** 1 week
**Goal:** every indicator in the Signal Engine Specification implemented as pure, vectorized, tested functions with no look-ahead.

All indicator functions live in `src/supertrends/indicators/`, take a pandas DataFrame or numpy arrays, return arrays of the same length with NaN during warm-up, and have no I/O.

### S2-T01: Primitives

- **Labels:** `type:feature` `area:indicators` `priority:p0` `size:M` `sprint:2`
- **Estimate:** M
- **Dependencies:** S1-T03
- **Spec references:** PRD: Indicators FR-2xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Indicators scenarios

**Description:**
`sma`, `ema`, `rma`, `stdev`, `true_range`, `atr`, `rsi`, `obv`, `percentile_rank`, `linreg_slope`, `pivots` (confirmed, width parameter), `zigzag`, `resample_weekly`.

**Acceptance criteria:**
- [ ] each matches a hand-computed fixture to 1e-9
- [ ] `pivots` never marks a pivot fewer than `width` bars from the end

### S2-T02: Supertrend with TradingView parity

- **Labels:** `type:feature` `area:indicators` `priority:p0` `size:L` `sprint:2`
- **Estimate:** L
- **Dependencies:** S2-T01
- **Spec references:** PRD: Indicators FR-2xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Indicators scenarios (Supertrend golden and parity)

**Description:**
Implement Factor 1's formula exactly. Golden fixtures: (a) a hand-computed 40-bar case covering both flip directions and band ratcheting; (b) TradingView parity files. For (b), add an owner checklist entry: export from TradingView, for two tickers on the daily chart, a CSV with OHLCV plus the built-in Supertrend (10, 3) columns, and place them in `tests/golden/tradingview/`. Until they exist the parity test is skipped with a visible reason, and the sprint checklist records that. When present, the test asserts the line matches within 0.01 and the direction matches on every bar after a 100-bar warm-up.

**Acceptance criteria:**
- [ ] hand-computed fixture passes
- [ ] parity test passes or is skipped pending owner files
- [ ] property test: direction is always +1 or -1 after warm-up, and the line is below close when up and above close when down

### S2-T03: Trend and momentum indicators

- **Labels:** `type:feature` `area:indicators` `priority:p0` `size:M` `sprint:2`
- **Estimate:** M
- **Dependencies:** S2-T01
- **Spec references:** PRD: Indicators FR-2xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Indicators scenarios

**Description:**
SMA 20 / 50 / 200 with slope and cross detection, MACD (12, 26, 9) daily and weekly, ADX(14) with +DI and -DI.

**Acceptance criteria:**
- [ ] fixtures match to 1e-6
- [ ] cross detection reports the bar index of the cross

### S2-T04: Divergence detector

- **Labels:** `type:feature` `area:indicators` `priority:p0` `size:L` `sprint:2`
- **Estimate:** L
- **Dependencies:** S2-T01
- **Spec references:** PRD: Indicators FR-2xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Indicators scenarios (divergence)

**Description:**
Regular and hidden, bullish and bearish, for RSI, MACD histogram, and OBV, on daily and weekly, using confirmed pivots only. Returns typed divergence records with both pivot bars, prices, and oscillator values.

**Acceptance criteria:**
- [ ] constructed fixtures for each of the four types are detected
- [ ] a divergence whose second pivot is not yet confirmed is not reported
- [ ] no false detection on a monotonic series

### S2-T05: Mean reversion and volatility indicators

- **Labels:** `type:feature` `area:indicators` `priority:p0` `size:M` `sprint:2`
- **Estimate:** M
- **Dependencies:** S2-T01
- **Spec references:** PRD: Indicators FR-2xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Indicators scenarios

**Description:**
Bollinger (20, 2), %B, bandwidth and its percentile rank, z-score, ATR%, ATR% rank, HV20, squeeze and expansion flags.

**Acceptance criteria:**
- [ ] fixtures match
- [ ] rank functions use only trailing windows

### S2-T06: Fibonacci and support / resistance

- **Labels:** `type:feature` `area:indicators` `priority:p0` `size:L` `sprint:2`
- **Estimate:** L
- **Dependencies:** S2-T01
- **Spec references:** PRD: Indicators FR-2xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Indicators scenarios (Fibonacci, support and resistance)

**Description:**
ZigZag leg selection, retracement and extension levels, level clustering with strength, nearest support and resistance, breakout and breakdown detection, 52-week high and low.

**Acceptance criteria:**
- [ ] on a constructed up-leg-then-pullback fixture, the 61.8 level is within 1e-6 of the expected price
- [ ] clusters merge pivots within 0.5 ATR
- [ ] a breakout is only flagged on the bar it happens

### S2-T07: Volume indicators and estimated order flow

- **Labels:** `type:feature` `area:indicators` `priority:p0` `size:M` `sprint:2`
- **Estimate:** M
- **Dependencies:** S2-T01
- **Spec references:** PRD: Indicators FR-2xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Indicators scenarios (volume and order flow)

**Description:**
Volume oscillator (5, 10), relative volume, CMF(20), accumulation and distribution days, intraday buy / sell split and daily delta, with the `intraday` and `daily_estimate` quality paths.

**Acceptance criteria:**
- [ ] buy plus sell equals volume for every bar
- [ ] the zero-range bar rule is covered
- [ ] the daily fallback is used and flagged when intraday bars are missing

### S2-T08: No-look-ahead and determinism harness

- **Labels:** `type:test` `area:indicators` `priority:p0` `size:M` `sprint:2`
- **Estimate:** M
- **Dependencies:** S2-T02, S2-T03, S2-T04, S2-T05, S2-T06, S2-T07
- **Spec references:** PRD: Indicators FR-2xx; NFR-001 compute budget; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Indicators scenarios (no look-ahead, determinism, benchmark)

**Description:**
A hypothesis property test applied to every public indicator: computing on `bars[:t]` yields the same values for indexes below `t - confirm_lag` as computing on the full series. A determinism test hashes all outputs for the fixture dataset and compares to a committed hash. A benchmark test enforces NFR-001's compute budget.

**Acceptance criteria:**
- [ ] all indicators are registered with the harness (a test fails if a public indicator function is missing from the registry)
- [ ] the benchmark passes in CI on 2 cores

### S2-T09: Indicator snapshot persistence

- **Labels:** `type:feature` `area:data` `area:indicators` `priority:p1` `size:S` `sprint:2`
- **Estimate:** S
- **Dependencies:** S2-T08, S1-T01
- **Spec references:** PRD: Indicators FR-2xx; ARCHITECTURE: section 5 Database Schema, section 4 Data Flows; TEST_PLAN: Indicators scenarios (snapshot persistence)

**Description:**
Compute-all function producing one snapshot row per ticker per date (JSONB of indicator values plus levels), stored in `indicator_snapshots` with the config hash.

**Acceptance criteria:**
- [ ] snapshot for the fixture dataset round-trips
- [ ] recomputing with the same inputs produces an identical JSON document

### Sprint 2 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

- [ ] Every indicator in the specification is implemented and registered with the no-look-ahead harness
- [ ] Supertrend hand-computed fixture passes; TradingView parity passes, or is skipped with the owner checklist entry open
- [ ] Determinism hash committed and checked in CI
- [ ] Indicator coverage at or above 95 percent
- [ ] Compute benchmark within budget
- [ ] `make up && make smoke` pass; spec docs audited
- [ ] Retrospective written; tag `sprint-2-complete` pushed

---

## Sprint 3: Scoring and Daily Picks

**Milestone:** Sprint 3: Scoring and Daily Picks
**Duration:** 2 weeks
**Goal:** a scheduled or manual run produces the top 3 buys and top 2 sells with structured evidence, served by the API. The real image and a minimal Helm chart install on kind in CI.

### S3-T01: Factor framework

- **Labels:** `type:feature` `area:scoring` `priority:p0` `size:M` `sprint:3`
- **Estimate:** M
- **Dependencies:** S2-T09
- **Spec references:** PRD: Scoring FR-3xx; ARCHITECTURE: section 2 Component Responsibilities, section 13 Configuration; TEST_PLAN: Scoring scenarios

**Description:**
A `Factor` protocol (`id`, `compute(snapshot, context) -> FactorResult`), `FactorResult` (score, evidence list, quality), a registry, and reason templates. Scores are validated to be within -100 to 100.

**Acceptance criteria:**
- [ ] a factor returning 101 raises in tests
- [ ] every factor ID in `config/scoring.yaml` maps to a registered factor and the reverse

### S3-T02: Factors 1 to 4 (Supertrend, SMA, MACD, Divergences)

- **Labels:** `type:feature` `area:scoring` `priority:p0` `size:L` `sprint:3`
- **Estimate:** L
- **Dependencies:** S3-T01
- **Spec references:** PRD: Scoring FR-3xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Scoring scenarios (factors 1 to 4)

**Description:**
Implement the scoring rules exactly as specified, each with table-driven tests covering every branch and both signs.

**Acceptance criteria:**
- [ ] one test row per rule line in the specification
- [ ] boundary values (for example `bars_since_flip` 5 and 6) are covered

### S3-T03: Factors 5 to 8 (Mean reversion, Fibonacci, Support / resistance, Volatility)

- **Labels:** `type:feature` `area:scoring` `priority:p0` `size:L` `sprint:3`
- **Estimate:** L
- **Dependencies:** S3-T01
- **Spec references:** PRD: Scoring FR-3xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Scoring scenarios (factors 5 to 8)

**Description:**
Same standard as S3-T02.

**Acceptance criteria:**
- [ ] one test row per rule line
- [ ] the mirror rules for down legs are covered

### S3-T04: Factors 9 and 10 (Volume oscillator, Buy / sell volume)

- **Labels:** `type:feature` `area:scoring` `priority:p0` `size:M` `sprint:3`
- **Estimate:** M
- **Dependencies:** S3-T01
- **Spec references:** PRD: Scoring FR-3xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Scoring scenarios (factors 9 and 10)

**Description:**
Same standard, including the quality-based weight multiplier for `daily_estimate`.

**Acceptance criteria:**
- [ ] one test row per rule line
- [ ] sign logic for rising volume on a falling price is covered

### S3-T05: Composite, confidence, bands

- **Labels:** `type:feature` `area:scoring` `priority:p0` `size:M` `sprint:3`
- **Estimate:** M
- **Dependencies:** S3-T02, S3-T03, S3-T04
- **Spec references:** PRD: Scoring FR-3xx; ARCHITECTURE: section 2 Component Responsibilities, section 13 Configuration; TEST_PLAN: Scoring scenarios (composite and confidence)

**Description:**
Weighted composite over non-missing factors with weight redistribution, display score, band, confidence. In this sprint all regime multipliers are 1.0 and fundamentals is `missing` (both arrive in Sprint 5); the code paths exist and are tested with injected values.

**Acceptance criteria:**
- [ ] contributions sum to the composite within 1e-9
- [ ] removing a factor redistributes weight proportionally
- [ ] display score of composite 0 is 50.0

### S3-T06: Selection

- **Labels:** `type:feature` `area:scoring` `priority:p0` `size:M` `sprint:3`
- **Estimate:** M
- **Dependencies:** S3-T05
- **Spec references:** PRD: Selection FR-4xx; ARCHITECTURE: section 2 Component Responsibilities; TEST_PLAN: Selection scenarios

**Description:**
Candidate rules, ranking with the full tie-breaker chain, max counts, correlation guard, "also qualified" list, and the nearest-miss record for an empty side.

**Acceptance criteria:**
- [ ] with 1 qualifying buy the result has 1 buy, not 3
- [ ] ties resolve in the documented order
- [ ] the correlation guard never lets two picks with correlation above 0.9 onto the same side (tested with SPY, VOO, and IVV stand-ins all qualifying: only the top one is picked)

### S3-T07: Run orchestrator and atomic publication

- **Labels:** `type:feature` `area:scoring` `area:data` `priority:p0` `size:L` `sprint:3`
- **Estimate:** L
- **Dependencies:** S3-T06, S1-T06
- **Spec references:** PRD: Selection FR-4xx, Operations FR-9xx; ARCHITECTURE: section 8 Run State Machine and Atomic Publication, section 4 Data Flows; TEST_PLAN: Run orchestration and atomic publication scenarios

**Description:**
`supertrends run daily [--date]`: state machine `queued -> ingesting -> computing -> scoring -> selecting -> narrating -> published | failed`. Each state transition is persisted. Publication writes recommendations and flips `runs.published_at` in a single transaction. A failed run leaves the previous published run as "latest". One run per trading date is the published one; a rerun for the same date creates a new run row that supersedes the old one only on success, and both remain stored. An advisory lock prevents concurrent runs. Tickers with `stale` or `insufficient_history` are excluded and listed in the run summary.

**Acceptance criteria:**
- [ ] killing the process mid-run leaves the previous run as latest
- [ ] two simultaneous triggers produce one run and one "already running" response
- [ ] the run summary lists exclusions with reasons

### S3-T08: Evidence document and template narrative

- **Labels:** `type:feature` `area:narrative` `priority:p0` `size:M` `sprint:3`
- **Estimate:** M
- **Dependencies:** S3-T06
- **Spec references:** PRD: Justification FR-5xx; ARCHITECTURE: section 2 Component Responsibilities, section 4 Data Flows; TEST_PLAN: Narrative and evidence scenarios

**Description:**
Build the evidence document per pick and a deterministic template narrative (lead with Supertrend, top two contributions, top opposing factor, invalidation level). The LLM path arrives in Sprint 5.

**Acceptance criteria:**
- [ ] the evidence JSON validates against a committed JSON schema
- [ ] every number in the template narrative appears in the evidence document

### S3-T09: Read API

- **Labels:** `type:feature` `area:api` `priority:p0` `size:M` `sprint:3`
- **Estimate:** M
- **Dependencies:** S3-T07, S1-T08
- **Spec references:** PRD: API FR-8xx; ARCHITECTURE: section 6.1 HTTP; TEST_PLAN: API contract scenarios

**Description:**
`GET /api/v1/recommendations/latest`, `GET /api/v1/recommendations?date=`, `GET /api/v1/rankings?date=`, `GET /api/v1/tickers/{symbol}/analysis?date=`, `GET /api/v1/tickers/{symbol}/bars`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}`, `POST /api/v1/runs` (token required), `GET /api/v1/config/scoring`. OpenAPI document committed at `docs/openapi.json` and diffed in CI. Every recommendation payload includes the disclaimer string.

**Acceptance criteria:**
- [ ] contract tests cover every endpoint and error
- [ ] `docs/openapi.json` is regenerated by `make openapi` and CI fails on drift

### S3-T10: Scheduling

- **Labels:** `type:feature` `area:deploy` `priority:p1` `size:S` `sprint:3`
- **Estimate:** S
- **Dependencies:** S3-T07
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment, section 8 Run State Machine and Atomic Publication; TEST_PLAN: Scheduling scenarios

**Description:**
The daily run is a Kubernetes CronJob (`30 17 * * 1-5`, time zone `America/New_York`) that calls `supertrends run daily`. The command exits 0 with "market closed" on non-trading days. Locally, `make run-daily` does the same.

**Acceptance criteria:**
- [ ] on a holiday date the command exits 0 and publishes nothing
- [ ] the CronJob template sets `concurrencyPolicy: Forbid` and `timeZone`

### S3-T11: Real image, minimal chart, kind install in CI

- **Labels:** `type:feature` `area:deploy` `area:ci` `priority:p0` `size:L` `sprint:3`
- **Estimate:** L
- **Dependencies:** S3-T09, S3-T10
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment; TEST_PLAN: Deployment and smoke scenarios

**Description:**
Complete the Dockerfile for the real app. Create the minimal chart (API Deployment, Service, run CronJob, migration Job hook, bundled Postgres StatefulSet for kind, `values-kind.yaml`). Add `kind-up`, `kind-load`, `helm-install`, `helm-test`, `kind-down`. Add the CI job `kind-e2e` that runs the whole loop with the fixture provider, triggers a run, and runs the smoke suite against the cluster.

**Acceptance criteria:**
- [ ] `make kind-up image kind-load helm-install helm-test smoke` passes locally and in CI
- [ ] the smoke suite asserts that `/api/v1/recommendations/latest` returns at most 3 buys and at most 2 sells with evidence

### S3-T12: Smoke suite

- **Labels:** `type:test` `area:deploy` `priority:p0` `size:M` `sprint:3`
- **Estimate:** M
- **Dependencies:** S3-T09
- **Spec references:** PRD: Operations FR-9xx, API FR-8xx; ARCHITECTURE: section 10 Build and Deployment; TEST_PLAN: Smoke checklist

**Description:**
`tests/smoke/` driven by `SMOKE_BASE_URL`: health, readiness, trigger run and wait, latest recommendations shape, analysis for one ticker, watchlist round trip. One suite reused by Compose, kind, and Stoke.

**Acceptance criteria:**
- [ ] the same command passes against `make up` and against the kind install

### S3-T13: Demo mode

- **Labels:** `type:feature` `area:deploy` `priority:p0` `size:M` `sprint:3`
- **Estimate:** M
- **Dependencies:** S3-T11, S3-T12
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment (Demo mode); TEST_PLAN: Demo matrix scenarios

**Description:**
Implement `make demo`, `make demo-verify`, and `make demo-down` as specified in Build and Deployment, "Demo mode". In this sprint the demo covers ingestion, scoring, selection, the API, and the CLI; later sprints extend it as they add functions.

**Acceptance criteria:**
- [ ] on a machine with only Docker, `make demo` ends with a URL and a populated latest run within 3 minutes
- [ ] `make demo-verify` prints one PASS or FAIL line per function and exits non-zero on any FAIL
- [ ] no API key, network access, or cluster is needed

### Sprint 3 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] `supertrends run daily` on the fixture dataset publishes picks; the result is identical across two clean runs (determinism)
- [ ] Every scoring rule line in the specification has a test row
- [ ] Atomic publication and concurrency tests pass
- [ ] API contract tests pass; `docs/openapi.json` current
- [ ] Image builds, chart installs on kind, smoke suite passes against it (in CI)
- [ ] Scoring and selection coverage at or above 92 percent
- [ ] Spec docs audited
- [ ] Retrospective written; tag `sprint-3-complete` pushed

---

## Sprint 4: UI

**Milestone:** Sprint 4: UI
**Duration:** 1 week
**Goal:** every screen in DESIGN.md, on real API data, served by the same image.

### S4-T01: Design tokens and base components

- **Labels:** `type:feature` `area:ui` `priority:p0` `size:M` `sprint:4`
- **Estimate:** M
- **Dependencies:** S0-T02
- **Spec references:** PRD: UI FR-7xx; NFR: accessibility; ARCHITECTURE: section 12 Repository Structure; TEST_PLAN: UI component and accessibility scenarios

**Description:**
CSS custom properties from the Design System section, light and dark themes, and components: Button, Card, Badge, ScoreDial, TrendRibbon, FactorBar, LevelList, DataQualityTag, Disclaimer, EmptyState, ErrorState, Skeleton.

**Acceptance criteria:**
- [ ] component tests for every state
- [ ] contrast checks pass AA in both themes (automated with axe)

### S4-T02: App shell, routing, data layer

- **Labels:** `type:feature` `area:ui` `priority:p0` `size:M` `sprint:4`
- **Estimate:** M
- **Dependencies:** S4-T01, S3-T09
- **Spec references:** PRD: UI FR-7xx, API FR-8xx; ARCHITECTURE: section 6.1 HTTP, section 12 Repository Structure; TEST_PLAN: UI scenarios

**Description:**
Routes: `/` (Today), `/ticker/:symbol`, `/watchlist`, `/track-record`, `/runs`, `/settings`, plus `/date/:yyyy-mm-dd`. TanStack Query for server state, Zustand for UI state (theme, selected date, token). A typed API client generated from `docs/openapi.json`.

**Acceptance criteria:**
- [ ] the client is regenerated by `make openapi`
- [ ] a 500 from the API renders the ErrorState with a retry, never a blank screen

### S4-T03: Today screen

- **Labels:** `type:feature` `area:ui` `priority:p0` `size:L` `sprint:4`
- **Estimate:** L
- **Dependencies:** S4-T02
- **Spec references:** PRD: UI FR-7xx, Selection FR-4xx, Watchlist FR-0xx; ARCHITECTURE: section 6.1 HTTP; TEST_PLAN: UI Today screen and e2e scenarios

**Description:**
Header with the as-of date, market regime, run status and data freshness. Three buy cards and two sell cards: ticker, band, ScoreDial, confidence, TrendRibbon (last 60 sessions colored by Supertrend direction), "flipped N bars ago", top factor contributions, narrative, invalidation level, key levels, flags (`event_risk`, `estimated order flow` quality), "day N on the list". Fewer cards when fewer qualify, with the nearest-miss line. Each card shows the watchlist groups the ticker belongs to; an optional group filter re-ranks within one group without changing the published overall picks. Disclaimer always visible.

**Acceptance criteria:**
- [ ] e2e: with a fixture run of 3 buys and 2 sells the screen shows exactly those
- [ ] with 1 buy it shows 1 card and the "no more qualifying buys" line
- [ ] buy and sell are distinguishable in grayscale

### S4-T04: Ticker screen with chart

- **Labels:** `type:feature` `area:ui` `priority:p0` `size:L` `sprint:4`
- **Estimate:** L
- **Dependencies:** S4-T02
- **Spec references:** PRD: UI FR-7xx, Indicators FR-2xx; NFR: accessibility; ARCHITECTURE: section 6.1 HTTP; TEST_PLAN: UI Ticker screen and e2e scenarios

**Description:**
Candlestick chart using `lightweight-charts` with overlays: Supertrend line (colored by direction), SMA 20 / 50 / 200, Fibonacci levels, support and resistance. Sub-panels: MACD with histogram, RSI with divergence markers, volume with estimated buy / sell split. Right rail: full factor table (score, weight, contribution, reasons), regime, adjustments, fundamentals summary, history of this ticker's scores.

**Acceptance criteria:**
- [ ] overlays match API values (e2e asserts the Supertrend series length and last value)
- [ ] toggling an overlay persists per browser
- [ ] the chart is keyboard reachable and has a data table alternative

### S4-T05: Watchlist and ranking screen

- **Labels:** `type:feature` `area:ui` `priority:p0` `size:M` `sprint:4`
- **Estimate:** M
- **Dependencies:** S4-T02
- **Spec references:** PRD: UI FR-7xx, Watchlist FR-0xx; ARCHITECTURE: section 6.1 HTTP; TEST_PLAN: UI Watchlist and ranking scenarios

**Description:**
Group filter (the watchlist groups from the seed, such as semis, fab-7, country-etfs) and a sortable ranking table for the selected date (score, band, confidence, Supertrend direction and age, regime, relative volume, data quality) with TrendRibbon per row. Add, remove, and group tickers.

**Acceptance criteria:**
- [ ] sorting is stable
- [ ] adding an invalid symbol shows the API's message inline
- [ ] excluded tickers are listed with their reason

### S4-T06: Runs and Settings screens

- **Labels:** `type:feature` `area:ui` `priority:p1` `size:M` `sprint:4`
- **Estimate:** M
- **Dependencies:** S4-T02
- **Spec references:** PRD: UI FR-7xx, Operations FR-9xx; NFR: secrets handling; ARCHITECTURE: section 6.1 HTTP, section 9 Security Model; TEST_PLAN: UI Runs and Settings scenarios

**Description:**
Runs: history with state, duration, exclusions, and a "Run now" button (token required) with live progress by polling. Settings: read-only view of the active scoring config and its hash, theme, API token entry (stored in memory only by default, optional localStorage with a warning), provider and LLM status.

**Acceptance criteria:**
- [ ] "Run now" without a token prompts for it
- [ ] a run already in progress disables the button
- [ ] no secret is ever rendered

### S4-T07: Serve UI from the API image

- **Labels:** `type:feature` `area:deploy` `area:ui` `priority:p0` `size:S` `sprint:4`
- **Estimate:** S
- **Dependencies:** S4-T03
- **Spec references:** PRD: UI FR-7xx; NFR: security headers; ARCHITECTURE: section 9 Security Model, section 10 Build and Deployment; TEST_PLAN: UI serving and CSP scenarios

**Description:**
FastAPI serves `ui/dist` with correct cache headers (hashed assets immutable, `index.html` no-cache) and SPA fallback. Strict Content-Security-Policy with no inline scripts and `connect-src 'self'`.

**Acceptance criteria:**
- [ ] the built image serves the UI at `/`
- [ ] CSP header present and tested
- [ ] deep links work after refresh

### S4-T08: End-to-end tests

- **Labels:** `type:test` `area:ui` `area:ci` `priority:p0` `size:M` `sprint:4`
- **Estimate:** M
- **Dependencies:** S4-T03, S4-T04, S4-T05, S4-T06, S4-T07
- **Spec references:** PRD: UI FR-7xx; ARCHITECTURE: section 10 Build and Deployment; TEST_PLAN: e2e scenarios e2e_US-001 to US-007, US-011, US-012

**Description:**
Playwright against `make up`: e2e_US-001 through e2e_US-007, US-011, US-012. Runs in CI in the `e2e-tests` job.

**Acceptance criteria:**
- [ ] all listed stories have a passing e2e test
- [ ] screenshots are uploaded as CI artifacts on failure

### S4-T09: Demo tour and visual report

- **Labels:** `type:feature` `area:ui` `area:deploy` `priority:p0` `size:M` `sprint:4`
- **Estimate:** M
- **Dependencies:** S3-T13, S4-T03
- **Spec references:** PRD: UI FR-7xx, Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment (Demo mode); TEST_PLAN: Demo matrix scenarios

**Description:**
A `/demo` route, shown only when `SUPERTRENDS_DEMO=1`, that lists every product function with a link to the screen that shows it and its live PASS or FAIL status. A persistent "DEMO DATA: synthetic prices, not real markets" banner on every screen in demo mode. `make demo-verify` now also drives the UI with Playwright and writes `demo-report/index.html` with a screenshot per screen.

**Acceptance criteria:**
- [ ] the tour lists every function in the demo matrix
- [ ] the report opens offline and shows one screenshot per screen
- [ ] the banner is present on every route in demo mode and absent otherwise

### Sprint 4 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] Every screen in DESIGN.md exists with loading, empty, error, and stale states
- [ ] e2e suite green in CI
- [ ] axe reports zero serious or critical issues on every route
- [ ] Today screen first meaningful paint under 1.5 seconds against the kind install (measured with Playwright)
- [ ] Image builds, chart installs on kind, smoke suite passes against it
- [ ] Spec docs audited
- [ ] Retrospective written; tag `sprint-4-complete` pushed

---

## Sprint 5: Justification and Dynamic Weights

**Milestone:** Sprint 5: Justification and Dynamic Weights
**Duration:** 1 week
**Goal:** LLM-written narratives that cannot invent numbers, the fundamentals overlay, and regime-driven weights.

### S5-T01: Narrative provider and prompt

- **Labels:** `type:feature` `area:narrative` `priority:p0` `size:M` `sprint:5`
- **Estimate:** M
- **Dependencies:** S3-T08
- **Spec references:** PRD: Justification FR-5xx; NFR-012 token budget; ARCHITECTURE: section 7 Provider Interfaces, section 13 Configuration; TEST_PLAN: Narrative scenarios

**Description:**
`NarrativeProvider` protocol with two implementations: `template` (from Sprint 3) and `openai_compatible` (httpx, `SUPERTRENDS_LLM_BASE_URL`, `SUPERTRENDS_LLM_MODEL`, optional `SUPERTRENDS_LLM_API_KEY`). The system prompt and user prompt template live in `src/supertrends/narrative/prompts/` and are versioned. The user prompt contains a compact rendering of the evidence document only.

**Acceptance criteria:**
- [ ] token budget test (NFR-012) passes on the fixture set
- [ ] the prompt version is stored with each narrative

### S5-T02: Numeric guard and fallback

- **Labels:** `type:feature` `area:narrative` `priority:p0` `size:M` `sprint:5`
- **Estimate:** M
- **Dependencies:** S5-T01
- **Spec references:** PRD: Justification FR-5xx; ARCHITECTURE: section 2 Component Responsibilities, section 11 Observability; TEST_PLAN: Narrative numeric guard scenarios

**Description:**
Implement the numeric guard, banned-phrase check, length check (3 to 5 sentences), retry once at temperature 0, then template fallback. Timeouts and errors never fail the run.

**Acceptance criteria:**
- [ ] a narrative containing a number not in the evidence is rejected
- [ ] a banned phrase is rejected
- [ ] with the endpoint unreachable the run publishes with `source: template`
- [ ] metrics count accepted, rejected, and fallback narratives

### S5-T03: Narrative evaluation set

- **Labels:** `type:test` `area:narrative` `priority:p1` `size:M` `sprint:5`
- **Estimate:** M
- **Dependencies:** S5-T02
- **Spec references:** PRD: Justification FR-5xx; ARCHITECTURE: section 7 Provider Interfaces; TEST_PLAN: Narrative evaluation scenarios

**Description:**
`tests/narrative_eval/`: 30 evidence documents covering every band, both sides, every flag. A recorded-response test runs in CI. A live evaluation command `make narrative-eval` runs against a configured endpoint and reports acceptance rate, mean tokens, and latency; target acceptance at or above 90 percent on the Stoke model. Record the result in `docs/NARRATIVE_EVAL.md`.

**Acceptance criteria:**
- [ ] CI test green on recorded responses
- [ ] the live command works against a local OpenAI-compatible mock

### S5-T04: Fundamentals ingestion and factor 11

- **Labels:** `type:feature` `area:scoring` `area:data` `priority:p0` `size:L` `sprint:5`
- **Estimate:** L
- **Dependencies:** S3-T05, S1-T04
- **Spec references:** PRD: Ingestion FR-1xx, Scoring FR-3xx; ARCHITECTURE: section 5 Database Schema, section 7 Provider Interfaces; TEST_PLAN: Fundamentals scenarios

**Description:**
Ingest quarterly financials and earnings dates through `FundamentalsProvider`, store point-in-time (each row has `known_at`, so backtests never see a number early), compute the sub-scores and factor score, handle ETFs and stale data.

**Acceptance criteria:**
- [ ] one test row per sub-score rule
- [ ] a backtest date before `known_at` does not see the row
- [ ] QQQ gets quality `missing` and its weight is redistributed

### S5-T05: Regime detection and dynamic weights

- **Labels:** `type:feature` `area:scoring` `priority:p0` `size:M` `sprint:5`
- **Estimate:** M
- **Dependencies:** S5-T04
- **Spec references:** PRD: Scoring FR-3xx; ARCHITECTURE: section 2 Component Responsibilities, section 13 Configuration; TEST_PLAN: Scoring regime and dynamic weight scenarios

**Description:**
Per-ticker regime from ADX, market regime from the benchmarks, the multiplier table, event and fundamentals adjustments, threshold adjustments, renormalization, and the stored list of adjustments that fired.

**Acceptance criteria:**
- [ ] weights always sum to 100 after adjustment
- [ ] each multiplier cell in the table has a test
- [ ] threshold adjustments stack as specified
- [ ] the evidence document lists adjustments

### S5-T06: Surface regimes and fundamentals in the UI

- **Labels:** `type:feature` `area:ui` `priority:p1` `size:M` `sprint:5`
- **Estimate:** M
- **Dependencies:** S5-T05, S4-T04
- **Spec references:** PRD: UI FR-7xx, Justification FR-5xx; ARCHITECTURE: section 6.1 HTTP; TEST_PLAN: e2e scenarios e2e_US-009 and US-010

**Description:**
Regime badges, "weights adjusted" explanation with before and after weights, earnings countdown and `event_risk` flag, fundamentals summary panel, narrative source tag (LLM model name or template).

**Acceptance criteria:**
- [ ] e2e for US-009 and US-010 pass

### S5-T07: Config versioning

- **Labels:** `type:feature` `area:scoring` `area:ci` `priority:p1` `size:S` `sprint:5`
- **Estimate:** S
- **Dependencies:** S0-T09
- **Spec references:** PRD: Scoring FR-3xx; ARCHITECTURE: section 13 Configuration, section 5 Database Schema; TEST_PLAN: Config versioning scenarios

**Description:**
Every distinct config hash is stored in `config_versions` with the full document. `scoring.version` must be bumped when weights, thresholds, or formulas change; a CI check compares the hash of `config/scoring.yaml` on the PR against `develop` and fails if the hash changed without a version bump.

**Acceptance criteria:**
- [ ] the CI check fails on a weight change without a bump
- [ ] any past recommendation can display the exact config that produced it

### Sprint 5 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] Runs publish LLM narratives against a mock endpoint and template narratives when it is down
- [ ] Numeric guard tests pass; no narrative in the evaluation set contains an unmatched number
- [ ] Fundamentals are point-in-time; ETFs handled
- [ ] Dynamic weights sum to 100 in every tested combination
- [ ] Image builds, chart installs on kind, smoke suite passes against it
- [ ] Spec docs audited (PRD scoring section matches the code and `config/scoring.yaml`)
- [ ] Retrospective written; tag `sprint-5-complete` pushed

---

## Sprint 6: Track Record and Backtest

**Milestone:** Sprint 6: Track Record and Backtest
**Duration:** 1 week
**Goal:** the product measures itself and shows the result, good or bad.

### S6-T01: Outcome tracker

- **Labels:** `type:feature` `area:track-record` `priority:p0` `size:M` `sprint:6`
- **Estimate:** M
- **Dependencies:** S3-T07
- **Spec references:** PRD: Track record and backtest FR-6xx; ARCHITECTURE: section 5 Database Schema, section 4 Data Flows; TEST_PLAN: Track record scenarios (outcomes)

**Description:**
On each run, fill `entry_price` for picks whose next session has opened and compute forward returns at 1, 5, 10, 20 trading days for the pick and SPY. Outcomes are append-only per (recommendation, horizon).

**Acceptance criteria:**
- [ ] returns match hand-computed values on the fixture dataset
- [ ] splits between entry and exit are handled through adjusted prices
- [ ] an outcome is never computed before its horizon has closed

### S6-T02: Statistics service and API

- **Labels:** `type:feature` `area:track-record` `area:api` `priority:p0` `size:M` `sprint:6`
- **Estimate:** M
- **Dependencies:** S6-T01
- **Spec references:** PRD: Track record and backtest FR-6xx, API FR-8xx; ARCHITECTURE: section 6.1 HTTP; TEST_PLAN: Track record scenarios (statistics)

**Description:**
`GET /api/v1/track-record?from=&to=&side=&band=`: hit rate, mean and median excess return, worst pick, sample size, per horizon; "small sample" flag below 20.

**Acceptance criteria:**
- [ ] statistics match a reference computed with pandas in the test
- [ ] empty ranges return zeros with sample size 0, not errors

### S6-T03: Backtest engine

- **Labels:** `type:feature` `area:track-record` `priority:p0` `size:L` `sprint:6`
- **Estimate:** L
- **Dependencies:** S6-T01, S5-T05
- **Spec references:** PRD: Track record and backtest FR-6xx; NFR: performance; ARCHITECTURE: section 4 Data Flows, section 5 Database Schema; TEST_PLAN: Backtest scenarios

**Description:**
`supertrends backtest` as specified: replays the daily loop over stored history through the same factor, composite, and selection code (no separate implementation), with point-in-time fundamentals and next-open entries. Writes results to a separate `backtests` schema and never touches published recommendations. Outputs JSON and a Markdown summary.

**Acceptance criteria:**
- [ ] a backtest over the fixture dataset reproduces the live run's picks for the same dates
- [ ] a deliberately leaky indicator injected in a test is caught by the no-look-ahead check
- [ ] runtime for 2 years and 20 tickers under 3 minutes on 2 cores

### S6-T04: Track Record screen

- **Labels:** `type:feature` `area:ui` `area:track-record` `priority:p0` `size:M` `sprint:6`
- **Estimate:** M
- **Dependencies:** S6-T02
- **Spec references:** PRD: UI FR-7xx, Track record and backtest FR-6xx; ARCHITECTURE: section 6.1 HTTP; TEST_PLAN: e2e scenario e2e_US-008

**Description:**
Summary tiles per side and horizon with sample sizes, a table of every past pick with outcome columns, filters by date range, side, band, and config version, an excess-return distribution chart, and a clearly separated "Backtest (hypothetical)" tab.

**Acceptance criteria:**
- [ ] e2e for US-008 passes
- [ ] losing picks are shown with the same prominence as winners
- [ ] backtest figures are never shown without the "hypothetical" label

### S6-T05: Observability

- **Labels:** `type:feature` `area:observability` `priority:p1` `size:M` `sprint:6`
- **Estimate:** M
- **Dependencies:** S3-T07
- **Spec references:** PRD: Operations FR-9xx; NFR: observability; ARCHITECTURE: section 11 Observability; TEST_PLAN: Observability scenarios

**Description:**
Metrics: `supertrends_run_duration_seconds`, `supertrends_run_state_total{state}`, `supertrends_tickers_scored`, `supertrends_tickers_excluded{reason}`, `supertrends_data_freshness_seconds`, `supertrends_provider_requests_total{provider,status}`, `supertrends_provider_rate_limited_total`, `supertrends_narrative_total{source,result}`, `supertrends_narrative_tokens{kind}`, `supertrends_picks_published{side}`. A Grafana dashboard JSON in `deploy/dashboards/` and PrometheusRule alerts: no published run for the latest completed session by 19:00 ET, data stale, provider error rate above 20 percent for 15 minutes, narrative fallback rate above 50 percent for a run.

**Acceptance criteria:**
- [ ] metrics are emitted and scraped in the kind install (ServiceMonitor optional there)
- [ ] the dashboard JSON loads in Grafana without errors
- [ ] alert rules pass `promtool check rules`

### S6-T06: Data retention and backup notes

- **Labels:** `type:chore` `area:data` `priority:p2` `size:S` `sprint:6`
- **Estimate:** S
- **Dependencies:** S1-T01
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 5 Database Schema, section 10 Build and Deployment; TEST_PLAN: Data retention and backup scenarios

**Description:**
Retention job: intraday bars older than 90 days are deleted; daily bars, recommendations, and outcomes are kept forever. `supertrends db backup` wraps `pg_dump` to a file path. Document restore.

**Acceptance criteria:**
- [ ] retention never deletes rows referenced by a recommendation's evidence window
- [ ] backup and restore round-trip in an integration test

### Sprint 6 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] Outcomes and statistics verified against reference computations
- [ ] Backtest reproduces live picks on the fixture dataset
- [ ] Track Record screen shows winners and losers with sample sizes
- [ ] Metrics, dashboard, and alert rules validated
- [ ] Image builds, chart installs on kind, smoke suite passes against it
- [ ] Spec docs audited
- [ ] Retrospective written; tag `sprint-6-complete` pushed

---

## Sprint 7: CLI, MCP, Harnesses

**Milestone:** Sprint 7: CLI, MCP, Harnesses
**Duration:** 1 week
**Goal:** agents and the terminal get the same answers as the UI.

### S7-T01: CLI

- **Labels:** `type:feature` `area:cli` `priority:p0` `size:M` `sprint:7`
- **Estimate:** M
- **Dependencies:** S3-T09, S6-T02
- **Spec references:** PRD: API/CLI/MCP FR-8xx; ARCHITECTURE: section 6.2 CLI; TEST_PLAN: CLI scenarios

**Description:**
Typer CLI in the same package. Commands: `supertrends today [--json]`, `supertrends analyze TICKER [--date] [--json]`, `supertrends rank [--date] [--top N]`, `supertrends watchlist list|add|remove`, `supertrends run daily [--date]`, `supertrends ingest`, `supertrends backtest`, `supertrends track-record`, `supertrends status`, `supertrends serve`, `supertrends mcp`, `supertrends healthcheck`, `supertrends db migrate|backup`, `supertrends config show|validate`. Remote mode with `--api-url` and `SUPERTRENDS_API_TOKEN`; local mode talks to the database directly.

**Acceptance criteria:**
- [ ] every command has `--help` text and a test
- [ ] `--json` output validates against the API schemas
- [ ] exit codes: 0 ok, 1 error, 2 usage, 3 not ready

### S7-T02: MCP server

- **Labels:** `type:feature` `area:mcp` `priority:p0` `size:L` `sprint:7`
- **Estimate:** L
- **Dependencies:** S7-T01
- **Spec references:** PRD: API/CLI/MCP FR-8xx; NFR: security; ARCHITECTURE: section 6.3 MCP, section 9 Security Model; TEST_PLAN: MCP scenarios

**Description:**
MCP server using the official Python SDK, exposed two ways: stdio (`supertrends mcp`) and streamable HTTP mounted at `/mcp` on the API (bearer token required). Tools:
- `supertrends_recommend` (date optional): today's picks with evidence
- `supertrends_analyze` (ticker, date optional): full factor breakdown and levels
- `supertrends_rank` (date optional, top N): ranked watchlist
- `supertrends_watchlist` (action list / add / remove, ticker): watchlist management; add and remove require the token
- `supertrends_status`: latest run, data freshness, provider and LLM health
- `supertrends_track_record` (range, side): statistics
- `supertrends_run` (date optional): trigger a run; requires the token

Every tool result that contains a pick includes the disclaimer. Tool descriptions tell the calling agent that results are informational and that Super Trends places no trades.

**Acceptance criteria:**
- [ ] an MCP client integration test lists the tools and calls each
- [ ] schemas are strict (no additional properties)
- [ ] unauthenticated HTTP calls to write tools return an error

### S7-T03: Pi extension

- **Labels:** `type:feature` `area:mcp` `priority:p1` `size:M` `sprint:7`
- **Estimate:** M
- **Dependencies:** S7-T02
- **Spec references:** PRD: API/CLI/MCP FR-8xx; ARCHITECTURE: section 6.3 MCP, section 12 Repository Structure; TEST_PLAN: Harness integration scenarios

**Description:**
`integrations/pi/` package `@stokeai-supertrends/pi-extension` built on `pi-agent-core` with TypeBox tool schemas mirroring the MCP tools, slash commands `/supertrends today`, `/supertrends analyze <ticker>`, `/supertrends rank`, and streaming progress for `supertrends_run` through `onUpdate`. It calls the HTTP API. Verify the current `pi-agent-core` package name and API at implementation time.

**Acceptance criteria:**
- [ ] unit tests with a mocked API
- [ ] README with install and config
- [ ] coverage at or above 70 percent

### S7-T04: Goose and OpenCode integration

- **Labels:** `type:feature` `area:mcp` `priority:p1` `size:S` `sprint:7`
- **Estimate:** S
- **Dependencies:** S7-T02
- **Spec references:** PRD: API/CLI/MCP FR-8xx; ARCHITECTURE: section 6.3 MCP, section 12 Repository Structure; TEST_PLAN: Harness integration scenarios

**Description:**
`integrations/goose/toolkit.yaml` pointing at the MCP server (stdio and HTTP variants). `integrations/opencode/README.md` with the config snippet. `integrations/claude-code/README.md` with the `.mcp.json` snippet.

**Acceptance criteria:**
- [ ] each config is validated by a script that starts the stdio server and lists tools using that config's command line

### S7-T05: Harness smoke tests

- **Labels:** `type:test` `area:mcp` `area:ci` `priority:p2` `size:S` `sprint:7`
- **Estimate:** S
- **Dependencies:** S7-T04
- **Spec references:** PRD: API/CLI/MCP FR-8xx; ARCHITECTURE: section 6.3 MCP, section 10 Build and Deployment; TEST_PLAN: Harness smoke scenarios

**Description:**
CI job `harness-smoke-tests` on `staging` and release tags: start the API with the fixture provider, run an MCP client through all read tools, and assert shape.

**Acceptance criteria:**
- [ ] job green on `staging`

### S7-T06: Agent skill for operating Super Trends

- **Labels:** `type:docs` `area:mcp` `priority:p2` `size:S` `sprint:7`
- **Estimate:** S
- **Dependencies:** S7-T01
- **Spec references:** PRD: API/CLI/MCP FR-8xx; ARCHITECTURE: section 6.2 CLI, section 12 Repository Structure; TEST_PLAN: Harness integration scenarios

**Description:**
`.agent/skills/daily-brief/` skill: how an agent should fetch today's picks, summarize them faithfully, and what it must not do (no trade execution, no position sizing, always carry the disclaimer).

**Acceptance criteria:**
- [ ] skill listed in `SKILLS.md`
- [ ] `run.sh` prints today's picks from a running instance

### Sprint 7 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] CLI commands tested; `supertrends today --json` matches the API payload
- [ ] MCP tools callable over stdio and HTTP; write tools require the token
- [ ] Pi, Goose, OpenCode, and Claude Code integration files validated
- [ ] Image builds, chart installs on kind, smoke suite passes against it
- [ ] Spec docs audited
- [ ] Retrospective written; tag `sprint-7-complete` pushed

---

## Sprint 8: Packaging and Stoke Deploy

**Milestone:** Sprint 8: Packaging and Stoke Deploy
**Duration:** 1 week
**Goal:** the complete chart, published as an OCI artifact, deployed to a staging namespace on Stoke through Flux, with deployment docs.

### S8-T01: Complete the Helm chart

- **Labels:** `type:feature` `area:deploy` `priority:p0` `size:L` `sprint:8`
- **Estimate:** L
- **Dependencies:** S3-T11, S6-T05
- **Spec references:** PRD: Operations FR-9xx; NFR: container hardening, availability; ARCHITECTURE: section 10 Build and Deployment, section 9 Security Model, section 11 Observability; TEST_PLAN: Helm chart scenarios

**Description:**
Everything in Build and Deployment, Path 4: all templates, `values.schema.json`, the four profiles, probes, graceful shutdown, PodDisruptionBudget, NetworkPolicy, security contexts, HPA for the API, ServiceMonitor, PrometheusRule, dashboard ConfigMap, Helm tests.

**Acceptance criteria:**
- [ ] `helm lint` and `helm template` pass for every profile
- [ ] schema negative tests fail as expected (a secret value in values, an invalid cron, weights that do not sum to 100 in an override)

### S8-T02: Stoke inventory and profile

- **Labels:** `type:feature` `area:deploy` `priority:p0` `size:M` `sprint:8`
- **Estimate:** M
- **Dependencies:** S8-T01, S0-T10
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment (Stoke profile), section 3 Decision Log, section 9 Security Model; TEST_PLAN: Helm chart and Stoke profile scenarios

**Description:**
Run (or ask the owner to run) `scripts/stoke-inventory.sh`. From `private/STOKE_INVENTORY.md`, finalize the Stoke profile. The public `values-stoke.yaml` carries only generic, non-identifying settings (architecture selector, resources, feature toggles) and documented placeholders. Cluster-specific values (LLM gateway URL and model name, hostnames, storage class, ServiceMonitor labels, secret mechanism) go into a values patch that lives only in the owner's Stoke GitOps repository; write it to `private/stoke-values.yaml` for the owner to copy. Anything classified INSTALL needs an ADR explaining why it cannot be avoided; the default answer is to reuse what Stoke already runs.

**Acceptance criteria:**
- [ ] `private/stoke-values.yaml` resolves every placeholder, or each unresolved one has an owner checklist entry
- [ ] nothing under `private/` is tracked by git
- [ ] `helm template` with the Stoke profile renders only ARM64-compatible images and requests no GPU

### S8-T03: OCI image and chart publishing

- **Labels:** `type:feature` `area:deploy` `area:ci` `priority:p0` `size:M` `sprint:8`
- **Estimate:** M
- **Dependencies:** S8-T01
- **Spec references:** PRD: Operations FR-9xx; NFR: supply chain security; ARCHITECTURE: section 10 Build and Deployment, section 9 Security Model; TEST_PLAN: Release and publishing scenarios

**Description:**
`release-images.yml` and `release-chart.yml`: multi-arch build, push to GHCR, cosign keyless signing, SBOM and provenance attestations, Trivy scan failing on high or critical, `helm package` and `helm push` to `oci://ghcr.io/mohnishbasha/charts`, chart signed with cosign. `sha-` tags on every merge to `staging`.

**Acceptance criteria:**
- [ ] a merge to `staging` produces a signed `sha-` image and chart
- [ ] `cosign verify` with the documented command succeeds
- [ ] a seeded critical CVE fails the scan in a test branch

### S8-T04: Flux manifests

- **Labels:** `type:feature` `area:deploy` `priority:p0` `size:M` `sprint:8`
- **Estimate:** M
- **Dependencies:** S8-T03
- **Spec references:** PRD: Operations FR-9xx; NFR: secrets handling; ARCHITECTURE: section 10 Build and Deployment, section 9 Security Model; TEST_PLAN: Flux manifest validation scenarios

**Description:**
`deploy/flux/` with base and overlays for `supertrends-stage` and `supertrends` namespaces: Namespace, OCIRepository (chart, with cosign verification), HelmRelease (values from the Stoke profile, image by digest, install and upgrade remediation with automatic rollback, Helm tests enabled), and a Kustomization. Secrets follow the mechanism found in the inventory (SOPS or External Secrets); no secret values in git.

**Acceptance criteria:**
- [ ] `kustomize build` succeeds for both overlays
- [ ] `flux build` (or `kubeconform` with Flux CRD schemas) validates them in CI
- [ ] the manifests are ready to be copied or referenced by the Stoke GitOps repository

### S8-T05: Staging deploy on Stoke

- **Labels:** `type:feature` `area:deploy` `priority:p0` `size:M` `sprint:8`
- **Estimate:** M
- **Dependencies:** S8-T04, S8-T02
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment (Stoke profile); TEST_PLAN: Smoke checklist, Staging deploy scenarios

**Description:**
Open a PR to the Stoke GitOps repository adding the `supertrends-stage` overlay (owner merges it), or, if the owner provided direct access, apply it. After reconciliation: `helm test`, `make smoke SMOKE_BASE_URL=...`, trigger a run on the fixture provider, then on the real provider once the owner has created the API key secret.

**Acceptance criteria:**
- [ ] staging namespace healthy on Stoke
- [ ] smoke suite passes against it
- [ ] a real-provider run publishes picks
- [ ] rollback tested once (`flux suspend`, `helm rollback`, resume) and recorded
- [ ] If cluster access is not available, everything up to the PR is complete and the remaining steps are in the owner checklist with exact commands

### S8-T06: Upgrade, rollback, and air-gap tests

- **Labels:** `type:test` `area:deploy` `area:ci` `priority:p1` `size:M` `sprint:8`
- **Estimate:** M
- **Dependencies:** S8-T01
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment; TEST_PLAN: Upgrade, rollback, and air-gap scenarios

**Description:**
CI job on kind: install the previous chart version, upgrade to the current one with a database migration, run smoke, roll back, run smoke. Document the air-gapped install for the self-host profile (mirror images and chart with `oras` or `skopeo`, set `global.imageRegistry`).

**Acceptance criteria:**
- [ ] upgrade and rollback job green
- [ ] the air-gap procedure is exercised once on kind with a local registry

### S8-T07: docs/DEPLOYMENT.md

- **Labels:** `type:docs` `area:deploy` `priority:p0` `size:M` `sprint:8`
- **Estimate:** M
- **Dependencies:** S8-T05
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment; TEST_PLAN: Deployment documentation scenarios

**Description:**
Local build, local deploy, images, chart, kind loop, Stoke through Flux, secrets, upgrades, rollback, backup and restore, troubleshooting (provider rate limits, stale data, LLM gateway down, CronJob time zone), and the verification command for every step.

**Acceptance criteria:**
- [ ] a second agent session following only DEPLOYMENT.md brings up kind from a clean clone
- [ ] every command in the doc is exercised by CI or marked "owner, cluster only"

### Sprint 8 checklist (non-blocking; unmet items go to docs/GATE_DEBT.md)

- [ ] `make demo && make demo-verify` passes and the demo matrix covers the functions added this sprint
- [ ] Chart complete; lint, template, and schema tests pass for all four profiles
- [ ] Signed multi-arch image and OCI chart published from `staging`; `cosign verify` succeeds
- [ ] Flux overlays validate in CI
- [ ] Staging on Stoke healthy and smoke-tested, or blocked only on recorded owner actions
- [ ] Upgrade and rollback test green
- [ ] `docs/DEPLOYMENT.md` complete and `docs/ARCHITECTURE.md` deployment chapter matches it
- [ ] Retrospective written; tag `sprint-8-complete` pushed

---

## Sprint 9: Release v1.0.0

**Milestone:** Sprint 9: Release v1.0.0
**Duration:** 1 week
**Goal:** a hardened, signed v1.0.0 running in the production namespace on Stoke, deployed by digest.

Note: where the source lists dependencies as "all prior", they are expressed below as the final task of each earlier sprint, which transitively covers all prior tasks.

### S9-T01: Security review

- **Labels:** `type:security` `area:ci` `priority:p0` `size:M` `sprint:9`
- **Estimate:** M
- **Dependencies:** S0-T10, S1-T08, S2-T09, S3-T13, S4-T09, S5-T07, S6-T06, S7-T06, S8-T07
- **Spec references:** PRD: Operations FR-9xx; NFR: security, secrets handling; ARCHITECTURE: section 9 Security Model, section 10 Build and Deployment; TEST_PLAN: Security scenarios

**Description:**
Walk the Security Guidelines section line by line and record evidence for each item in `docs/SECURITY_REVIEW.md`. Run `pip-audit`, `npm audit`, Trivy (image and chart config), `gitleaks` over the full history, and a check that no response, log, or metric contains a secret. (Dependencies: all prior.)

**Acceptance criteria:**
- [ ] zero high or critical findings open
- [ ] any accepted medium has a written rationale

### S9-T02: Resilience tests

- **Labels:** `type:test` `area:data` `priority:p0` `size:M` `sprint:9`
- **Estimate:** M
- **Dependencies:** S3-T07
- **Spec references:** PRD: Operations FR-9xx, Ingestion FR-1xx; ARCHITECTURE: section 8 Run State Machine and Atomic Publication, section 4 Data Flows; TEST_PLAN: Resilience and fault injection scenarios

**Description:**
Fault injection in integration tests: provider 429 storm, provider outage mid-run, database restart mid-run, LLM timeout, half-day session, missing intraday data, a ticker delisted mid-history, a split on run day.

**Acceptance criteria:**
- [ ] each scenario ends in either a correct published run or a clean failed run with the previous result still latest
- [ ] none ends in a partial publication

### S9-T03: Performance pass

- **Labels:** `type:chore` `area:observability` `priority:p1` `size:M` `sprint:9`
- **Estimate:** M
- **Dependencies:** S8-T05
- **Spec references:** PRD: Operations FR-9xx; NFR-001, NFR-003, NFR-004, NFR-010; ARCHITECTURE: section 11 Observability, section 10 Build and Deployment; TEST_PLAN: Performance and NFR scenarios

**Description:**
Measure NFR-001, 003, 004, 010 on the Stoke staging namespace and in CI. Fix regressions. Record results in `docs/PERFORMANCE.md`.

**Acceptance criteria:**
- [ ] all four NFRs met or an ADR explains the gap and the plan

### S9-T04: Full QA pass

- **Labels:** `type:test` `area:ci` `priority:p0` `size:M` `sprint:9`
- **Estimate:** M
- **Dependencies:** S0-T10, S1-T08, S2-T09, S3-T13, S4-T09, S5-T07, S6-T06, S7-T06, S8-T07
- **Spec references:** PRD: all FR groups; ARCHITECTURE: section 10 Build and Deployment; TEST_PLAN: all scenarios and the manual smoke checklist

**Description:**
Run every scenario in TEST_PLAN.md. Run the manual smoke checklist on staging. Confirm the TradingView parity test is passing (not skipped); if the owner files are still missing, this is a release blocker recorded in the owner checklist. (Dependencies: all prior.)

**Acceptance criteria:**
- [ ] no Deferred scenarios remain
- [ ] Skipped ones each have a reason and a manual result

### S9-T05: Documentation pass

- **Labels:** `type:docs` `area:ui` `priority:p1` `size:M` `sprint:9`
- **Estimate:** M
- **Dependencies:** S0-T10, S1-T08, S2-T09, S3-T13, S4-T09, S5-T07, S6-T06, S7-T06, S8-T07
- **Spec references:** PRD: UI FR-7xx, Operations FR-9xx; ARCHITECTURE: section 11 Observability; TEST_PLAN: Documentation scenarios

**Description:**
README from the template, `docs/USER_GUIDE.md` (how to read a card, what each factor means, what confidence and invalidation mean, how to tune `config/scoring.yaml`, how to read the track record), `docs/RUNBOOK.md` (alerts and what to do), CHANGELOG for 1.0.0. (Dependencies: all prior.)

**Acceptance criteria:**
- [ ] every factor in the UI links to its section in the user guide
- [ ] the runbook covers every alert rule

### S9-T06: Release

- **Labels:** `type:chore` `area:deploy` `priority:p0` `size:M` `sprint:9`
- **Estimate:** M
- **Dependencies:** S9-T01, S9-T02, S9-T03, S9-T04, S9-T05
- **Spec references:** PRD: Operations FR-9xx; NFR: supply chain security; ARCHITECTURE: section 10 Build and Deployment (Release Checklist); TEST_PLAN: Release scenarios

**Description:**
Follow the Release Checklist in Versioning: bump `VERSION` to `1.0.0`, PR `staging` to `main` (owner approval), annotated tag `v1.0.0`, release workflow publishes signed multi-arch images and the chart, GitHub Release body from `scripts/extract-changelog.sh`.

**Acceptance criteria:**
- [ ] `ghcr.io/mohnishbasha/stokeai-supertrends:1.0.0` exists for both architectures and verifies with cosign
- [ ] the chart `1.0.0` is pullable from the OCI registry

### S9-T07: Production deploy by digest

- **Labels:** `type:chore` `area:deploy` `priority:p0` `size:S` `sprint:9`
- **Estimate:** S
- **Dependencies:** S9-T06
- **Spec references:** PRD: Operations FR-9xx; ARCHITECTURE: section 10 Build and Deployment, section 11 Observability; TEST_PLAN: Smoke checklist, Production deploy scenarios

**Description:**
Update the `supertrends` overlay to chart `1.0.0` and the image digest from the release, through the Stoke GitOps repository. After reconciliation: Helm tests, smoke suite, first production run, dashboard and alerts confirmed.

**Acceptance criteria:**
- [ ] production namespace healthy
- [ ] the first scheduled run publishes
- [ ] post-release actions from Versioning completed

## Final Gate (the only hard gate)

- [ ] Every checklist item from Sprints 0 to 8 is checked and `docs/GATE_DEBT.md` is empty
- [ ] `make demo && make demo-verify` passes with every function PASS
- [ ] Security review complete with zero high or critical findings
- [ ] Resilience scenarios pass
- [ ] NFRs measured and met
- [ ] TradingView parity test passing
- [ ] v1.0.0 tagged, signed, published; chart published
- [ ] Production on Stoke running by digest; first scheduled run published
- [ ] All five spec docs final and consistent with the code
- [ ] Retrospective written; tag `sprint-9-complete` pushed
