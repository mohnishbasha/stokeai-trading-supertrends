@import AGENTS.md

## Memory model

| Need | Read |
|---|---|
| Product behavior, scoring intent, user-visible rules | `docs/PRD.md` |
| Structure, contracts, ADRs, Makefile and deploy design | `docs/ARCHITECTURE.md` and `docs/adr/` |
| UI layout, tokens, components | `docs/DESIGN.md` |
| Current task, sprint scope, acceptance | `docs/SPRINT_PLAN.md` |
| Test scenarios and coverage expectations | `docs/TEST_PLAN.md` |
| Actions only the owner can take | `docs/OWNER_CHECKLIST.md` |
| Unmet sprint checklist items | `docs/GATE_DEBT.md` |
| Lessons from past sprints | `docs/RETROSPECTIVES.md` |
| Original full build specification (read only) | `BUILD_PROMPT.md` |

## Key entry points

| Directory | Purpose |
|---|---|
| `src/supertrends/indicators` | Pure indicator math (Supertrend, RSI, volume, and others) |
| `src/supertrends/scoring` | Factors, regime, weights, composite score, confidence |
| `src/supertrends/selection` | Candidate filtering, ranking, correlation limits |
| `src/supertrends/narrative` | Evidence document, templates, optional LLM text, guard |
| `src/supertrends/data` | Models, repository, ingest, calendar, quality, providers |
| `src/supertrends/runs` | Daily run orchestrator, state, publish |
| `src/supertrends/trackrecord` | Outcomes, statistics, backtest |
| `src/supertrends/api` | FastAPI app, routes, schemas, security |
| `src/supertrends/mcp` | MCP server and tools |
| `src/supertrends/cli` | `supertrends` command line |
| `ui/src` | React UI (routes, components, store, lib, generated API client) |
| `config/scoring.yaml` | Every period, weight, and threshold, versioned and hashed |
| `deploy/` | Compose, Helm chart, Flux, kind, systemd, dashboards |
| `scripts/` | Prerequisite, version, coverage, license, and install scripts |
| `tests/` | unit, integration, smoke, regression, golden, narrative_eval, fixtures |

## Before writing any code

- [ ] Read the GitHub issue and its acceptance criteria.
- [ ] Read the matching sections of `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `docs/TEST_PLAN.md`.
- [ ] Add or update the scenarios in `docs/TEST_PLAN.md` for this change.
- [ ] Create a branch named `feature/s{n}-t{nn}-slug` off `develop`.
- [ ] Write a failing test first.

## PR checklist

```bash
make check
make test
make coverage
scripts/check-versions.sh
scripts/check-spdx.sh
```

- [ ] Spec docs updated in the same PR when behavior changed.
- [ ] Conventional Commit title.
- [ ] No secrets, vendor data, or cluster details in the diff.
- [ ] `scoring.version` bumped if any scoring rule changed.
- [ ] Disclaimer still shown with every pick on every surface touched.

## Claude-specific rules

- Do not edit `runner.mk`, `run-supertrends.sh`, `run-supertrends-status.sh`, or `logs/`.
- Do not run git commands that rewrite history or push unless the owner asks.
- Keep working on unblocked tasks. Stop only when nothing unblocked remains, and record owner-only items in `docs/OWNER_CHECKLIST.md`.
- If you are about to pass LLM output into scoring, ranking, or selection, stop.
- Verify current vendor API shapes and tool versions against official docs at implementation time, and record the date in the relevant ADR.
- Use skills under `.agent/skills/` when they fit (see `SKILLS.md`).
- Keep `CLAUDE.local.md` personal and untracked.
