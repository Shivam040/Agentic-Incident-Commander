## What changed?

Describe the implementation and why it is needed.

## Risk / safety impact

- [ ] No change to remediation side effects
- [ ] HITL approval remains mandatory for state-changing actions
- [ ] No secrets or credentials were committed
- [ ] New/changed behavior has tests

## Validation

- [ ] `ruff check src tests scripts`
- [ ] `pytest -q`
- [ ] Docker build succeeds
- [ ] `/health` and `/metrics` smoke tests pass when Docker behavior changed

## Evidence

Include relevant test output, screenshots, or evaluation results.
