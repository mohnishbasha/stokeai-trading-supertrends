---
name: check-types
description: Run lint, format check, type-check (mypy strict, tsc), and the version check. Use before opening a PR.
---

# check-types

Runs `make check`: `ruff check`, `ruff format --check`, `mypy --strict`, UI lint and type-check, and `scripts/check-versions.sh`.

## Usage

```bash
.agent/skills/check-types/run.sh
```

Exit code is non-zero on any finding. Do not add `# type: ignore` without a reason comment.
