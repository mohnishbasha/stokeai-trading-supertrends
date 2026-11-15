# SKILLS.md

## Skills index

| Name | Directory | When to use |
|---|---|---|
| `run-tests` | `.agent/skills/run-tests/` | Run the unit test suites (Python and UI) before reporting work as done |
| `check-types` | `.agent/skills/check-types/` | Run lint, format check, type-check, and version check |
| `daily-brief` | `.agent/skills/daily-brief/` | Fetch the daily read from a running instance. Not available until Sprint 7 |

## Skill format

A skill is a directory under `.agent/skills/` containing:

- `SKILL.md` with YAML frontmatter holding `name` and `description`, followed by usage notes.
- An executable `run.sh` that starts with `#!/usr/bin/env bash`, the SPDX and copyright header, and `set -euo pipefail`, then changes to the repository root and runs the command.

Example frontmatter:

```yaml
---
name: run-tests
description: Run the unit tests for Python and the UI.
---
```

## Adding a skill

1. Create `.agent/skills/<name>/`.
2. Write `SKILL.md` with `name` (matching the directory) and a one-line `description` that says when to use it.
3. Write `run.sh` with `set -euo pipefail`, make it executable (`chmod +x`), and run `shellcheck` on it.
4. Keep it thin: call an existing Makefile target or CLI command rather than duplicating logic.
5. Add a row to the index table above.

## Pi skill loading notes

Pi discovers skills from `.agent/skills/*/SKILL.md`. It reads the frontmatter `name` and `description` to decide when a skill applies, then loads the body on demand. Keep descriptions short and specific so the match is reliable. Skills that are not yet available should say so in the description and exit with a clear notice if run.
