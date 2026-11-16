# Security Policy

## Reporting a vulnerability

Report vulnerabilities privately through GitHub Security Advisories:
https://github.com/mohnishbasha/stokeai-trading-supertrends/security/advisories/new

Do not open a public issue, pull request, or discussion for a vulnerability.

If you cannot use GitHub Security Advisories, email legal@serverlessvc.com.

Please include the affected version or commit, steps to reproduce, and the
impact you expect. Do not include real credentials, vendor market data, or
details of any private deployment.

## Supported versions

The project is pre-1.0. Only the latest commit on `develop` is supported.

## Scope notes

- The project holds no brokerage credentials and has no brokerage integration.
- Deployments are private by default (no public load balancer in any default
  profile). Reports that depend on exposing an instance publicly describe a
  configuration change, though we still want to hear about hardening gaps.
- Secrets (API keys, the bearer token, database password) come from
  environment variables sourced from Kubernetes Secrets, never from the
  repository. If you find one committed, report it here.
