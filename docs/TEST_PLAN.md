# Super Trends Test Plan

Version: 1.0.0
Date: 2026-11-14
Status: Specification, living document. Scenarios start as `Deferred` and flip to `Automated` in the PR that adds the test (Sprint 0 rows are automated; see section 10).

Companion documents: `docs/PRD.md` (FR and NFR ids), `docs/ARCHITECTURE.md` (section numbers), `docs/SPRINT_PLAN.md` (task ids), `docs/DESIGN.md`.

Spec reference convention used in the tables below: `FR-2xx` means a PRD functional requirement group (FR-0xx Watchlist, FR-1xx Ingestion, FR-2xx Indicators, FR-3xx Scoring, FR-4xx Selection, FR-5xx Justification, FR-6xx Track record and backtest, FR-7xx UI, FR-8xx API / CLI / MCP, FR-9xx Operations). `NFR-nnn` is a PRD non-functional requirement. `A§n` is an ARCHITECTURE section: 1 System Overview, 2 Component Responsibilities, 3 Decision Log, 4 Data Flows, 5 Database Schema, 6 API Contract (6.1 HTTP, 6.2 CLI, 6.3 MCP), 7 Provider Interfaces, 8 Run State Machine and Atomic Publication, 9 Security Model, 10 Build and Deployment, 11 Observability, 12 Repository Structure, 13 Configuration. Where the PRD has not yet fixed an exact FR number, the group (for example `FR-3xx`) is used and the sprint task is the tie-breaker.

Super Trends output is general market analysis, not investment advice. This plan tests that the disclaimer travels with every pick; it makes no claim about market outcomes.

## Contents

1. Test strategy
2. Test pyramid
3. Coverage targets
4. Naming convention
5. Golden-fixture policy for indicators
6. No-look-ahead property test
7. Determinism test
8. Narrative tests
9. Smoke checklist used after every deploy
10. Test scenarios by feature area
11. Test infrastructure and maintenance
12. Manual QA checklist for release

---

## 1. Test strategy

### 1.1 Principles

1. **TDD is mandatory.** For every task: add the scenarios to this file first (status `Deferred`), write the failing test, confirm it fails for the right reason, implement, then flip the status to `Automated` in the same PR. The PR template carries the checkbox "Failing test written first".
2. **No test touches the network.** Providers and the LLM are mocked, faked, or replayed from recorded responses. CI runs the test step with outbound network blocked (container network `none` or an egress deny rule), so an accidental call fails loudly. A test that needs a real vendor is not a test in this plan.
3. **Synthetic fixture provider first.** The deterministic fixture provider (S1-T03: seeded geometric Brownian motion with regime switches, gaps, a split, and volume patterns; 12 synthetic tickers plus `SPY` and `QQQ` stand-ins; 3 years daily, 30 days of 5-minute bars) is the default data source for unit, integration, smoke, e2e, kind, and demo runs.
4. **Recorded responses are scrubbed and minimal.** Vendor response fixtures contain only the shape the adapter parses, with synthetic or scrubbed numbers, no API keys, no account data, and no real prices from a licensed feed.
5. **Vendor market data is never committed.** The one deliberate exception is the owner-provided TradingView parity export in `tests/golden/tradingview/` (see section 5), which the owner places locally and which is covered by an explicit repository decision recorded in `docs/OWNER_CHECKLIST.md`. If the owner decides it must not be public, the folder is git-ignored and the parity test stays `Skipped` in public CI and runs locally and in the private release pipeline.
6. **Math is tested harder than plumbing.** Silent math errors produce confident wrong picks, so indicators and scoring have the highest coverage thresholds, table-driven tests with one row per rule line, and golden and property tests on top.
7. **Specification rules are never weakened to pass a test.** If a test and the Signal Engine Specification disagree, the test is wrong or an ADR and owner checklist entry is written.
8. **Every fixed bug gets a regression test** in `tests/regression/`, written to fail first, committed with the fix, and never deleted.
9. **Honesty is testable.** Disclaimer presence, "hypothetical" labels on backtests, "small sample" labels, "estimated order flow" quality tags, and the "DEMO DATA" banner each have scenarios.

### 1.2 What is tested where

| Concern | Primary test type | Why |
|---|---|---|
| Indicator formulas | Golden plus property | Exact expected values and invariants |
| Factor scoring rules | Unit (table-driven) plus property | One row per rule line, both signs, boundaries |
| Weights, composite, confidence, selection | Unit plus determinism | Deterministic, pure functions |
| Atomic publication, append-only tables, advisory lock | Integration with Postgres | Needs real transactions and triggers |
| Provider adapters | Contract plus recorded fixtures | Same suite for fixture, Massive, and the alternate provider |
| HTTP API shapes and errors | Contract (schema based) plus integration | `docs/openapi.json` is the contract |
| UI behavior | vitest component tests plus Playwright e2e | Every state, every user story |
| Deployed system | Smoke (one suite for Compose, kind, Stoke) | Cheap, run after every deploy |
| Narrative safety | Unit, narrative eval, recorded responses | LLM output is untrusted text |

### 1.3 Environments

| Environment | Data | Provider | LLM | Used for |
|---|---|---|---|---|
| Unit and property | In-memory arrays and DataFrames | none | none | `make test` |
| Integration | Postgres via testcontainers | fixture or mocked HTTP | mock server | `make coverage`, CI `integration-tests` |
| Compose (`make up`) | Fixture dataset | fixture | `llm-mock` | smoke, e2e |
| Demo (`make demo`) | Synthetic, 60 replayed days | fixture | `llm-mock` | `make demo-verify` |
| kind | Fixture dataset | fixture | `llm-mock` | `kind-e2e`, Helm tests, smoke |
| Stoke staging | Fixture first, then real provider after the owner creates the key secret | fixture then configured | in-cluster gateway | smoke, owner review |

---

## 2. Test pyramid

```
                      /\
                     /  \      Manual QA (section 12): release only
                    /----\
                   / Smoke \    7 checks, any deployment, after every deploy
                  /--------\
                 /   E2E    \   Playwright, one flow per user story
                /------------\
               / Contract     \ OpenAPI schema, MCP schemas, provider contract suite
              /----------------\
             /   Integration    \ Real Postgres, mocked providers and LLM
            /--------------------\
           / Golden and Property  \ Indicator and factor math, invariants, no look-ahead
          /------------------------\
         /          Unit            \ Pure logic, table-driven rules, components
        /----------------------------\
```

The base is wide on purpose: the product's risk sits in pure computation. Roughly: 60 percent unit, 15 percent golden and property, 12 percent integration, 6 percent contract, 5 percent e2e, 2 percent smoke by test count.

| Layer | Tool | Location | Runs in | Typical runtime |
|---|---|---|---|---|
| Unit (Python) | pytest | `tests/unit/` | `make test`, CI `unit-tests` | under 60 s |
| Unit (UI) | vitest, Testing Library | `ui/src/**/*.test.tsx` | `make test`, CI `unit-tests` | under 60 s |
| Property | pytest with hypothesis | `tests/unit/` (files named `*_property.py`) | `make test` | under 120 s (bounded examples) |
| Golden | pytest | `tests/golden/` | `make test` | under 30 s |
| Integration | pytest with testcontainers (Postgres) | `tests/integration/` | `make coverage`, CI `integration-tests` | under 5 min |
| Contract | pytest, schemathesis or jsonschema against `docs/openapi.json`; provider contract suite | `tests/integration/contract/` | CI `integration-tests` | under 2 min |
| E2E | Playwright | `ui/tests/e2e/` | CI `e2e-tests` against `make up` | under 10 min |
| Smoke | pytest | `tests/smoke/` | `make smoke` against `SMOKE_BASE_URL` | under 3 min |
| Narrative eval | pytest, `make narrative-eval` | `tests/narrative_eval/` | CI (recorded), manual (live) | under 30 s recorded |
| Regression | pytest, vitest | `tests/regression/` | every CI run | grows over time |
| Coverage | pytest-cov, vitest coverage, `scripts/check_coverage.py` | n/a | `make coverage` | n/a |
| Accessibility | axe via Playwright | `ui/tests/e2e/a11y/` | CI `e2e-tests` | under 3 min |
| Performance | pytest benchmark test | `tests/unit/test_perf_budget.py` | CI, 2 cores | under 90 s |

---

## 3. Coverage targets

Values are copied verbatim from `.coverage-thresholds.toml`. `make coverage` fails if any package is below its threshold; the Definition of Done forbids dropping below them.

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

Additional rules beyond line coverage:

- **Rule coverage:** every rule line in the Signal Engine Specification has at least one test row (sprint 3 checklist). Section 10 tracks this by scenario id.
- **Branch coverage:** `indicators`, `scoring`, and `selection` are measured with branch coverage on (`--cov-branch`).
- **Registry coverage:** a test fails if a public indicator function is missing from the no-look-ahead registry, and another fails if a factor id in `config/scoring.yaml` is not registered (and the reverse).
- **No threshold lowering.** Thresholds only go up. A change that lowers one needs an ADR and owner approval.

---

## 4. Naming convention

Scenario and test names follow `{type}_{module}_{operation}_{scenario}_{outcome}`, lower snake case, ASCII only.

| Part | Meaning | Values |
|---|---|---|
| type | Test layer | `unit`, `prop`, `golden`, `it`, `contract`, `e2e`, `smoke`, `eval`, `reg` |
| module | Package or area | `supertrend`, `sma`, `macd`, `ingest`, `selection`, `api`, `ui_today`, and so on |
| operation | Function or action under test | `compute`, `score`, `rank`, `publish`, `render` |
| scenario | The input condition | `weekly_conflict`, `flip_5_bars_ago`, `empty_side` |
| outcome | Expected result | `score_minus_15`, `rejected`, `returns_422` |

Examples:

```
unit_supertrend_score_fresh_flip_5_bars_adds_15
unit_supertrend_score_fresh_flip_6_bars_adds_0
prop_indicators_all_truncation_does_not_change_past_values
golden_supertrend_tradingview_parity_within_0_01
it_runs_publish_midrun_kill_previous_run_stays_latest
contract_api_post_runs_without_token_returns_401
e2e_us001_today_shows_three_buys_two_sells
smoke_recommendations_latest_at_most_3_buys_2_sells
eval_narrative_numeric_guard_unmatched_number_rejected
reg_142_split_on_run_day_refetches_history
```

Mapping to the Appendix G forms: unit tests are `test_{module}_{function}_{scenario}_{expected_outcome}` (file functions carry the `test_` prefix required by pytest, scenario ids here omit it), integration is `it_{component}_{operation}_{scenario}`, smoke is `smoke_{feature}_{minimal_assertion}`, e2e is `e2e_{user_story_id}_{scenario}`, regression is `regression_{gh_issue_number}_{what_was_broken}`. The scenario names in section 10 use the five-part form for unit, property, golden, and integration tests so a reader can see the outcome without opening the test. Smoke, e2e, and regression names keep their Appendix G forms.

Rules:

- A scenario id (for example `TS-IND-001`) maps to exactly one test function or one parametrized test with a documented id per row; the test docstring starts with the scenario id.
- Table-driven tests name each row after the rule line: `unit_supertrend_score[base_up]`.
- Python file layout: `tests/unit/indicators/test_supertrend.py`, and so on, mirroring `src/supertrends/`.

---

## 5. Golden-fixture policy for indicators

### 5.1 Fixture kinds

| Kind | Source | Location | Committed |
|---|---|---|---|
| Hand-computed | Written by hand from the formulas (for example the 40-bar Supertrend case with both flip directions and band ratcheting, and the Ripster EMA Clouds case with a stack flip in each direction) | `tests/golden/handcomputed/` | Yes |
| Synthetic dataset | Output of the fixture provider with a fixed seed | generated at test time; hash in `tests/golden/synthetic_dataset.sha256` | Hash only |
| Expected-output files | Indicator and factor outputs for the synthetic dataset | `tests/golden/expected/` | Yes |
| TradingView parity | CSV exports provided by the owner: OHLCV plus the built-in Supertrend (10, 3) columns, two tickers, daily chart | `tests/golden/tradingview/` | Owner decision (see 1.1 item 5) |
| Recorded provider responses | Scrubbed, minimal | `tests/fixtures/providers/` | Yes |

### 5.2 Tolerances

| Indicator group | Tolerance | Source |
|---|---|---|
| Primitives (sma, ema, rma, stdev, true_range, atr, rsi, obv, percentile_rank, linreg_slope) | 1e-9 | S2-T01 |
| SMA, MACD, ADX | 1e-6 | S2-T03 |
| Fibonacci levels on constructed fixtures | 1e-6 | S2-T06 |
| Supertrend line versus TradingView export | 0.01 per bar after a 100-bar warm-up | S2-T02 |
| Supertrend direction versus TradingView export | exact on every bar after warm-up | S2-T02 |
| Composite contributions sum | 1e-9 | S3-T05 |
| Weights sum after adjustment | exactly 100 within 1e-9 | S5-T05 |

### 5.3 Warm-up

Indicator arrays return NaN during warm-up. Golden comparisons skip NaN positions on both sides and assert that the NaN positions match (a value where the reference has NaN, or the reverse, fails). The TradingView parity comparison ignores the first 100 bars. The hand-computed Supertrend case compares from the first defined bar, including the "atr[t-1] undefined gives direction -1" warm-up rule.

### 5.4 Sign convention at the boundary

TradingView's `ta.supertrend` returns direction with the opposite sign (negative means up). The parity test converts at the import boundary only (one function, `tv_direction_to_internal`, unit tested). Nothing inside `src/supertrends/` knows the TradingView convention. A test asserts that internal direction is always +1 (up) or -1 (down) after warm-up.

### 5.5 Regeneration rules

1. Golden files change only in a PR that also changes `scoring.version` or fixes a proven math bug.
2. The PR description shows the before and after values and the reason.
3. Regeneration uses a named script (`scripts/regen-golden.sh`) that refuses to run without `--reason "..."` and writes the reason into the PR body template; it never overwrites TradingView exports or hand-computed files.
4. `scripts/validate-fixtures.sh` runs in CI: recorded provider responses still parse with the current provider models, and the synthetic dataset hash matches the committed hash.
5. The determinism hash (section 7) is regenerated only together with the golden files and under the same rules.
6. Hand-computed fixtures are never regenerated from code. If one fails, either the code or the hand computation is wrong and the discrepancy is explained in the PR.

### 5.6 TradingView parity file status

Until the owner supplies the CSV files, the parity test is `Skipped` with the visible reason "TradingView export not yet provided (owner checklist item open)". It is a release blocker at S9-T04: it must be passing, not skipped, for v1.0.0. The same applies to the Ripster EMA Clouds parity test (TS-IND-141, TS-IND-142), which uses the same owner export (the export also carries the Ripster EMA Clouds plots at default settings).

---

## 6. No-look-ahead property test

Requirement: NFR-007. An indicator value for bar t uses only data up to and including bar t. Pivots confirm 5 bars late, fundamentals are point-in-time, and backtest entries use the next session's open.

### 6.1 Design

For every public indicator and every factor, using hypothesis-generated OHLCV series (valid bars only: low <= open, close <= high; positive volume; lengths from 300 to 700 bars; gaps and zero-range bars included by strategy):

```
full  = f(bars)                       # computed on the full series, length N
for each cut t in a sampled set (t drawn by hypothesis, plus fixed cuts 250, N-1, N-6):
    trunc = f(bars[:t])               # computed with all future bars removed
    lag   = confirm_lag(f)            # 0 for ordinary indicators, 5 for pivots, 5 for divergence and S/R pivot inputs
    assert trunc[: t - lag] == full[: t - lag]     # NaN positions equal, values equal to 1e-12
```

Properties that must hold for all registered functions:

1. **Truncation invariance.** Values at indexes below `t - confirm_lag` are identical whether or not future bars exist.
2. **Perturbation invariance.** Replacing every bar after t with arbitrary random bars does not change values at index <= t - confirm_lag.
3. **Output length.** Output length equals input length; warm-up is NaN.
4. **Pivot confirmation.** `pivots(width=w)` never marks a pivot fewer than `w` bars from the end of the array it was given; a pivot at p is absent from `f(bars[:p + w])` and present in `f(bars[:p + w + 1])` when it is a real extreme.
5. **Rolling windows are trailing.** `percentile_rank`, `bbw_rank`, `atr_pct_rank` use only trailing windows.
6. **Weekly resampling.** The in-progress week is never treated as complete: weekly values for a week ending Friday use only bars up to that Friday, and the partial current week uses only bars up to t.

### 6.2 Factor level

For each of the 12 factors, `factor.compute(snapshot_at(t), ctx_at(t))` must equal the same call made on data truncated to bars up to t. The test builds the snapshot from `bars[:t]` and from `bars` followed by slicing at t, and compares score, evidence, and quality byte for byte.

### 6.3 Registry rule

All public indicator functions are registered in `src/supertrends/indicators/registry.py` with their `confirm_lag` (public non-indicator names are listed in `EXEMPT` with a reason). A test enumerates `supertrends.indicators.__all__` and fails if any public function is not registered. Adding an indicator without registering it fails CI.

### 6.4 Negative control (the judge must be able to fail)

A deliberately leaky indicator (for example one that centers a moving average, or uses `x[t+1]`) is injected in a test and the harness must flag it. The same leaky indicator wired into the backtest engine must be caught by the backtest no-look-ahead check (S6-T03 AC).

### 6.5 Point-in-time rules

| Rule | Test |
|---|---|
| Fundamentals rows carry `known_at`; a query as of date d never returns a row with `known_at > d` | integration plus unit |
| Earnings dates as of d are those known at d | unit |
| Backtest entry price at day t is the open of session t+1 | unit plus integration |
| Backtest day t uses bars up to t only | property |
| Outcome horizons are computed only after the horizon session has closed | unit |

### 6.6 Settings

`hypothesis` profile `ci`: 100 examples per property, deadline disabled for the benchmark-sensitive ones, `derandomize=True` in CI so failures reproduce; profile `nightly`: 1000 examples, run by `nightly.yml`. Failing examples are stored in the hypothesis database directory which is git-ignored, and each failure produces a regression test with the shrunk example inlined.

---

## 7. Determinism test

Requirement: NFR-002. Same bars plus the same config hash produce byte-identical factor scores and ranking. The LLM never influences a score.

### 7.1 Design

1. **Hash test (committed).** Compute all indicator outputs, all factor results, composites, display scores, confidence, bands, and the selection for the synthetic dataset on a fixed as-of date. Serialize with canonical JSON (sorted keys, NaN as null, floats rounded to 10 significant digits and then formatted by `repr`, no locale; ADR-056), hash with sha256, and compare to `tests/golden/determinism.sha256`. Regeneration follows the golden policy (5.5).
2. **Double-run test.** Run the full scoring pipeline twice in one process and twice in separate processes (`subprocess`, different `PYTHONHASHSEED`, different `TZ`, different `LC_ALL`); the serialized outputs must be byte-identical.
3. **Order independence.** Shuffle the ticker processing order and the input row order of a ticker's bars (sorted before use); the ranking and scores are unchanged.
4. **Live path.** `supertrends run daily` on the fixture dataset twice from clean databases publishes identical recommendations (ticker, side, scores, contributions, rank), compared after removing run ids and timestamps.
5. **LLM isolation.** Run the pipeline with the narrative provider set to `template`, to a mock that returns valid text, to a mock that returns invalid text, and to an endpoint that times out. Scores, ranks, and selections are byte-identical across all four. A static test (AST scan) asserts that no module under `scoring/` or `selection/` imports from `narrative/`.
6. **Config hash.** The hash is sha256 of the canonical JSON and is stable across key order; changing one weight changes the hash.
7. **Cross-architecture.** The hash test runs on `linux/amd64` (CI) and `linux/arm64` (CI image job or kind on ARM runner). Floating point differences are avoided by avoiding fused operations in the pure Python reference path and by rounding stored scores to a fixed number of decimals at the persistence boundary; if arm64 and amd64 hashes differ, that is a bug to fix, not a tolerance to add. The indicator hash rounds floats to 10 significant digits (ADR-056): full-precision `repr` differed between macOS arm64 and Linux amd64 in the last bits of a few recursive indicators. That rounding is a fixed canonical form shared with the snapshot document (ADR-057), not a comparison tolerance, and it is never widened to make a hash pass.

---

## 8. Narrative tests

Requirement: NFR-012, Justification section of the Signal Engine Specification, Security Guidelines (LLM output is untrusted text).

| Area | What is tested |
|---|---|
| Token budget | The rendered prompt for each of the 30 evidence documents in `tests/narrative_eval/` is at most 900 prompt tokens (counted with the tokenizer configured for the budget check, with a conservative character-based fallback); completion is capped at 220 tokens in the request; a CI test fails if any fixture exceeds the budget; a metric `supertrends_narrative_tokens{kind}` is asserted to be emitted |
| Prompt content | The prompt contains only numbers and enumerated labels from the evidence document; a provider-supplied string such as a company name never appears (prompt injection control) |
| Numeric guard | Every number extracted from the narrative (integers, decimals, percentages, ordinals excluded by rule, dates handled by rule) must match a value in the evidence document within rounding; any unmatched number rejects the narrative |
| Forbidden words | "guaranteed", "will", "can't lose" (and the apostrophe variant), plus advice on position size, options, leverage; price targets beyond `next_target` |
| Length | 3 to 5 sentences |
| Order | Supertrend state first, then the two largest positive contributions, then the largest opposing factor, then the invalidation level (template path asserts exact order; LLM path asserts by recorded responses) |
| Retry and fallback | On rejection, timeout (8 seconds), or endpoint error: one retry at temperature 0, then the deterministic template narrative; the stored record has `source: llm` or `template`, the model name, and the prompt version |
| Run safety | A narrative failure never fails the run and never changes a score, rank, or selection |
| Rendering | LLM text is rendered as plain text, never HTML or Markdown with links |
| Eval set | 30 evidence documents cover every band, both sides, every flag; recorded-response test in CI; live `make narrative-eval` reports acceptance rate, mean tokens, and latency, with a target of at least 90 percent acceptance on the Stoke model (live run is manual, see TS-NAR-014) |

Detailed scenarios are in section 10.8.

---

## 9. Smoke checklist used after every deploy

The smoke suite lives in `tests/smoke/`, is driven by `SMOKE_BASE_URL`, and is the same suite for Compose, kind, and Stoke. Write endpoints use the token from `SUPERTRENDS_API_TOKEN` (smoke reads it from the environment, never prints it).

### 9.1 Checklist

| # | Check | Pass condition | Endpoint or command |
|---|---|---|---|
| 1 | Health and readiness | `/healthz` and `/readyz` return 200; reported version equals the deployed version | `curl -fsS $BASE/healthz`, `curl -fsS $BASE/readyz`, `curl -fsS $BASE/api/v1/status \| jq .version` |
| 2 | Latest recommendations | At most 3 buys and at most 2 sells; each pick has evidence, narrative, invalidation, and the disclaimer | `curl -fsS $BASE/api/v1/recommendations/latest \| jq '(.buys\|length), (.sells\|length)'` |
| 3 | One ticker analysis | 12 factors (or fewer with a stated reason); contributions sum to the composite within 1e-6 | `curl -fsS $BASE/api/v1/tickers/AAA/analysis` (fixture ticker; use a real watchlist ticker on a real provider) |
| 4 | Watchlist round trip | Add then remove with the token succeeds; the same calls without the token are rejected (401) | `curl -X POST -H "Authorization: Bearer $T" $BASE/api/v1/watchlist/items`, then `curl -X DELETE -H "Authorization: Bearer $T" $BASE/api/v1/watchlist/items/{symbol}` |
| 5 | Triggered run | `POST /api/v1/runs` reaches `published`, or reports "market closed" on a non-trading day | `curl -X POST -H "Authorization: Bearer $T" $BASE/api/v1/runs`, then poll `GET /api/v1/runs/{id}` |
| 6 | Track record | `GET /api/v1/track-record` responds with sample sizes | `curl -fsS $BASE/api/v1/track-record \| jq .` |
| 7 | UI root | `/` loads, shows the as-of date and the disclaimer | `curl -fsS $BASE/ \| grep -i disclaimer` plus the Playwright smoke page check |

Additional post-deploy checks (manual or scripted, not in the seven-item suite):

- A. License notice: `/api/v1/status` and the UI footer show "Copyright Serverless Ventures LLC. Noncommercial use only."
- B. Response headers on `/`: CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
- C. `/metrics` responds and contains `supertrends_run_state_total`.
- D. No secret appears in `kubectl logs` output (grep for the token prefix; output of the grep is not printed).

### 9.2 Local Compose (`make up && make smoke`)

```bash
make image
make up                      # app + Postgres, waits for healthy
make smoke                   # SMOKE_BASE_URL defaults to http://localhost:8080
make down
```

Pass: `pytest tests/smoke` exits 0 with 7 passed. Run after every sprint and before every merge to `staging`.

### 9.3 kind

```bash
make kind-up image kind-load helm-install helm-test
kubectl -n supertrends port-forward svc/supertrends 8080:8080 &
make smoke
make helm-uninstall kind-down
```

Pass: `helm test` reports all test pods succeeded; `make smoke` exits 0; `kubectl -n supertrends get pods` shows API and Postgres Ready, and the migration Job completed. CI job `kind-e2e` automates this from Sprint 3.

### 9.4 Stoke staging (owner or runner with access; cluster only)

```bash
flux get helmrelease -n supertrends-stage            # Ready=True, expected chart version
kubectl -n supertrends-stage get pods                # all Ready, arm64 nodes
helm test supertrends -n supertrends-stage --logs
make smoke SMOKE_BASE_URL=https://<staging-host>      # host from the private values patch, never committed
```

Then: trigger a run on the fixture provider, confirm `published`; after the owner creates the provider key secret, trigger a run on the real provider and confirm `published`, picks, and dashboard panels populated. Record the image digest tested. Rollback is verified once per release (`flux suspend`, `helm rollback`, resume, smoke again). Hostnames and cluster identifiers are never pasted into public files.

### 9.5 Failure handling

A failed smoke item blocks promotion. The deploy is rolled back (`helm rollback` or Flux revert), a `type:bug` issue is filed with the failing check number, and a regression test is added if the cause was a code defect.

---

## 10. Test scenarios by feature area

Status values: `Deferred` (test not yet written), `Automated` (test exists and passes in CI), `Skipped: <reason>; manual: <step>` (cannot be automated yet). Every row starts as `Deferred` because no code exists yet. A scenario row is flipped to `Automated` in the PR that adds its test. At S9-T04 no `Deferred` rows may remain.

Id prefixes: WL watchlist, ING ingestion and data, IND indicators, SCR scoring, REG regime and weights, CMP composite and confidence, SEL selection, NAR narrative, TRK track record, BKT backtest, API, UI, CLI, MCP, OPS operations, DEP deployment, SEC security, A11Y accessibility.

### 10.1 Watchlist (TS-WL)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-WL-001 | `unit_watchlist_seed_load_14_groups_200_symbols_succeeds` | Loading `config/watchlist.seed.yaml` yields 14 groups and 200 unique symbols | FR-0xx, S1-T07 | Automated |
| TS-WL-002 | `unit_watchlist_seed_multi_group_symbol_stored_once_three_memberships` | A symbol listed in three groups is one ticker row with three memberships | FR-0xx, A§5 | Automated |
| TS-WL-003 | `it_watchlist_seed_unresolvable_symbol_marked_unresolved_with_reason` | An unresolvable seed symbol is recorded `unresolved` with a reason, excluded, never substituted | FR-0xx, S1-T07 | Automated |
| TS-WL-004 | `unit_watchlist_seed_needs_review_symbol_flagged_not_scored` | A `needs_review` symbol is listed but not scored | FR-0xx | Automated |
| TS-WL-005 | `unit_watchlist_seed_vix_not_scored_crypto_not_ingested` | VIX is kept but not scored; the crypto file is kept but not ingested | FR-0xx | Automated |
| TS-WL-006 | `contract_api_watchlist_add_ticker_301_returns_422` | The 300-ticker hard cap rejects the 301st ticker | FR-0xx, A§6.1 | Automated |
| TS-WL-007 | `unit_watchlist_symbol_regex_rejects_lowercase_and_overlong_returns_422` | Symbols must match `^[A-Z][A-Z0-9.\-]{0,9}$` | FR-0xx, A§9 | Automated |
| TS-WL-008 | `it_watchlist_benchmarks_spy_qqq_ingested_even_if_removed` | Removing SPY or QQQ from the watchlist still ingests them as benchmarks | FR-0xx, FR-1xx | Automated |
| TS-WL-009 | `contract_api_watchlist_write_without_token_returns_401` | POST, PUT, DELETE on the watchlist need the bearer token | FR-0xx, A§9 | Automated |
| TS-WL-010 | `contract_api_watchlist_read_without_token_returns_200` | GET watchlist endpoints need no token | FR-0xx | Automated |
| TS-WL-011 | `it_watchlist_add_unknown_symbol_provider_validation_returns_422_with_message` | A symbol the provider does not know is rejected with an inline message | FR-0xx, US-004 | Automated |
| TS-WL-012 | `unit_watchlist_group_crud_create_rename_delete_group_keeps_tickers` | Deleting a named group removes memberships, not tickers | FR-0xx | Automated |
| TS-WL-013 | `unit_watchlist_add_duplicate_symbol_returns_409_no_second_row` | Adding an existing symbol returns 409 `already-exists` (A§6.1) and writes no second row | FR-0xx | Automated |
| TS-WL-014 | `unit_watchlist_validation_fixture_provider_permissive_regex_accepts_synthetic` | The fixture provider uses the permissive regex path | FR-0xx, S1-T07 | Automated |
| TS-WL-015 | `it_watchlist_seed_second_start_does_not_reseed_or_duplicate` | Seeding runs on first start only and is idempotent | FR-0xx | Automated |

### 10.2 Ingestion and data (TS-ING)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-ING-001 | `unit_fixture_provider_generate_same_seed_identical_bars` | Same seed gives byte-identical bars | FR-1xx, S1-T03 | Automated |
| TS-ING-002 | `unit_fixture_provider_dataset_has_trending_ranging_reversing_tickers` | By construction the dataset includes one trending, one ranging, one reversing ticker (asserted via ADX and flips) | FR-1xx, S1-T03 | Automated |
| TS-ING-003 | `golden_fixture_provider_dataset_hash_matches_committed_hash` | Synthetic dataset hash equals `tests/golden/synthetic_dataset.sha256` | FR-1xx, A§12 | Automated |
| TS-ING-004 | `contract_provider_fixture_passes_shared_contract_suite` | Fixture provider passes the provider contract suite | FR-1xx, A§7 | Automated |
| TS-ING-005 | `contract_provider_massive_recorded_passes_shared_contract_suite` | Massive adapter passes the contract suite on recorded scrubbed responses | FR-1xx, A§7 | Automated |
| TS-ING-006 | `contract_provider_alternate_recorded_passes_shared_contract_suite` | Alternate provider adapter passes the contract suite | FR-1xx, S1-T05 | Automated |
| TS-ING-007 | `unit_provider_registry_unknown_name_fails_startup_with_clear_message` | An unknown provider name fails at startup | FR-1xx, A§7 | Automated |
| TS-ING-008 | `unit_provider_registry_env_switch_changes_active_provider_without_code_change` | `SUPERTRENDS_MARKET_PROVIDER` selects the provider | FR-1xx, S1-T05 | Automated |
| TS-ING-009 | `it_provider_massive_429_sequence_retried_then_succeeds` | A 429 sequence backs off with jitter and succeeds | FR-1xx, S1-T04 | Automated |
| TS-ING-010 | `unit_provider_rate_limiter_token_bucket_respects_calls_per_minute` | The token bucket never exceeds the configured calls per minute (fake clock) | FR-1xx, S1-T04 | Automated |
| TS-ING-011 | `it_provider_massive_5xx_exponential_backoff_with_jitter_bounded` | 5xx retries are bounded in count and backoff | FR-1xx | Automated |
| TS-ING-012 | `it_provider_massive_response_cache_same_endpoint_params_one_call` | Responses are cached by (endpoint, params) | FR-1xx | Automated |
| TS-ING-013 | `it_provider_calls_recorded_without_api_key_in_path_or_params` | Every call is stored in `provider_calls` with no secret | FR-1xx, NFR-009 | Automated |
| TS-ING-014 | `unit_provider_massive_no_key_reports_unconfigured_app_starts_on_fixture` | No key means `unconfigured` and fixture fallback | FR-1xx, S1-T04 | Automated |
| TS-ING-015 | `unit_provider_massive_base_url_configurable_legacy_host_accepted` | Base URL setting accepts `api.massive.com` and `api.polygon.io` | FR-1xx | Automated |
| TS-ING-016 | `it_ingest_second_run_is_idempotent_no_row_changes` | Re-running ingestion changes nothing | FR-1xx, S1-T06 | Automated |
| TS-ING-017 | `it_ingest_incremental_fetch_starts_from_last_stored_bar` | Only bars after the last stored bar are requested | FR-1xx | Automated |
| TS-ING-018 | `it_ingest_split_detected_triggers_full_adjusted_history_refetch` | A new split refetches the full history for that ticker | FR-1xx, S1-T06 | Automated |
| TS-ING-019 | `unit_ingest_holiday_does_not_mark_tickers_stale` | A market holiday never produces `stale` | FR-1xx | Automated |
| TS-ING-020 | `unit_ingest_half_day_session_treated_as_complete_session` | Half days (for example the day after Thanksgiving) are valid sessions | FR-1xx, S9-T02 | Automated |
| TS-ING-021 | `unit_quality_gap_more_than_3_sessions_marks_degraded` | A gap above 3 sessions is `degraded` | FR-1xx | Automated |
| TS-ING-022 | `unit_quality_latest_bar_older_than_last_session_marks_stale` | Latest daily bar older than the last completed session is `stale` | FR-1xx, US-020 | Automated |
| TS-ING-023 | `unit_quality_fewer_than_250_bars_marks_insufficient_history` | Below 250 daily bars the ticker is excluded | FR-1xx | Automated |
| TS-ING-024 | `unit_quality_exactly_250_bars_is_scoreable` | Boundary: 250 bars scores | FR-1xx | Automated |
| TS-ING-025 | `unit_resample_weekly_week_ending_friday_ohlcv_correct` | Weekly bars: open first, high max, low min, close last, volume sum | FR-1xx, FR-2xx | Automated |
| TS-ING-026 | `unit_resample_weekly_holiday_friday_uses_last_session_of_week` | A holiday Friday closes the week on Thursday | FR-1xx | Automated |
| TS-ING-027 | `unit_calendar_xnys_session_times_dst_boundaries_correct` | Exchange time handling across DST in America/New_York | FR-1xx | Deferred |
| TS-ING-028 | `it_ingest_grouped_daily_one_call_per_date_for_whole_watchlist` | Daily updates use the grouped endpoint, per-ticker calls only for backfill | FR-1xx, S1-T04 | Automated |
| TS-ING-029 | `it_schema_migrations_upgrade_head_and_downgrade_base_succeed` | Alembic up and down on an empty database | A§5, S1-T01 | Automated |
| TS-ING-030 | `it_schema_recommendations_update_rejected_by_append_only_trigger` | UPDATE on `recommendations` is rejected | A§5, NFR-006 | Automated |
| TS-ING-031 | `it_schema_factor_scores_delete_rejected_by_append_only_trigger` | DELETE on `factor_scores` is rejected | A§5 | Automated |
| TS-ING-032 | `it_schema_bars_composite_primary_key_rejects_duplicate_ticker_ts` | Bars have a (ticker, ts) primary key | A§5 | Automated |
| TS-ING-033 | `it_retention_intraday_older_than_90_days_deleted_daily_kept` | Retention deletes old intraday, never daily bars | FR-9xx, S6-T06 | Deferred |
| TS-ING-034 | `it_retention_never_deletes_rows_in_a_recommendation_evidence_window` | Evidence-window rows are protected | FR-9xx, S6-T06 | Deferred |
| TS-ING-035 | `it_backup_pg_dump_restore_roundtrip_preserves_recommendations` | `supertrends db backup` then restore round-trips | FR-9xx, S6-T06 | Deferred |
| TS-ING-036 | `unit_ingest_delisted_ticker_mid_history_marked_stale_not_scored` | A ticker whose bars stop is excluded and flagged | FR-1xx, S9-T02 | Deferred |
| TS-ING-037 | `unit_ingest_adjusted_prices_used_for_returns_across_split` | Adjusted series gives continuous returns across a split | FR-1xx | Deferred |
| TS-ING-038 | `contract_provider_fundamentals_recorded_passes_shared_contract_suite` | `FundamentalsProvider` contract on recorded fixtures | FR-1xx, A§7 | Deferred |
| TS-ING-039 | `it_provider_capability_flags_intraday_trades_adjusted_reported_correctly` | Capability flags are exposed and respected | FR-1xx, A§7 | Deferred |
| TS-ING-040 | `unit_fixtures_validate_script_recorded_responses_match_provider_models` | `scripts/validate-fixtures.sh` fails on a stale recorded response | A§12, Appendix G | Deferred |
| TS-ING-041 | `contract_provider_fake_passes_shared_contract_suite` | A fake provider (full and reduced capabilities) passes the shared market and fundamentals contract suite in `tests/contract/provider_contract.py` | FR-1xx, A§7, S1-T02 | Automated |
| TS-ING-042 | `unit_provider_contract_suite_violating_provider_detected_assertion_fails` | The suite fails a provider with unsorted bars, out-of-range bars, or a missing `CapabilityNotSupported` | A§7, S1-T02 | Automated |
| TS-ING-043 | `unit_provider_registry_mixed_vendors_market_and_fundamentals_selected_independently` | Market and fundamentals providers from different vendors can be combined; a registered name with no implementation fails with a clear `ConfigError` | A§7.4, S1-T02 | Automated |
| TS-ING-044 | `unit_provider_errors_derive_from_provider_error_and_validate_bar_rejects_invalid_rows` | Error hierarchy (A§7.3) and OHLC validation raising `ProviderDataError` | A§7.2, A§7.3, S1-T02 | Automated |
| TS-ING-045 | `it_schema_recommendations_delete_rejected_by_append_only_trigger` | DELETE on `recommendations` is rejected; `entry_price` may be set once from NULL | A§5.3, S1-T01 | Automated |
| TS-ING-046 | `it_schema_factor_scores_update_rejected_by_append_only_trigger` | UPDATE on `factor_scores` is rejected with SQLSTATE `P0001` naming the table | A§5.3, S1-T01 | Automated |
| TS-ING-047 | `it_schema_every_append_only_table_has_the_reject_trigger` | The seven append-only tables, `recommendations`, and `runs` carry their triggers | A§5.3, S1-T01 | Automated |
| TS-ING-048 | `it_schema_runs_forward_transition_allowed_and_backward_rejected` | The `runs` trigger allows only section 8 edges; terminal runs are immutable except `superseded_by` once; DELETE rejected; one active run | A§5.1, A§8, S1-T01 | Automated |
| TS-ING-049 | `it_schema_watchlist_cap_rejects_301st_item_at_commit` | The 300-item cap trigger; a symbol in three groups is stored once | A§5.1, ADR-019, S1-T01 | Automated |
| TS-ING-050 | `it_schema_models_match_migrated_database` | Model metadata equals the migrated schema (no drift), including the `backtests` schema | A§5.4, S1-T01 | Automated |
| TS-ING-051 | `it_schema_migrations_at_head_false_when_behind_and_true_after_migrate` | `migrations_at_head` for `/readyz`; `migrate` is idempotent | A§5.4, S1-T01 | Automated |
| TS-ING-052 | `unit_models_define_every_live_and_backtest_table` | Table set, primary keys, partial unique indexes, ULID checks, named constraints | A§5.1, A§5.2, S1-T01 | Automated |
| TS-ING-053 | `unit_db_session_scope_rolls_back_on_error` | Engine from settings, URL normalization, session commit and rollback, advisory-locked `migrate` | A§5.4, S1-T01 | Automated |
| TS-ING-100 | `unit_alternate_capabilities_intraday_on_grouped_and_trades_off` | Capability flags are correct and unsupported methods raise `CapabilityNotSupported` with no request | A§7.2, A§7.7, S1-T05 | Automated |
| TS-ING-101 | `unit_alternate_daily_request_is_adjusted_header_authed_and_paginated` | Adjusted daily bars, header auth only, `page_token` pagination, intraday regular-session filter, corporate-action ratios and merged dividends | A§7.7, S1-T05 | Automated |
| TS-ING-102 | `unit_alternate_retries_429_then_succeeds_honoring_retry_after` | Retry with injectable sleep on 429, 5xx, and transport errors; exhausted budget maps to `ProviderRateLimited` or `ProviderUnavailable`; 401/403 map to `ProviderUnconfigured`; malformed or invalid payloads map to `ProviderDataError` | A§7.3, S1-T05 | Automated |
| TS-ING-103 | `unit_alternate_key_never_leaks_into_repr_status_errors_or_logs` | The API key appears in no URL, repr, status, error message, or log record; a missing or malformed key reports `unconfigured` without network | A§7.3, S1-T05 | Automated |
| TS-ING-104 | `unit_alternate_registry_env_switch_selects_adapter_with_no_code_change` | `SUPERTRENDS_MARKET_PROVIDER=alternate` (env plus `load_settings`) returns the alternate adapter and `fixture` returns the fixture path; alternate bars mix with another fundamentals vendor | A§7.4, S1-T05 | Automated |
| TS-ING-105 | `unit_fixture_provider_different_seed_different_bars` | A different seed gives different bars; values depend on the seed and session index only, not the end date | FR-1xx, ADR-028, S1-T03 | Automated |
| TS-ING-106 | `unit_fixture_provider_split_reported_as_corporate_action` | Exactly one 4:1 split exists, is reported by `corporate_actions`, and bars are split adjusted | FR-1xx, A§7.5, S1-T03 | Automated |
| TS-ING-107 | `unit_fixture_provider_history_sizes` | About 3 years of daily bars and 30 sessions of 5-minute bars (aggregating exactly to the daily bars) for 12 tickers plus `SPY` and `QQQ` | FR-1xx, A§7.5, S1-T03 | Automated |
| TS-ING-108 | `unit_fixture_provider_unknown_symbol_none_unless_permissive` | Unknown symbols resolve to `None`; permissive mode generates bars from a hash of the symbol | FR-1xx, A§7.5, S1-T03 | Automated |
| TS-ING-109 | `unit_fixture_provider_etf_has_no_financials_and_stocks_do` | Stocks have quarterly financials with `known_at` 30 days after period end; ETFs have none; earnings dates include one 3 sessions out | FR-1xx, A§7.5, S1-T03 | Automated |
| TS-ING-110 | `unit_calendar_half_day_closes_early` | XNYS sessions skip holidays, half days close early, last completed session is computed from the clock | ADR-028, S1-T03 | Automated |
| TS-ING-111 | `unit_provider_database_call_recorder_returns_db_call_recorder` | `database_call_recorder()` writes sanitized `provider_calls` rows through `DbCallRecorder`, and the shared Massive client uses it | FR-112, NFR-009, S1-T04, S1-T06 | Automated |
| TS-ING-060 | `unit_ingest_daily_window_backfill_when_no_bars_or_full` | Empty store or `--full` requests the 1130-day backfill window | FR-1xx, S1-T06 | Automated |
| TS-ING-061 | `unit_ingest_window_skipped_when_only_weekend_or_holiday_follows` | No fetch when no session lies after the last stored bar | FR-1xx, S1-T06 | Automated |
| TS-ING-062 | `unit_ingest_regular_session_only_drops_pre_and_after_hours` | Intraday bars outside 09:30 to the close (early close aware) are dropped | FR-1xx, S1-T06 | Automated |
| TS-ING-063 | `unit_ingest_new_splits_ignores_known_and_dividends` | Only unseen split actions trigger a refetch | FR-1xx, S1-T06 | Automated |
| TS-ING-064 | `unit_ingest_fundamentals_due_policy` | Refresh when empty, first session of ISO week, after earnings, or `--full` | FR-1xx, S1-T06 | Automated |
| TS-ING-065 | `unit_ingest_resolve_as_of` | A date resolves to the latest session not after it and never past the last completed session | FR-1xx, S1-T06 | Automated |
| TS-ING-066 | `unit_provider_calls_sanitize_strips_query_string_and_credential_params` | Endpoint query string and credential params never reach a row | FR-1xx, S1-T06 | Automated |
| TS-ING-067 | `unit_cli_ingest_prints_per_ticker_summary_and_quality_counts` | `supertrends ingest` summary output and argument passing | FR-1xx, S1-T06 | Automated |
| TS-ING-068 | `unit_cli_ingest_provider_outage_exits_1` | `IngestError` exits 1 | FR-1xx, S1-T06 | Automated |
| TS-ING-069 | `unit_cli_ingest_unreachable_database_exits_3` | Database error exits 3 without leaking the password | FR-1xx, S1-T06 | Automated |
| TS-ING-070 | `unit_cli_ingest_invalid_date_exits_2` | Invalid `--date` or `--symbols` exits 2 | FR-1xx, S1-T06 | Automated |
| TS-ING-071 | `it_ingest_provider_error_isolated_per_ticker_and_marks_stale` | One ticker failing does not abort the others | FR-1xx, S1-T06 | Automated |
| TS-ING-072 | `it_ingest_all_tickers_failing_raises_provider_unavailable` | Every ticker failing raises `IngestError(provider_unavailable)` | FR-1xx, S1-T06 | Automated |
| TS-ING-073 | `it_ingest_unresolved_symbol_is_reported_not_stored` | Unknown symbol is reported `unresolved` and writes nothing | FR-1xx, S1-T06 | Automated |
| TS-ING-074 | `it_ingest_intraday_keeps_regular_session_bars_only` | Stored 5-minute bars are regular session only | FR-1xx, S1-T06 | Automated |
| TS-ING-075 | `it_ingest_default_symbols_exclude_unresolved_and_crypto_and_add_benchmarks` | Default universe is the resolved equity watchlist plus SPY and QQQ | FR-1xx, S1-T06 | Automated |
| TS-ING-076 | `it_cli_ingest_fills_database_and_second_run_changes_nothing` | CLI end to end on the fixture provider: fill, idempotent rerun, `--full` | FR-1xx, S1-T06 | Automated |

### 10.3 Indicators (TS-IND)

Golden and property tests apply to every indicator. Tolerances are in section 5.2. Every indicator below is also registered in the no-look-ahead harness (section 6), tracked as TS-IND-090 to TS-IND-092.

#### 10.3.1 Primitives

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-001 | `golden_sma_compute_handcomputed_series_matches_1e9` | SMA(5) on a hand series | FR-2xx, S2-T01 | Automated |
| TS-IND-002 | `golden_ema_compute_seeded_with_sma_of_first_n_matches_1e9` | EMA alpha 2/(n+1) seeded with the SMA of the first n values | FR-2xx, Conventions | Automated |
| TS-IND-003 | `golden_rma_compute_wilder_seed_and_recursion_matches_1e9` | RMA seeded with SMA, then `(prev*(n-1)+x)/n` | FR-2xx, Conventions | Automated |
| TS-IND-004 | `golden_true_range_compute_gap_up_gap_down_inside_bar_matches_1e9` | TR uses prior close for gaps | FR-2xx | Automated |
| TS-IND-005 | `unit_true_range_compute_first_bar_is_high_minus_low` | First bar has no prior close | FR-2xx | Automated |
| TS-IND-006 | `golden_atr_compute_rma10_and_rma14_match_1e9` | ATR is RMA of TR | FR-2xx | Automated |
| TS-IND-007 | `golden_rsi_compute_wilder_14_matches_1e9` | RSI(14) Wilder on a hand series | FR-2xx | Automated |
| TS-IND-008 | `unit_rsi_compute_all_gains_returns_100_all_losses_returns_0` | Degenerate series bounds | FR-2xx | Automated |
| TS-IND-009 | `golden_obv_compute_up_down_flat_closes_matches_1e9` | OBV adds, subtracts, or holds | FR-2xx | Automated |
| TS-IND-010 | `golden_stdev_compute_population_20_matches_1e9` | Population stdev, not sample | FR-2xx | Automated |
| TS-IND-011 | `unit_percentile_rank_compute_trailing_window_only_matches_1e9` | Percentile rank over trailing window | FR-2xx | Automated |
| TS-IND-012 | `golden_linreg_slope_compute_known_line_returns_exact_slope` | Least-squares slope on a linear series | FR-2xx | Automated |
| TS-IND-013 | `unit_pivots_compute_width_5_never_marks_within_5_bars_of_end` | Confirmed pivot rule | FR-2xx, S2-T01 | Automated |
| TS-IND-014 | `unit_zigzag_compute_threshold_8pct_vs_3_atr_pct_uses_max` | Threshold is `max(8%, 3*ATR%)` | FR-2xx, S2-T01 | Automated |
| TS-IND-015 | `unit_resample_weekly_compute_friday_close_matches_manual` | Weekly resample helper | FR-1xx, FR-2xx | Automated |
| TS-IND-016 | `prop_primitives_compute_output_length_equals_input_nan_warmup` | All primitives return same-length arrays with NaN warm-up | FR-2xx | Automated |
| TS-IND-017 | `unit_indicators_all_aggregation_exposes_primitives` | `supertrends.indicators.__all__` aggregates every module's `__all__` | FR-2xx, S2-T01 | Automated |
| TS-IND-018 | `unit_indicators_import_boundary_no_api_cli_mcp_data_runs` | No indicator module imports api, cli, mcp, data, or runs | ARCHITECTURE 2 | Automated |

#### 10.3.2 Supertrend

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-020 | `golden_supertrend_compute_handcomputed_40_bar_both_flips_and_ratcheting_matches` | Hand-computed 40-bar case: up flip, down flip, band ratcheting | FR-2xx, S2-T02 | Automated |
| TS-IND-021 | `golden_supertrend_tradingview_parity_line_within_0_01_after_100_bar_warmup` | Line within 0.01 per bar versus TradingView export, two tickers | FR-2xx, S2-T02 | Skipped: TradingView CSV exports not yet provided by the owner (owner checklist item); manual: export built-in Supertrend (10, 3) with OHLCV for two tickers on the daily chart to `tests/golden/tradingview/` and run `pytest tests/golden -k tradingview`. Release blocker at S9-T04 |
| TS-IND-022 | `golden_supertrend_tradingview_parity_direction_matches_every_bar_after_warmup` | Direction identical on every bar after the first 100 | FR-2xx, S2-T02 | Skipped: same owner files as TS-IND-021; manual: same step |
| TS-IND-023 | `unit_supertrend_tv_boundary_conversion_negative_tv_direction_maps_to_plus_1_up` | TradingView -1 (up) converts to internal +1 only at the import boundary | FR-2xx, Conventions | Automated |
| TS-IND-024 | `unit_supertrend_tv_boundary_conversion_positive_tv_direction_maps_to_minus_1_down` | TradingView +1 (down) converts to internal -1 | FR-2xx, Conventions | Automated |
| TS-IND-025 | `unit_supertrend_compute_atr_undefined_prior_bar_direction_minus_1` | Warm-up rule: `atr[t-1]` undefined gives direction -1 | FR-2xx | Automated |
| TS-IND-026 | `unit_supertrend_compute_final_up_ratchets_down_only_while_close_stays_below` | `final_up` lowers or resets after a close above it | FR-2xx | Automated |
| TS-IND-027 | `unit_supertrend_compute_final_lo_ratchets_up_only_while_close_stays_above` | `final_lo` rises or resets after a close below it | FR-2xx | Automated |
| TS-IND-028 | `unit_supertrend_compute_flip_up_when_close_exceeds_final_up` | Direction flips to +1 | FR-2xx | Automated |
| TS-IND-029 | `unit_supertrend_compute_flip_down_when_close_below_final_lo` | Direction flips to -1 | FR-2xx | Automated |
| TS-IND-030 | `prop_supertrend_compute_direction_always_plus_or_minus_1_after_warmup` | Direction domain | FR-2xx, S2-T02 | Automated |
| TS-IND-031 | `prop_supertrend_compute_line_below_close_when_up_above_close_when_down` | Line side invariant | FR-2xx, S2-T02 | Automated |
| TS-IND-032 | `unit_supertrend_derived_bars_since_flip_counts_from_last_flip` | `bars_since_flip` is 0 on the flip bar | FR-2xx | Automated |
| TS-IND-033 | `unit_supertrend_derived_distance_atr_signed_close_minus_st_over_atr` | `st_distance_atr` sign and value | FR-2xx | Automated |
| TS-IND-034 | `unit_supertrend_derived_weekly_direction_uses_resampled_weekly_bars` | `st_dir_w` computed on weekly bars | FR-2xx | Automated |
| TS-IND-035 | `unit_supertrend_derived_st_line_equals_invalidation_level` | `st_line` is exposed as the invalidation level | FR-2xx, FR-5xx | Automated |
| TS-IND-036 | `unit_supertrend_params_non_default_length_and_factor_from_config` | Length and factor come from `config/scoring.yaml` | FR-2xx, A§13 | Automated |

#### 10.3.3 SMA 20 / 50 / 200 with slope and cross

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-040 | `golden_sma_stack_compute_20_50_200_matches_1e6` | Three SMAs on the synthetic dataset | FR-2xx, S2-T03 | Automated |
| TS-IND-041 | `unit_sma_slope_compute_5_bar_slope_sign_positive_negative_flat` | SMA20 slope over 5 bars | FR-2xx | Automated |
| TS-IND-042 | `unit_sma_cross_detect_golden_cross_reports_bar_index` | Golden cross bar index | FR-2xx, S2-T03 | Automated |
| TS-IND-043 | `unit_sma_cross_detect_death_cross_reports_bar_index` | Death cross bar index | FR-2xx, S2-T03 | Automated |
| TS-IND-044 | `unit_sma_cross_detect_no_cross_in_series_returns_none` | No cross reports none | FR-2xx | Automated |

#### 10.3.4 MACD

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-050 | `golden_macd_compute_12_26_9_daily_matches_1e6` | line, signal, hist | FR-2xx, S2-T03 | Automated |
| TS-IND-051 | `golden_macd_compute_weekly_matches_1e6` | Weekly MACD on resampled bars | FR-2xx, S2-T03 | Automated |
| TS-IND-052 | `unit_macd_signal_cross_detect_bullish_and_bearish_within_3_bars` | Cross detection with bar index | FR-2xx | Automated |
| TS-IND-053 | `unit_macd_hist_run_detect_three_rising_and_three_falling_bars` | Histogram run helper used by the factor | FR-2xx | Automated |

#### 10.3.5 ADX(14), +DI, -DI

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-060 | `golden_adx_compute_14_matches_1e6` | ADX with Wilder smoothing on a hand series | FR-2xx, S2-T03 | Automated |
| TS-IND-061 | `unit_adx_compute_plus_di_minus_di_nonnegative_and_bounded_0_100` | DI and ADX range | FR-2xx | Automated |
| TS-IND-062 | `unit_adx_compute_flat_series_returns_zero_without_division_error` | Zero-range input does not divide by zero | FR-2xx | Automated |

#### 10.3.6 Divergences

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-070 | `unit_divergence_detect_regular_bullish_price_lower_low_osc_higher_low_found` | Constructed fixture | FR-2xx, S2-T04 | Automated |
| TS-IND-071 | `unit_divergence_detect_regular_bearish_price_higher_high_osc_lower_high_found` | Constructed fixture | FR-2xx, S2-T04 | Automated |
| TS-IND-072 | `unit_divergence_detect_hidden_bullish_price_higher_low_osc_lower_low_found` | Constructed fixture | FR-2xx, S2-T04 | Automated |
| TS-IND-073 | `unit_divergence_detect_hidden_bearish_price_lower_high_osc_higher_high_found` | Constructed fixture | FR-2xx, S2-T04 | Automated |
| TS-IND-074 | `unit_divergence_detect_second_pivot_unconfirmed_not_reported` | A pivot fewer than 5 bars old is ignored | FR-2xx, NFR-007 | Automated |
| TS-IND-075 | `unit_divergence_detect_monotonic_series_no_false_detection` | No pivots, no divergence | FR-2xx, S2-T04 | Automated |
| TS-IND-076 | `unit_divergence_detect_second_pivot_older_than_15_bars_excluded` | Recency window | FR-2xx | Automated |
| TS-IND-077 | `unit_divergence_detect_pivots_outside_60_bar_lookback_excluded` | Lookback window | FR-2xx | Automated |
| TS-IND-078 | `unit_divergence_detect_rsi_macd_hist_obv_each_reported_separately` | Three oscillators produce separate records | FR-2xx | Automated |
| TS-IND-079 | `unit_divergence_detect_weekly_uses_pivot_width_3` | Weekly pivot width is 3 | FR-2xx | Automated |
| TS-IND-080 | `unit_divergence_record_contains_both_pivot_bars_prices_and_oscillator_values` | Typed record shape | FR-2xx, S2-T04 | Automated |
| TS-IND-200 | `unit_divergence_detect_newer_pivot_supersedes_second_pivot` | Only the two most recent pivots compare | FR-2xx, S2-T04 | Automated |
| TS-IND-201 | `unit_divergence_macd_hist_helper_matches_independent_loop` | Local MACD histogram mirrors `momentum.macd` (cross-checked by S2-T08) | FR-2xx, S2-T04 | Automated |
| TS-IND-202 | `unit_divergence_detect_nan_osc_or_equal_values_not_divergence` | NaN oscillator or equal values give none | FR-2xx, S2-T04 | Automated |
| TS-IND-203 | `unit_divergence_detect_lows_and_highs_compared_separately` | Bullish and bearish pairs reported together | FR-2xx, S2-T04 | Automated |
| TS-IND-204 | `unit_divergence_detect_invalid_inputs_and_empty` | Length mismatch, width < 1, empty, bad as_of | FR-2xx, S2-T04 | Automated |
| TS-IND-205 | `unit_divergence_series_matches_detect_each_bar` | Per-bar flag array equals as-of detection | FR-2xx, S2-T04 | Automated |
| TS-IND-206 | `unit_divergence_records_sorted_by_confirmed_at` | Record list ordering and confirmed_at | FR-2xx, S2-T04 | Automated |
| TS-IND-207 | `unit_divergence_aggregation_exports` | Names re-exported by `supertrends.indicators` | FR-2xx, S2-T04 | Automated |
| TS-IND-208 | `property_divergence_no_look_ahead_p2_plus_width_le_last_index` | Hypothesis: no record with p2 + width > last index; truncation invariance | FR-2xx, S2-T04 | Automated |
| TS-IND-209 | `unit_divergence_detect_pivots_too_far_apart_never_active` | p1 and p2 more than 54 bars apart never form an active divergence | FR-2xx, S2-T04 | Automated |

#### 10.3.7 Mean reversion and volatility indicators

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-081 | `golden_bollinger_compute_20_2_bands_pct_b_bandwidth_match_1e6` | Bands, %B, bandwidth | FR-2xx, S2-T05 | Automated |
| TS-IND-082 | `unit_zscore_compute_uses_population_stdev20_and_sma20` | `z = (close - SMA20) / stdev20` | FR-2xx | Automated |
| TS-IND-083 | `unit_atr_pct_rank_compute_252_bar_trailing_window` | ATR% rank window | FR-2xx, S2-T05 | Automated |
| TS-IND-084 | `unit_bbw_rank_compute_126_bar_trailing_window` | Bandwidth rank window | FR-2xx, S2-T05 | Automated |
| TS-IND-085 | `golden_hv20_compute_log_returns_annualized_sqrt_252_matches_1e6` | Historical volatility | FR-2xx | Automated |
| TS-IND-086 | `unit_volatility_flags_squeeze_true_when_bbw_rank_below_15` | Squeeze boundary at 15 | FR-2xx | Automated |
| TS-IND-087 | `unit_volatility_flags_expansion_requires_rank_above_85_and_bbw_rising_3_bars` | Expansion needs both conditions | FR-2xx | Automated |
| TS-IND-210 | `unit_bollinger_flat_window_pct_b_and_zscore_nan` | Zero-width bands give NaN, no inf | S2-T05 | Automated |
| TS-IND-211 | `unit_meanrev_short_input_all_nan_same_length` | Input shorter than window | S2-T05 | Automated |
| TS-IND-212 | `unit_meanrev_exports_in_all_and_package_aggregate` | `__all__` aggregation | S2-T05 | Automated |
| TS-IND-213 | `unit_ranks_and_hv20_unchanged_when_future_bars_appended` | No look-ahead for trailing ranks | S2-T05 | Automated |
| TS-IND-214 | `unit_hv20_constant_series_zero_and_nonpositive_close_nan` | HV20 edge cases | S2-T05 | Automated |
| TS-IND-215 | `unit_expansion_nan_propagation_and_length_mismatch_raises` | NaN warm-up and validation | S2-T05 | Automated |
| TS-IND-216 | `unit_bandwidth_flat_zero_and_atr_pct_zero_close_nan` | Flat prices and zero close | S2-T05 | Automated |
| TS-IND-217 | `unit_volatility_exports_in_all_and_package_aggregate` | `__all__` aggregation | S2-T05 | Automated |

#### 10.3.8 Fibonacci

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-100 | `unit_zigzag_leg_select_most_recent_completed_leg_over_120_bars` | Latest completed leg A to B | FR-2xx, S2-T06 | Automated |
| TS-IND-101 | `unit_fib_levels_up_leg_pullback_61_8_within_1e6_of_expected` | Constructed up-leg-then-pullback fixture | FR-2xx, S2-T06 | Automated |
| TS-IND-102 | `unit_fib_levels_all_five_retracements_measured_from_b_toward_a` | 23.6, 38.2, 50.0, 61.8, 78.6 | FR-2xx | Automated |
| TS-IND-103 | `unit_fib_extensions_127_2_and_161_8_computed_for_evidence` | Extensions present | FR-2xx | Automated |
| TS-IND-104 | `unit_fib_levels_down_leg_mirrored_levels_correct` | Mirror for a down leg | FR-2xx | Automated |
| TS-IND-105 | `unit_fib_no_qualifying_leg_returns_none_quality_degraded` | No leg gives none | FR-2xx | Automated |
| TS-IND-106 | `unit_fib_near_and_holding_helpers_follow_factor_6_formula` | `near` and `holding`, up and down | FR-2xx, S2-T06 | Automated |
| TS-IND-107 | `unit_fib_threshold_uses_3_atr_pct_when_above_8_percent` | Wide ranges lift the threshold, no leg | FR-2xx, S2-T06 | Automated |

#### 10.3.9 Support and resistance

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-110 | `unit_levels_cluster_merges_pivots_within_half_atr` | Clustering tolerance | FR-2xx, S2-T06 | Automated |
| TS-IND-111 | `unit_levels_strength_touches_times_recency_weight_decays_1_0_to_0_3` | Strength formula | FR-2xx | Automated |
| TS-IND-112 | `unit_levels_keep_4_strongest_above_and_4_below_price` | Level count | FR-2xx | Automated |
| TS-IND-113 | `unit_levels_52_week_high_and_low_added_as_levels` | 52-week levels | FR-2xx, S2-T06 | Automated |
| TS-IND-114 | `unit_levels_breakout_flagged_only_on_the_bar_it_happens` | One-bar breakout flag | FR-2xx, S2-T06 | Automated |
| TS-IND-115 | `unit_levels_breakdown_requires_support_intact_prior_day` | Breakdown flag precondition | FR-2xx | Automated |
| TS-IND-116 | `unit_levels_nearest_support_resistance_distance_in_atr_units` | `d_s` and `d_r` | FR-2xx | Automated |
| TS-IND-117 | `unit_levels_insufficient_history_returns_none` | ATR warm-up gives none | FR-2xx, S2-T06 | Automated |
| TS-IND-118 | `unit_levels_breakdown_flagged_only_on_the_bar_it_happens` | Mirror of TS-IND-114 | FR-2xx, S2-T06 | Automated |
| TS-IND-119 | `unit_levels_breakout_requires_relative_volume_1_5` | Volume gate | FR-2xx, S2-T06 | Automated |
| TS-IND-220 | `unit_levels_cluster_is_anchored_not_chained` | Anchor clustering, no chaining (ADR-055) | FR-2xx, S2-T06 | Automated |
| TS-IND-221 | `unit_levels_unconfirmed_pivots_are_not_used` | Pivot within 5 bars of the end ignored | FR-2xx, S2-T06 | Automated |

#### 10.3.10 Volume indicators and estimated order flow

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-120 | `golden_volume_oscillator_compute_5_10_matches_1e6` | `vo = 100 * (EMA5 - EMA10) / EMA10` | FR-2xx, S2-T07 | Automated |
| TS-IND-121 | `unit_relative_volume_compute_volume_over_sma20_volume` | Relative volume | FR-2xx | Automated |
| TS-IND-122 | `golden_cmf_compute_20_matches_1e6` | Chaikin Money Flow | FR-2xx, S2-T07 | Automated |
| TS-IND-123 | `unit_flow_split_buy_plus_sell_equals_volume_for_every_bar` | Conservation of volume | FR-2xx, S2-T07 | Automated |
| TS-IND-124 | `unit_flow_split_zero_range_bar_close_ge_prev_close_all_buy` | Zero-range rule, up or flat | FR-2xx, S2-T07 | Automated |
| TS-IND-125 | `unit_flow_split_zero_range_bar_close_lt_prev_close_all_sell` | Zero-range rule, down | FR-2xx, S2-T07 | Automated |
| TS-IND-126 | `unit_flow_daily_delta_and_delta_pct_computed_from_5m_bars` | Daily delta and delta percent | FR-2xx | Automated |
| TS-IND-127 | `unit_flow_delta_pct_10_mean_of_last_10_sessions` | 10-session mean | FR-2xx | Automated |
| TS-IND-128 | `unit_flow_quality_intraday_when_5m_bars_for_8_of_10_sessions` | `intraday` threshold boundary (8 of 10, 7 of 10) | FR-2xx | Automated |
| TS-IND-129 | `unit_flow_quality_daily_estimate_when_intraday_missing_and_flagged` | Fallback to daily bars with flag | FR-2xx, S2-T07 | Automated |
| TS-IND-130 | `unit_flow_accumulation_distribution_days_counted_over_last_20_sessions` | Up or down close with relative volume at or above 1.5 | FR-2xx | Automated |
| TS-IND-131 | `unit_flow_provider_trades_capability_interface_allows_tick_rule_quality` | `trades` quality path is accepted by the interface | FR-2xx, A§7 | Automated |
| TS-IND-132 | `unit_flow_regular_session_only_excludes_pre_and_post_market_bars` | 5-minute bars outside 09:30 to 16:00 ET are ignored | FR-2xx | Automated |
| TS-IND-230 | `unit_volume_oscillator_zero_ema_is_nan_and_bad_windows_raise` | Zero EMA gives NaN, invalid window raises | S2-T07 | Automated |
| TS-IND-231 | `unit_volume_obv_slope_sign_up_down_flat` | OBV slope sign over 20 bars | S2-T07 | Automated |
| TS-IND-232 | `unit_volume_cmf_zero_range_bar_and_zero_volume` | Zero-range multiplier 0, zero volume sum NaN | S2-T07 | Automated |
| TS-IND-233 | `unit_volume_relative_volume_zero_average_is_nan` | Zero SMA gives NaN | S2-T07 | Automated |
| TS-IND-234 | `unit_volume_length_mismatch_raises` | Length mismatch raises | S2-T07 | Automated |
| TS-IND-235 | `unit_flow_daily_path_uses_prior_daily_close_first_bar_buy` | PRD A-07 and A-23 on daily bars | S2-T07 | Automated |
| TS-IND-236 | `unit_flow_zero_volume_session_nan_excluded_from_mean` | Zero-volume session | S2-T07 | Automated |
| TS-IND-237 | `unit_flow_missing_sessions_older_than_window_ignored` | 8-of-10 counts only the last 10 sessions | S2-T07 | Automated |
| TS-IND-238 | `unit_flow_unsorted_or_mismatched_inputs_raise` | Input validation | S2-T07 | Automated |

#### 10.3.11 Harness, snapshots, performance

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-090 | `prop_indicators_all_truncation_does_not_change_past_values` | The section 6 property for every registered indicator | NFR-007, S2-T08 | Automated |
| TS-IND-091 | `unit_indicators_registry_missing_public_function_fails_test` | A public indicator not in the registry fails CI | NFR-007, S2-T08 | Automated |
| TS-IND-092 | `prop_indicators_leaky_negative_control_is_detected` | An injected leaky indicator is flagged | NFR-007, S2-T08 | Automated |
| TS-IND-093 | `golden_indicators_determinism_hash_matches_committed_hash` | Hash of all outputs on the synthetic dataset | NFR-002, S2-T08 | Automated |
| TS-IND-094 | `unit_perf_budget_200_tickers_3y_daily_compute_under_60s_on_2_cores` | Benchmark for NFR-001 compute budget | NFR-001, S2-T08 | Automated |
| TS-IND-095 | `it_snapshots_persist_roundtrip_identical_json_for_same_inputs` | `indicator_snapshots` round trip and stable recompute | FR-2xx, S2-T09 | Automated |
| TS-IND-096 | `unit_indicators_nan_warmup_never_leaks_as_zero_into_snapshot` | NaN is stored as null, not zero | FR-2xx | Automated |
| TS-IND-097 | `unit_indicators_series_outputs_match_input_length_and_warm_up_is_nan` | Series outputs have the input length, float64, NaN warm-up | NFR-007, S2-T08 | Automated |
| TS-IND-098 | `prop_pivots_confirm_width_bars_late` | A pivot is absent before `p + w` bars exist and present one bar later | NFR-007, S2-T08 | Automated |
| TS-IND-099 | `prop_weekly_values_use_only_bars_up_to_t` | Weekly resample and weekly divergences use bars up to t; a partial week revised on completion is not look-ahead (6.1 item 6, ADR-033) | NFR-007, S2-T08 | Automated |
| TS-IND-240 | `unit_indicators_function_may_share_its_module_name` | `supertrend` the function is exported next to the module of the same name | S2-T08 | Automated |
| TS-IND-241 | `unit_divergence_private_macd_hist_equals_momentum_macd_hist` | `divergence._macd_hist` equals `momentum.macd().hist` to 1e-12 | S2-T08 | Automated |
| TS-IND-242 | `golden_indicators_double_run_in_subprocess_with_other_environment` | Same hashes in one process twice and in subprocesses with other PYTHONHASHSEED, TZ, LC_ALL | NFR-002, S2-T08 | Automated |
| TS-IND-243 | `unit_regen_golden_refuses_without_reason` | `scripts/regen-golden.sh` needs `--reason`, `--check` writes nothing and spares TradingView and hand-computed files | S2-T08 | Automated |
| TS-IND-244 | `unit_spec_test_plan_scenario_ids_are_unique` | No scenario ID repeats in TEST_PLAN | GD-009, S2-T08 | Automated |
| TS-IND-245 | `unit_spec_prd_ambiguity_ids_are_unique` | PRD section 17 A-ids are unique | GD-009, S2-T08 | Automated |
| TS-IND-246 | `unit_spec_architecture_adr_headings_are_unique` | ADR heading numbers are unique | GD-009, S2-T08 | Automated |
| TS-IND-247 | `unit_indicators_registry_exemptions_are_not_plain_functions` | Exempt names exist in `__all__`, have a reason, and are not functions | S2-T08 | Automated |
| TS-IND-248 | `unit_validate_fixtures_checks_the_synthetic_dataset_hash` | `scripts/validate-fixtures.sh` passes on the committed hash | S2-T08 | Automated |
| TS-IND-250 | `unit_snapshot_has_daily_weekly_levels_fib_divergence_flow_sections` | The document carries daily and weekly values, levels (52-week extremes, Supertrend invalidation), Fibonacci, divergences, flow and the config hash | FR-2xx, S2-T09 | Automated |
| TS-IND-251 | `unit_snapshot_as_of_t_is_identical_with_or_without_later_bars` | Snapshot bytes at t equal on truncated, full and future-perturbed bundles | NFR-007, S2-T09 | Automated |
| TS-IND-252 | `unit_snapshot_json_bytes_are_deterministic_sorted_and_rounded` | Same inputs give the same bytes; sorted keys; floats at 10 significant digits (ADR-056) | NFR-002, S2-T09 | Automated |
| TS-IND-253 | `unit_snapshot_covers_every_registered_series_indicator` | Each registered series indicator is in the snapshot or listed as a building block | FR-2xx, S2-T09 | Automated |
| TS-IND-254 | `unit_snapshot_uses_parameters_from_the_config` | A changed config value changes the values and the config hash | FR-2xx, S2-T09 | Automated |
| TS-IND-255 | `unit_snapshot_rejects_dates_without_bars` | No bar on or before the as-of date is an error; a later date uses the last bar | S2-T09 | Automated |
| TS-IND-256 | `it_snapshots_write_same_document_twice_is_skipped` | An identical second write leaves one row and reports `unchanged` | FR-2xx, S2-T09 | Automated |
| TS-IND-257 | `it_snapshots_write_different_document_for_same_key_raises` | A different document for the same run and symbol raises `SnapshotConflictError`; the stored row is untouched | FR-2xx, S2-T09 | Automated |
| TS-IND-258 | `it_snapshots_update_and_delete_rejected_by_append_only_trigger` | UPDATE and DELETE on `indicator_snapshots` fail with `append_only_violation` | FR-2xx, S2-T09 | Automated |
| TS-IND-259 | `it_snapshots_compute_and_store_skips_unknown_symbols_and_checks_config_hash` | Symbols without bars are skipped as `no_data`; a config whose hash differs from the run's is refused | FR-2xx, S2-T09 | Automated |

#### 10.3.12 Ripster EMA Clouds

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-IND-133 | `golden_ripster_clouds_handcomputed_fixture_top_bot_dir_pos_stack_match_every_bar` | Hand-computed case: stack flip in each direction, close inside a cloud, held and failed 8/9 pullback | FR-224, S2-T10 | Automated |
| TS-IND-134 | `unit_ripster_clouds_stack_flip_bars_since_stack_flip_counts_from_last_change_to_nonzero` | `rc_bars_since_stack_flip` is 0 on the flip bar, both directions | FR-224, S2-T10 | Automated |
| TS-IND-135 | `unit_ripster_clouds_ema_computed_on_hl2_for_all_ten_periods` | EMAs 8, 9, 5, 12, 34, 50, 72, 89, 180, 200 on `hl2` | FR-224, S2-T10 | Automated |
| TS-IND-136 | `unit_ripster_clouds_close_inside_cloud_pos_is_zero` | `pos` is 0 when close is inside the cloud, +1 above, -1 below | FR-224 | Automated |
| TS-IND-137 | `unit_ripster_pullback_held_low_tests_c1_within_3_bars_and_close_above_bot_flag_true` | Bullish held test of the 8/9 cloud | FR-224, S2-T10 | Automated |
| TS-IND-138 | `unit_ripster_pullback_failed_close_at_or_below_bot_c1_flag_false` | Bullish failed test | FR-224, S2-T10 | Automated |
| TS-IND-139 | `unit_ripster_pullback_stale_test_4_bars_ago_flag_false` | Boundary: 3 bars counts, 4 bars does not | FR-224 | Automated |
| TS-IND-140 | `unit_ripster_clouds_weekly_34_50_direction_uses_resampled_weekly_bars` | `rc_dir_w` computed on weekly bars, evidence only | FR-224 | Automated |
| TS-IND-141 | `golden_ripster_clouds_tradingview_parity_each_ema_within_0_01_after_200_bar_warmup` | All ten EMAs within 0.01 per bar versus the TradingView export, computed on the export's own bars, two tickers | FR-224, S2-T10 | Skipped: TradingView CSV exports with the Ripster EMA Clouds plots not yet provided by the owner (owner checklist item 3); manual: export the Ripster EMA Clouds indicator at default settings with OHLCV for the same two tickers on the daily chart to `tests/golden/tradingview/` and run `pytest tests/golden -k tradingview`. Release blocker at S9-T04 |
| TS-IND-142 | `golden_ripster_clouds_tradingview_parity_cloud_direction_matches_every_bar_after_warmup` | Every cloud direction identical on every bar after the first 200 | FR-224, S2-T10 | Skipped: same owner files as TS-IND-141; manual: same step |
| TS-IND-143 | `prop_ripster_clouds_top_ge_bot_for_every_cloud_after_warmup` | Property: `top >= bot` | FR-224, S2-T10 | Automated |
| TS-IND-144 | `prop_ripster_clouds_stack_nonzero_only_when_5_12_and_34_50_clouds_do_not_overlap` | Property: `stack` domain | FR-224, S2-T10 | Automated |
| TS-IND-145 | `unit_ripster_clouds_registered_with_no_look_ahead_harness` | The Ripster indicator is in the registry and passes the section 6 property | NFR-007, S2-T08, S2-T10 | Automated |
| TS-IND-146 | `unit_ripster_clouds_warmup_bars_are_nan_never_zero` | Fewer than 200 bars gives NaN for the 180/200 cloud | FR-224 | Automated |

### 10.4 Scoring, per factor (TS-SCR)

Each rule line in the Signal Engine Specification has one table-driven row. Boundary values are listed explicitly. All factor scores are validated to be in -100 to 100.

#### 10.4.0 Framework

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-001 | `unit_factor_result_score_101_raises_validation_error` | A factor returning 101 raises | FR-3xx, S3-T01 | Automated |
| TS-SCR-002 | `unit_factor_result_score_minus_101_raises_validation_error` | A factor returning -101 raises | FR-3xx, S3-T01 | Automated |
| TS-SCR-003 | `unit_factor_registry_every_config_factor_id_registered_and_reverse` | Config ids and registered factors match both ways | FR-3xx, S3-T01 | Automated |
| TS-SCR-004 | `unit_factor_result_contains_evidence_items_name_value_unit_reason_and_quality` | FactorResult shape | FR-3xx | Automated |
| TS-SCR-005 | `prop_factors_all_scores_within_minus_100_and_100_for_random_snapshots` | Range property for all 12 factors | FR-3xx | Deferred |
| TS-SCR-006 | `unit_factor_reasons_one_deterministic_template_per_rule_that_fired` | Reasons come from templates, one per fired rule | FR-5xx | Deferred |
| TS-SCR-007 | `prop_factors_all_truncation_does_not_change_score_at_t` | Factor-level no-look-ahead (section 6.2) | NFR-007 | Deferred |
| TS-SCR-301 | `unit_config_equals_appendix_e_ignoring_comments_and_the_version_bump` | `config/scoring.yaml` equals BUILD_PROMPT Appendix E line for line (comments ignored, `scoring.version` 2) | spec 1.1.0, S3-T01 | Automated |
| TS-SCR-302 | `unit_config_scoring_version_is_2_for_spec_1_1_0` | The Ripster weights and block are a scoring change, so `scoring.version` is 2 | Spec Change Protocol, S3-T01 | Automated |
| TS-SCR-303 | `unit_config_ripster_block_values_match_appendix_e` | The `ripster` block parses into typed values (pairs, points summing to 100, lookback 3, penalty 10, gate) | FR-333, S3-T01 | Automated |
| TS-SCR-304 | `unit_config_ripster_block_is_strict` | Unknown, missing, or out-of-range `ripster` keys are rejected naming the key | FR-3xx, S3-T01 | Automated |
| TS-SCR-305 | `unit_config_twelve_factor_ids_in_weights_order_and_regime_multipliers_cover_ripster` | Twelve IDs in `weights` order; regime multipliers carry ripster | FR-316, S3-T01 | Automated |
| TS-SCR-306 | `unit_factor_quality_vocabulary_is_ok_degraded_missing_daily_estimate` | Quality vocabulary matches `factor_scores.quality`; registry iterates in config weight order | ADR-059, S3-T01 | Automated |
| TS-SCR-307 | `unit_factor_stub_raises_not_implemented_naming_its_owner_task` | Registry get, duplicate and empty IDs, Protocol, and the owner map; once S3-T02, T03, T04 and T14 landed no stub raising `NotImplementedError` is left (fundamentals stays a `missing` stub until S5-T04) | ADR-059, S3-T01 | Automated |
| TS-SCR-308 | `unit_factor_fundamentals_stub_returns_missing_with_score_zero` | Sprint 3 fundamentals is always `missing`, score 0, weight dropped | FR-315, S3-T01 | Automated |
| TS-SCR-309 | `unit_factor_result_missing_helper_scores_zero_with_missing_quality` | `FactorResult.missing`; a `missing` result with a nonzero score is rejected | FR-315, S3-T01 | Automated |
| TS-SCR-310 | `unit_snapshot_contains_every_input_path_of_the_factor` | Every declared input path of each factor exists in the snapshot and is non-null unless legitimately absent | S3-T01 audit | Automated |
| TS-SCR-311 | `unit_snapshot_new_daily_fields_match_independent_computations` | `prev_close`, `high`, `low`, `close_lag_3`, `ret_5`, `avg_dollar_volume_20d` hand-derived; null in warm-up | S3-T01 audit | Automated |
| TS-SCR-312 | `unit_snapshot_sma_cross_is_sma50_against_sma200_over_the_config_lookback` | Golden and death cross is SMA50 vs SMA200 (Factor 2) | FR-3xx, S3-T01 | Automated |
| TS-SCR-313 | `unit_snapshot_ripster_block_matches_independent_ema_clouds` | Ripster block (clouds, bias, stack, flip count, pullback, weekly direction) vs independent loops; warm-up null; configured lookback; schema 2 | FR-333, S3-T01 | Automated |
| TS-SCR-314 | `unit_factor_result_nan_inf_and_just_out_of_range_scores_raise` | NaN and infinities never become a score; results are frozen and strict; weight multiplier is positive and finite | ADR-059, S3-T01 | Automated |
| TS-SCR-315 | `unit_reason_number_formatting_is_consistent` | One number format in reasons (ints as is, floats 2 decimals); NaN rejected | FR-5xx, S3-T01 | Automated |
| TS-SCR-316 | `unit_factor_context_defaults_and_immutability` | `FactorContext` defaults and immutability; each factor module docstring lists its input paths | ADR-059, S3-T01 | Automated |
| TS-SCR-317 | `unit_config_architecture_13_1_mirrors_the_config_file` | The yaml in ARCHITECTURE 13.1 equals `config/scoring.yaml`, comments ignored | S3-T01 | Automated |
| TS-SCR-318 | `unit_factors_registry_is_complete_in_a_fresh_interpreter_without_other_imports` | One module per factor; the explicit list builds the full registry with no import side effects | ADR-059, S3-T01 | Automated |
| TS-SCR-319 | `unit_snapshot_contains_regime_confidence_and_selection_inputs` | ADX, the confidence deductions, and the selection gate inputs are in the snapshot | FR-3xx, S3-T01 | Automated |

#### 10.4.1 Factor 1: Supertrend

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-010 | `unit_supertrend_score_daily_up_base_plus_60` | `base = +60` when `st_dir_d == +1` | FR-3xx | Automated |
| TS-SCR-011 | `unit_supertrend_score_daily_down_base_minus_60` | `base = -60` when down | FR-3xx | Automated |
| TS-SCR-012 | `unit_supertrend_score_weekly_agrees_up_adds_25` | Weekly agreement, up | FR-3xx | Automated |
| TS-SCR-013 | `unit_supertrend_score_weekly_agrees_down_adds_minus_25` | Weekly agreement, down (`+25 * st_dir_d`) | FR-3xx | Automated |
| TS-SCR-014 | `unit_supertrend_score_weekly_conflict_up_adds_minus_15` | Weekly conflict, daily up | FR-3xx | Automated |
| TS-SCR-015 | `unit_supertrend_score_weekly_conflict_down_adds_plus_15` | Weekly conflict, daily down (`-15 * -1`) | FR-3xx | Automated |
| TS-SCR-016 | `unit_supertrend_score_flip_5_bars_ago_adds_freshness_15` | Boundary `bars_since_flip == 5` | FR-3xx, S3-T02 | Automated |
| TS-SCR-017 | `unit_supertrend_score_flip_6_bars_ago_adds_freshness_0` | Boundary `bars_since_flip == 6` | FR-3xx, S3-T02 | Automated |
| TS-SCR-018 | `unit_supertrend_score_fresh_flip_down_adds_minus_15` | Freshness sign follows direction | FR-3xx | Automated |
| TS-SCR-019 | `unit_supertrend_score_distance_4_0_atr_no_stretch_penalty` | Boundary: `|distance| == 4` is not over 4 | FR-3xx | Automated |
| TS-SCR-020 | `unit_supertrend_score_distance_4_01_atr_up_subtracts_10` | Stretch penalty, up | FR-3xx | Automated |
| TS-SCR-021 | `unit_supertrend_score_distance_4_01_atr_down_adds_10` | Stretch penalty, down | FR-3xx | Automated |
| TS-SCR-022 | `unit_supertrend_score_max_case_up_fresh_weekly_agree_equals_100` | 60 + 25 + 15 = 100, clipped | FR-3xx | Automated |
| TS-SCR-023 | `unit_supertrend_score_max_case_down_equals_minus_100` | Mirror extreme | FR-3xx | Automated |
| TS-SCR-024 | `unit_supertrend_score_evidence_includes_line_direction_bars_since_flip_distance` | Evidence content | FR-3xx, FR-5xx | Automated |

#### 10.4.2 Factor 2: SMA analysis

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-030 | `unit_sma_score_close_above_sma200_adds_30` | +30 | FR-3xx | Automated |
| TS-SCR-031 | `unit_sma_score_close_below_sma200_subtracts_30` | -30 | FR-3xx | Automated |
| TS-SCR-032 | `unit_sma_score_sma50_above_sma200_adds_25` | +25 | FR-3xx | Automated |
| TS-SCR-033 | `unit_sma_score_sma50_below_sma200_subtracts_25` | -25 | FR-3xx | Automated |
| TS-SCR-034 | `unit_sma_score_close_above_sma50_adds_20` | +20 | FR-3xx | Automated |
| TS-SCR-035 | `unit_sma_score_close_below_sma50_subtracts_20` | -20 | FR-3xx | Automated |
| TS-SCR-036 | `unit_sma_score_sma20_slope_5_bars_positive_adds_15` | +15 | FR-3xx | Automated |
| TS-SCR-037 | `unit_sma_score_sma20_slope_5_bars_negative_subtracts_15` | -15 | FR-3xx | Automated |
| TS-SCR-038 | `unit_sma_score_golden_cross_10_bars_ago_adds_10` | Boundary: a cross on the 10th bar of the window (as-of bar is bar 1) counts (A-26) | FR-3xx | Automated |
| TS-SCR-039 | `unit_sma_score_golden_cross_11_bars_ago_adds_0` | Boundary: the 11th bar does not count (A-26) | FR-3xx | Automated |
| TS-SCR-040 | `unit_sma_score_death_cross_within_10_bars_subtracts_10` | -10 | FR-3xx | Automated |
| TS-SCR-041 | `unit_sma_score_all_bullish_sum_100_clipped` | 30 + 25 + 20 + 15 + 10 = 100 | FR-3xx | Automated |
| TS-SCR-042 | `unit_sma_score_all_bearish_sum_minus_100_clipped` | Mirror | FR-3xx | Automated |
| TS-SCR-043 | `unit_sma_score_close_equal_to_sma_adds_neither_sign` | Tie handling is defined and tested (equal is neither above nor below) | FR-3xx | Automated |

#### 10.4.3 Factor 3: MACD

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-050 | `unit_macd_score_line_above_signal_adds_35` | +35 | FR-3xx | Automated |
| TS-SCR-051 | `unit_macd_score_line_below_signal_subtracts_35` | -35 | FR-3xx | Automated |
| TS-SCR-052 | `unit_macd_score_line_above_zero_adds_25` | +25 | FR-3xx | Automated |
| TS-SCR-053 | `unit_macd_score_line_below_zero_subtracts_25` | -25 | FR-3xx | Automated |
| TS-SCR-054 | `unit_macd_score_hist_rising_3_bars_adds_25` | +25 | FR-3xx | Automated |
| TS-SCR-055 | `unit_macd_score_hist_rising_2_bars_adds_0` | Boundary: 2 consecutive is not 3 | FR-3xx | Automated |
| TS-SCR-056 | `unit_macd_score_hist_falling_3_bars_subtracts_25` | -25 | FR-3xx | Automated |
| TS-SCR-057 | `unit_macd_score_bullish_cross_3_bars_ago_adds_15` | Boundary: a cross on the 3rd bar of the window counts (A-26) | FR-3xx | Automated |
| TS-SCR-058 | `unit_macd_score_bullish_cross_4_bars_ago_adds_0` | Boundary: the 4th bar does not count (A-26) | FR-3xx | Automated |
| TS-SCR-059 | `unit_macd_score_bearish_cross_within_3_bars_subtracts_15` | -15 | FR-3xx | Automated |
| TS-SCR-060 | `unit_macd_score_weekly_disagrees_with_daily_multiplies_by_0_75` | Weekly line versus signal disagrees | FR-3xx | Automated |
| TS-SCR-061 | `unit_macd_score_weekly_agrees_with_daily_multiplier_1_0` | No change when weekly agrees | FR-3xx | Automated |
| TS-SCR-062 | `unit_macd_score_weekly_macd_reported_as_evidence` | Weekly MACD values in evidence | FR-3xx | Automated |

#### 10.4.4 Factor 4: Divergences

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-070 | `unit_divergence_score_regular_bullish_rsi_adds_40` | RSI +40 | FR-3xx | Automated |
| TS-SCR-071 | `unit_divergence_score_regular_bearish_rsi_subtracts_40` | RSI -40 | FR-3xx | Automated |
| TS-SCR-072 | `unit_divergence_score_regular_bullish_macd_hist_adds_35` | MACD hist +35 | FR-3xx | Automated |
| TS-SCR-073 | `unit_divergence_score_regular_bullish_obv_adds_25` | OBV +25 | FR-3xx | Automated |
| TS-SCR-074 | `unit_divergence_score_hidden_bullish_rsi_counts_half_value_20` | Hidden counts at half | FR-3xx | Automated |
| TS-SCR-075 | `unit_divergence_score_hidden_bearish_obv_counts_half_value_minus_12_5` | Hidden bearish OBV | FR-3xx | Automated |
| TS-SCR-076 | `unit_divergence_score_same_type_on_weekly_multiplies_total_by_1_25` | Weekly confirmation multiplier | FR-3xx | Automated |
| TS-SCR-077 | `unit_divergence_score_sum_over_100_clipped_to_100` | Clip | FR-3xx | Automated |
| TS-SCR-078 | `unit_divergence_score_none_present_returns_zero` | No divergence | FR-3xx | Automated |
| TS-SCR-079 | `unit_divergence_score_opposite_signs_net_out` | Bullish RSI and bearish OBV combine | FR-3xx | Automated |
| TS-SCR-080 | `unit_divergence_score_second_pivot_16_bars_ago_not_counted` | Recency boundary: `t - p2` of 15 counts, 16 does not (A-26) | FR-3xx | Automated |
| TS-SCR-320 | `unit_sma_cross_boundary_10_bars_on_real_snapshots` | Real snapshots against an independent SMA50/SMA200 cross finder: counts on the 10th bar of the window, not the 11th | FR-3xx, S3-T02 | Automated |
| TS-SCR-321 | `unit_macd_cross_boundary_3_bars_on_real_snapshots` | Real snapshots against an independent MACD loop: counts on the 3rd bar, not the 4th | FR-3xx, S3-T02 | Automated |
| TS-SCR-322 | `unit_macd_histogram_run_boundary_2_and_3_bars_on_real_snapshots` | Histogram up or down 2 bars gives no run; 3 bars gives +1 or -1 (independent loop) | FR-3xx, S3-T02 | Automated |
| TS-SCR-323 | `unit_factors_1_to_4_on_real_snapshots_are_in_range_with_evidence` | Factors 1 to 4 on real snapshots: `ok`, in range, evidence with reasons, deterministic | FR-3xx, FR-5xx, S3-T02 | Automated |
| TS-SCR-324 | `unit_factors_1_to_4_on_a_short_history_degrade_or_go_missing_not_raise` | 40 bars: SMA missing (score 0), MACD degraded without weekly; no exception | FR-3xx, A-27, S3-T02 | Automated |
| TS-SCR-325 | `unit_factor_missing_and_degraded_inputs_follow_the_policy` | Null warm-up inputs give `missing`; null weekly, slope, ATR or distance give `degraded` with that part 0 (supertrend, sma, macd rows) | A-27, S3-T02 | Automated |
| TS-SCR-326 | `unit_factor_thresholds_and_points_come_from_the_config` | Freshness, stretch, cross windows, weekly multipliers, divergence points, hidden and weekly multipliers and recency are read from the config | FR-3xx, S3-T02 | Automated |

#### 10.4.5 Factor 5: Mean reversion

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-090 | `unit_mean_reversion_score_z_plus_2_5_z_part_minus_60` | Stretched up is bearish | FR-3xx | Automated |
| TS-SCR-091 | `unit_mean_reversion_score_z_minus_2_5_z_part_plus_60` | Stretched down is bullish | FR-3xx | Automated |
| TS-SCR-092 | `unit_mean_reversion_score_z_beyond_2_5_clipped_at_60` | `clip(z/2.5, -1, 1)` | FR-3xx | Automated |
| TS-SCR-093 | `unit_mean_reversion_score_z_zero_z_part_zero` | Neutral | FR-3xx | Automated |
| TS-SCR-094 | `unit_mean_reversion_score_rsi_30_rsi_part_plus_40` | Boundary at 30 | FR-3xx | Automated |
| TS-SCR-095 | `unit_mean_reversion_score_rsi_70_rsi_part_minus_40` | Boundary at 70 | FR-3xx | Automated |
| TS-SCR-096 | `unit_mean_reversion_score_rsi_50_rsi_part_zero_linear_midpoint` | Linear between | FR-3xx | Automated |
| TS-SCR-097 | `unit_mean_reversion_score_rsi_below_30_stays_plus_40` | No overshoot | FR-3xx | Automated |
| TS-SCR-098 | `unit_mean_reversion_score_pct_b_is_evidence_only_not_in_score` | `pct_b` does not change the score | FR-3xx | Automated |
| TS-SCR-099 | `unit_mean_reversion_score_stdev_zero_flat_series_returns_zero_degraded` | Zero stdev handled without error | FR-3xx | Automated |
| TS-SCR-360 | `unit_mean_reversion_score_parts_sum` | z_part + rsi_part, both signs and opposing parts; FR-307 example -100 | FR-307, S3-T03 | Automated |
| TS-SCR-361 | `unit_mean_reversion_evidence_and_reasons_use_templates` | Evidence names, units and rendered reasons | FR-5xx, S3-T03 | Automated |
| TS-SCR-362 | `unit_mean_reversion_null_inputs_degrade_or_go_missing` | One null input degrades, both null is `missing` | FR-307, S3-T03 | Automated |
| TS-SCR-363 | `unit_mean_reversion_on_real_snapshots_is_in_range_and_declares_inputs` | Computed snapshots score in range and equal the formula | FR-307, S3-T03 | Automated |

#### 10.4.6 Factor 6: Fibonacci

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-100 | `unit_fib_score_up_leg_near_38_2_and_holding_adds_60` | +60 | FR-3xx | Automated |
| TS-SCR-101 | `unit_fib_score_up_leg_near_50_and_holding_adds_70` | +70 | FR-3xx | Automated |
| TS-SCR-102 | `unit_fib_score_up_leg_near_61_8_and_holding_adds_80` | +80 | FR-3xx | Automated |
| TS-SCR-103 | `unit_fib_score_up_leg_close_below_78_6_subtracts_50` | Swing failed | FR-3xx | Automated |
| TS-SCR-104 | `unit_fib_score_up_leg_close_above_b_adds_20` | Leg resumed | FR-3xx | Automated |
| TS-SCR-105 | `unit_fib_score_up_leg_otherwise_zero` | No rule matches | FR-3xx | Automated |
| TS-SCR-106 | `unit_fib_score_near_boundary_exactly_half_atr_counts_as_near` | `abs(close - level) <= 0.5*atr14` | FR-3xx | Automated |
| TS-SCR-107 | `unit_fib_score_holding_requires_close_above_prior_close_and_low_ge_level_minus_half_atr` | Both `holding` conditions | FR-3xx | Automated |
| TS-SCR-108 | `unit_fib_score_down_leg_near_38_2_and_holding_subtracts_60` | Mirror of +60 | FR-3xx | Automated |
| TS-SCR-109 | `unit_fib_score_down_leg_near_50_and_holding_subtracts_70` | Mirror | FR-3xx | Automated |
| TS-SCR-110 | `unit_fib_score_down_leg_near_61_8_and_holding_subtracts_80` | Mirror | FR-3xx | Automated |
| TS-SCR-111 | `unit_fib_score_down_leg_close_above_78_6_adds_50` | Mirror of failure rule | FR-3xx | Automated |
| TS-SCR-112 | `unit_fib_score_down_leg_close_below_b_subtracts_20` | Mirror | FR-3xx | Automated |
| TS-SCR-113 | `unit_fib_score_no_leg_score_zero_quality_degraded` | No qualifying leg | FR-3xx | Automated |
| TS-SCR-114 | `unit_fib_score_evidence_includes_next_level_127_2_extension` | Next target evidence | FR-3xx, FR-5xx | Automated |
| TS-SCR-364 | `unit_fib_first_listed_rule_wins_when_two_levels_are_near` | Listed order decides when two levels are near (PRD A-28); both signs | FR-308, A-28, S3-T03 | Automated |
| TS-SCR-365 | `unit_fib_missing_price_inputs_make_the_factor_missing` | Null close, prior close, low, high or ATR is `missing` | FR-308, S3-T03 | Automated |
| TS-SCR-366 | `unit_fib_fail_rule_is_ignored_while_a_hold_rule_matches` | Hold rules precede the failure and resume rules; both signs | FR-308, A-28, S3-T03 | Automated |
| TS-SCR-367 | `unit_fib_on_real_snapshots_scores_in_range` | Computed snapshots: in range; no leg means `degraded` | FR-309, S3-T03 | Automated |
| TS-SCR-368 | `unit_fib_absent_extensions_leave_out_the_target_evidence` | No extensions in the snapshot: score unchanged, target items omitted | FR-308, S3-T03 | Automated |

#### 10.4.7 Factor 7: Support and resistance

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-120 | `unit_levels_score_rr_formula_room_above_vs_below_base_clip_60` | `rr = d_r / max(d_s, 0.25)`, `base = clip((rr-1)*40, -60, 60)` | FR-3xx | Automated |
| TS-SCR-121 | `unit_levels_score_d_s_zero_uses_floor_0_25` | Division floor | FR-3xx | Automated |
| TS-SCR-122 | `unit_levels_score_rr_1_0_base_zero` | Neutral | FR-3xx | Automated |
| TS-SCR-123 | `unit_levels_score_breakout_rel_volume_1_5_adds_40` | Boundary: relative volume exactly 1.5 | FR-3xx | Automated |
| TS-SCR-124 | `unit_levels_score_breakout_rel_volume_1_49_adds_0` | Boundary just below | FR-3xx | Automated |
| TS-SCR-125 | `unit_levels_score_breakout_level_not_intact_yesterday_adds_0` | Intact-yesterday condition | FR-3xx | Automated |
| TS-SCR-126 | `unit_levels_score_breakdown_rel_volume_1_5_subtracts_40` | -40 | FR-3xx | Automated |
| TS-SCR-127 | `unit_levels_score_total_clipped_to_100` | Base 60 plus breakout 40 | FR-3xx | Automated |
| TS-SCR-128 | `unit_levels_score_no_resistance_above_uses_52_week_high_level` | 52-week levels join the set | FR-3xx | Automated |
| TS-SCR-370 | `unit_levels_close_beyond_the_52_week_extreme_floors_distance_at_zero` | No resistance and close at or past the 52-week high gives `d_r` 0; mirror for support | FR-310, A-29, S3-T03 | Automated |
| TS-SCR-371 | `unit_levels_no_support_below_uses_52_week_low_level` | The 52-week low gives `d_s` when no support exists | FR-310, A-29, S3-T03 | Automated |
| TS-SCR-372 | `unit_levels_missing_inputs_make_the_factor_missing` | No levels block, close, ATR (or zero) or 52-week range is `missing` | FR-310, S3-T03 | Automated |
| TS-SCR-373 | `unit_levels_evidence_and_reasons_use_templates` | Evidence names, units and rendered reasons | FR-5xx, S3-T03 | Automated |
| TS-SCR-374 | `unit_levels_on_real_snapshots_matches_independent_rr` | Computed snapshots equal the rr formula | FR-310, S3-T03 | Automated |

#### 10.4.8 Factor 8: Volatility

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-130 | `unit_volatility_score_squeeze_up_trend_adds_30` | `+30 * st_dir_d` | FR-3xx | Automated |
| TS-SCR-131 | `unit_volatility_score_squeeze_down_trend_subtracts_30` | Direction sign | FR-3xx | Automated |
| TS-SCR-132 | `unit_volatility_score_squeeze_boundary_rank_15_is_not_squeeze` | `bbw_rank < 15` strict | FR-3xx | Automated |
| TS-SCR-133 | `unit_volatility_score_expansion_with_move_in_trend_direction_adds_20` | `+20 * st_dir_d` | FR-3xx | Automated |
| TS-SCR-134 | `unit_volatility_score_expansion_move_against_trend_adds_0` | Move over 3 bars opposes direction | FR-3xx | Automated |
| TS-SCR-135 | `unit_volatility_score_atr_pct_rank_above_90_halves_score` | Multiplier 0.5 | FR-3xx | Automated |
| TS-SCR-136 | `unit_volatility_score_atr_pct_rank_exactly_90_no_halving` | Boundary | FR-3xx | Automated |
| TS-SCR-137 | `unit_volatility_score_neither_squeeze_nor_expansion_returns_zero` | No rule | FR-3xx | Automated |
| TS-SCR-138 | `unit_volatility_evidence_expected_1d_move_equals_atr14` | Risk evidence on every card | FR-3xx, FR-7xx | Automated |
| TS-SCR-380 | `unit_volatility_expansion_rank_85_is_not_expansion` | `bbw_rank > 85` is strict even with the flag set | FR-311, S3-T03 | Automated |
| TS-SCR-381 | `unit_volatility_expansion_needs_the_rising_flag` | A high rank without the rising flag scores 0 | FR-311, S3-T03 | Automated |
| TS-SCR-382 | `unit_volatility_null_atr_rank_or_atr_degrades` | Null ATR rank or ATR degrades; the score stays | FR-311, S3-T03 | Automated |
| TS-SCR-383 | `unit_volatility_missing_direction_or_rank_is_missing` | No direction or band width rank is `missing` | FR-311, S3-T03 | Automated |
| TS-SCR-384 | `unit_volatility_evidence_and_reasons_use_templates` | Rendered reasons for every evidence item | FR-5xx, S3-T03 | Automated |
| TS-SCR-385 | `unit_volatility_on_real_snapshots_agrees_with_snapshot_flags` | Computed snapshots: in range, squeeze equals the flag, score equals the rules | FR-311, S3-T03 | Automated |
| TS-SCR-386 | `unit_volatility_null_risk_inputs_are_left_out_of_the_evidence` | Null ATR %, HV20 and band width drop their items; score unchanged | FR-311, S3-T03 | Automated |
| TS-SCR-390 | `unit_factors_5_to_8_are_pure_and_deterministic` | Same snapshot same result, snapshot not mutated, JSON-safe, reasons and units set | ADR-061, S3-T03 | Automated |
| TS-SCR-391 | `unit_factors_5_to_8_read_only_declared_inputs` | A snapshot reduced to the declared input paths gives the same result | ADR-061, S3-T03 | Automated |

#### 10.4.9 Factor 9: Volume oscillator

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-140 | `unit_volume_osc_score_positive_vo_rising_price_vo_part_positive` | Rising volume confirms an up move | FR-3xx | Automated |
| TS-SCR-141 | `unit_volume_osc_score_positive_vo_falling_price_vo_part_negative` | Selling on rising volume | FR-3xx, S3-T04 | Automated |
| TS-SCR-142 | `unit_volume_osc_score_negative_vo_rising_price_vo_part_negative` | Rally on fading volume | FR-3xx | Automated |
| TS-SCR-143 | `unit_volume_osc_score_negative_vo_falling_price_vo_part_positive` | Decline on fading volume | FR-3xx | Automated |
| TS-SCR-144 | `unit_volume_osc_score_vo_part_clipped_at_60` | `clip(vo*2, -60, 60)` | FR-3xx | Automated |
| TS-SCR-145 | `unit_volume_osc_score_ret5_zero_vo_part_zero` | `sign(0) == 0` | FR-3xx | Automated |
| TS-SCR-146 | `unit_volume_osc_score_obv_slope_positive_adds_40` | `obv_part` | FR-3xx | Automated |
| TS-SCR-147 | `unit_volume_osc_score_obv_slope_negative_subtracts_40` | `obv_part` | FR-3xx | Automated |
| TS-SCR-148 | `unit_volume_osc_score_total_clipped_to_100` | Clip | FR-3xx | Automated |
| TS-SCR-400 | `unit_volume_osc_null_input_is_missing_score_zero` | Any of `vo`, `ret5`, `obv_slope` in warm-up gives a missing factor | FR-312, S3-T04 | Automated |
| TS-SCR-401 | `unit_volume_osc_evidence_lists_inputs_and_parts_with_reasons` | Evidence has vo, ret5, OBV sign, vo_part, obv_part | FR-312, S3-T04 | Automated |
| TS-SCR-402 | `unit_volume_osc_reason_names_confirm_or_fade` | The vo_part reason says confirms or fades | FR-312, S3-T04 | Automated |
| TS-SCR-403 | `unit_volume_osc_input_paths_resolve` | Declared input paths resolve | FR-312, S3-T04 | Automated |
| TS-SCR-404 | `unit_volume_osc_pure_and_deterministic` | Same snapshot, equal results, no mutation | FR-301, S3-T04 | Automated |

#### 10.4.10 Factor 10: Buy / sell volume

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-150 | `unit_flow_score_delta_pct_10_clip_50_plus_cmf_clip_50` | Both parts and both clips | FR-3xx | Automated |
| TS-SCR-151 | `unit_flow_score_delta_pct_10_0_2_clipped_at_50` | `0.2*300 = 60` clips to 50 | FR-3xx | Automated |
| TS-SCR-152 | `unit_flow_score_cmf20_negative_part_clipped_at_minus_50` | Clip low | FR-3xx | Automated |
| TS-SCR-153 | `unit_flow_score_quality_intraday_weight_multiplier_1_0` | No weight change | FR-3xx | Automated |
| TS-SCR-154 | `unit_flow_score_quality_daily_estimate_weight_multiplier_0_6` | Weight times 0.6 | FR-3xx, S3-T04 | Automated |
| TS-SCR-155 | `unit_flow_score_quality_stored_and_shown_in_evidence` | Quality visible in evidence | FR-3xx, FR-7xx | Automated |
| TS-SCR-156 | `unit_flow_score_accumulation_distribution_days_reported_as_evidence` | 20-session counts | FR-3xx | Automated |
| TS-SCR-157 | `unit_flow_score_trades_quality_path_accepts_provider_flag` | Optional upgrade is accepted by the interface | FR-3xx, A§7 | Automated |
| TS-SCR-405 | `unit_flow_null_input_is_missing_score_zero` | `delta_pct_10` or `cmf20` in warm-up gives a missing factor | FR-313, S3-T04 | Automated |
| TS-SCR-406 | `unit_flow_unknown_quality_is_rejected` | A quality outside intraday, daily_estimate, trades raises ValueError | FR-313, S3-T04 | Automated |
| TS-SCR-407 | `unit_flow_null_day_counts_leave_out_evidence_items` | Null accumulation or distribution counts are left out; score unchanged | FR-313, S3-T04 | Automated |
| TS-SCR-408 | `unit_flow_evidence_lists_delta_and_cmf_with_reasons` | Evidence has delta_pct_10 and cmf_20 with formatted reasons | FR-313, S3-T04 | Automated |
| TS-SCR-409 | `unit_flow_input_paths_resolve_and_pure` | Declared paths resolve; compute is pure | FR-301, S3-T04 | Automated |

#### 10.4.11 Factor 11: Fundamentals overlay

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-160 | `unit_fundamentals_score_revenue_growth_minus_10pct_gives_minus_20` | Linear anchor low | FR-3xx, S5-T04 | Deferred |
| TS-SCR-161 | `unit_fundamentals_score_revenue_growth_plus_20pct_gives_plus_20` | Linear anchor high | FR-3xx | Deferred |
| TS-SCR-162 | `unit_fundamentals_score_revenue_growth_plus_5pct_interpolates_linearly` | Midpoint | FR-3xx | Deferred |
| TS-SCR-163 | `unit_fundamentals_score_revenue_growth_beyond_range_clips_at_20` | Clip | FR-3xx | Deferred |
| TS-SCR-164 | `unit_fundamentals_score_eps_growth_minus_20_to_plus_30_maps_minus_20_to_plus_20` | Anchors | FR-3xx | Deferred |
| TS-SCR-165 | `unit_fundamentals_score_gross_margin_change_minus_3pt_to_plus_3pt_maps_minus_15_to_plus_15` | Anchors | FR-3xx | Deferred |
| TS-SCR-166 | `unit_fundamentals_score_fcf_margin_minus_5_to_plus_20_maps_minus_15_to_plus_15` | Anchors | FR-3xx | Deferred |
| TS-SCR-167 | `unit_fundamentals_score_net_debt_ebitda_le_1_gives_plus_10` | Boundary | FR-3xx | Deferred |
| TS-SCR-168 | `unit_fundamentals_score_net_debt_ebitda_ge_4_gives_minus_10` | Boundary | FR-3xx | Deferred |
| TS-SCR-169 | `unit_fundamentals_score_net_debt_ebitda_2_5_interpolates_linearly` | Between | FR-3xx | Deferred |
| TS-SCR-170 | `unit_fundamentals_score_valuation_10th_percentile_gives_plus_20` | Valuation anchor | FR-3xx | Deferred |
| TS-SCR-171 | `unit_fundamentals_score_valuation_90th_percentile_gives_minus_20` | Valuation anchor | FR-3xx | Deferred |
| TS-SCR-172 | `unit_fundamentals_score_negative_earnings_uses_ev_sales_percentile` | Valuation basis switch | FR-3xx | Deferred |
| TS-SCR-173 | `unit_fundamentals_score_sum_clipped_to_minus_100_and_100` | Sum of sub-scores clip | FR-3xx | Deferred |
| TS-SCR-174 | `unit_fundamentals_score_etf_quality_missing_no_score` | QQQ, SPY | FR-3xx | Deferred |
| TS-SCR-175 | `unit_fundamentals_score_older_than_120_days_quality_degraded_weight_halved` | Boundary 120 versus 121 days | FR-3xx | Deferred |
| TS-SCR-176 | `it_fundamentals_ingest_rows_stored_with_known_at_point_in_time` | `known_at` column | FR-3xx, NFR-007 | Deferred |
| TS-SCR-177 | `it_fundamentals_query_as_of_date_before_known_at_does_not_see_row` | Point in time | FR-3xx, S5-T04 | Deferred |
| TS-SCR-178 | `unit_fundamentals_days_to_earnings_stored_in_trading_days_not_in_score` | Event-risk input, excluded from score | FR-3xx | Deferred |
| TS-SCR-179 | `unit_fundamentals_refresh_weekly_and_day_after_earnings` | Refresh schedule logic | FR-3xx, FR-1xx | Deferred |

#### 10.4.12 Factor 12: Ripster EMA Clouds

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SCR-180 | `unit_ripster_score_close_above_c3_bias_adds_30` | `bias` = +30 | FR-333 | Automated |
| TS-SCR-181 | `unit_ripster_score_close_below_c3_bias_subtracts_30` | `bias` = -30 | FR-333 | Automated |
| TS-SCR-182 | `unit_ripster_score_close_inside_c3_pos_0_bias_is_0` | `pos(c3)` = 0 scores 0 for `bias` | FR-333, S3-T14 | Automated |
| TS-SCR-183 | `unit_ripster_score_c2_bullish_trend_adds_20` | `trend` = +20 | FR-333 | Automated |
| TS-SCR-184 | `unit_ripster_score_c2_bearish_trend_subtracts_20` | `trend` = -20 | FR-333 | Automated |
| TS-SCR-185 | `unit_ripster_score_c2_fully_above_c3_stacking_adds_20` | `stack` = +1 | FR-333 | Automated |
| TS-SCR-186 | `unit_ripster_score_c2_fully_below_c3_stacking_subtracts_20` | `stack` = -1 | FR-333 | Automated |
| TS-SCR-187 | `unit_ripster_score_c2_overlapping_c3_stacking_is_0` | Overlapping clouds give 0 | FR-333 | Automated |
| TS-SCR-188 | `unit_ripster_score_c3_bullish_mid_adds_10` | `mid` = +10 | FR-333 | Automated |
| TS-SCR-189 | `unit_ripster_score_c3_bearish_mid_subtracts_10` | `mid` = -10 | FR-333 | Automated |
| TS-SCR-190 | `unit_ripster_score_close_above_c5_long_adds_10` | `long` = +10 | FR-333 | Automated |
| TS-SCR-191 | `unit_ripster_score_close_below_c5_long_subtracts_10` | `long` = -10 | FR-333 | Automated |
| TS-SCR-192 | `unit_ripster_score_close_inside_c5_long_is_0` | `pos(c5)` = 0 | FR-333 | Automated |
| TS-SCR-193 | `unit_ripster_score_pullback_held_low_2_bars_ago_close_above_bot_c1_adds_10` | Held bullish pullback | FR-333, S3-T14 | Automated |
| TS-SCR-194 | `unit_ripster_score_pullback_failed_close_at_or_below_bot_c1_is_0` | Failed bullish pullback | FR-333, S3-T14 | Automated |
| TS-SCR-195 | `unit_ripster_score_pullback_stale_test_4_bars_ago_is_0` | Stale test (4 bars ago) does not count | FR-333, S3-T14 | Automated |
| TS-SCR-196 | `unit_ripster_score_pullback_test_3_bars_ago_counts` | Boundary, resolved with PRD A-25: the window is t-2..t, so a test 2 bars ago (the oldest bar of the 3-bar window) counts and a test 3 bars ago (t-3) does not | FR-333 | Automated |
| TS-SCR-197 | `unit_ripster_score_pullback_bearish_held_stack_minus_1_high_at_or_above_bot_c1_close_below_top_c1_subtracts_10` | Held bearish pullback | FR-333 | Automated |
| TS-SCR-198 | `unit_ripster_score_pullback_bearish_failed_close_at_or_above_top_c1_is_0` | Failed bearish pullback | FR-333 | Automated |
| TS-SCR-199 | `unit_ripster_score_pullback_stack_0_is_0_even_when_c1_tested` | Pullback requires `stack != 0` | FR-333 | Automated |
| TS-SCR-200 | `unit_ripster_score_all_components_bullish_maximum_30_20_20_10_10_10_is_100` | Upper bound | FR-333 | Automated |
| TS-SCR-201 | `unit_ripster_score_all_components_bearish_maximum_is_minus_100` | Lower bound | FR-333 | Automated |
| TS-SCR-202 | `unit_ripster_score_c4_72_89_cloud_is_evidence_only_not_scored` | Changing the 72/89 cloud leaves the score unchanged | FR-333 | Automated |
| TS-SCR-203 | `unit_ripster_score_pullback_lookback_read_from_config_ripster_key` | `ripster.pullback_lookback_bars` | FR-333, A§13 | Automated |
| TS-SCR-204 | `unit_ripster_score_evidence_lists_six_components_and_derived_rc_values` | Components and `rc_*` values in the evidence | FR-333, FR-5xx | Automated |
| TS-SCR-420 | `unit_ripster_score_clip_to_plus_minus_100_when_points_exceed` | Sum above 100 or below -100 is clipped | FR-333, S3-T14 | Automated |
| TS-SCR-421 | `unit_ripster_score_points_read_from_config_ripster_key` | `ripster.points` sets every component | FR-333, S3-T14 | Automated |
| TS-SCR-422 | `unit_ripster_score_reasons_are_deterministic_and_name_the_rule` | Reason templates, one per rule line | FR-333, S3-T14 | Automated |
| TS-SCR-423 | `unit_ripster_score_missing_core_input_is_missing_quality_score_zero` | Null bias, stack, c2 or c3 direction (under 50 bars) gives `missing`, score 0 | FR-333, A-31, S3-T14 | Automated |
| TS-SCR-424 | `unit_ripster_score_c5_not_defined_yet_scores_long_zero_and_is_degraded` | Null 180/200 position (50 to 199 bars): `long` 0, quality `degraded` | FR-333, A-31, S3-T14 | Automated |
| TS-SCR-425 | `unit_ripster_score_is_pure_and_does_not_mutate_the_snapshot` | Purity | FR-333, S3-T14 | Automated |
| TS-SCR-426 | `unit_ripster_score_pullback_bearish_end_to_end_held_failed_and_stale` | Bearish held, failed and stale tests from hand-built bars | FR-333, S3-T14 | Automated |
| TS-SCR-427 | `unit_ripster_score_on_computed_snapshot_reads_every_declared_input` | Factor on `compute_snapshot` output equals an independent evaluation of the rule lines | FR-333, S3-T14 | Automated |
| TS-SCR-428 | `unit_ripster_score_registry_factor_is_the_module_factor` | Registry `ripster` is the implemented factor, not the stub | FR-333, S3-T14 | Automated |
| TS-SCR-429 | `unit_ripster_score_null_cloud_edges_and_weekly_direction_stay_null_in_evidence` | Null edges and weekly direction stay null in the evidence | FR-333, FR-5xx, S3-T14 | Automated |
| TS-SCR-430 | `unit_confidence_stack_penalty_rule_lines (opposing)` | `confidence_stack_penalty` is 10 when `rc_stack == -st_dir_d`, both signs (helper for TS-CMP-031) | FR-335, S3-T14 | Automated |
| TS-SCR-431 | `unit_confidence_stack_penalty_rule_lines (same sign or zero)` | No deduction for same sign or `rc_stack` 0 (helper for TS-CMP-032) | FR-335, S3-T14 | Automated |
| TS-SCR-432 | `unit_confidence_stack_penalty_reads_amount_from_config` | `ripster.confidence_stack_conflict_penalty` | FR-335, S3-T14 | Automated |
| TS-SCR-433 | `unit_confidence_stack_penalty_null_input_gives_no_deduction` | Warm-up nulls never deduct | FR-335, S3-T14 | Automated |

### 10.5 Regime and weights (TS-REG)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-REG-001 | `unit_regime_classify_adx_25_is_trending` | Boundary: ADX >= 25 | FR-3xx, S5-T05 | Automated |
| TS-REG-002 | `unit_regime_classify_adx_24_99_is_transitional` | Just below 25 | FR-3xx | Automated |
| TS-REG-003 | `unit_regime_classify_adx_20_is_transitional` | Boundary: ranging is `< 20` | FR-3xx | Automated |
| TS-REG-004 | `unit_regime_classify_adx_19_99_is_ranging` | Just below 20 | FR-3xx | Automated |
| TS-REG-005 | `unit_weights_base_sum_equals_100` | Twelve base weights sum to 100 | FR-3xx, A§13 | Automated |
| TS-REG-006 | `unit_config_weights_not_summing_to_100_fails_validation_naming_key` | Schema rejects | FR-3xx, S0-T09 | Automated |
| TS-REG-007 | `unit_weights_multiplier_table_every_cell_trending_matches_spec` | One parametrized row per cell, trending column (12 cells) | FR-3xx, S5-T05 | Automated |
| TS-REG-008 | `unit_weights_multiplier_table_every_cell_ranging_matches_spec` | Ranging column (12 cells) | FR-3xx, S5-T05 | Automated |
| TS-REG-009 | `unit_weights_multiplier_table_every_cell_transitional_all_1_0` | Transitional column (12 cells) | FR-3xx, S5-T05 | Automated |
| TS-REG-010 | `unit_weights_renormalize_after_regime_multipliers_sum_exactly_100` | Renormalization | FR-3xx | Automated |
| TS-REG-011 | `unit_weights_event_adjust_days_to_earnings_5_multiplies_fundamentals_1_5` | Boundary: 5 trading days | FR-3xx | Automated |
| TS-REG-012 | `unit_weights_event_adjust_days_to_earnings_6_no_change` | Boundary: 6 | FR-3xx | Automated |
| TS-REG-013 | `unit_weights_event_adjust_sets_event_risk_flag` | `event_risk` flag | FR-3xx, US-010 | Automated |
| TS-REG-014 | `unit_weights_event_adjust_applied_after_regime_before_renormalize` | Order of operations | FR-3xx | Automated |
| TS-REG-015 | `unit_thresholds_fundamentals_score_minus_40_raises_buy_threshold_5` | Boundary: `<= -40` | FR-3xx | Deferred |
| TS-REG-016 | `unit_thresholds_fundamentals_score_minus_39_no_buy_shift` | Just above | FR-3xx | Deferred |
| TS-REG-017 | `unit_thresholds_fundamentals_score_plus_40_lowers_sell_threshold_5` | Boundary: `>= +40` | FR-3xx | Deferred |
| TS-REG-018 | `unit_market_regime_both_benchmarks_down_is_risk_off_buy_plus_5` | QQQ and SPY down | FR-3xx | Deferred |
| TS-REG-019 | `unit_market_regime_both_benchmarks_up_is_risk_on_sell_minus_5` | Both up | FR-3xx | Deferred |
| TS-REG-020 | `unit_market_regime_mixed_is_neutral_no_change` | One up one down | FR-3xx | Deferred |
| TS-REG-021 | `unit_thresholds_adjustments_stack_risk_off_plus_weak_fundamentals_buy_75` | 65 + 5 + 5 | FR-3xx, S5-T05 | Deferred |
| TS-REG-022 | `unit_thresholds_adjustments_stack_risk_on_plus_strong_fundamentals_sell_25` | 35 - 5 - 5 | FR-3xx | Deferred |
| TS-REG-023 | `unit_regime_adjustments_list_records_every_fired_adjustment` | Stored list includes regime, earnings, threshold shifts | FR-3xx, FR-5xx | Deferred |
| TS-REG-024 | `prop_weights_after_any_adjustment_combination_sum_to_100` | All combinations of regime, event, missing factors | FR-3xx, S5-T05 | Automated |
| TS-REG-025 | `unit_weights_missing_factor_redistributes_proportionally_across_others` | ETF fundamentals missing | FR-3xx | Automated |
| TS-REG-026 | `unit_weights_degraded_factor_weight_halved_then_renormalized` | Fundamentals older than 120 days | FR-3xx | Automated |
| TS-REG-027 | `unit_weights_daily_estimate_flow_multiplier_0_6_then_renormalized` | Flow weight times 0.6 | FR-3xx | Automated |
| TS-REG-028 | `unit_weights_all_but_one_factor_missing_remaining_weight_100` | Extreme redistribution | FR-3xx | Automated |
| TS-REG-029 | `unit_weights_sprint3_defaults_all_multipliers_1_fundamentals_missing_paths_exist` | Code paths exist with injected values | FR-3xx, S3-T05 | Automated |
| TS-REG-030 | `it_regime_benchmarks_spy_qqq_used_even_when_not_on_watchlist` | Market regime source | FR-3xx, FR-0xx | Deferred |
| TS-REG-031 | `unit_weights_base_ripster_is_10_and_supertrend_is_20` | New base weights: supertrend 20, sma 7, macd 8, divergence 9, mean_reversion 7, fibonacci 5, levels 7, volatility 4, volume_osc 6, flow 9, fundamentals 8, ripster 10 | FR-3xx, A§13, S3-T14 | Automated |
| TS-REG-032 | `unit_weights_multiplier_ripster_trending_1_20_ranging_0_70_transitional_1_00` | Ripster row of the regime table | FR-3xx, S5-T05 | Automated |
| TS-REG-033 | `unit_config_ripster_block_missing_key_fails_validation_naming_key` | `ripster` block keys validated by the schema (twelve weights) | FR-3xx, S0-T09 | Deferred |
| TS-REG-101 | `unit_weights_adjustments_name_regime_when_it_tilts` | Adjustments list names the regime when multipliers differ from 1.0; empty for transitional or no regime | FR-318, FR-323, S3-T05 | Automated |
| TS-REG-102 | `unit_regime_classify_null_or_nan_adx_is_transitional` | ADX in warm-up gives no tilt | FR-317, S3-T05 | Automated |
| TS-REG-103 | `unit_regime_classify_thresholds_read_from_config` | `regime.trending_min` and `regime.ranging_max` drive the boundaries | FR-317, S3-T05 | Automated |
| TS-REG-104 | `unit_weights_results_must_cover_exactly_the_factor_ids` | Absent, unknown or mislabelled result is a ValueError | FR-324, S3-T05 | Automated |
| TS-REG-105 | `unit_weights_all_factors_missing_raises_no_scorable_factors` | No composite without a scorable factor | FR-324, S3-T05 | Automated |
| TS-REG-106 | `unit_weights_result_is_frozen_with_read_only_mappings` | Frozen record, read-only mappings | FR-318, S3-T05 | Automated |
| TS-REG-107 | `unit_regime_multipliers_unknown_regime_raises` | Unknown regime name is a ValueError naming it | FR-318, S3-T05 | Automated |
| TS-REG-108 | `unit_weights_event_adjust_negative_days_to_earnings_no_change` | A past earnings date is not an event | FR-319, S3-T05 | Automated |
| TS-REG-109 | `unit_weights_event_risk_flag_from_context_without_weight_change` | Injected `event_risk` is carried through | FR-319, S3-T05 | Automated |

### 10.6 Composite, display, bands, confidence (TS-CMP)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-CMP-001 | `unit_composite_compute_weighted_mean_over_non_missing_factors` | `sum(w*s)/sum(w)` | FR-3xx | Automated |
| TS-CMP-002 | `unit_composite_compute_contributions_sum_to_composite_within_1e9` | `contribution = weight*score/100` | FR-3xx, S3-T05 | Automated |
| TS-CMP-003 | `unit_composite_compute_removing_factor_redistributes_weight_proportionally` | Missing factor | FR-3xx, S3-T05 | Automated |
| TS-CMP-004 | `unit_display_compute_composite_zero_is_50_0` | `round((c+100)/2, 1)` | FR-3xx, S3-T05 | Automated |
| TS-CMP-005 | `unit_display_compute_composite_plus_100_is_100` | Upper bound | FR-3xx | Automated |
| TS-CMP-006 | `unit_display_compute_composite_minus_100_is_0` | Lower bound | FR-3xx | Automated |
| TS-CMP-007 | `unit_display_compute_rounds_to_one_decimal_half_even_defined` | Rounding rule is defined and tested | FR-3xx | Automated |
| TS-CMP-008 | `unit_band_assign_80_0_strong_buy` | Boundary | FR-3xx | Automated |
| TS-CMP-009 | `unit_band_assign_79_9_buy` | Boundary | FR-3xx | Automated |
| TS-CMP-010 | `unit_band_assign_65_0_buy` | Boundary | FR-3xx | Automated |
| TS-CMP-011 | `unit_band_assign_64_9_neutral_leaning_up` | Boundary | FR-3xx | Automated |
| TS-CMP-012 | `unit_band_assign_50_0_neutral_leaning_up` | Boundary | FR-3xx | Automated |
| TS-CMP-013 | `unit_band_assign_49_9_neutral_leaning_down` | Boundary | FR-3xx | Automated |
| TS-CMP-014 | `unit_band_assign_35_1_neutral_leaning_down` | Boundary | FR-3xx | Automated |
| TS-CMP-015 | `unit_band_assign_35_0_sell` | Boundary | FR-3xx | Automated |
| TS-CMP-016 | `unit_band_assign_20_1_sell` | Boundary | FR-3xx | Automated |
| TS-CMP-017 | `unit_band_assign_20_0_strong_sell` | Boundary | FR-3xx | Automated |
| TS-CMP-018 | `unit_band_assign_0_0_strong_sell` | Boundary | FR-3xx | Automated |
| TS-CMP-019 | `prop_band_assign_every_display_value_maps_to_exactly_one_band` | No gaps or overlaps over 0.0 to 100.0 step 0.1 | FR-3xx | Automated |
| TS-CMP-020 | `unit_confidence_agreement_share_of_weight_with_same_sign_as_composite` | Agreement in 0..1 | FR-3xx | Automated |
| TS-CMP-021 | `unit_confidence_all_factors_agree_is_100_before_penalties` | Upper bound | FR-3xx | Automated |
| TS-CMP-022 | `unit_confidence_atr_pct_rank_above_90_subtracts_15` | Penalty | FR-3xx | Automated |
| TS-CMP-023 | `unit_confidence_any_factor_degraded_subtracts_10` | Penalty | FR-3xx | Automated |
| TS-CMP-024 | `unit_confidence_weekly_direction_differs_from_daily_subtracts_10` | Penalty | FR-3xx | Automated |
| TS-CMP-025 | `unit_confidence_event_risk_subtracts_10` | Penalty | FR-3xx | Automated |
| TS-CMP-026 | `unit_confidence_all_penalties_stack_subtracts_55` | Sum of penalties (15 + 10 + 10 + 10 + 10) | FR-3xx | Automated |
| TS-CMP-027 | `unit_confidence_clipped_to_0_when_penalties_exceed_agreement` | Lower clip | FR-3xx | Automated |
| TS-CMP-028 | `unit_confidence_zero_composite_sign_handling_defined` | A composite of exactly 0 has a defined agreement rule | FR-3xx | Automated |
| TS-CMP-029 | `unit_confidence_missing_factors_excluded_from_agreement_denominator` | Weight base is over non-missing factors | FR-3xx | Automated |
| TS-CMP-030 | `prop_composite_all_stages_outputs_in_range_for_random_factor_scores` | Composite -100..100, display 0..100, confidence 0..100 | FR-3xx | Automated |
| TS-CMP-031 | `unit_confidence_ripster_stack_opposes_daily_supertrend_subtracts_10` | `rc_stack == -st_dir_d`: confidence reduced by 10 and the deduction is shown | FR-335, S3-T14 | Automated |
| TS-CMP-032 | `unit_confidence_ripster_stack_same_sign_or_zero_no_deduction` | `st_dir_d` = +1 with `rc_stack` = +1 or 0 gives no Ripster deduction | FR-335 | Automated |
| TS-CMP-033 | `unit_confidence_ripster_worked_example_agreement_0_80_gives_70` | Agreement 0.80, `st_dir_d` = -1, `rc_stack` = +1 gives 80 - 10 = 70 | FR-335 | Automated |
| TS-CMP-101 | `unit_scorecard_worked_example_end_to_end` | Composite 3000/92, display 66.3, Buy, confidence 6200/92 on a hand example | FR-324 to FR-327, S3-T05 | Automated |
| TS-CMP-102 | `unit_scorecard_is_frozen_with_read_only_mappings` | Frozen record, read-only mappings | FR-328, S3-T05 | Automated |
| TS-CMP-103 | `unit_scorecard_injected_regime_applies_multipliers_adx_regime_reported` | `regime` from ADX, `regime_applied` from the context | FR-317, FR-318, S3-T05 | Automated |
| TS-CMP-104 | `unit_scorecard_earnings_sets_event_risk_adjustment_and_deduction` | Earnings in 3 days: flag, adjustment text, confidence minus 10 | FR-319, FR-327, S3-T05 | Automated |
| TS-CMP-105 | `unit_scorecard_all_missing_raises` | NoScorableFactorsError | FR-324, S3-T05 | Automated |
| TS-CMP-106 | `unit_scorecard_missing_adx_regime_is_transitional` | Null ADX labels the regime transitional | FR-317, S3-T05 | Automated |
| TS-CMP-107 | `unit_scorecard_deterministic_and_inputs_not_mutated` | Equal cards for equal inputs; inputs untouched | FR-329, S3-T05 | Automated |
| TS-CMP-108 | `unit_scorecard_deductions_listed_in_order_with_reasons` | Order: atr, degraded, weekly, ripster, event; each has a reason | FR-327, S3-T05 | Automated |
| TS-CMP-110 | `unit_band_labels_match_spec` | Band strings are the spec labels | FR-326, S3-T05 | Automated |
| TS-CMP-111 | `unit_band_edges_follow_config_thresholds` | Buy floor and Sell ceiling read from `thresholds` | FR-326, S3-T05 | Automated |
| TS-CMP-112 | `unit_confidence_daily_estimate_is_not_degraded` | Only quality `degraded` costs 10 | FR-327, S3-T05 | Automated |
| TS-CMP-113 | `unit_confidence_ripster_stack_zero_direction_or_null_no_deduction` | `-0 == 0` and null inputs do not fire | FR-335, S3-T05 | Automated |
| TS-CMP-114 | `unit_confidence_ripster_penalty_read_from_config` | Deduction is `ripster.confidence_stack_conflict_penalty` | FR-335, S3-T05 | Automated |
| TS-CMP-115 | `unit_confidence_fr327_worked_example_atr_and_weekly` | 80 - 15 - 10 = 55 | FR-327, S3-T05 | Automated |
| TS-CMP-116 | `unit_confidence_missing_snapshot_path_names_it` | KeyError naming the absent path | FR-327, S3-T05 | Automated |

### 10.7 Selection (TS-SEL)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SEL-001 | `unit_selection_buy_candidate_all_conditions_met_qualifies` | display, direction, confidence, quality, liquidity | FR-4xx | Automated |
| TS-SEL-002 | `unit_selection_buy_candidate_display_64_9_not_qualified` | Boundary of 65 | FR-4xx | Automated |
| TS-SEL-003 | `unit_selection_buy_candidate_display_65_0_qualifies` | Boundary | FR-4xx | Automated |
| TS-SEL-004 | `unit_selection_buy_candidate_st_dir_down_not_qualified` | Direction condition | FR-4xx | Automated |
| TS-SEL-005 | `unit_selection_buy_candidate_confidence_49_not_qualified` | Boundary of 50 | FR-4xx | Automated |
| TS-SEL-006 | `unit_selection_buy_candidate_confidence_50_qualifies` | Boundary | FR-4xx | Automated |
| TS-SEL-007 | `unit_selection_buy_candidate_stale_data_not_qualified` | Data quality | FR-4xx, US-020 | Automated |
| TS-SEL-008 | `unit_selection_buy_candidate_dollar_volume_below_20m_not_qualified` | Liquidity floor | FR-4xx | Automated |
| TS-SEL-009 | `unit_selection_buy_candidate_dollar_volume_exactly_20m_qualifies` | Boundary | FR-4xx | Automated |
| TS-SEL-010 | `unit_selection_buy_candidate_threshold_adjustments_raise_bar_to_75` | Uses per-ticker adjusted threshold | FR-4xx, FR-3xx | Automated |
| TS-SEL-011 | `unit_selection_sell_candidate_all_conditions_met_qualifies` | Mirror rules | FR-4xx | Automated |
| TS-SEL-012 | `unit_selection_sell_candidate_display_35_0_qualifies` | Boundary | FR-4xx | Automated |
| TS-SEL-013 | `unit_selection_sell_candidate_display_35_1_not_qualified` | Boundary | FR-4xx | Automated |
| TS-SEL-014 | `unit_selection_sell_candidate_st_dir_up_not_qualified` | Direction | FR-4xx | Automated |
| TS-SEL-015 | `unit_selection_sell_candidate_threshold_adjustments_lower_bar_to_25` | Adjusted threshold | FR-4xx | Automated |
| TS-SEL-016 | `unit_selection_rank_buys_by_display_descending` | Buy ranking | FR-4xx | Automated |
| TS-SEL-017 | `unit_selection_rank_sells_by_display_ascending` | Sell ranking | FR-4xx | Automated |
| TS-SEL-018 | `unit_selection_tiebreak_equal_display_higher_confidence_wins` | Tie-breaker 1 | FR-4xx | Automated |
| TS-SEL-019 | `unit_selection_tiebreak_equal_confidence_more_recent_flip_wins` | Tie-breaker 2 | FR-4xx | Automated |
| TS-SEL-020 | `unit_selection_tiebreak_equal_flip_higher_relative_volume_wins` | Tie-breaker 3 | FR-4xx | Automated |
| TS-SEL-021 | `unit_selection_tiebreak_all_equal_alphabetical_ticker_wins` | Tie-breaker 4 | FR-4xx | Automated |
| TS-SEL-022 | `prop_selection_rank_independent_of_input_order` | Shuffled input gives the same result | FR-4xx, NFR-002 | Automated |
| TS-SEL-023 | `unit_selection_publish_top_3_buys_and_top_2_sells_by_default` | Max counts | FR-4xx | Automated |
| TS-SEL-024 | `unit_selection_max_counts_read_from_config_selection_keys` | `max_buys`, `max_sells` | FR-4xx, A§13 | Automated |
| TS-SEL-025 | `unit_selection_only_one_qualifying_buy_result_has_one_buy_not_three` | Never pad | FR-4xx, S3-T06 | Automated |
| TS-SEL-026 | `unit_selection_zero_qualifying_sells_result_has_empty_sell_side` | Empty side is valid | FR-4xx | Automated |
| TS-SEL-027 | `unit_selection_empty_side_records_nearest_miss_with_reason` | Nearest-miss record | FR-4xx, S3-T06 | Automated |
| TS-SEL-028 | `unit_selection_correlation_guard_skips_candidate_above_0_9_with_selected_pick` | Guard | FR-4xx | Automated |
| TS-SEL-029 | `unit_selection_correlation_guard_exactly_0_9_is_not_skipped` | Boundary: "above 0.9" | FR-4xx | Automated |
| TS-SEL-030 | `unit_selection_correlation_guard_spy_voo_ivv_only_top_one_selected` | Three near-duplicates qualify | FR-4xx, S3-T06 | Automated |
| TS-SEL-031 | `unit_selection_correlation_guard_skipped_listed_as_also_qualified_with_duplicate_of` | "Also qualified" entry names the duplicated pick | FR-4xx | Automated |
| TS-SEL-032 | `unit_selection_correlation_guard_applied_per_side_not_across_sides` | Buy and sell sides independent | FR-4xx | Automated |
| TS-SEL-033 | `unit_selection_correlation_guard_uses_60_day_return_window` | Window | FR-4xx, A§13 | Automated |
| TS-SEL-034 | `unit_selection_correlation_guard_walks_past_skipped_to_fill_side` | Continue until full or exhausted | FR-4xx | Automated |
| TS-SEL-035 | `unit_selection_excluded_stale_and_insufficient_history_listed_with_reasons` | Exclusions never silently dropped | FR-4xx, US-020 | Automated |
| TS-SEL-036 | `unit_selection_stickiness_none_ticker_may_repeat_consecutive_days` | No stickiness rule | FR-4xx | Automated |
| TS-SEL-037 | `unit_selection_day_n_on_list_counter_counts_consecutive_days` | "day N on the list" | FR-4xx, FR-7xx | Automated |
| TS-SEL-038 | `unit_selection_sell_is_bearish_label_no_short_instruction_in_output` | No shorting, sizing, instrument advice in payload text | FR-4xx, FR-5xx | Automated |
| TS-SEL-039 | `unit_selection_buy_candidate_rc_bias_minus_1_not_qualified_reason_close_below_34_50_cloud` | Close below the 34/50 cloud rejects a buy and records the reason | FR-334, S3-T14 | Automated |
| TS-SEL-040 | `unit_selection_buy_candidate_rc_bias_0_close_inside_34_50_cloud_qualifies` | Close inside the cloud passes the buy gate | FR-334, S3-T14 | Automated |
| TS-SEL-041 | `unit_selection_buy_candidate_rc_bias_plus_1_passes_ripster_gate` | Close above the cloud passes the buy gate | FR-334 | Automated |
| TS-SEL-042 | `unit_selection_sell_candidate_rc_bias_plus_1_not_qualified_reason_close_above_34_50_cloud` | Close above the 34/50 cloud rejects a sell and records the reason | FR-334, S3-T14 | Automated |
| TS-SEL-043 | `unit_selection_sell_candidate_rc_bias_0_close_inside_34_50_cloud_qualifies` | Close inside the cloud passes the sell gate | FR-334, S3-T14 | Automated |
| TS-SEL-044 | `unit_selection_sell_candidate_rc_bias_minus_1_passes_ripster_gate` | Close below the cloud passes the sell gate | FR-334 | Automated |
| TS-SEL-045 | `unit_selection_ripster_gate_rejection_listed_in_nearest_miss_reasons` | A gate rejection appears as the nearest-miss reason when a side is empty | FR-334, FR-4xx | Automated |
| TS-SEL-101 | `unit_selection_input_from_snapshot_reads_selection_input_paths` | The selection input builder reads exactly `SELECTION_INPUT_PATHS`; a null or NaN value (warm-up) becomes None, never 0; an absent path is a KeyError naming it | FR-4xx, ADR-065, S3-T06 | Automated |
| TS-SEL-102 | `unit_selection_candidate_reasons_in_rule_order` | Every failing rule is listed, in the order of the selection rules | FR-4xx, ADR-050 | Automated |
| TS-SEL-103 | `unit_selection_candidate_null_inputs_fail_with_reasons` | Null direction, bias or dollar volume fail closed with a reason; an unrounded confidence prints with up to two decimals | FR-4xx, ADR-065 | Automated |
| TS-SEL-104 | `unit_selection_rc_bias_gate_disabled_and_unknown_side` | `ripster.selection_bias_gate: false` passes everything; a bad side, empty ticker, or a negative or non-finite threshold shift raises | FR-334, S3-T06 | Automated |
| TS-SEL-105 | `unit_selection_nearest_miss_score_clearing_threshold_is_distance_zero` | Nearest-miss distance is the score shortfall against the adjusted threshold, 0 when the score clears it and another rule failed; ties use the side's ranking | FR-4xx, ADR-065 | Automated |
| TS-SEL-106 | `unit_selection_nearest_miss_absent_when_full_or_nothing_missed` | A full side has no nearest miss; stale and guard-skipped candidates are not misses | FR-4xx, ADR-065 | Automated |
| TS-SEL-107 | `unit_selection_correlation_undefined_never_skips` | Too little shared history, a flat series, or no closes has no correlation and is never "above 0.9" | FR-4xx, A-33 | Automated |
| TS-SEL-108 | `unit_selection_return_correlation_uses_shared_dates_only` | Simple returns and Pearson on hand values; only dates both series share are used | FR-4xx, A-33 | Automated |
| TS-SEL-109 | `unit_selection_duplicate_names_most_correlated_pick` | A guard-skipped candidate correlated with two picks is listed under the more correlated one | FR-4xx, ADR-065 | Automated |
| TS-SEL-110 | `unit_selection_candidates_after_side_full_not_walked` | The walk stops when the side is full, so a later duplicate is not listed as also qualified | FR-4xx, ADR-065 | Automated |
| TS-SEL-111 | `unit_selection_select_rejects_duplicate_tickers_and_bad_side` | The same ticker twice, an unknown side, a non-positive or non-finite close, or a window below 2 is a ValueError | FR-4xx | Automated |
| TS-SEL-112 | `unit_selection_select_is_pure_and_deterministic` | Same inputs give an equal result; inputs are not mutated | FR-4xx, NFR-002 | Automated |
| TS-SEL-113 | `unit_selection_import_boundary_no_api_cli_mcp_data_runs` | Selection imports nothing from api, cli, mcp, data, runs or narrative | A§2 | Automated |
| TS-SEL-114 | `unit_selection_null_tie_breakers_rank_last` | An unknown flip age or relative volume ranks after any known one | FR-4xx, ADR-065 | Automated |
| TS-SEL-115 | `unit_selection_max_zero_publishes_nothing_and_no_nearest_miss` | `max_buys: 0` publishes no buys; the side is full, so no nearest miss | FR-4xx, A§13 | Automated |
| TS-SEL-150 | `unit_selection_bias_gate_rule_lines (buy, close below cloud)` | `selection_bias_gate(snapshot, 'buy')` rejects with reason `close below the 34/50 cloud` (helper for TS-SEL-039) | FR-334, S3-T14 | Automated |
| TS-SEL-151 | `unit_selection_bias_gate_rule_lines (buy, inside)` | Buy passes inside the cloud (helper for TS-SEL-040) | FR-334, S3-T14 | Automated |
| TS-SEL-152 | `unit_selection_bias_gate_rule_lines (buy, above)` | Buy passes above the cloud (helper for TS-SEL-041) | FR-334, S3-T14 | Automated |
| TS-SEL-153 | `unit_selection_bias_gate_rule_lines (sell, close above cloud)` | Sell rejected with reason `close above the 34/50 cloud` (helper for TS-SEL-042) | FR-334, S3-T14 | Automated |
| TS-SEL-154 | `unit_selection_bias_gate_rule_lines (sell, inside)` | Sell passes inside the cloud (helper for TS-SEL-043) | FR-334, S3-T14 | Automated |
| TS-SEL-155 | `unit_selection_bias_gate_rule_lines (sell, below)` | Sell passes below the cloud (helper for TS-SEL-044) | FR-334, S3-T14 | Automated |
| TS-SEL-156 | `unit_selection_bias_gate_disabled_passes_everything` | `ripster.selection_bias_gate: false` disables the gate | FR-334, S3-T14 | Automated |
| TS-SEL-157 | `unit_selection_bias_gate_null_bias_fails_closed_with_reason` | Undefined bias rejects with `34/50 cloud bias not available` | FR-334, A-31, S3-T14 | Automated |
| TS-SEL-158 | `unit_selection_bias_gate_unknown_side_raises` | Side other than buy or sell raises ValueError | FR-334, S3-T14 | Automated |
| TS-SEL-159 | `unit_selection_bias_gate_does_not_read_other_fields_or_mutate` | Verdict depends on `ripster.bias` only; no mutation | FR-334, S3-T14 | Automated |

### 10.8 Justification and narrative (TS-NAR)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-NAR-001 | `unit_evidence_build_document_validates_against_committed_json_schema` | Evidence JSON schema | FR-5xx, S3-T08 | Automated |
| TS-NAR-002 | `unit_evidence_build_contributions_sum_to_composite` | `contribution = weight*score/100` | FR-5xx | Automated |
| TS-NAR-003 | `unit_evidence_build_includes_invalidation_level_and_rule` | Supertrend line and rule text | FR-5xx, US-007 | Automated |
| TS-NAR-004 | `unit_evidence_build_includes_levels_support_resistance_fib_next_target` | Levels block | FR-5xx | Automated |
| TS-NAR-005 | `unit_evidence_build_includes_adjustments_flags_and_config_hash` | Adjustments, flags, `config_hash` | FR-5xx | Automated |
| TS-NAR-006 | `unit_narrative_template_leads_with_supertrend_and_34_50_cloud_bias_then_top_two_then_opposing_then_invalidation` | Order: Supertrend state and the 34/50 cloud bias first | FR-5xx | Automated |
| TS-NAR-007 | `unit_narrative_template_every_number_appears_in_evidence_document` | Template passes its own guard | FR-5xx, S3-T08 | Automated |
| TS-NAR-008 | `unit_narrative_template_three_to_five_sentences` | Length | FR-5xx | Automated |
| TS-NAR-009 | `unit_narrative_template_no_opposing_factor_omits_line_without_inventing` | No factor argues against | FR-5xx | Automated |
| TS-NAR-010 | `unit_narrative_prompt_token_budget_all_30_fixtures_at_most_900_tokens` | NFR-012 prompt side | NFR-012, S5-T01 | Deferred |
| TS-NAR-011 | `unit_narrative_request_max_completion_tokens_220_enforced` | Completion cap in the request | NFR-012 | Deferred |
| TS-NAR-012 | `unit_narrative_prompt_over_budget_fixture_fails_ci_check` | The check can fail | NFR-012 | Deferred |
| TS-NAR-013 | `unit_narrative_metrics_prompt_and_completion_tokens_emitted` | `supertrends_narrative_tokens{kind}` | NFR-012, A§11 | Deferred |
| TS-NAR-014 | `eval_narrative_live_acceptance_rate_at_least_90pct_on_stoke_model` | Live evaluation against the configured endpoint, results recorded in `docs/NARRATIVE_EVAL.md` | FR-5xx, S5-T03 | Skipped: needs a live model endpoint, and no test may call the network in CI; manual: run `make narrative-eval` against the Stoke gateway (or a local OpenAI-compatible mock for the command itself) and record acceptance, mean tokens, latency |
| TS-NAR-015 | `eval_narrative_recorded_responses_30_documents_no_unmatched_number` | Recorded-response test in CI | FR-5xx, S5-T03 | Deferred |
| TS-NAR-016 | `unit_numeric_guard_number_not_in_evidence_rejects` | Unmatched number rejects | FR-5xx, S5-T02 | Deferred |
| TS-NAR-017 | `unit_numeric_guard_number_matching_within_rounding_accepts` | 212.4 versus 212.40 | FR-5xx | Deferred |
| TS-NAR-018 | `unit_numeric_guard_percent_and_decimal_formats_extracted` | `3.2%`, `1,234.5`, `-4` | FR-5xx | Deferred |
| TS-NAR-019 | `unit_numeric_guard_number_words_and_digits_both_checked` | "three bars" matches bars_since_flip 3 | FR-5xx | Deferred |
| TS-NAR-020 | `unit_numeric_guard_price_target_beyond_next_target_rejected` | No targets beyond `next_target` | FR-5xx | Deferred |
| TS-NAR-021 | `unit_banned_phrases_guaranteed_rejected` | Forbidden word | FR-5xx, S5-T02 | Deferred |
| TS-NAR-022 | `unit_banned_phrases_will_rejected_word_boundary_aware` | "will" rejected, "willing" and "Williams" not falsely rejected | FR-5xx | Deferred |
| TS-NAR-023 | `unit_banned_phrases_cant_lose_variants_rejected` | `can't lose`, `cannot lose`, curly apostrophe | FR-5xx | Deferred |
| TS-NAR-024 | `unit_banned_phrases_position_size_options_leverage_advice_rejected` | Advice terms | FR-5xx | Deferred |
| TS-NAR-025 | `unit_narrative_length_check_two_sentences_rejected_six_rejected` | 3 to 5 | FR-5xx | Deferred |
| TS-NAR-026 | `it_narrative_llm_timeout_8s_retry_once_temperature_0_then_template` | Timeout path | FR-5xx, S5-T02 | Deferred |
| TS-NAR-027 | `it_narrative_llm_endpoint_error_500_falls_back_to_template_run_publishes` | Error path | FR-5xx, US-019 | Deferred |
| TS-NAR-028 | `it_narrative_llm_rejected_first_accepted_on_retry_source_llm` | Retry success | FR-5xx | Deferred |
| TS-NAR-029 | `it_narrative_llm_rejected_twice_source_template_model_recorded` | Both attempts rejected | FR-5xx | Deferred |
| TS-NAR-030 | `it_narrative_stored_record_has_source_model_name_and_prompt_version` | Stored fields | FR-5xx, S5-T01 | Deferred |
| TS-NAR-031 | `it_narrative_metrics_count_accepted_rejected_fallback` | `supertrends_narrative_total{source,result}` | FR-5xx, A§11 | Deferred |
| TS-NAR-032 | `it_narrative_failure_never_changes_score_rank_or_selection` | Link to determinism 7.1 item 5 | NFR-002 | Deferred |
| TS-NAR-033 | `unit_narrative_prompt_excludes_provider_supplied_strings_company_names_news` | Prompt injection control | FR-5xx, A§9 | Deferred |
| TS-NAR-034 | `unit_narrative_output_rendered_as_plain_text_html_and_markdown_links_escaped` | Untrusted output | FR-5xx, A§9 | Deferred |
| TS-NAR-035 | `unit_narrative_provider_base_url_only_from_config_not_request_input` | SSRF control | A§9 | Deferred |
| TS-NAR-036 | `it_narrative_mock_endpoint_run_publishes_llm_narratives` | Sprint 5 checklist item | FR-5xx | Deferred |
| TS-NAR-037 | `unit_narrative_prompt_versioned_in_prompts_directory_version_in_record` | Prompt versioning | FR-5xx | Deferred |
| TS-NAR-038 | `unit_narrative_disclaimer_present_in_every_narrative_payload` | Disclaimer attached | FR-5xx, A§9 | Deferred |
| TS-NAR-039 | `unit_evidence_build_includes_ripster_block_and_levels_cloud_34_50` | `ripster` block and `levels.cloud_34_50` validate against the committed schema | FR-5xx, S3-T14 | Automated |
| TS-NAR-101 | `unit_evidence_build_is_json_serializable_pure_and_deterministic` | Plain JSON, no NaN, no argument mutation, same input same bytes | FR-5xx, S3-T08 | Automated |
| TS-NAR-102 | `unit_evidence_build_flags_event_risk_degraded_and_estimated_flow` | Flags from the card, factor qualities and data quality | FR-5xx, S3-T08 | Automated |
| TS-NAR-103 | `unit_evidence_build_embeds_duplicates_from_also_qualified` | Guard-skipped candidates listed under the pick they duplicate; market regime passed through | FR-5xx, S3-T08 | Automated |
| TS-NAR-104 | `unit_evidence_schema_rejects_missing_and_unknown_fields` | The schema can fail: missing key, extra key, bad side | FR-5xx, S3-T08 | Automated |
| TS-NAR-105 | `unit_evidence_build_rejects_results_that_do_not_match_the_card` | Results must cover exactly the twelve factors | FR-5xx, S3-T08 | Automated |
| TS-NAR-106 | `unit_narrative_template_sell_is_bearish_label_without_trade_advice` | Sell reads bearish; no shorting, sizing, options, leverage, "will" | FR-5xx, S3-T08 | Automated |
| TS-NAR-107 | `unit_narrative_template_is_deterministic_and_reports_numbers` | Same document, same result; numbers and sentence count reported | FR-5xx, S3-T08 | Automated |
| TS-NAR-108 | `unit_narrative_template_handles_missing_line_and_unknown_cloud_bias` | Nulls never print None or an invented number | FR-5xx, S3-T08 | Automated |
| TS-NAR-109 | `unit_numeric_guard_number_not_in_evidence_rejects` | Template-side check of the guard (S5-T02 hardens it) | FR-5xx, S3-T08 | Automated |
| TS-NAR-110 | `unit_numeric_guard_number_matching_within_rounding_accepts` | Match within the narrative number's own rounding | FR-5xx, S3-T08 | Automated |
| TS-NAR-111 | `unit_numeric_guard_percent_and_decimal_formats_extracted` | Extraction of percent, thousands comma, signs, 34/50 | FR-5xx, S3-T08 | Automated |
| TS-NAR-112 | `unit_numeric_guard_collects_numbers_from_values_and_reason_strings` | Evidence pool: numeric leaves and numbers inside strings | FR-5xx, S3-T08 | Automated |
| TS-NAR-150 | `unit_evidence_ripster_block_has_exactly_the_spec_keys_with_integer_signs` | `ripster_evidence` keys and int/float types match the spec example | FR-5xx, S3-T14 | Automated |
| TS-NAR-151 | `unit_evidence_ripster_block_bearish_values` | Negative signs and zero stack | FR-5xx, S3-T14 | Automated |
| TS-NAR-152 | `unit_evidence_ripster_block_null_fields_stay_null_never_zero` | Nulls stay None | FR-5xx, S3-T14 | Automated |
| TS-NAR-153 | `unit_evidence_ripster_block_is_json_serializable_and_pure` | Plain JSON types, no aliasing or mutation | FR-5xx, S3-T14 | Automated |
| TS-NAR-154 | `unit_evidence_ripster_block_from_computed_snapshot_matches_its_fields` | On a real snapshot every key equals the snapshot field | FR-5xx, S3-T14 | Automated |

### 10.9 Track record (TS-TRK)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-TRK-001 | `it_outcomes_entry_price_is_next_session_open` | `entry_price` set when the next session has opened | FR-6xx, S6-T01 | Deferred |
| TS-TRK-002 | `it_outcomes_entry_price_not_set_before_next_session_opens` | No early fill | FR-6xx | Deferred |
| TS-TRK-003 | `unit_outcomes_forward_returns_1_5_10_20_match_handcomputed_on_fixture` | Horizons | FR-6xx, S6-T01 | Deferred |
| TS-TRK-004 | `unit_outcomes_spy_return_same_window_as_pick` | Benchmark window alignment | FR-6xx | Deferred |
| TS-TRK-005 | `unit_outcomes_not_computed_before_horizon_session_has_closed` | Horizon not yet closed | FR-6xx, NFR-007 | Deferred |
| TS-TRK-006 | `unit_outcomes_split_between_entry_and_exit_uses_adjusted_prices` | Corporate action | FR-6xx | Deferred |
| TS-TRK-007 | `it_outcomes_append_only_per_recommendation_and_horizon` | No update of an outcome | FR-6xx, A§5 | Deferred |
| TS-TRK-008 | `it_outcomes_rerun_is_idempotent_no_duplicate_rows` | Repeat run | FR-6xx | Deferred |
| TS-TRK-009 | `unit_stats_buy_hit_is_positive_excess_return_vs_spy` | Buy hit | FR-6xx | Deferred |
| TS-TRK-010 | `unit_stats_sell_hit_is_negative_excess_return_vs_spy` | Sell hit | FR-6xx | Deferred |
| TS-TRK-011 | `unit_stats_excess_return_exactly_zero_is_not_a_hit_either_side` | Zero handling defined | FR-6xx | Deferred |
| TS-TRK-012 | `unit_stats_hit_rate_mean_median_worst_match_pandas_reference` | Reference computation | FR-6xx, S6-T02 | Deferred |
| TS-TRK-013 | `unit_stats_sample_size_reported_next_to_every_statistic` | n beside each stat | FR-6xx | Deferred |
| TS-TRK-014 | `unit_stats_sample_19_labeled_small_sample` | Boundary under 20 | FR-6xx | Deferred |
| TS-TRK-015 | `unit_stats_sample_20_not_labeled_small_sample` | Boundary 20 | FR-6xx | Deferred |
| TS-TRK-016 | `unit_stats_group_by_side_horizon_overall_and_by_band` | Groupings | FR-6xx | Deferred |
| TS-TRK-017 | `unit_stats_empty_range_returns_zeros_sample_size_0_not_error` | Empty range | FR-6xx, S6-T02 | Deferred |
| TS-TRK-018 | `unit_stats_worst_pick_reported_per_side_per_horizon` | Worst pick | FR-6xx | Deferred |
| TS-TRK-019 | `contract_api_track_record_filters_from_to_side_band_config_version` | Filter params and validation | FR-6xx, A§6.1 | Deferred |
| TS-TRK-020 | `unit_stats_losing_picks_included_with_same_weight_as_winners` | No survivorship filter | FR-6xx | Deferred |
| TS-TRK-021 | `it_config_versions_every_distinct_hash_stored_with_full_document` | `config_versions` | FR-6xx, S5-T07 | Deferred |
| TS-TRK-022 | `it_recommendation_displays_exact_config_that_produced_it` | Config lookup by hash | FR-6xx, US-012, US-013 | Deferred |
| TS-TRK-023 | `unit_config_version_check_weight_change_without_bump_fails_ci_script` | `scoring.version` rule | FR-6xx, S5-T07 | Deferred |

### 10.10 Backtest (TS-BKT)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-BKT-001 | `it_backtest_fixture_dataset_reproduces_live_run_picks_for_same_dates` | Same code path as live | FR-6xx, S6-T03 | Deferred |
| TS-BKT-002 | `prop_backtest_indicators_at_day_t_use_bars_up_to_t_only` | No look-ahead | NFR-007, FR-6xx | Deferred |
| TS-BKT-003 | `unit_backtest_entry_is_next_session_open` | Entry rule | FR-6xx | Deferred |
| TS-BKT-004 | `it_backtest_fundamentals_use_value_known_at_t` | Point in time | FR-6xx, S5-T04 | Deferred |
| TS-BKT-005 | `it_backtest_leaky_indicator_injected_is_caught_by_lookahead_check` | Negative control | NFR-007, S6-T03 | Deferred |
| TS-BKT-006 | `it_backtest_writes_only_to_backtests_schema_never_published_recommendations` | Isolation | FR-6xx, A§5 | Deferred |
| TS-BKT-007 | `unit_backtest_equity_curve_equal_weight_daily_buys_hold_5_days_vs_spy` | Curve definition | FR-6xx | Deferred |
| TS-BKT-008 | `unit_backtest_output_json_and_markdown_summary_generated` | Outputs | FR-6xx | Deferred |
| TS-BKT-009 | `unit_backtest_results_labeled_hypothetical_in_json_markdown_and_api` | Label on every surface | FR-6xx | Deferred |
| TS-BKT-010 | `unit_perf_backtest_2_years_20_tickers_under_3_minutes_on_2_cores` | Runtime budget | FR-6xx, S6-T03 | Deferred |
| TS-BKT-011 | `unit_backtest_from_after_to_returns_usage_error` | Argument validation | FR-6xx, A§6.2 | Deferred |
| TS-BKT-012 | `unit_backtest_config_file_other_than_default_records_its_hash` | `--config` path | FR-6xx | Deferred |
| TS-BKT-013 | `unit_backtest_non_trading_dates_skipped_without_error` | Calendar | FR-6xx | Deferred |
| TS-BKT-014 | `unit_backtest_track_record_statistics_same_functions_as_live_stats` | Reuse | FR-6xx | Deferred |

### 10.11 API (TS-API)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-API-001 | `contract_api_healthz_returns_200_status_ok` | `{"status":"ok"}` | FR-8xx, A§6.1 | Automated |
| TS-API-002 | `contract_api_readyz_database_down_returns_503` | Readiness | FR-8xx, S1-T08 | Automated |
| TS-API-003 | `contract_api_readyz_migrations_behind_head_returns_503` | Migration check | FR-8xx | Automated |
| TS-API-004 | `contract_api_metrics_returns_prometheus_text` | `/metrics` | FR-8xx, A§11 | Automated |
| TS-API-005 | `contract_api_recommendations_latest_shape_matches_openapi` | Schema | FR-8xx | Deferred |
| TS-API-006 | `contract_api_recommendations_latest_includes_disclaimer_string` | Disclaimer | FR-8xx, A§9 | Deferred |
| TS-API-007 | `contract_api_recommendations_by_date_returns_that_days_published_run` | Date browse | FR-8xx, US-012 | Deferred |
| TS-API-008 | `contract_api_recommendations_by_date_non_trading_date_returns_422` | Validation | FR-8xx | Deferred |
| TS-API-009 | `contract_api_recommendations_by_date_no_run_returns_404_problem` | Not found | FR-8xx | Deferred |
| TS-API-010 | `contract_api_rankings_by_date_sorted_with_data_quality_and_exclusions` | Ranking | FR-8xx | Deferred |
| TS-API-011 | `contract_api_ticker_analysis_returns_11_factors_or_stated_reason` | Analysis | FR-8xx, US-016 | Deferred |
| TS-API-012 | `contract_api_ticker_analysis_unknown_symbol_returns_404` | Error | FR-8xx | Deferred |
| TS-API-013 | `contract_api_ticker_analysis_invalid_symbol_returns_422` | Regex | FR-8xx, A§9 | Deferred |
| TS-API-014 | `contract_api_ticker_bars_range_and_pagination_bounded` | Bars endpoint | FR-8xx, A§9 | Deferred |
| TS-API-015 | `contract_api_runs_list_pagination_bounded` | Runs list | FR-8xx | Deferred |
| TS-API-016 | `contract_api_runs_get_by_id_returns_state_history_and_exclusions` | Run detail | FR-8xx | Deferred |
| TS-API-017 | `contract_api_post_runs_without_token_returns_401` | Auth | FR-8xx, A§9 | Deferred |
| TS-API-018 | `contract_api_post_runs_wrong_token_returns_401_constant_time_compare` | Auth, compare function is `hmac.compare_digest` | FR-8xx, A§9 | Deferred |
| TS-API-019 | `contract_api_post_runs_with_token_returns_202_and_run_id` | Accepted | FR-8xx | Deferred |
| TS-API-020 | `contract_api_post_runs_while_running_returns_409_already_running` | Concurrency | FR-8xx, S3-T07 | Deferred |
| TS-API-021 | `contract_api_config_scoring_returns_active_config_and_hash` | Config view | FR-8xx | Deferred |
| TS-API-022 | `contract_api_status_returns_version_commit_and_license_notice` | License notice | FR-8xx, A§9 | Deferred |
| TS-API-023 | `contract_api_errors_use_rfc_9457_problem_json` | Error format | FR-8xx, S1-T08 | Automated |
| TS-API-024 | `contract_api_openapi_document_matches_committed_docs_openapi_json` | Drift check | FR-8xx, S3-T09 | Deferred |
| TS-API-025 | `contract_api_write_endpoints_rate_limited_returns_429` | Rate limit | FR-8xx, A§9 | Deferred |
| TS-API-026 | `contract_api_unknown_host_header_rejected` | `SUPERTRENDS_ALLOWED_HOSTS` | FR-8xx, A§9 | Automated |
| TS-API-027 | `contract_api_json_logs_valid_json_lines_with_request_id` | Log format | A§9, A§11 | Automated |
| TS-API-028 | `unit_logging_scrubber_secret_values_never_appear_in_log_output` | Log-scrubbing test | NFR-009, S1-T08 | Automated |
| TS-API-029 | `unit_perf_api_read_endpoints_p95_under_200ms_200_tickers_1_year_runs` | NFR-004 benchmark | NFR-004 | Deferred |
| TS-API-030 | `contract_api_watchlist_endpoints_cover_every_documented_error` | Per-endpoint errors | FR-8xx, A§6.1 | Deferred |
| TS-API-031 | `it_api_serves_ui_dist_with_hashed_assets_immutable_index_no_cache` | Cache headers | FR-8xx, S4-T07 | Deferred |
| TS-API-032 | `it_api_spa_fallback_deep_link_returns_index_html` | Deep links | FR-8xx, S4-T07 | Deferred |
| TS-API-033 | `contract_api_csp_header_present_no_inline_script_connect_src_self` | CSP | FR-8xx, A§9 | Deferred |
| TS-API-034 | `contract_api_security_headers_nosniff_referrer_no_referrer_frame_ancestors_none` | Headers | A§9 | Deferred |
| TS-API-035 | `contract_api_every_pick_payload_carries_disclaimer_on_all_endpoints` | Disclaimer on rankings, analysis, latest, by date | A§9 | Deferred |
| TS-API-036 | `contract_api_request_id_echoed_when_safe_else_generated` | `X-Request-ID` accepted if safe, else replaced; always in the response header | A§6.0, S1-T08 | Automated |
| TS-API-037 | `contract_api_host_allowlist_exempts_healthz_readyz_metrics_only` | 421 problem for foreign Host except the three probe paths | A§9, ADR-024, S1-T08 | Automated |
| TS-API-038 | `contract_api_unhandled_error_returns_500_problem_without_stack_or_secret` | `internal` problem, request ID in body | A§6.1, S1-T08 | Automated |
| TS-API-039 | `contract_api_validation_error_returns_422_problem_with_errors_member` | `validation-error` problem | A§6.1, S1-T08 | Automated |
| TS-API-040 | `contract_api_metrics_http_series_use_route_template_not_raw_path` | No high-cardinality labels | A§11.1, S1-T08 | Automated |
| TS-API-041 | `it_api_readyz_200_at_head_503_when_unmigrated_against_real_postgres` | Real database | A§6.1, S1-T08 | Automated |
| TS-API-042 | `unit_api_write_token_dependency_401_with_www_authenticate_on_missing_or_wrong_token` | `require_write_token` | A§6.1, A§9, S1-T08 | Automated |

### 10.12 UI (TS-UI)

Component tests use vitest and Testing Library; flows use Playwright against `make up` with the fixture provider.

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-UI-001 | `unit_ui_components_every_state_renders_button_card_badge_dial_ribbon_bar` | Each design-system component in each state | FR-7xx, S4-T01 | Deferred |
| TS-UI-002 | `unit_ui_tokens_light_and_dark_themes_define_all_css_custom_properties` | Token completeness | FR-7xx | Deferred |
| TS-UI-003 | `unit_ui_store_theme_selected_date_token_persistence_rules` | Zustand store; token in memory by default | FR-7xx, S4-T06 | Deferred |
| TS-UI-004 | `unit_ui_lib_api_client_error_500_surfaces_error_state` | Typed client | FR-7xx, S4-T02 | Deferred |
| TS-UI-005 | `e2e_us001_today_shows_three_buys_two_sells_without_clicks` | Today screen | US-001, FR-7xx | Deferred |
| TS-UI-006 | `e2e_us001_today_one_buy_shows_one_card_and_no_more_qualifying_buys_line` | Never pad in UI | US-001, FR-7xx | Deferred |
| TS-UI-007 | `e2e_us001_today_empty_side_shows_nearest_miss_line` | Nearest miss | FR-7xx | Deferred |
| TS-UI-008 | `e2e_us001_today_buy_and_sell_distinguishable_in_grayscale` | Not color alone | NFR-011, S4-T03 | Deferred |
| TS-UI-009 | `e2e_us001_today_card_shows_flags_event_risk_and_estimated_order_flow` | Flags | FR-7xx | Deferred |
| TS-UI-010 | `e2e_us001_today_card_shows_day_n_on_the_list_and_group_membership` | Card fields | FR-7xx | Deferred |
| TS-UI-011 | `e2e_us001_today_group_filter_reranks_without_changing_published_picks` | Group filter | FR-7xx, S4-T03 | Deferred |
| TS-UI-012 | `e2e_us002_card_shows_narrative_and_factor_breakdown_in_one_view` | Read a card in under 30 seconds (content present) | US-002, FR-7xx | Deferred |
| TS-UI-013 | `e2e_us003_ticker_shows_supertrend_direction_and_bars_since_flip` | Supertrend visible | US-003 | Deferred |
| TS-UI-014 | `e2e_us004_watchlist_add_remove_group_ticker_roundtrip` | Watchlist management | US-004 | Deferred |
| TS-UI-015 | `e2e_us005_ticker_chart_overlays_supertrend_sma_fib_levels_present` | Chart overlays | US-005 | Deferred |
| TS-UI-016 | `e2e_us005_chart_supertrend_series_length_and_last_value_match_api` | Overlay matches API | US-005, S4-T04 | Deferred |
| TS-UI-017 | `e2e_us005_chart_overlay_toggle_persists_per_browser` | Persistence | S4-T04 | Deferred |
| TS-UI-018 | `e2e_us005_chart_keyboard_reachable_and_data_table_alternative_present` | Accessibility of chart | NFR-011, S4-T04 | Deferred |
| TS-UI-019 | `e2e_us005_chart_subpanels_macd_rsi_volume_rendered` | Sub-panels | FR-7xx | Deferred |
| TS-UI-020 | `e2e_us006_rankings_table_sortable_stable_with_trend_ribbon` | Rankings | US-006, S4-T05 | Deferred |
| TS-UI-021 | `e2e_us006_rankings_excluded_tickers_listed_with_reason` | Exclusions | US-006, US-020 | Deferred |
| TS-UI-022 | `e2e_us006_watchlist_add_invalid_symbol_shows_api_message_inline` | Inline error | S4-T05 | Deferred |
| TS-UI-023 | `e2e_us007_card_and_ticker_show_invalidation_level` | Invalidation | US-007 | Deferred |
| TS-UI-024 | `e2e_us008_track_record_tiles_show_sample_sizes_and_small_sample_label` | Track record | US-008, S6-T04 | Deferred |
| TS-UI-025 | `e2e_us008_track_record_losing_picks_shown_with_equal_prominence` | Honesty | US-008, S6-T04 | Deferred |
| TS-UI-026 | `e2e_us008_backtest_tab_separate_and_labeled_hypothetical` | Backtest label | US-008, S6-T04 | Deferred |
| TS-UI-027 | `e2e_us009_regime_badge_and_weights_adjusted_explanation_with_before_after` | Regime | US-009, S5-T06 | Deferred |
| TS-UI-028 | `e2e_us010_earnings_countdown_and_event_risk_flag_shown` | Event risk | US-010, S5-T06 | Deferred |
| TS-UI-029 | `e2e_us011_run_now_without_token_prompts_for_token` | Manual run | US-011, S4-T06 | Deferred |
| TS-UI-030 | `e2e_us011_run_now_shows_live_progress_by_polling_until_published` | Progress | US-011 | Deferred |
| TS-UI-031 | `e2e_us011_run_in_progress_disables_run_now_button` | Concurrency | S4-T06 | Deferred |
| TS-UI-032 | `e2e_us012_date_route_shows_that_days_picks_with_config_that_produced_them` | Date browse | US-012, FR-7xx | Deferred |
| TS-UI-033 | `e2e_ui_every_screen_loading_empty_error_stale_states_exist` | State coverage per screen (Today, Ticker, Watchlist, Track Record, Runs, Settings) | FR-7xx, S4 checklist | Deferred |
| TS-UI-034 | `e2e_ui_api_500_renders_error_state_with_retry_never_blank` | Error state | FR-7xx, S4-T02 | Deferred |
| TS-UI-035 | `e2e_ui_disclaimer_visible_on_every_screen_showing_picks` | Disclaimer | A§9, FR-7xx | Deferred |
| TS-UI-036 | `e2e_ui_footer_shows_copyright_noncommercial_notice_and_license_link` | License notice | A§9 | Deferred |
| TS-UI-037 | `e2e_ui_settings_no_secret_rendered_token_in_memory_by_default` | Secrets | NFR-009, S4-T06 | Deferred |
| TS-UI-038 | `e2e_ui_settings_token_in_local_storage_requires_warning_acknowledgement` | Optional persistence | S4-T06 | Deferred |
| TS-UI-039 | `e2e_ui_today_first_meaningful_paint_under_1_5s_against_kind_install` | NFR-003 | NFR-003, S4 checklist | Deferred |
| TS-UI-040 | `e2e_ui_demo_banner_present_on_every_route_when_demo_mode_absent_otherwise` | Banner | S4-T09 | Deferred |
| TS-UI-041 | `e2e_ui_demo_tour_lists_every_function_in_demo_matrix_with_status` | `/demo` | S4-T09 | Deferred |
| TS-UI-042 | `e2e_ui_stale_data_banner_shown_when_latest_run_older_than_last_session` | Stale state | FR-7xx, US-020 | Deferred |
| TS-UI-043 | `e2e_ui_narrative_source_tag_shows_model_name_or_template` | Tag | FR-7xx, S5-T06 | Deferred |
| TS-UI-044 | `e2e_ui_narrative_rendered_as_plain_text_script_tag_inert` | XSS | A§9 | Deferred |
| TS-UI-045 | `e2e_ui_csp_no_violations_in_console_on_every_route` | CSP console clean | A§9, S4-T07 | Deferred |
| TS-UI-046 | `unit_ui_estimated_order_flow_quality_tag_shown_for_daily_estimate` | Data quality tag | FR-7xx | Deferred |
| TS-UI-047 | `e2e_ui_visual_report_one_screenshot_per_screen_opens_offline` | `demo-report/index.html` | S4-T09 | Deferred |
| TS-UI-048 | `e2e_ui_color_scheme_dark_default_light_available_and_persisted` | Theme | FR-7xx, DESIGN | Deferred |
| TS-UI-049 | `e2e_ui_visual_regression_today_and_ticker_light_and_dark_baseline` | Screenshot comparison | FR-7xx | Skipped: pixel baselines are brittle across OS and font rendering; manual: review `demo-report/` screenshots in section 12 and attach to the release PR |

### 10.13 CLI (TS-CLI)

Exit codes: 0 ok, 1 error, 2 usage, 3 not ready.

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-CLI-001 | `unit_cli_version_prints_version_and_commit_and_license_notice` | `supertrends {VERSION} ({commit})` | FR-8xx, S0-T01 | Automated |
| TS-CLI-002 | `unit_cli_every_command_has_help_text` | `--help` for each command | FR-8xx, S7-T01 | Deferred |
| TS-CLI-003 | `unit_cli_today_json_validates_against_api_schema` | `--json` | FR-8xx | Deferred |
| TS-CLI-004 | `unit_cli_today_json_matches_api_payload` | Same answers as API | FR-8xx, S7 checklist | Deferred |
| TS-CLI-005 | `unit_cli_today_text_output_includes_disclaimer` | Disclaimer | A§9 | Deferred |
| TS-CLI-006 | `unit_cli_analyze_ticker_date_json_validates` | `analyze` | FR-8xx | Deferred |
| TS-CLI-007 | `unit_cli_rank_top_n_limits_rows` | `rank --top` | FR-8xx | Deferred |
| TS-CLI-008 | `unit_cli_watchlist_list_add_remove_roundtrip` | Watchlist | FR-8xx | Deferred |
| TS-CLI-009 | `unit_cli_run_daily_non_trading_day_exits_0_market_closed` | Calendar | FR-8xx, S3-T10 | Deferred |
| TS-CLI-010 | `unit_cli_run_daily_date_flag_runs_that_date` | `--date` | FR-8xx | Deferred |
| TS-CLI-011 | `unit_cli_ingest_fixture_provider_fills_database` | `ingest` | FR-8xx | Deferred |
| TS-CLI-012 | `unit_cli_backtest_prints_hypothetical_label` | Label | FR-6xx, FR-8xx | Deferred |
| TS-CLI-013 | `unit_cli_track_record_prints_sample_sizes` | Track record | FR-8xx | Deferred |
| TS-CLI-014 | `unit_cli_status_prints_latest_run_and_freshness` | Status | FR-8xx | Deferred |
| TS-CLI-015 | `unit_cli_healthcheck_exits_0_when_ready_3_when_not_ready` | Exit codes | FR-8xx, A§6.2 | Deferred |
| TS-CLI-016 | `unit_cli_usage_error_exits_2` | Bad flags | FR-8xx | Deferred |
| TS-CLI-017 | `unit_cli_runtime_error_exits_1` | Generic error | FR-8xx | Deferred |
| TS-CLI-018 | `unit_cli_remote_mode_api_url_and_token_env_used` | `--api-url`, `SUPERTRENDS_API_TOKEN` | FR-8xx | Deferred |
| TS-CLI-019 | `unit_cli_remote_mode_write_without_token_exits_1_with_message` | Auth failure | FR-8xx | Deferred |
| TS-CLI-020 | `unit_cli_config_show_and_validate_unknown_key_fails_naming_key` | Config commands | FR-8xx, S0-T09 | Automated |
| TS-CLI-021 | `unit_cli_db_migrate_and_backup_invoke_expected_operations` | DB commands | FR-8xx | Deferred: `db migrate` automated by TS-CLI-024, `db backup` in S6-T06 |
| TS-CLI-022 | `unit_cli_output_never_prints_secrets_token_redacted_in_errors` | Secret hygiene | NFR-009 | Deferred |
| TS-CLI-023 | `it_cli_serve_binds_address_and_healthcheck_passes` | `serve` | FR-8xx | Deferred |
| TS-CLI-024 | `unit_cli_db_migrate_prints_applied_revision_and_exits_3_when_unreachable` | `supertrends db migrate [--revision]` | A§6.2, S1-T01 | Automated |

### 10.14 MCP and harnesses (TS-MCP)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-MCP-001 | `it_mcp_stdio_client_lists_seven_tools` | `supertrends_recommend`, `supertrends_analyze`, `supertrends_rank`, `supertrends_watchlist`, `supertrends_status`, `supertrends_track_record`, `supertrends_run` | FR-8xx, A§6.3 | Deferred |
| TS-MCP-002 | `it_mcp_http_client_lists_seven_tools_with_bearer_token` | Streamable HTTP at `/mcp` | FR-8xx, A§6.3 | Deferred |
| TS-MCP-003 | `it_mcp_recommend_returns_picks_with_evidence_and_disclaimer` | US-015 | US-015, FR-8xx | Deferred |
| TS-MCP-004 | `it_mcp_analyze_returns_full_factor_breakdown_and_levels` | US-016 | US-016, FR-8xx | Deferred |
| TS-MCP-005 | `it_mcp_rank_top_n_returns_ranked_list` | Rank | FR-8xx | Deferred |
| TS-MCP-006 | `it_mcp_status_and_track_record_return_expected_shape` | Read tools | FR-8xx | Deferred |
| TS-MCP-007 | `it_mcp_watchlist_add_remove_over_http_without_token_returns_error` | Write tool auth | FR-8xx, A§9 | Deferred |
| TS-MCP-008 | `it_mcp_run_over_http_without_token_returns_error` | Write tool auth | FR-8xx | Deferred |
| TS-MCP-009 | `contract_mcp_tool_schemas_strict_no_additional_properties` | Strict schemas | FR-8xx, S7-T02 | Deferred |
| TS-MCP-010 | `contract_mcp_every_tool_description_ends_with_informational_notice` | "Informational market analysis only..." | FR-8xx, A§9 | Deferred |
| TS-MCP-011 | `contract_mcp_every_pick_result_includes_disclaimer` | Disclaimer | A§9 | Deferred |
| TS-MCP-012 | `contract_mcp_invalid_ticker_input_rejected_by_schema` | Input validation | FR-8xx | Deferred |
| TS-MCP-013 | `it_mcp_no_trade_or_sizing_fields_in_any_tool_output` | No order instructions | A§9 | Deferred |
| TS-MCP-014 | `unit_pi_extension_tools_mirror_mcp_tool_schemas` | TypeBox mirrors MCP | FR-8xx, S7-T03 | Deferred |
| TS-MCP-015 | `unit_pi_extension_slash_commands_call_http_api_mocked` | `/supertrends today`, `analyze`, `rank` | S7-T03 | Deferred |
| TS-MCP-016 | `unit_pi_extension_run_streams_progress_through_on_update` | Progress | S7-T03 | Deferred |
| TS-MCP-017 | `it_harness_goose_opencode_claude_code_configs_start_stdio_server_and_list_tools` | Config validation script | S7-T04 | Deferred |
| TS-MCP-018 | `it_harness_smoke_mcp_client_runs_all_read_tools_on_staging_and_tags` | CI `harness-smoke-tests` | S7-T05 | Deferred |
| TS-MCP-019 | `unit_agent_skill_daily_brief_run_sh_prints_picks_from_running_instance` | Skill script | S7-T06 | Deferred |
| TS-MCP-020 | `unit_agent_skills_run_tests_and_check_types_run_sh_exit_0` | Agent harness skills | S0-T07 | Automated |

### 10.15 Operations and run state machine (TS-OPS)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-OPS-001 | `it_runs_state_machine_transitions_queued_to_published_in_order` | Each state persisted | FR-9xx, A§8 | Deferred |
| TS-OPS-002 | `unit_runs_state_machine_illegal_transition_raises` | Cannot skip or reverse | FR-9xx, A§8 | Deferred |
| TS-OPS-003 | `it_runs_publish_writes_recommendations_and_published_at_in_single_transaction` | Atomic publication | NFR-006, A§8 | Deferred |
| TS-OPS-004 | `it_runs_publish_midrun_process_kill_previous_run_stays_latest` | Kill during narrating | NFR-006, S3-T07 | Deferred |
| TS-OPS-005 | `it_runs_publish_failure_during_commit_rolls_back_all_rows` | No partial publication | NFR-006, S9-T02 | Deferred |
| TS-OPS-006 | `it_runs_failed_run_leaves_previous_published_run_as_latest` | Failed state | NFR-006 | Deferred |
| TS-OPS-007 | `it_runs_two_simultaneous_triggers_one_run_one_already_running_response` | Advisory lock | FR-9xx, S3-T07 | Deferred |
| TS-OPS-008 | `it_runs_rerun_same_date_new_row_supersedes_only_on_success_both_stored` | Supersession | FR-9xx, S3-T07 | Deferred |
| TS-OPS-009 | `it_runs_rerun_same_date_failing_keeps_old_run_published` | Failed rerun | NFR-006 | Deferred |
| TS-OPS-010 | `it_runs_summary_lists_stale_and_insufficient_history_exclusions_with_reasons` | Exclusions | FR-9xx, US-020 | Deferred |
| TS-OPS-011 | `unit_runs_daily_non_trading_day_exits_0_publishes_nothing` | Holiday | FR-9xx, S3-T10 | Deferred |
| TS-OPS-012 | `it_runs_daily_twice_from_clean_databases_identical_picks` | Determinism (live path) | NFR-002, S3 checklist | Deferred |
| TS-OPS-013 | `it_runs_fault_provider_429_storm_ends_in_correct_publish_or_clean_failure` | Resilience | S9-T02 | Deferred |
| TS-OPS-014 | `it_runs_fault_provider_outage_midrun_clean_failure_previous_latest` | Resilience | S9-T02 | Deferred |
| TS-OPS-015 | `it_runs_fault_database_restart_midrun_clean_failure_previous_latest` | Resilience | S9-T02 | Deferred |
| TS-OPS-016 | `it_runs_fault_llm_timeout_publishes_with_template_narratives` | Resilience | S9-T02, US-019 | Deferred |
| TS-OPS-017 | `it_runs_fault_half_day_session_publishes_correctly` | Resilience | S9-T02 | Deferred |
| TS-OPS-018 | `it_runs_fault_missing_intraday_data_uses_daily_estimate_and_flags` | Resilience | S9-T02 | Deferred |
| TS-OPS-019 | `it_runs_fault_ticker_delisted_mid_history_excluded_run_publishes` | Resilience | S9-T02 | Deferred |
| TS-OPS-020 | `it_runs_fault_split_on_run_day_refetches_and_scores_adjusted` | Resilience | S9-T02 | Deferred |
| TS-OPS-021 | `unit_perf_full_scoring_200_tickers_under_60s_2_cores` | NFR-001 | NFR-001 | Deferred |
| TS-OPS-022 | `it_ops_metrics_emitted_run_duration_state_total_excluded_freshness_picks` | Metric names | A§11, S6-T05 | Deferred |
| TS-OPS-023 | `unit_ops_alert_rules_pass_promtool_check_rules` | Alerts | A§11, S6-T05 | Deferred |
| TS-OPS-024 | `unit_ops_dashboard_json_valid_schema_and_loads` | Grafana JSON | A§11, S6-T05 | Skipped: full Grafana load needs a running Grafana; manual: import `deploy/dashboards/*.json` into Grafana on kind or Stoke and confirm no panel errors; JSON syntax and schema validated automatically |
| TS-OPS-025 | `it_ops_alert_no_published_run_by_1900_et_fires_in_rule_unit_test` | Alert logic via promtool unit tests | A§11 | Deferred |
| TS-OPS-026 | `it_ops_provider_calls_table_records_status_and_latency_per_call` | Provider health | A§5, A§11 | Deferred |
| TS-OPS-027 | `it_ops_memory_api_pod_under_512_mib_and_run_job_under_1_5_gib` | NFR-010 | NFR-010 | Skipped: needs cluster metrics under real load; manual: read `container_memory_working_set_bytes` on Stoke staging during a run and record in `docs/PERFORMANCE.md` |
| TS-OPS-028 | `it_ops_full_daily_run_200_symbols_under_10_minutes_on_stoke` | NFR-001 end to end | NFR-001 | Skipped: requires the Stoke cluster; manual: time a staging run with the 200-symbol seed and record in `docs/PERFORMANCE.md` |
| TS-OPS-029 | `it_ops_cronjob_template_sets_concurrency_forbid_and_time_zone_new_york` | CronJob | FR-9xx, S3-T10 | Deferred |
| TS-OPS-030 | `it_ops_structured_logs_include_request_id_run_id_and_no_secret_values` | Logging | A§11, NFR-009 | Deferred |

### 10.16 Deployment and packaging (TS-DEP)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-DEP-001 | `it_build_clean_clone_setup_build_check_succeed` | `make setup && make build && make check` | A§10, S0-T03 | Automated |
| TS-DEP-002 | `unit_version_check_script_passes_when_all_files_agree` | `scripts/check-versions.sh` | A§10, S0-T04 | Automated |
| TS-DEP-003 | `unit_version_check_script_fails_naming_ui_package_json_on_mismatch` | Negative | A§10, S0-T04 | Automated |
| TS-DEP-004 | `unit_changelog_extract_script_returns_section_for_version` | `scripts/extract-changelog.sh` | A§10, S0-T04 | Automated |
| TS-DEP-005 | `it_image_runs_as_non_root_uid_10001_read_only_root_fs` | Container hardening | A§9, S0-T06 | Automated |
| TS-DEP-006 | `it_image_compose_up_healthz_returns_ok_then_down_cleans_volumes` | Compose loop | A§10, S0-T06 | Automated |
| TS-DEP-007 | `it_image_builds_for_linux_amd64_and_linux_arm64_in_ci` | NFR-005 | NFR-005, S0-T05 | Automated |
| TS-DEP-008 | `it_image_arm64_runs_smoke_under_emulation_or_arm_runner` | Prove arm64, do not assume | NFR-005, Impl. Notes 14 | Deferred |
| TS-DEP-009 | `it_image_no_gpu_requested_in_any_chart_profile` | CPU only | NFR-005, A§10 | Deferred |
| TS-DEP-010 | `it_chart_helm_lint_and_template_pass_for_kind_stoke_selfhost_hosted_profiles` | `make helm-lint` | A§10, S8-T01 | Deferred |
| TS-DEP-011 | `it_chart_values_schema_rejects_secret_value_in_values` | Negative schema test | A§10, S8-T01 | Deferred |
| TS-DEP-012 | `it_chart_values_schema_rejects_invalid_cron_expression` | Negative | S8-T01 | Deferred |
| TS-DEP-013 | `it_chart_values_schema_rejects_weights_not_summing_to_100_in_override` | Negative | S8-T01 | Deferred |
| TS-DEP-014 | `it_chart_stoke_profile_renders_only_arm64_compatible_images_no_gpu` | Stoke profile | S8-T02 | Deferred |
| TS-DEP-015 | `it_chart_stoke_values_contain_no_cluster_identifiers_or_hostnames` | Public repo rule | A§9, S8-T02 | Deferred |
| TS-DEP-016 | `it_chart_security_context_probes_pdb_networkpolicy_hpa_present_in_render` | Template checks | A§9, S8-T01 | Deferred |
| TS-DEP-017 | `it_chart_every_container_has_requests_and_limits` | Resources | A§9 | Deferred |
| TS-DEP-018 | `it_chart_automount_service_account_token_false` | Least privilege | A§9 | Deferred |
| TS-DEP-019 | `it_kind_install_helm_test_and_smoke_pass` | `make kind-up image kind-load helm-install helm-test smoke` | A§10, S3-T11 | Deferred |
| TS-DEP-020 | `it_kind_migration_job_runs_before_api_and_completes` | Migration hook | A§10 | Deferred |
| TS-DEP-021 | `it_kind_upgrade_previous_chart_to_current_with_migration_then_rollback_smoke_green` | Upgrade and rollback | A§10, S8-T06 | Deferred |
| TS-DEP-022 | `it_kind_air_gap_install_from_local_registry_with_global_image_registry` | Air gap | A§10, S8-T06 | Deferred |
| TS-DEP-023 | `it_flux_kustomize_build_succeeds_for_stage_and_prod_overlays` | Flux manifests | A§10, S8-T04 | Deferred |
| TS-DEP-024 | `it_flux_manifests_validate_with_kubeconform_and_flux_crd_schemas` | Validation | A§10, S8-T04 | Deferred |
| TS-DEP-025 | `it_flux_helmrelease_image_by_digest_and_rollback_remediation_enabled` | Digest, remediation | A§10, S8-T04 | Deferred |
| TS-DEP-026 | `it_release_image_scan_trivy_fails_on_seeded_critical_cve_in_test_branch` | Supply chain | A§10, S8-T03 | Deferred |
| TS-DEP-027 | `it_release_cosign_verify_succeeds_for_image_and_chart` | Signatures | A§10, S8-T03 | Skipped: needs a published signed artifact in GHCR, which cannot exist inside a PR build; manual: run the documented `cosign verify` command (`make image-verify`) after the first `staging` publish and again after the v1.0.0 release |
| TS-DEP-028 | `it_release_sbom_and_provenance_attached_to_image_manifest` | SBOM | A§10, S8-T03 | Deferred |
| TS-DEP-029 | `it_release_chart_pullable_from_oci_registry_at_version` | OCI chart | A§10, S9-T06 | Skipped: requires the real registry after release; manual: `helm pull oci://ghcr.io/mohnishbasha/charts/stokeai-supertrends --version 1.0.0` |
| TS-DEP-030 | `it_stoke_staging_helm_test_and_smoke_pass_and_rollback_verified_once` | Stoke staging | A§10, S8-T05 | Skipped: needs Stoke cluster access and owner-held secrets; manual: section 9.4 commands, record digest and result in the release PR |
| TS-DEP-031 | `it_stoke_production_first_scheduled_run_publishes_by_digest` | Production | A§10, S9-T07 | Skipped: production cluster only; manual: section 12 items, confirm the CronJob run reached `published` |
| TS-DEP-032 | `it_demo_make_demo_ends_with_url_and_populated_latest_run_within_3_minutes` | Demo mode | A§10, S3-T13 | Deferred |
| TS-DEP-033 | `it_demo_verify_prints_one_pass_or_fail_line_per_function_exits_nonzero_on_fail` | Demo verify | A§10, S3-T13 | Deferred |
| TS-DEP-034 | `it_demo_cannot_be_enabled_with_a_real_provider` | Guard | A§10, S3-T13 | Deferred |
| TS-DEP-035 | `it_demo_seed_replays_60_trading_days_through_real_orchestrator` | Seed | A§10, S3-T13 | Deferred |
| TS-DEP-036 | `it_demo_latest_run_has_3_buys_2_sells_by_construction` | Synthetic tickers constructed for it | A§10, S3-T13 | Deferred |
| TS-DEP-037 | `it_systemd_units_and_install_script_pass_shellcheck_and_unit_verify` | Single host path | A§10 | Deferred |
| TS-DEP-038 | `unit_scripts_shellcheck_passes_for_all_scripts` | Shell hygiene | A§10, S0-T10 | Automated |
| TS-DEP-039 | `unit_scripts_stoke_inventory_no_kubeconfig_writes_unknown_rows_exit_0` | Inventory script | S0-T10 | Automated |
| TS-DEP-040 | `unit_scripts_stoke_inventory_is_read_only_only_get_commands_issued` | Read-only | S0-T10 | Automated |
| TS-DEP-041 | `unit_repo_private_directory_and_logs_are_git_ignored_and_untracked` | Public repo hygiene | A§9, S0-T07 | Automated |
| TS-DEP-042 | `unit_repo_operator_files_runner_mk_and_run_scripts_not_ignored_and_untouched` | Operator files | S0-T07 | Automated |
| TS-DEP-043 | `it_ci_lint_error_in_pr_fails_lint_and_typecheck_job` | CI guard | S0-T05 | Automated |
| TS-DEP-044 | `it_ci_workflows_use_pull_request_not_pull_request_target_and_pinned_actions` | Workflow lint | A§9 | Automated |
| TS-DEP-045 | `it_ci_openapi_drift_fails_when_docs_openapi_json_stale` | Drift | S3-T09 | Deferred |
| TS-DEP-046 | `it_ci_test_step_runs_with_outbound_network_blocked` | No network in tests | S1 checklist | Deferred |

### 10.17 Security (TS-SEC)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-SEC-001 | `it_security_no_outbound_connection_except_configured_provider_and_llm_mocks` | App run with egress blocked except mocks; any other connection attempt fails the test | NFR-008, A§9 | Deferred |
| TS-SEC-002 | `it_security_no_third_party_telemetry_in_ui_bundle_or_api` | Scan built UI for external hosts; CSP `connect-src 'self'` | NFR-008 | Deferred |
| TS-SEC-003 | `unit_security_api_key_never_in_logs_errors_or_provider_calls` | Key redaction | NFR-009, S1-T04 | Deferred |
| TS-SEC-004 | `unit_security_structlog_processor_redacts_known_secret_fields` | Redaction processor | NFR-009 | Automated |
| TS-SEC-005 | `contract_security_no_api_response_contains_secret_value` | Walk all endpoint responses with seeded secrets in the environment | NFR-009 | Deferred |
| TS-SEC-006 | `it_security_metrics_output_contains_no_secret_value` | `/metrics` scan | NFR-009 | Automated |
| TS-SEC-007 | `unit_security_token_compare_uses_constant_time_function` | `hmac.compare_digest` | A§9 | Automated |
| TS-SEC-008 | `unit_security_input_validation_symbol_regex_dates_pagination_bounds` | Parameter validation | A§9 | Deferred |
| TS-SEC-009 | `unit_security_llm_and_provider_base_urls_from_config_only` | SSRF | A§9 | Deferred |
| TS-SEC-010 | `unit_security_disclaimer_text_identical_to_disclaimer_md_everywhere` | Single source of truth | A§9 | Deferred |
| TS-SEC-011 | `contract_security_disclaimer_present_on_api_cli_mcp_and_ui_pick_surfaces` | Surface matrix test, a surface without it is a p0 bug | A§9, Impl. Notes 20 | Deferred |
| TS-SEC-012 | `unit_security_no_output_field_for_position_size_options_leverage_or_orders` | Schema scan | A§9 | Deferred |
| TS-SEC-013 | `unit_security_no_brokerage_dependency_or_credential_setting_in_codebase` | Hard boundary | A§9 | Deferred |
| TS-SEC-014 | `unit_security_app_never_stores_holdings_account_size_or_risk_tolerance_fields` | Schema scan | A§9 | Deferred |
| TS-SEC-015 | `it_security_gitleaks_full_history_scan_reports_no_findings` | CI gate | A§9, S9-T01 | Deferred |
| TS-SEC-016 | `it_security_pip_audit_and_npm_audit_no_high_or_critical` | Dependency audit | A§9, S0-T05 | Automated |
| TS-SEC-017 | `it_security_license_script_fails_on_gpl_agpl_sspl_or_unknown` | Dependency licenses | A§9, S0-T08 | Automated |
| TS-SEC-018 | `it_security_spdx_header_check_fails_on_source_file_without_header` | SPDX | A§9, S0-T08 | Automated |
| TS-SEC-019 | `it_security_cla_check_blocks_pr_from_non_owner_without_signed_cla` | CLA | A§9, S0-T08 | Skipped: needs a real fork PR from a second GitHub account; manual: open a PR from a test account with no CLA and confirm the check blocks, then sign and confirm it passes |
| TS-SEC-020 | `unit_security_docs_and_package_metadata_never_say_open_source` | Wording scan for README, docs, UI, package metadata, topics | A§9 | Deferred |
| TS-SEC-021 | `unit_security_docs_contain_no_em_dash_or_hype_words` | Style lint for files written by the agent | Impl. Notes 19 | Deferred |
| TS-SEC-022 | `unit_security_docs_contain_no_certainty_language_about_markets` | Banned phrase list over UI copy and templates | Impl. Notes 19 | Deferred |
| TS-SEC-023 | `unit_security_recorded_fixtures_contain_no_real_vendor_prices_or_keys` | Fixture scrub check | A§9 | Deferred |
| TS-SEC-024 | `unit_security_repo_has_no_committed_published_picks_or_run_output` | Scan for run output files | A§9 | Deferred |
| TS-SEC-025 | `it_security_networkpolicy_default_deny_with_only_documented_allow_rules` | Render check | A§9 | Deferred |
| TS-SEC-026 | `it_security_networkpolicy_enforced_on_stoke_cni` | Enforcement depends on the CNI | A§9 | Skipped: depends on the cluster CNI, only checkable on Stoke; manual: from a test pod in the namespace attempt a connection that policy should block and confirm failure |
| TS-SEC-027 | `it_security_host_header_not_in_allowed_hosts_rejected_with_421_or_400` | Allowed hosts | A§9 | Deferred |
| TS-SEC-028 | `it_security_default_profiles_have_no_public_loadbalancer_service` | Render check | A§9 | Deferred |
| TS-SEC-029 | `it_security_secrets_only_via_existing_secret_env_not_values_files` | Chart render | NFR-009, A§9 | Deferred |
| TS-SEC-030 | `it_security_env_example_lists_names_with_empty_values_and_env_files_ignored` | `.env.example` | A§9 | Deferred |
| TS-SEC-031 | `it_security_base_images_pinned_by_digest_and_actions_pinned_by_sha` | Supply chain | A§9 | Deferred |
| TS-SEC-032 | `it_security_workflow_permissions_minimal_per_job_fork_prs_no_secrets` | CI hygiene | A§9 | Deferred |
| TS-SEC-033 | `it_security_write_endpoints_rate_limit_burst_returns_429_then_recovers` | Rate limit | A§9 | Deferred |
| TS-SEC-034 | `it_security_llm_prompt_and_provider_strings_excluded_from_prompt_no_injection_path` | Duplicate coverage at integration level | A§9 | Deferred |
| TS-SEC-035 | `unit_security_license_notice_shown_in_footer_version_output_and_status_endpoint` | Required notice | A§9 | Deferred |
| TS-SEC-036 | `it_security_review_document_records_evidence_for_every_guideline_item` | `docs/SECURITY_REVIEW.md` completeness check | A§9, S9-T01 | Skipped: requires human judgment on evidence quality; manual: reviewer walks Security Guidelines line by line against `docs/SECURITY_REVIEW.md` |
| TS-SEC-037 | `unit_network_outbound_connection_attempt_fails_blocked` | Unit tests run with sockets disabled (`pytest-socket`: `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1`); an outbound connection raises `SocketConnectBlockedError`, loopback still works | A§7, Sprint 1 checklist, S1-T02 | Automated |

### 10.18 Accessibility (TS-A11Y)

| ID | Scenario name | Description | Spec ref | Status |
|---|---|---|---|---|
| TS-A11Y-001 | `e2e_a11y_axe_zero_serious_or_critical_on_every_route_dark_theme` | axe run on `/`, `/ticker/:symbol`, `/watchlist`, `/track-record`, `/runs`, `/settings`, `/date/:date` | NFR-011, S4 checklist | Deferred |
| TS-A11Y-002 | `e2e_a11y_axe_zero_serious_or_critical_on_every_route_light_theme` | Same in light theme | NFR-011 | Deferred |
| TS-A11Y-003 | `unit_a11y_contrast_tokens_meet_wcag_2_2_aa_in_both_themes` | Computed contrast on token pairs | NFR-011, S4-T01 | Deferred |
| TS-A11Y-004 | `e2e_a11y_buy_sell_distinguished_by_label_icon_or_shape_not_color_alone` | Grayscale screenshot check | NFR-011 | Deferred |
| TS-A11Y-005 | `e2e_a11y_trend_ribbon_has_text_alternative_for_direction_changes` | Non-color encoding | NFR-011 | Deferred |
| TS-A11Y-006 | `e2e_a11y_score_dial_exposes_value_and_band_to_assistive_tech` | ARIA | NFR-011 | Deferred |
| TS-A11Y-007 | `e2e_a11y_keyboard_only_navigation_reaches_every_interactive_element` | Tab order | NFR-011 | Deferred |
| TS-A11Y-008 | `e2e_a11y_focus_visible_on_all_controls_and_chart_keyboard_reachable` | Focus | NFR-011, S4-T04 | Deferred |
| TS-A11Y-009 | `e2e_a11y_chart_has_data_table_alternative_with_same_values` | Table alternative | NFR-011, S4-T04 | Deferred |
| TS-A11Y-010 | `e2e_a11y_error_and_empty_states_announced_via_live_region_or_role_alert` | Announcements | NFR-011 | Deferred |
| TS-A11Y-011 | `e2e_a11y_reduced_motion_preference_disables_animations` | `prefers-reduced-motion` | NFR-011 | Deferred |
| TS-A11Y-012 | `e2e_a11y_text_resize_200_percent_no_loss_of_content` | Zoom | NFR-011 | Deferred |
| TS-A11Y-013 | `e2e_a11y_screen_reader_pass_on_today_and_ticker_screens` | VoiceOver or NVDA reading order and labels | NFR-011 | Skipped: automated tools cannot judge reading quality; manual: section 12 screen reader step on Today and Ticker, record the result in the release PR |

### 10.19 Scenario count summary

| Area | Prefix | Scenarios |
|---|---|---|
| Watchlist | TS-WL | 15 |
| Ingestion and data | TS-ING | 44 |
| Indicators | TS-IND | 110 |
| Scoring (12 factors plus framework) | TS-SCR | 165 |
| Regime and weights | TS-REG | 33 |
| Composite and confidence | TS-CMP | 33 |
| Selection | TS-SEL | 45 |
| Justification and narrative | TS-NAR | 56 |
| Track record | TS-TRK | 23 |
| Backtest | TS-BKT | 14 |
| API | TS-API | 35 |
| UI | TS-UI | 49 |
| CLI | TS-CLI | 23 |
| MCP and harnesses | TS-MCP | 20 |
| Operations and run state machine | TS-OPS | 30 |
| Deployment and packaging | TS-DEP | 46 |
| Security | TS-SEC | 37 |
| Accessibility | TS-A11Y | 13 |

The counts are maintained by `scripts/count-scenarios.sh`, which parses this file and fails CI if the number of rows, the status vocabulary, or the id sequence is inconsistent with the table above, or if any `Automated` row has no matching test function.

---

## 11. Test infrastructure and maintenance

### 11.1 Layout and runners

| Type | When | Runner | Location |
|---|---|---|---|
| Unit | Pure logic, no I/O | pytest, vitest | `tests/unit/`, `ui/src/**/*.test.tsx` |
| Golden | Indicator and factor math against fixed expected values | pytest | `tests/golden/` |
| Property | No look-ahead, bounds, invariants | pytest with hypothesis | `tests/unit/` |
| Integration | Real Postgres, mocked providers and LLM | pytest with testcontainers | `tests/integration/` |
| Smoke | Minimal end-to-end sanity against any deployment | pytest | `tests/smoke/` |
| E2E | Full user flows through the UI | Playwright | `ui/tests/e2e/` |
| Narrative eval | Guard and prompt quality | pytest plus `make narrative-eval` | `tests/narrative_eval/` |
| Regression | Every fixed bug | pytest, vitest | `tests/regression/` |

Shared fixtures live in `tests/fixtures/`. Providers and the LLM are always injected, never reached through the network.

### 11.2 Naming (Appendix G forms)

```
Unit:        test_{module}_{function}_{scenario}_{expected_outcome}
Integration: it_{component}_{operation}_{scenario}
Smoke:       smoke_{feature}_{minimal_assertion}
E2E:         e2e_{user_story_id}_{scenario}
Regression:  regression_{gh_issue_number}_{what_was_broken}
```

### 11.3 Regression test lifecycle

```
Bug reported -> GitHub issue created (type:bug)
  -> reproduction confirmed -> regression test written (FAILS)
  -> fix implemented -> regression test passes
  -> PR: regression test and fix in the same commit
  -> merged -> issue closed -> test runs in CI forever
```

Regression tests are never deleted.

### 11.4 Maintenance rules

1. **Scenario ownership.** The PR that adds or changes behavior adds or updates scenario rows in this file (PR template checkbox "TEST_PLAN.md scenarios added or updated"). The status moves `Deferred` to `Automated` in the PR that adds the test.
2. **Sprint end audit.** At the end of each sprint, the spec doc audit includes this file: every row for a feature shipped in the sprint is `Automated` or `Skipped` with a reason; none are silently dropped.
3. **Skipped rows.** Every `Skipped` row carries a written reason and a manual step. At S9-T04 each `Skipped` row has a recorded manual result in the release PR. The TradingView parity rows (TS-IND-021, TS-IND-022, TS-IND-141, TS-IND-142) may not remain skipped for v1.0.0.
4. **Golden files.** Changed only under the policy in section 5.5; `scripts/validate-fixtures.sh` runs in CI.
5. **Flaky tests.** A flaky test is a bug with `type:bug` and `priority:p1`. It is fixed or quarantined within one sprint with the reason recorded; retries are not used to hide non-determinism in scoring tests.
6. **Time and randomness.** Tests inject clocks and seeds. No test depends on the wall clock, the machine time zone, or locale.
7. **Hypothesis.** Seeds are derandomized in CI; the `nightly` profile (1000 examples) runs in `nightly.yml`. Every property failure becomes a regression test.
8. **Performance budgets.** The compute benchmark (NFR-001) and API latency check (NFR-004) are tests, not dashboards; they fail the build on regression. They run on 2 cores in CI to match the Stoke budget.
9. **Coverage.** `make coverage` runs unit and integration with `--cov` and `scripts/check_coverage.py .coverage-thresholds.toml`; thresholds are listed in section 3.
10. **CI jobs.** `lint-and-typecheck`, `unit-tests`, `coverage`, `integration-tests` (Postgres service container), `e2e-tests`, `build-image`, `kind-e2e` (PRs touching `src/`, `deploy/`, `Dockerfile`; pushes to `staging`), `harness-smoke-tests` (push to `staging`, tags), `flux-validate`, and `nightly`.
11. **Artifacts.** Playwright screenshots and traces upload on failure; `demo-report/` uploads from the demo job.
12. **Fixtures hygiene.** `scripts/validate-fixtures.sh` checks that recorded provider responses still match the provider models and that the synthetic dataset hash matches the committed hash.

### 11.5 Definition of Done (test related items)

- New scenarios added to this file before code; statuses current.
- Failing test written first and shown failing for the right reason.
- `make check` exits 0 with 0 warnings; `make coverage` meets thresholds.
- No test calls the network; no vendor data committed.

---

## 12. Manual QA checklist for release

Run against the staging build (and, for items marked P, again on production after deploy). Record results in the release PR. Hostnames and values are never pasted into public files.

### 12.1 Pre-flight

- [ ] `docs/GATE_DEBT.md` is empty and every sprint checklist is checked
- [ ] No `Deferred` rows remain in section 10; every `Skipped` row has a recorded manual result
- [ ] TradingView parity tests (TS-IND-021, TS-IND-022, TS-IND-141, TS-IND-142) are passing, not skipped (release blocker otherwise)
- [ ] `make coverage` meets every threshold in section 3
- [ ] `scripts/check-versions.sh` passes and the changelog section for the version, including a "Scoring" heading if `scoring.version` changed, is written

### 12.2 Smoke and demo

- [ ] `make up && make smoke` passes on the release candidate image (section 9.2)
- [ ] `make demo && make demo-verify` passes with every function PASS; the report shows one screenshot per screen
- [ ] kind install, `helm test`, and smoke pass (section 9.3)
- [ ] Stoke staging smoke passes (section 9.4); image digest recorded
- [ ] Rollback verified once (`flux suspend`, `helm rollback`, resume, smoke)
- [ ] P: production smoke passes after deploy by digest

### 12.3 Product review (owner)

- [ ] One full real-provider run reviewed: picks have evidence, narrative, invalidation level, and disclaimer
- [ ] Fewer than 3 buys or fewer than 2 sells is displayed as a valid result, not padded
- [ ] Spot check three tickers in TradingView against the chart: Supertrend line and direction agree on the latest bars
- [ ] Spot check one pick's factor table: contributions sum to the composite; adjustments listed match the regime and earnings state
- [ ] Narrative for three picks read by a human: no number or claim absent from the factor table; no certainty language
- [ ] LLM gateway down (scale to zero or block in staging): the run still publishes with template narratives and the UI shows the `template` source tag
- [ ] Stale data case: stop ingestion for one ticker; it is excluded, flagged, and never scored
- [ ] Track Record screen: sample sizes beside every statistic, "small sample" label under 20, losing picks as prominent as winners, backtest tab labeled hypothetical

### 12.4 UI, accessibility, and honesty

- [ ] Walk every screen (Today, Ticker, Watchlist, Track Record, Runs, Settings, date view) in dark and light themes at 100 percent and 200 percent zoom
- [ ] Disclaimer visible on every screen that shows a pick; footer shows "Copyright Serverless Ventures LLC. Noncommercial use only." with the license link
- [ ] Buy and sell distinguishable with a grayscale filter applied (TS-UI-008)
- [ ] Keyboard-only pass through Today and Ticker; chart data table reachable (TS-A11Y-007, TS-A11Y-009)
- [ ] Screen reader pass on Today and Ticker (TS-A11Y-013)
- [ ] Visual review of `demo-report/` screenshots (TS-UI-049)
- [ ] First meaningful paint of Today under 1.5 seconds on the tailnet with a warm API (NFR-003), measured and recorded

### 12.5 Security and privacy

- [ ] `docs/SECURITY_REVIEW.md` complete; zero high or critical findings; accepted mediums have a written rationale
- [ ] `gitleaks` over full history clean; `pip-audit`, `npm audit`, and Trivy clean at high and critical
- [ ] `kubectl logs` for API and a run job searched for the token and provider key prefixes: no matches (do not print the matches)
- [ ] Unauthenticated write calls rejected (`POST /api/v1/watchlist/items`, `DELETE /api/v1/watchlist/items/{symbol}`, `POST /api/v1/runs`, MCP write tools `supertrends_watchlist` add/remove and `supertrends_run` over HTTP)
- [ ] Request with an unlisted `Host` header rejected
- [ ] NetworkPolicy block verified with a test pod (TS-SEC-026)
- [ ] `cosign verify` succeeds for the image and the chart (TS-DEP-027)
- [ ] No public LoadBalancer or public ingress exists for the service
- [ ] Owner checklist entries confirmed: vendor plan permits intended use; securities-lawyer note acknowledged before any sharing

### 12.6 Performance and operations

- [ ] NFR-001 full run under 10 minutes for the 200-symbol seed on Stoke, excluding vendor rate-limit waits (TS-OPS-028)
- [ ] NFR-004 API p95 under 200 ms (TS-API-029) and NFR-010 memory ceilings (TS-OPS-027) recorded in `docs/PERFORMANCE.md`
- [ ] Grafana dashboard imports without errors and shows run duration, state, freshness, provider errors (TS-OPS-024)
- [ ] Alert rules loaded; the "no published run by 19:00 ET" rule verified with the promtool unit test
- [ ] Backup and restore round trip on staging

### 12.7 Release and post-release

- [ ] PR `staging` to `main` approved by the owner; annotated tag pushed; release workflow green
- [ ] Production overlay updated to the new chart version and image digest
- [ ] First scheduled production run publishes (TS-DEP-031)
- [ ] Back-merge `main` into `develop`; milestone closed; retrospective written
