---
name: audit-input-validation
description: Audit web application client forms and server endpoints for input validation. Use when reviewing forms, API handlers, controllers, schemas, route tests, or launch readiness for missing type, length, format, allowed-character, and server-side validation coverage; generate reviewable validation tests when server endpoint gaps are found.
---

# Audit Input Validation

Audit every user-controlled input path from UI to server and report concrete validation gaps with file and line references.

## Workflow

1. Map the application surfaces:
   - Find client forms, controlled inputs, file uploads, query builders, and API calls.
   - Find server routes, controllers, handlers, schemas, serializers, background jobs fed by user input, and webhook-like endpoints.
   - Build a route-to-form map where possible by following client API calls to server handlers.
2. For each input, verify validation at both layers:
   - Type: int, float, boolean, enum, string, array, object, file.
   - Bounds: length, numeric ranges, item counts, file sizes.
   - Format: email, URL, UUID, date/time, phone, slug, currency, etc.
   - Allowed character set: especially for names, slugs, search, rich text, filenames, and identifiers.
   - Required/optional behavior and default values.
3. Treat server-side validation as mandatory even when client validation exists.
4. Review tests for each endpoint that accepts user input. Look for invalid type, too long, malformed format, disallowed characters, missing required fields, and boundary values.
5. When server validation tests are missing and the project has an established test pattern, add focused tests as a reviewable diff. Do not commit automatically.

## Useful Searches

Use the repository's route definitions and framework conventions first. Useful search terms include `route`, `router`, `controller`, `handler`, `schema`, `validate`, `changeset`, `zod`, `yup`, `joi`, `params`, `body`, `query`, `Form`, `input`, `textarea`, `select`, `upload`, and `multipart`.

Do not count TypeScript types, UI placeholders, HTML input types, or OpenAPI documentation as server validation unless runtime code enforces them.

## Output

Produce a table with one row per form or endpoint:

| Surface | Input | Client validation | Server validation | Test coverage | Findings |
|---|---|---|---|---|---|
| `path/file:line` | `field_name` | present/missing/partial | present/missing/partial | present/missing/partial | concrete issue |

After the table, list fixes in priority order. Each finding must include:

- File and line reference.
- Risk in one sentence.
- Suggested fix, preferably matching the repository's validation style.
- Tests added or tests still needed.
