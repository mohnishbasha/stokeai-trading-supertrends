# Contributing

Thank you for considering a contribution. Super Trends Market Agent is
source-available and free for noncommercial use (see [LICENSE](LICENSE)).
By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Contributor License Agreement

Every contribution requires a signed [CLA](CLA.md). It lets Serverless Ventures
LLC license your contribution under any terms, including commercial ones. The
CLA check blocks pull requests from contributors who have not signed, and an
unsigned contribution cannot be merged.

## Development setup

Prerequisites: Python 3.12, uv, Node 22, Docker with buildx, make, and jq.

```
make setup    # install Python and Node dependencies from the lock files
make build    # build the project
make check    # lint, type checks, SPDX and license checks
make test     # run the test suite
```

## Test-driven development

TDD is mandatory. Write a failing test first, see it fail for the right
reason, then write the code that makes it pass. Pull requests that add
behavior without a test are not accepted.

## Specs are the source of truth

The documents in `docs/` are the source of truth. If code and a spec disagree,
the spec wins until it is changed through the Spec Change Protocol:

- Option A: the code is wrong; fix the code to match the spec.
- Option B: the spec is wrong; change the spec first (in the same pull
  request), then the code and tests.
- Option C: the spec is silent or ambiguous; record the resolution in the
  spec (an ADR where appropriate), then implement it.

Any change to scoring is always option B, and must bump `scoring.version`.

## Branches and pull requests

Branch off `develop` using one of these prefixes:

- `feature/*`
- `fix/*`
- `chore/*`
- `docs/*`

Pull requests target `develop`.

## Commit messages

Use Conventional Commits. Allowed types:

- `feat`
- `fix`
- `chore`
- `docs`
- `test`
- `refactor`
- `perf`
- `ci`

## SPDX headers

Every source file starts with these two lines (in the file's comment syntax):

```
SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
Copyright 2026 Serverless Ventures LLC
```

`scripts/check-spdx.sh` checks this, and CI fails on a source file without them.

## What never goes in the repository

The repository is public. Treat every file, commit message, issue, pull
request, and CI log as published. Never commit:

- Secrets, API keys, tokens, or kubeconfigs.
- Vendor market data, or real prices from a licensed feed (fixtures must be
  synthetic or scrubbed to the minimum shape).
- Cluster details such as tailnet names or IPs, node hostnames, or internal
  service URLs.
- Real run output, or picks from a running instance.

Report security problems privately, as described in [SECURITY.md](SECURITY.md).
