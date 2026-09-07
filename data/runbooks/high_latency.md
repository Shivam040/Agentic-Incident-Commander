# High Latency and 5xx Runbook

## Signals
- p95 latency above 1000 ms
- error rate above 10%
- downstream dependency timeout messages
- CPU saturation or thread/connection pool exhaustion

## Investigation
1. Confirm whether latency and errors rose together.
2. Check CPU, memory, request rate, dependency errors, and connection pools.
3. Identify whether failures are isolated to one service or downstream dependency.
4. Prefer reversible diagnostic actions before state changes.

## Remediation guidance
- If application instances are unhealthy but the dependency is available, a rolling restart may recover leaked/stuck resources.
- If CPU saturation is load-driven, scale out before restarting.
- If the database itself is unavailable, do not repeatedly restart application instances; escalate the dependency incident.

## Safety
Any state-changing remediation requires human approval.
