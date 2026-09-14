---
name: audit-auth-and-access-control
description: Audit authentication, session management, authorization checks, admin access, password reset flows, token storage, and cross-user data isolation. Use when reviewing login flows, protected routes, controllers, policies, database queries, or launch readiness for missing access controls and user data exposure risks.
---

# Audit Auth And Access Control

Find authentication and authorization paths where a user can stay logged in too long, escalate privileges, or access another user's data.

## Workflow

1. Map identity flows:
   - Sign up, sign in, sign out, token refresh, session creation, password reset, email verification, magic links, OAuth callbacks, and mobile auth callbacks.
   - Locate where auth tokens or session identifiers are stored on the client.
2. Map protected surfaces:
   - Server routes, controllers, page loaders, API handlers, admin routes, background actions, websocket channels, and storage/download endpoints.
   - Identify the current-user lookup and authorization policy pattern used by the codebase.
3. Check the required controls:
   - No auth tokens in `localStorage` or other XSS-exposed persistent storage unless the app has an explicit, documented threat-model exception.
   - Sessions and refresh tokens have TTLs and revocation paths.
   - Password reset, email verification, and magic links expire and are single-use.
   - Admin routes have role or permission checks at the server boundary.
   - User-owned records are always scoped by the authenticated user or an explicit membership/permission relationship.
4. Review tests for negative cases:
   - Unauthenticated access.
   - Wrong role.
   - Expired or reused reset token.
   - User A reading, updating, deleting, exporting, or downloading user B's records.

## Cross-User Data Isolation

For every handler that accepts an ID or slug, trace the query. Flag any path where lookup happens by record ID alone before checking ownership, membership, tenant, organization, or role. Prefer queries that include the current-user or current-tenant constraint in the database lookup itself.

Examples of risky patterns:

- `find(id)` followed by no ownership check.
- Client-supplied `user_id`, `account_id`, `tenant_id`, or `organization_id` trusted directly.
- Download routes or signed URLs generated without checking record ownership.
- Admin-only routes relying on hidden UI instead of server authorization.

## Useful Searches

Search for auth and ownership terms such as `current_user`, `user_id`, `account_id`, `tenant_id`, `organization_id`, `role`, `admin`, `policy`, `authorize`, `session`, `token`, `refresh`, `reset`, `magic`, `verify`, `localStorage`, `find`, `get`, `delete`, `update`, and `download`.

## Output

Lead with critical findings. For each finding include:

- File and line reference.
- Affected route or flow.
- Exploit sketch using realistic user roles.
- Existing control, if any.
- Suggested fix using the app's auth/policy conventions.
- Missing test that would prevent regression.

Include a coverage summary with counts for checked routes, protected routes, admin routes, and cross-user record lookups.
