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
