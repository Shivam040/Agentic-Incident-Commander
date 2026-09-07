# Database Connection Pool Pressure Runbook

## Signals
- connection pool utilization above 90%
- timeout errors
- elevated 5xx responses
- request latency spikes

## Investigation
1. Check pool utilization and timeout frequency.
2. Check database health before changing the application.
3. Check for traffic bursts and slow queries.
4. Correlate failures with deployment or configuration changes.

## Safe response
- Avoid destructive database operations.
- Prefer traffic reduction, safe scaling, or a controlled rolling restart when supported by evidence.
- Escalate if database health is impaired.

## Approval
A human operator must approve any state-changing action.
