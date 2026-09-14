---
name: audit-cors
description: Audit Cross-Origin Resource Sharing configuration for web applications and APIs. Use when reviewing server middleware, API gateway settings, deployment config, credentials/cookies, or production launch readiness for wildcard origins, overly broad methods/headers, or mismatched client-domain allowlists.
---

# Audit CORS

Check that CORS is explicitly configured, production-safe, and aligned with actual client domains.

## Workflow

1. Find all CORS enforcement points:
   - Server middleware, framework config, route-specific handlers, API gateway, CDN, reverse proxy, serverless platform config, and custom `OPTIONS` handlers.
2. Identify allowed origins:
   - Read app config, env vars, deployment files, docs, frontend base URLs, native app webviews if applicable, and production/staging domains.
   - Compare configured allowlists to actual client domains used by the app.
3. Check unsafe patterns:
   - Wildcard `*` in production APIs.
   - Reflecting any request `Origin` without allowlist validation.
   - `Access-Control-Allow-Credentials: true` combined with broad or reflected origins.
   - Overly broad methods or headers when only a smaller set is needed.
   - Missing `Vary: Origin` when origin responses vary.
   - Inconsistent CORS behavior between normal responses and error responses.
4. Verify preflight handling:
   - `OPTIONS` responses succeed for allowed origins.
   - Disallowed origins are rejected or receive no permissive CORS headers.
   - Authenticated cookie/session APIs do not accidentally allow arbitrary origins.

## Useful Searches

Search for CORS and header terms such as `cors`, `origin`, `Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials`, `OPTIONS`, `allowedOrigins`, `allow_origin`, `credentials`, `Vary`, `headers`, `methods`, gateway config, CDN config, and reverse proxy config.

## Output

Report:

- CORS locations inspected.
- Allowed origins found.
- Actual client domains inferred from the repo.
- Findings with file and line references.
- Recommended production and development allowlist values.

For each finding include the exact risky header/config and a minimal fix matching the app's framework.
