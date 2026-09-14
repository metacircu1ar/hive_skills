---
name: audit-rate-limiting
description: Audit API and action routes for rate-limit coverage, identity keys, abuse cost, and policy fit. Use when reviewing public endpoints, authenticated APIs, auth flows, expensive operations, email sends, uploads, AI generation, payment actions, or launch readiness for abuse prevention.
---

# Audit Rate Limiting

Scan every API route and action endpoint for rate-limit coverage and policy fit.

## Workflow

1. Inventory routes:
   - API routers, controllers, server actions, RPC procedures, websocket events, auth endpoints, upload endpoints, webhook receivers, and public pages that trigger server work.
2. Locate rate-limit mechanisms:
   - Middleware, plugs, guards, reverse proxy config, gateway rules, CDN/WAF rules, queue throttles, per-provider limits, and library calls.
3. Classify each route:
   - Public anonymous, authenticated user, admin, internal, webhook, or background-triggered.
   - Cheap read, expensive read, mutation, email/SMS send, file upload, AI generation, payment/revenue action, auth attempt, or data export.
4. Evaluate policy fit:
   - Public unauthenticated routes usually need per-IP or per-device limits.
   - Authenticated user actions usually need per-user limits; some also need per-IP limits.
   - Expensive operations need tighter limits and cost-aware quotas.
   - Login, password reset, magic link, email send, invite, and OTP endpoints need abuse-specific limits.
   - Webhooks should usually authenticate by signature and may need provider/IP or event dedupe controls rather than user limits.
5. Review test coverage for allowed requests, exceeded limits, identity-key separation, and reset behavior.

## Common Findings

- Route has no rate limit.
- Limit key is only IP for a logged-in expensive action where per-user quota is required.
- Limit key is only user for login/reset abuse where IP/device throttling is also needed.
- Limits are stored in process memory in a horizontally scaled production app.
- High-cost endpoints share the same loose policy as ordinary reads.
- Failure response reveals unnecessary account existence information.

## Useful Searches

Search for route and throttling terms such as `rate`, `limit`, `throttle`, `quota`, `bucket`, `Redis`, `cache`, `middleware`, `plug`, `guard`, `login`, `reset`, `otp`, `email`, `invite`, `upload`, `generate`, `export`, and `webhook`.

## Output

Produce a route coverage table:

| Route | Classification | Limit present | Key | Store | Policy fit | Tests | Finding |
|---|---|---|---|---|---|---|---|
| `METHOD /path` | expensive mutation | yes/no | IP/user/etc. | memory/Redis/etc. | good/weak/missing | yes/no | issue |

Then list prioritized fixes with file and line references, suggested policy, and test cases to add.
