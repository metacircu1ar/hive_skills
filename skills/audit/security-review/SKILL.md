---
name: security-review
description: Run an umbrella web application security review that composes focused audit skills and reports OWASP-style findings. Use before launch, before major releases, after large auth/payment/data changes, or when a user asks for a broad security pass across validation, auth, secrets, rate limits, CORS, database access, resilience, assets, and type safety.
---

# Security Review

Run a broad, evidence-driven security and production-readiness review by composing the focused audit skills in this library.

## Workflow

1. Identify app shape:
   - Frameworks, server entrypoints, client apps, route definitions, auth model, database, deployment config, and test commands.
2. Run focused sibling skills when applicable:
   - `audit-input-validation`
   - `audit-auth-and-access-control`
   - `audit-secrets-and-config`
   - `audit-rate-limiting`
   - `audit-cors`
   - `audit-database-performance`
   - `audit-resilience-and-observability`
   - `audit-asset-pipeline`
   - `audit-type-safety`
3. Map results to common risk classes:
   - Broken access control.
   - Injection and unsafe input handling.
   - Cryptographic or secret management failures.
   - Security misconfiguration.
   - Vulnerable operational posture.
   - Identification and authentication failures.
   - Software and data integrity failures.
   - Logging and monitoring failures.
4. Remove duplicate findings:
   - Keep the finding under the most specific category.
   - Cross-reference related findings when one fix resolves multiple risks.
5. Validate high-impact claims:
   - Re-read the code path before reporting critical or high severity issues.
   - Include enough file and line evidence that another engineer can reproduce the concern quickly.

## Severity Guide

- Critical: likely account takeover, cross-user data exposure/modification, secret compromise, payment abuse, data loss, or unauthenticated admin action.
- High: missing server validation on dangerous input, weak auth/session controls, forgeable webhooks, unbounded expensive abuse path, or production-wide misconfiguration.
- Medium: incomplete coverage that increases exploitability or incident cost.
- Low: hardening, documentation, or maintainability issue with limited direct exploitability.

## Useful Searches

Start with the focused sibling skills' search guidance. For a first pass, search route definitions, auth policy code, config files, env handling, webhook endpoints, upload handlers, database queries, TypeScript bypasses, and production deployment files.

## Output

Lead with findings, ordered by severity. Use this shape:

```markdown
## Findings

### Critical
- `file:line` Title
  Impact: one sentence.
  Evidence: concise code-path summary.
  Fix: concrete change.
  Test: regression test to add or run.

### High
...

## Coverage
- Skills run:
- Areas not applicable:
- Areas not inspected and why:

## Suggested Next Pass
- Short list of follow-up checks or implementation tasks.
```

Do not pad the report with generic checklist items. If no issues are found in an area, say what was inspected and why it appears covered.
