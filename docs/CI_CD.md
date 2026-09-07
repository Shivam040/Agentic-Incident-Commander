# Stage 4D — CI/CD and Repository Hardening

This patch adds CI/CD and repository-quality controls without changing the agent workflow, prompts, evaluation data, Dockerfile, or application source.

## What is added

- `.github/workflows/ci.yml`
  - Python 3.11 + 3.12 test matrix
  - Ruff linting
  - source compilation check
  - pytest branch coverage with a starting 50% gate
  - HTML/XML coverage artifacts
  - deterministic API/HITL integration job
  - Docker Buildx build and hardened container health smoke test

- `.github/workflows/release.yml`
  - optional GHCR publishing on a GitHub Release
  - OCI labels, semantic-version tags, SHA tag
  - BuildKit cache, SBOM, and provenance metadata

- `.github/dependabot.yml`
  - weekly pip, GitHub Actions, and Docker dependency update PRs

- `.github/CODEOWNERS`
  - owner review for all files and additional emphasis on high-risk safety/orchestration files

- `.github/pull_request_template.md`
  - explicit safety/HITL and validation checklist

- `.github/ISSUE_TEMPLATE/*`
  - structured bug and feature reports

- `SECURITY.md`
  - private vulnerability reporting guidance and a documented safety boundary

- `tests/test_stage4d_integration.py`
  - full deterministic approve path
  - full deterministic reject path
  - persisted checkpoint read/history assertions

- `scripts/ci_docker_smoke.sh`
  - health and metrics checks
  - API request smoke
  - non-root verification
  - read-only root filesystem verification
  - dropped capability verification
  - no-new-privileges verification

## First local validation

Run from the project root in PowerShell:

```powershell
python -m pip install -e ".[dev]"
ruff check src tests scripts
pytest -q
```

Then run the new integration tests specifically:

```powershell
pytest -q tests/test_stage4d_integration.py
```

Coverage:

```powershell
pytest -q `
  --cov=incident_commander `
  --cov-branch `
  --cov-report=term-missing `
  --cov-report=html `
  --cov-report=xml
```

Do **not** raise the CI threshold based on guesswork. Read the measured `TOTAL` percentage first. After the workflow is stable, set `--cov-fail-under` to a value a few points below the measured baseline and then improve coverage intentionally.

## Push and verify GitHub Actions

After committing the patch, push to a feature branch and create a pull request. The expected checks are:

- `Python 3.11`
- `Python 3.12`
- `Deterministic integration`
- `Hardened Docker smoke`

Do not merge until all are green.

## Recommended repository ruleset

After the checks have run at least once, configure `Settings -> Rules -> Rulesets` for `main`:

1. Require a pull request before merging.
2. Require at least one approval.
3. Require conversation resolution.
4. Require these status checks:
   - Python 3.11
   - Python 3.12
   - Deterministic integration
   - Hardened Docker smoke
5. Block force pushes.
6. Block branch deletion.
7. Require branches to be up to date before merge if you want strict merge gating.

Also enable Dependabot alerts/security updates and secret scanning/push protection when available for the repository.

## GHCR publishing

The release workflow does nothing during normal pushes. It publishes only when:

- a GitHub Release is published, or
- `workflow_dispatch` is manually invoked.

It authenticates to `ghcr.io` using GitHub's automatically generated `GITHUB_TOKEN`; no personal registry password is required.

To publish a versioned image, create a tag/release such as `v0.4.0`, then publish the GitHub Release. Expected tags include the semantic version, major/minor, SHA, and `latest` for release-triggered builds.

After the first publish, set the GHCR package visibility to **Public** if you want recruiters to pull it without authentication.

## Resume metrics to collect after first CI run

Record these only after GitHub measures them:

- number of automated tests passing
- measured line/branch coverage percentage
- number of Python versions validated
- Docker build + smoke-test pass status
- GHCR image publication status

Do not claim a coverage percentage before reading the generated coverage report.
