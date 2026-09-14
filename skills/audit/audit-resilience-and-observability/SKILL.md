---
name: audit-resilience-and-observability
description: Audit web applications for production resilience and debugging readiness. Use when reviewing UI error boundaries, request handlers, external IO, background jobs, health checks, logging, incident diagnostics, database backups, or launch readiness for operational failure modes.
---

# Audit Resilience And Observability

Check whether the app can fail gracefully, recover predictably, and produce enough evidence to debug production incidents.

## Workflow

1. UI crash containment:
   - Verify error boundaries or equivalent app-level crash handlers wrap UI roots and major route boundaries.
   - Confirm users see recoverable states rather than a blank screen.
2. Request-path resilience:
   - Find synchronous email, SMS, webhook calls, AI calls, payment calls, or other external IO inside request handlers.
   - Recommend queueing or async jobs for slow or failure-prone operations where user response does not require completion.
   - Check timeouts, retries, idempotency, and duplicate-event handling around external services.
3. Health checks:
   - Verify a health endpoint exists.
   - Confirm it checks real dependencies needed to serve traffic, such as database, cache, queue, storage, and required external APIs where appropriate.
   - Distinguish shallow liveness from deeper readiness.
4. Logging and incident debugging:
   - Check that production logs include request IDs, user/account IDs where safe, route/action names, error classes, provider event IDs, and job IDs.
   - Confirm sensitive values are redacted.
   - Check that failures in background jobs and webhooks are observable.
5. Backup and restore:
   - Look for documented database backup strategy, retention, and restore testing.
   - Flag apps that only mention backups without a restore verification path.

## Useful Searches

Search for resilience terms such as `ErrorBoundary`, `error boundary`, `try`, `catch`, `timeout`, `retry`, `queue`, `job`, `worker`, `email`, `webhook`, `health`, `ready`, `live`, `logger`, `request_id`, `trace`, `Sentry`, `Bugsnag`, `backup`, and `restore`.

## Output

Produce sections for:

- UI crash handling.
- External IO and queueing.
- Health checks.
- Logging and tracing.
- Backups and restore.

Each finding needs file and line or documentation path, operational impact, suggested fix, and a verification step. Prioritize issues that would cause data loss, long outages, duplicate charges/emails, or impossible incident diagnosis.
