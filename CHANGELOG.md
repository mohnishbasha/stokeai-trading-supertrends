# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Python package and the `supertrends` CLI with `--version`, `serve`, and `healthcheck`; `/healthz` and `/readyz` (S0-T01).
- `supertrends config show | validate | export-schema` (S0-T09).
- UI project: Vite, React, TypeScript strict, ESLint, Vitest, and Playwright with a placeholder route (S0-T02).
- `VERSION` as the version source of truth, `scripts/check-versions.sh`, `scripts/version-sync.sh`, `scripts/extract-changelog.sh`, and this changelog (S0-T04).
- Root `Makefile` with `make help`; later-sprint targets print when they arrive (S0-T03).
- Multi-stage `Dockerfile` (non-root, read-only root filesystem) and `deploy/compose/docker-compose.local.yml` with Postgres (S0-T06).
- CI pipeline (lint and type-check, unit, coverage, integration, e2e placeholder, multi-arch image build, changelog rule) and Dependabot (S0-T05).
- Agent harness files: `AGENTS.md`, `CLAUDE.md`, `SKILLS.md`, `SOUL.md`, and the `run-tests` and `check-types` skills (S0-T07).
- License and community files, SPDX header check, dependency license check, and the CLA check (S0-T08).
- `scripts/stoke-inventory.sh`, a read-only Stoke cluster inventory written to git-ignored `private/` (S0-T10).

### Scoring

- `config/scoring.yaml` seeded with every default from the Signal Engine Specification (`scoring.version` 1), with a JSON schema and a stable `config_hash`.
