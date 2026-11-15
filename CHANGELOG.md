# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Python package and the `supertrends` CLI with `--version`, `serve`, and `healthcheck`; `/healthz` and `/readyz` (S0-T01).
- `supertrends config show | validate | export-schema` (S0-T09).
- UI project: Vite, React, TypeScript strict, ESLint, Vitest, and Playwright with a placeholder route (S0-T02).
- `VERSION` as the version source of truth, `scripts/check-versions.sh`, `scripts/version-sync.sh`, `scripts/extract-changelog.sh`, and this changelog (S0-T04).

### Scoring

- `config/scoring.yaml` seeded with every default from the Signal Engine Specification (`scoring.version` 1), with a JSON schema and a stable `config_hash`.
