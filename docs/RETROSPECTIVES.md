# Retrospectives

One entry per sprint, written at the end of the Sprint End Protocol, before the `sprint-{n}-complete` tag.

## Sprint 0: Scaffolding (completed 2026-11-15)

### What was built

| Task | Issue | PR | Summary |
|---|---|---|---|
| S0-T01 | [#1](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/1) | #98 | Python project (uv, Python 3.12), `src/supertrends` package, `supertrends` CLI with `version` |
| S0-T02 | [#2](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/2) | #100 | Vite, React, and TypeScript UI project with ESLint, Vitest, and strict `tsc` |
| S0-T03 | [#3](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/3) | #102 | Root `Makefile` with `help` and every target (real or placeholder) |
| S0-T04 | [#4](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/4) | #101 | `VERSION` as the single version source, `check-versions.sh`, version sync and changelog scripts |
| S0-T05 | [#5](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/5) | #104 | CI pipeline (lint and type-check, unit, coverage, integration, e2e placeholder, multi-arch image build, changelog rule), audits, gitleaks, Dependabot |
| S0-T06 | [#6](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/6) | #103 | Non-root multi-stage Dockerfile, local Compose with Postgres, `/healthz` |
| S0-T07 | [#7](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/7) | #111 | `.gitignore`, `AGENTS.md`, `CLAUDE.md`, `SKILLS.md`, `SOUL.md`, `run-tests` and `check-types` skills |
| S0-T08 | [#8](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/8) | #112 | License and community files, SPDX check, dependency license check, CLA check and signer |
| S0-T09 | [#9](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/9) | #99 | Scoring config, JSON Schema export, `config_hash`, `supertrends config` commands |
| S0-T10 | [#10](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/10) | #113 | Read-only `scripts/stoke-inventory.sh` writing to git-ignored `private/` |

Promotion: `develop` to `staging` in #114 (CI green on `staging`). The Sprint End docs and a second promotion follow, then the `sprint-0-complete` tag on `staging`.

### Spec sections updated

- `docs/ARCHITECTURE.md`: ADR-051 (CLA without `pull_request_target`) and ADR-052 (reviewed dev-only license exceptions); seven rows in section 10.0 recording deltas (Makefile export, Compose host port, Dockerfile before Alembic, required job display names, ruff excluding Markdown, CLA workflows, license exceptions).
- `docs/TEST_PLAN.md`: 21 Sprint 0 scenarios flipped from Deferred to Automated in the PRs that added them; the status header no longer says no code exists; TS-SEC-019 stays Skipped (manual).
- `docs/SPRINT_PLAN.md`: every Sprint 0 acceptance criterion ticked except the S0-T08 CLA blocking criterion (marked not met); the Sprint 0 checklist filled in.
- `docs/OWNER_CHECKLIST.md`: #17 resolved (required check names), #18 (make `cla` required) and #19 (manual CLA test) added.
- `docs/schemas/scoring.schema.json` added (generated from the config model).
- `docs/GATE_DEBT.md` created with GD-001.
- `docs/PRD.md`, `docs/DESIGN.md`: audited, no change needed.

### Tests added (counts by type)

| Type | Count | Notes |
|---|---|---|
| Python unit | 122 | `tests/unit` (workflow lint, scripts, config, CLI, versions, licenses, CLA, harness files) |
| Integration | 3 | Postgres service, image hardening, Compose loop (skipped locally without the env vars, run in CI) |
| Smoke | 3 | `tests/smoke`, driven by `SMOKE_BASE_URL` |
| UI unit (Vitest) | 2 | `ui/src` |
| E2E | 0 | Placeholder job until Sprint 4 |

### Coverage delta

From no code to 96% Python line and branch coverage (431 statements, 16 missed) and 100% UI statements. All per-directory thresholds in `.coverage-thresholds.toml` pass; most thresholded directories do not exist yet.

### What worked

- Writing each task's TEST_PLAN rows and failing tests first kept the PRs small and reviewable, with one PR per issue in dependency order.
- Naming the CI jobs after the branch protection contexts (`ci / lint-and-typecheck`, `ci / unit-tests`) made the protection work without changing it.
- Running the CLA check from the base commit with a read-only token gave a safe gate without `pull_request_target`.
- Local verification on an alternate host port (18080) avoided colliding with other projects' containers.

### What did not work

- The required checks never reported at first because the job display names did not match the protection contexts. This was found only when a PR sat waiting.
- `pip-audit --strict` failed on the local, unpublished project. The fix was to audit an exported, locked requirements file.
- A CLA check that runs from the base commit fails on the PR that introduces it, and on the first promotion to `staging` (#112, #114). Both were expected one-time bootstraps.
- Changing branch protection was not permitted, so the CLA criterion stays open as gate debt (GD-001).
- Ruff 0.17 started formatting Python blocks inside Markdown and reformatted a spec doc. It now excludes `*.md`.
- Intermittent GitHub API connection failures needed retries in every helper script.

### What to change

- Check new workflow job names against the branch protection contexts in a unit test from the start (now in `test_workflows.py`).
- When adding a gate that runs from the base commit, plan the bootstrap PR explicitly and say so in the PR body.
- Keep retry wrappers around every `gh` call in sprint automation.
- Ask the owner early for any protection or settings change, so it lands before the criterion that depends on it.

## Sprint 1: Data Layer (written 2026-11-15, blocked on owner PR merges)

All eight tasks are implemented and reviewed in open PRs. None is merged yet: the agent was not permitted to run `gh pr merge` (docs/OWNER_CHECKLIST.md #21). Issues #11 to #18 therefore stay open, `develop` has not been promoted to `staging`, and the `sprint-1-complete` tag has not been pushed (GD-002). This entry records the state at that point. It will be amended when the merges land.

### What was built

| Task | Issue | PR | Summary |
|---|---|---|---|
| S1-T01 | [#11](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/11) | #118 | SQLAlchemy 2 models for the full section 5 schema, Alembic migrations 0001 (tables) and 0002 (append-only triggers), `supertrends db migrate` under an advisory lock |
| S1-T02 | [#12](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/12) | #117 | `MarketDataProvider` and `FundamentalsProvider` protocols, typed results, provider errors, registry with lazy targets, shared contract suites, pytest-socket |
| S1-T03 | [#13](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/13) | #120 | Seeded synthetic provider (trend, range, reversal, decline, and split tickers plus benchmarks; 756 daily and 30 intraday sessions), XNYS calendar helpers |
| S1-T04 | [#14](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/14) | #121 | Massive REST adapter with token bucket, backoff with jitter, response cache, scrubbed call records, recorded fixtures |
| S1-T05 | [#15](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/15) | #119 | Alpaca Market Data adapter (ADR-032) behind the same interface |
| S1-T06 | [#16](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/16) | #124 | `supertrends ingest`: incremental upsert, split-triggered refetch, weekly resample, quality pass (`ok`, `degraded`, `stale`, `insufficient_history`), `DbCallRecorder` |
| S1-T07 | [#17](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/17) | #123 | Watchlist service, `/api/v1/watchlist` CRUD with bearer-token writes, seed file (14 groups, 200 symbols), `supertrends watchlist` commands |
| S1-T08 | [#18](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/18) | #122 | `/readyz` with database and migration checks, `/metrics`, structlog JSON with request IDs and scrubber, RFC 9457 problems, Host allowlist, Compose `migrate` service |

Owner-blocker records: #125 (docs/OWNER_CHECKLIST.md #21 to #23). Promotion and smoke on `staging`: not done (GD-002, GD-004).

### Spec sections updated

- `docs/ARCHITECTURE.md`: ADR-032 accepted (Alpaca as the alternate provider, vendor docs checked 2026-11-15); ADR-016 updated (Zlib and CC0-1.0 on the license allowlist, pending owner confirmation in docs/OWNER_CHECKLIST.md #22); section 6.1 watchlist contract details; section 7.4 registry note; section 10.0 delta rows for provider interfaces, Massive endpoint paths (`/stocks/v1/splits`, `/stocks/v1/dividends`, `/stocks/financials/v1/income-statements`, no earnings endpoint), and watchlist behavior.
- `docs/TEST_PLAN.md`: about 120 TS-ING, TS-WL, TS-API, TS-SEC, and TS-CLI scenarios added or flipped to Automated across the eight PRs. ID collisions are left to fix at merge (GD-009). TS-ING-003 stays Deferred (GD-012).
- `docs/OWNER_CHECKLIST.md`: #2 extended (Massive plan for 5-minute bars on 200 symbols); #13 annotated (seed review); #20 (Alpaca key) added; #21 to #23 (merges, license allowlist, gitleaks scope) added.
- `docs/SPRINT_PLAN.md`: Sprint 1 acceptance criteria ticked with their PRs, and the Sprint 1 checklist filled in.
- `docs/GATE_DEBT.md`: GD-002 to GD-012 added.
- `docs/PRD.md`, `docs/DESIGN.md`: audited, no change needed. Sprint 1 adds no UI, and the ingestion and watchlist behavior matches the PRD except GD-005.

### Tests added (counts by type)

Counted on the integrated tree, a local merge of all eight branches.

| Type | Count | Notes |
|---|---|---|
| Python unit | 339 (122 to 461) | Includes the provider contract suites run against the fake, fixture, Massive, and Alpaca providers with `httpx.MockTransport` |
| Integration | 42 (3 to 45) | Schema, migrations, triggers, ingest and CLI idempotency, watchlist API, readiness against Postgres 17; 43 passed and 2 image tests skipped locally |
| Smoke | 0 (3) | Existing suite; passes on the integrated tree with the Compose `migrate` service |
| UI unit (Vitest) | 0 (2) | No UI work this sprint |
| E2E | 0 | Placeholder until Sprint 4 |

### Coverage delta

Python line and branch coverage went from 96% (431 statements) to 91% (3,170 statements, 227 missed) on the integrated tree. Every per-directory threshold in `.coverage-thresholds.toml` passes, including `data` 85 and `api` 85. The drop comes mostly from Postgres-only paths in `data/db.py` and `data/ingest.py`, which only the integration job exercises.

### What worked

- Running tasks in parallel in isolated worktrees, stacked on their dependencies (T03, T04, and T05 on T02; T06, T07, and T08 on T01), got all eight tasks to reviewable PRs in one pass.
- Shared contract suites in `tests/contract` made it cheap to prove the fixture, Massive, and Alpaca providers interchangeable.
- pytest-socket in `addopts` turned "no test touches the network" into a hard failure.
- A local integration of all branches before writing the sprint-end docs found real defects that no single PR showed: the missing Compose `migrate` service (fixed in #122) and three T07/T08 integration fixes (GD-010).

### What did not work

- Merging was denied by the permission system. That blocked issue closing, promotion, smoke on `staging`, and the tag. This came up only at the first merge, after all the work was done.
- gitleaks in CI scans every fetched branch, so one PR's fake test keys failed `lint-and-typecheck` on unrelated PRs (GD-011). One agent misread this as an npm audit failure.
- Parallel agents picked the same TEST_PLAN scenario IDs and the same new files (`api/security.py`), which created merge conflicts and duplicates (GD-009, GD-010).
- One agent skipped test-first (GD-006), and two used a different co-author trailer than the brief specified.
- Cross-cutting description items (provider call recording, rate limiting on every adapter) fell between tasks, because no task's acceptance criteria named them (GD-007, GD-008).

### What to change

- Confirm merge and tag-push permissions at sprint start, and record them as owner items before any work begins.
- Give each parallel task a reserved scenario-ID range, and assign every shared new module (for example `api/security.py`) to one task.
- Add a unit test that fails on duplicate TEST_PLAN scenario IDs.
- Run the local integration of all branches (checks, integration tests, `make up && make smoke`) before marking any stacked PR ready, not only at sprint end.
- Turn cross-cutting description requirements into explicit acceptance criteria in the task that owns the wiring.
