# AGENTS.md

## Product

Super Trends Market Agent (Python package and CLI `supertrends`): a source-available, self-hosted agent that scores a watchlist with deterministic technical and fundamental signals and publishes a disciplined daily read of buy and sell candidates, with evidence for each pick. Free for noncommercial use. Not investment advice.

Repository: `mohnishbasha/stokeai-trading-supertrends`.

## Commands

All commands run from the repository root.

```bash
make help              # list targets
make setup             # check prerequisites, install Python and UI dependencies
make build             # build the UI and the Python wheel
make build-release     # reproducible release build
make check             # ruff, mypy --strict, UI lint and type-check, version check
make test              # unit tests (Python and UI)
make coverage          # coverage with thresholds
make dev               # native dev: Postgres in Compose, API and UI with reload
make up                # run the built image with Compose
make down              # stop Compose and remove volumes
make smoke             # smoke suite against SMOKE_BASE_URL
make demo              # local demo on synthetic data, no keys needed
make demo-verify       # check every product function against the running demo
make demo-down         # stop the demo and remove its data
make run-daily         # trigger the daily run locally
make openapi           # regenerate docs/openapi.json and the UI client
make version-sync      # write VERSION into the checked files
make image             # build the image for the local architecture
make image-multiarch   # build for linux/amd64 and linux/arm64 (no push)
make image-push        # build multi-arch, push, sign, attach SBOM and provenance
make image-scan        # vulnerability scan, fails on HIGH or CRITICAL
make image-verify      # verify the image signature
make helm-lint         # lint and template every profile
make helm-package      # package the chart at the current version
make helm-push         # push the chart to the OCI registry
make kind-up           # create the local kind cluster
make kind-load         # load the local image into kind
make helm-install      # install or upgrade the chart (PROFILE defaults to kind)
make helm-test         # run chart tests
make helm-uninstall    # remove the chart
make kind-down         # delete the local kind cluster
uv run supertrends --version
```

Targets for later sprints print a notice and exit 0 until implemented.

## Repository tree

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
  private/                                            # git-ignored: cluster inventory and values
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
    adr/
  migrations/
  src/supertrends/
    __init__.py  version.py  settings.py  errors.py  logging.py
    indicators/     primitives.py  supertrend.py  trend.py  momentum.py  divergence.py
                    meanrev.py  volatility.py  fibonacci.py  levels.py  volume.py  flow.py  registry.py
    scoring/        factor.py  factors/ (one module per factor)  regime.py  weights.py
                    composite.py  confidence.py  config.py
    selection/      candidates.py  ranking.py  correlation.py
    narrative/      evidence.py  template.py  llm.py  guard.py  prompts/
    data/           models.py  repo.py  ingest.py  calendar.py  quality.py
                    providers/  base.py  fixture.py  massive.py  alternate.py  registry.py
    runs/           orchestrator.py  state.py  publish.py
    trackrecord/    outcomes.py  stats.py  backtest.py
    api/            app.py  deps.py  routes/  schemas.py  security.py  static.py
    mcp/            server.py  tools.py
    cli/            main.py  commands/
    observability/  metrics.py
  ui/
    package.json  vite.config.ts  tsconfig.json  index.html
    src/  main.tsx  routes/  components/  store/  lib/  api/ (generated)  styles/tokens.css
    tests/  e2e/
  integrations/
    pi/  goose/  opencode/  claude-code/
  deploy/
    compose/   docker-compose.dev.yml  docker-compose.local.yml  docker-compose.prod.yml
    helm/stokeai-supertrends/
    flux/      base/  overlays/stage/  overlays/prod/
    kind/      cluster.yaml
    systemd/   supertrends.service  supertrends-daily.timer
    dashboards/ supertrends.json
  scripts/
    check-prereqs.sh  check-versions.sh  version-sync.sh  extract-changelog.sh
    check_coverage.py  gen-third-party-licenses.sh  stoke-inventory.sh  validate-fixtures.sh  install.sh
  tests/
    unit/  integration/  smoke/  regression/  golden/  narrative_eval/  fixtures/
```

## Python style

- Python 3.12. `mypy --strict`, no `Any` in public signatures, no `# type: ignore` without a reason comment.
- `ruff` for lint and format, zero warnings.
- Indicator, factor, and selection code is pure: no I/O, no clock, no randomness, no globals. Time and data are passed in.
- Use numpy and pandas vector operations. A Python loop over bars is allowed only for recursive indicators (Supertrend band ratchet, RMA) and must be covered by the benchmark test.
- Do not compare floats with `==` in logic, except against values from the same assignment. Store a direction flag instead.
- Prices are floats in computation, rounded only at presentation. Scores are rounded to 1 decimal at the API boundary.
- No `print`. Use structlog. Never log secrets, tokens, or provider URLs containing keys.
- Domain errors subclass `SuperTrendsError`. Every `except` handles, re-raises, or records and fails the run cleanly.
- pydantic v2 models at every boundary (API, config, provider responses, evidence documents).
- SQL through SQLAlchemy 2 typed queries. No string-built SQL.
- Public functions have docstrings that state units and warm-up behavior.
- No magic numbers: thresholds, periods, and weights come from `config/scoring.yaml` or a named constant.
- TODO format: `TODO(#issue): text`.
- Conventional Commits: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`.
- Shell scripts: `set -euo pipefail`, pass `shellcheck`.

## TypeScript style

- `strict: true`, no `any`, no non-null assertions without a comment, no `console.log` in committed code.
- Function components and hooks only. Server state in TanStack Query, UI state in Zustand, no prop drilling beyond two levels.
- The API client is generated from `docs/openapi.json`. Write no hand-written fetch calls to the API.
- Format every rendered number through `ui/src/lib/format.ts`.
- Test each component for loading, empty, error, and populated states.

## ALWAYS

- Read the relevant spec section before changing behavior, and update the spec in the same PR as the code.
- Write a failing test first, and keep every test permanently.
- Keep the engine a library: `indicators`, `scoring`, and `selection` import nothing from `api`, `cli`, `mcp`, `data`, or `runs`.
- Use one implementation of the daily loop for live runs and backtests.
- Render every surface from the stored evidence document.
- Show the disclaimer with every pick on every surface.
- Return fewer picks when fewer qualify (fewer than 3 buys or 2 sells is valid).
- Use the synthetic fixture provider and scrubbed, minimal recorded responses in tests.
- Keep `make demo` working.
- Implement the most literal reading of an ambiguous spec, write an ADR, and add an owner checklist entry.
- Keep Linux ARM64 working for every image.
- Put owner-only actions in `docs/OWNER_CHECKLIST.md` with exact commands.
- Choose the plain design over the clever one.

## NEVER

- Never let LLM output reach scoring, ranking, or selection.
- Never introduce look-ahead: pivots confirm late, fundamentals are point-in-time, backtest entries use the next open.
- Never weaken a formula, weight, or threshold to make a test pass.
- Never pad picks to reach a count.
- Never call the network in tests.
- Never add trade execution or order placement.
- Never store personal financial data.
- Never commit, log, or echo a secret, and never place a secret value in a values file, manifest, test, or comment.
- Never commit vendor market data.
- Never request GPUs or install cluster-wide components.
- Never ask for or use cluster-admin credentials in CI.
- Never use em dashes or en dashes as punctuation, and never use hype words in any copy.
- Never use certainty language about markets.
- Never describe the project with any term other than source-available and free for noncommercial use.
- Never edit `BUILD_PROMPT.md`. Changes go into the spec docs.

## Versioning

- The root `VERSION` file is the single source of truth for the version.
- Run `make version-sync` (script `scripts/version-sync.sh`) to write `VERSION` into the checked files.
- Run `scripts/check-versions.sh` to verify all copies match. `make check` runs it.
- The scoring config carries its own `scoring.version`. Bump it on any scoring rule change.
- Every sprint ends with the tag `sprint-N-complete`, because the runner depends on it.

## Boundaries

- Never touch `runner.mk`, `run-supertrends.sh`, `run-supertrends-status.sh`, or `logs/`. They belong to the operator. `logs/` stays git-ignored.
- The repository is public. Never commit secrets, vendor data, or cluster details. Keep local cluster data under `private/` (git-ignored).
- Never change a scoring rule without a spec update and a `scoring.version` bump.
- Never let the LLM affect scores. Removing the narrative layer must change no score and no pick.
- Never call the network in tests.
- Never add trade execution.
- Deploy to the cluster only through Flux and the owner's GitOps repository.
