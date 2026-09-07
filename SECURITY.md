# Security Policy

## Supported versions

This is a portfolio/research project. Security fixes are applied to the latest `main` branch and the latest published release.

## Reporting a vulnerability

Please do **not** open a public issue for a credential leak, authentication weakness, unsafe remediation path, or other security-sensitive defect.

Preferred reporting path:

1. Use GitHub's **Private vulnerability reporting / Security Advisories** for this repository when available.
2. Include the affected commit/version, reproduction steps, expected impact, and any suggested mitigation.
3. Do not include real production secrets, tokens, or sensitive telemetry in the report.

## Safety boundary

The repository's remediation executor is simulation-only. State-changing proposals must pass the LangGraph human-in-the-loop approval gate before the trusted remediation tool is invoked. Changes to this boundary require explicit review and regression tests.
