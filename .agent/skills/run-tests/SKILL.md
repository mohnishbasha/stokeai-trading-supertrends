---
name: run-tests
description: Run the unit tests for Python and the UI. Use before reporting work as done.
---

# run-tests

Runs `make test`: Python unit tests (`pytest tests/unit`) and UI tests (`vitest`).

## Usage

```bash
.agent/skills/run-tests/run.sh
```

Exit code is non-zero if any test fails. Tests never use the network. If a test fails, fix the code or the test for a documented reason. Do not weaken a scoring rule to pass.
