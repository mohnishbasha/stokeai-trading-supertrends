# Gate Debt

Unmet sprint checklist items and acceptance criteria, carried forward. Sprints do not gate each other: an unmet item is logged here and the run continues. The Final Gate at the end of Sprint 9 requires this file to have no open entries.

Each entry: id, sprint, item, reason, plan, status (`open` or `resolved`, with the resolving PR).

| ID | Sprint | Item | Reason | Plan | Status |
|---|---|---|---|---|---|
| GD-001 | 0 | S0-T08 acceptance criterion: "a PR from a non-owner account without a signed CLA is blocked" | The `cla` workflow (ADR-051) runs on every PR and fails for an unsigned non-owner author, but it is not a required status check on `develop`, `staging`, or `main`, so the failure does not block the merge. The agent was not permitted to change branch protection. The end-to-end proof from a second account (TS-SEC-019) also needs an account the agent does not have | Owner adds `cla` to the required checks (docs/OWNER_CHECKLIST.md #18, one command) and runs the manual TS-SEC-019 test (#19). Then the agent opens a test PR that confirms the check is listed as required, and marks this entry resolved | open |
