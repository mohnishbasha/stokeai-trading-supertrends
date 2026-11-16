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

## Sprint 1: Data Layer (completed 2026-11-15)

All eight tasks are merged to `develop` and promoted to `staging` (#129), and issues #11 to #18 are closed. The merges were first blocked: the agent's `gh pr merge` was denied, which #125 records as docs/OWNER_CHECKLIST.md #21. Once permission was granted, the agent merged the stacked PRs in dependency order, updating each branch from `develop` and resolving its conflicts.

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

Supporting PRs:
- #127 unblocked CI. It added a `.gitleaksignore` union of the synthetic test keys on the open branches, because gitleaks scans every fetched branch. It also reverted the Dependabot bump of the Python base image from 3.12 to 3.15, which broke `build-image`: the runtime venv's 3.12 interpreter was missing. Dependabot now ignores Python minor and major bumps, per ADR-002.
- #125 holds the owner records: OWNER_CHECKLIST #21 to #23.
- #128 wired provider-call recording into `provider_calls` (GD-007).
- #129 promoted `develop` to `staging`. Smoke passed there, 3 of 3.

### Spec sections updated

- `docs/ARCHITECTURE.md`: ADR-032 accepted (Alpaca as the alternate provider, vendor docs checked 2026-11-15); ADR-016 updated (Zlib and CC0-1.0 on the license allowlist, pending owner confirmation in docs/OWNER_CHECKLIST.md #22); section 6.1 watchlist contract details; section 7.4 registry note; section 10.0 delta rows for provider interfaces, Massive endpoint paths (`/stocks/v1/splits`, `/stocks/v1/dividends`, `/stocks/financials/v1/income-statements`, no earnings endpoint), and watchlist behavior.
- `docs/TEST_PLAN.md`: about 120 TS-ING, TS-WL, TS-API, TS-SEC, and TS-CLI scenarios added or flipped to Automated across the eight PRs. ID collisions were renumbered at merge (GD-009); TS-ING-111 added by #128. TS-ING-003 stays Deferred (GD-012).
- `docs/OWNER_CHECKLIST.md`: #2 extended (Massive plan for 5-minute bars on 200 symbols); #13 annotated (seed review); #20 (Alpaca key) added; #21 to #23 (merges, now resolved; license allowlist; gitleaks scope) and #24 (implementation comments on #11 to #14) added.
- `docs/SPRINT_PLAN.md`: Sprint 1 acceptance criteria ticked with their PRs, and the Sprint 1 checklist filled in.
- `docs/GATE_DEBT.md`: GD-002 to GD-014 added; GD-002, GD-004, GD-007, and GD-009 to GD-011 resolved within the sprint.
- `docs/PRD.md`, `docs/DESIGN.md`: audited, no change needed. Sprint 1 adds no UI, and the ingestion and watchlist behavior matches the PRD except GD-005. Audit finding: PRD FR-009 and ARCHITECTURE section 6 disagree on ingesting VIX (GD-013).

### Tests added (counts by type)

Counted on `staging` a6bc05d (collected tests; Sprint 0 baseline in parentheses).

| Type | Count | Notes |
|---|---|---|
| Python unit | 339 (122 to 461) | Includes the provider contract suites run against the fake, fixture, Massive, and Alpaca providers with `httpx.MockTransport` |
| Integration | 42 (3 to 45) | Schema, migrations, triggers, ingest and CLI idempotency, watchlist API, readiness against Postgres 17; 43 passed and 2 image tests skipped locally (they need a loaded image) |
| Smoke | 0 (3) | Existing suite; 3 of 3 pass on `develop` and `staging` with the Compose `migrate` service |
| UI unit (Vitest) | 0 (2) | No UI work this sprint |
| E2E | 0 | Placeholder until Sprint 4 |

### Coverage delta

Python line and branch coverage stayed at 96%: 431 statements at the end of Sprint 0, 3,146 statements with 101 missed on `staging` a6bc05d (unit and integration tests together, as `make coverage` runs them). Every per-directory threshold in `.coverage-thresholds.toml` passes, including `data` 85 and `api` 85. A mid-sprint run on the integrated tree measured 91%, because it had no Postgres; the Postgres-only paths in `data/db.py` and `data/ingest.py` are covered only when the integration tests run.

### What worked

- Running tasks in parallel in isolated worktrees, stacked on their dependencies (T03, T04, and T05 on T02; T06, T07, and T08 on T01), got all eight tasks to reviewable PRs in one pass.
- Shared contract suites in `tests/contract` made it cheap to prove the fixture, Massive, and Alpaca providers interchangeable.
- pytest-socket in `addopts` turned "no test touches the network" into a hard failure.
- Merging each stacked PR in a scratch worktree, with a script that auto-resolves TEST_PLAN rows and renumbers colliding IDs, made eight conflicting merges routine. Every merge ran checks, unit, contract, and Postgres integration tests locally before pushing.
- A local integration of all branches before writing the sprint-end docs found real defects that no single PR showed: the missing Compose `migrate` service (fixed in #122) and three T07/T08 integration fixes (GD-010).

### What did not work

- Merging was first denied by the permission system. That blocked issue closing, promotion, smoke on `staging`, and the tag until permission was granted. This came up only at the first merge, after all the work was done. Posting the implementation comments on #11 to #14 was also denied (GD-014).
- Dependabot bumped the Python base image to 3.15. That contradicts ADR-002's 3.12 pin and broke the image (#127). Dependabot updates need the same pin checks as code.
- gitleaks in CI scans every fetched branch, so one PR's fake test keys failed `lint-and-typecheck` on unrelated PRs (GD-011). One agent misread this as an npm audit failure.
- Parallel agents picked the same TEST_PLAN scenario IDs and the same new files (`api/security.py`), which created merge conflicts and duplicates (GD-009, GD-010).
- One agent skipped test-first (GD-006), and two used a different co-author trailer than the brief specified.
- Cross-cutting description items fell between tasks, because no task's acceptance criteria named them. Provider call recording was fixed late in #128 (GD-007); rate limiting on every adapter is still open (GD-008). Parallel tasks also defined the ingest symbol set twice, which surfaced a spec conflict (GD-013).

### What to change

- Confirm merge and tag-push permissions at sprint start, and record them as owner items before any work begins.
- Give each parallel task a reserved scenario-ID range, and assign every shared new module (for example `api/security.py`) to one task.
- Add a unit test that fails on duplicate TEST_PLAN scenario IDs.
- Run the local integration of all branches (checks, integration tests, `make up && make smoke`) before marking any stacked PR ready, not only at sprint end.
- Turn cross-cutting description requirements into explicit acceptance criteria in the task that owns the wiring.

## Sprint 2: Indicator Engine (work done 2026-11-15; S2-T10 and promotion merges pending)

All nine tasks are implemented, with green CI, in nine stacked PRs. None is merged: the agent's `gh pr merge` was denied again (docs/OWNER_CHECKLIST.md #25, GD-015). As a result, issues #19 to #27 are open and In Review with implementation comments, `develop` has not been promoted to `staging`, and the `sprint-2-complete` tag is not pushed. Everything below was measured on the integrated tip of the stack (the #139 branch, 67de23a).

### What was built

| Task | Issue | PR | Summary |
|---|---|---|---|
| S2-T01 | [#19](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/19) | #131 | Primitives: SMA, EMA, RMA, stdev, true range, ATR, RSI, OBV, percentile rank, linear-regression slope, confirmed pivots, ZigZag, weekly resample; stub modules and the package aggregator; numpy as a direct dependency |
| S2-T02 | [#20](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/20) | #137 | Supertrend per Factor 1 with band ratcheting, bars since flip, distance in ATR, weekly direction; 40-bar hand-computed fixture; TradingView parity harness (skipped pending owner exports) |
| S2-T03 | [#21](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/21) | #134 | SMA stack, slope, and cross events; MACD daily and weekly with signal cross and histogram runs; ADX with +DI and -DI |
| S2-T04 | [#22](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/22) | #135 | Regular and hidden, bullish and bearish divergences for RSI, MACD histogram, and OBV, daily and weekly, confirmed pivots only |
| S2-T05 | [#23](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/23) | #132 | Bollinger, %B, z-score, bandwidth and its rank, ATR% and its rank, HV20, squeeze and expansion flags |
| S2-T06 | [#24](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/24) | #133 | ZigZag leg selection, Fibonacci retracements and extensions, support and resistance clusters with strength, nearest levels, breakout and breakdown, 52-week high and low |
| S2-T07 | [#25](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/25) | #136 | Volume oscillator, relative volume, OBV slope sign, CMF, accumulation and distribution days, estimated order flow with `trades`, `intraday`, and `daily_estimate` quality |
| S2-T08 | [#26](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/26) | #138 | Indicator registry (56 indicators, 21 exempt names), truncation and perturbation properties with a negative control, determinism and synthetic dataset hashes, `scripts/validate-fixtures.sh` and `scripts/regen-golden.sh`, 200-ticker benchmark, duplicate-ID tests |
| S2-T10 | [#143](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/143) | #144 | Ripster EMA Clouds (Factor 12 clouds): five EMA clouds on `hl2`, stack, bars since the stack flip, the 8/9 pullback test, weekly 34/50 direction; hand-computed fixture with an independent derivation script; TradingView parity (skipped pending owner exports). Added after the sprint-end audit by the Ripster spec change (#142) |
| S2-T09 | [#27](https://github.com/mohnishbasha/stokeai-trading-supertrends/issues/27) | #139 | Pure `compute_snapshot` producing the canonical snapshot document; insert-only `indicator_snapshots` persistence with idempotent retry, conflict detection, and a config-hash check |

Supporting PR: #140 holds the sprint-end docs (this entry, the checklist, gate debt, owner item #25, and the spec audit).

### Spec sections updated

- `docs/PRD.md` section 17: A-16 to A-23 (primitive definitions, Supertrend edge cases, trend and momentum details, divergence windows, HV20 stdev kind, expansion rule, support and resistance clustering, order flow edge cases).
- `docs/ARCHITECTURE.md`: ADR-053 (primitives and the aggregator), ADR-054 (trend and momentum), ADR-055 (support, resistance, and Fibonacci), ADR-056 (registry and determinism harness; in #140 it also records the 10-significant-digit hash rule), ADR-057 (snapshot document and persistence); `indicator_snapshots` table note in section 5.
- `docs/TEST_PLAN.md`: 152 TS-IND scenarios Automated, TS-IND-021 and 022 Skipped pending owner files, TS-ING-003 Automated; section 6.3 now names `indicators/registry.py`. In #140, sections 7.1 items 1 and 7 describe the 10-significant-digit rounding instead of plain `repr`.
- `docs/SPRINT_PLAN.md`: Sprint 2 acceptance criteria ticked with their PRs; Sprint 2 checklist filled in.
- `docs/GATE_DEBT.md`: GD-015 to GD-017 added; GD-006, GD-009, and GD-012 updated.
- `docs/OWNER_CHECKLIST.md`: #25 (merge order) added.
- `docs/DESIGN.md`: audited, no change; Sprint 2 adds no UI.

### Tests added (counts by type)

Collected on the integrated tip, with Sprint 1's end in parentheses.

| Type | Count | Notes |
|---|---|---|
| Python unit | 180 (461 to 641) | Hand-computed fixtures, independent plain-Python references, and hypothesis properties for every indicator module |
| Golden | 7 (0 to 7) | New `tests/golden` suite: determinism hash, synthetic dataset hash, Supertrend hand fixture, TradingView parity (2 skipped pending owner files) |
| Integration | 5 (45 to 50) | Snapshot round-trip, idempotent retry, conflict, and config-hash refusal against Postgres 17 |
| Smoke | 0 (3) | 3 of 3 pass on the integrated tip with `make up` |
| UI unit (Vitest) | 0 (2) | No UI work this sprint |

`make coverage` with Postgres: 694 passed and 4 skipped (2 image tests that need a loaded image, 2 parity tests).

### Coverage delta

Python line and branch coverage went from 96% to 97%: 3,146 statements on Sprint 1's `staging`, now 4,430 statements with 112 missed. `indicators` is at 99% (1,133 statements) against its 95% threshold, and every per-directory threshold passes. Without Postgres the total reads 93%, because the snapshot and ingest database paths are covered only by integration tests.

### What worked

- Sprint 1's lessons applied: each task got a reserved TS-IND range and its own files, and T01 committed stub modules for every later module. Seven parallel tasks then produced no scenario-ID collisions.
- One shared brief (conventions, test-first commit order, the five commands, the PR body) kept nine agents consistent. Each of the eight implementation PRs shows its failing-test commit first (GD-006); T08 is itself a test task.
- Expected values came from independent references (plain-Python loops, and hand derivations committed beside the fixtures), never from the code under test.
- The registry test that fails on any unregistered public name found the `supertrend` function shadowed by its own module in the aggregator.
- Integrating the whole stack locally before the sprint-end docs ran coverage, image build, and smoke on the real combined tree.

### What did not work

- Merging was denied again, and Sprint 1's lesson ("confirm merge permission at sprint start") was not acted on before work began. The sprint ends with all code in review and four End Protocol steps blocked (GD-015).
- PRD ambiguity numbers (A-xx) and ADR numbers were not reserved, so parallel PRs both claimed A-16 and ADR-054. They were renumbered while integrating the stack.
- The first determinism hash used full-precision `repr` and differed between macOS and Linux CI. Fixed by rounding to 10 significant digits (ADR-056), but the TEST_PLAN text was found stale only in the spec audit.
- `make up` failed on the host because port 8080 was taken. `SUPERTRENDS_HOST_PORT` worked around it, but smoke's default URL did not follow the override.
- GD-003 and GD-013 were planned for Sprint 2 but had no task, so they slipped (GD-017).

### What to change

- Before any work in a sprint, test `gh pr merge` on a trivial docs PR. If it is denied, record the owner item on day one.
- Reserve ADR and PRD ambiguity number ranges per task, the same way as scenario IDs.
- Make `make smoke` default its base URL from `SUPERTRENDS_HOST_PORT`.
- Turn carried gate-debt items into acceptance criteria on a named task at sprint planning, so they are not left without an owner.

### Addendum: S2-T10 and the close-out (2026-11-15)

The owner merged #131 to #140, closing #19 to #27. The Ripster EMA Clouds spec change (#142) then added S2-T10 (#143) to Sprint 2. It was built test-first: the failing tests are in 0eda12e and the implementation in ca1a461, both in #144 with green CI. The agent's `gh pr merge` is still denied, so #144 and the promotion PR #145 wait on the owner (docs/OWNER_CHECKLIST.md #26). Smoke on `staging` and the `sprint-2-complete` tag follow those merges (GD-015).

- **Spec sections updated:** `docs/TEST_PLAN.md` TS-IND-133 to 146 Automated, with 141 and 142 Skipped pending the owner export. `docs/SPRINT_PLAN.md` S2-T10 acceptance ticked and the checklist re-run. `docs/GATE_DEBT.md` GD-015 updated and GD-018 added. `docs/OWNER_CHECKLIST.md` #25 done and #26 added. PRD A-24 and ADR-058 (from #142) were audited against the code and need no change.
- **Tests added:** 20 (18 unit and property tests in `tests/unit/indicators/test_ripster_clouds.py`, plus 2 golden parity tests, which are skipped). Collected totals are now 659 unit, 9 golden, and 50 integration tests.
- **Coverage delta:** the total is still 97 percent with Postgres (712 passed, 6 skipped; 4,561 statements). `indicators` is at 99 percent (1,264 statements), and `ripster_clouds.py` at 96 percent.
- **Smoke:** 3 of 3 on the #144 tip with `make image && make up`. Port 8080 was taken again, so `SUPERTRENDS_HOST_PORT=18080` and `SMOKE_BASE_URL` were both set by hand. The "What to change" item on the smoke default is still open.
- **What worked:** A spec change that adds a task to a sprint already marked complete fit the non-gating model cleanly. The checklist was re-run, and one row moved from unmet to met.
- **What did not:** The sprint-end docs were written before the scope was final, so they had to be revised. Merge permission is still the single blocker for closing out the sprint.
- **What to change:** When a spec PR adds a task to a past sprint, open that task's issue and its PR in the same session, so the sprint does not reopen days later.
