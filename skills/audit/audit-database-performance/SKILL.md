---
name: audit-database-performance
description: Audit database-backed application code for missing indexes, unbounded result sets, missing pagination, expensive joins, and connection pool risks. Use when reviewing list endpoints, filtered queries, joins, migrations, ORM code, production readiness, or scaling risks before launch.
---

# Audit Database Performance

Find database access patterns that work at small scale but become slow or unstable under ordinary production traffic.

## Workflow

1. Identify database technology and access patterns:
   - ORM, query builder, raw SQL, migrations, schemas, indexes, connection settings, and pooling.
2. Inventory high-risk queries:
   - List endpoints, search endpoints, exports, dashboards, joins, filtered queries, sorted queries, background jobs, and admin reports.
3. Check indexes:
   - Every frequently filtered, joined, ordered, or foreign-key column should be covered by a suitable index.
   - Composite indexes should match common query shapes and ordering.
   - Flag indexes that are missing for obvious production paths; avoid speculative index spam.
4. Check result bounds:
   - List endpoints should paginate or enforce limits.
   - Search and admin views should avoid unbounded `all`, `find_many`, `SELECT *`, broad preloads, and full-table exports in request handlers.
   - Background jobs should batch large data sets.
5. Check connection resilience:
   - Production pool size and timeout settings exist.
   - App worker count, job workers, and database max connections are plausibly coordinated.
   - Serverless apps avoid opening unbounded direct database connections when a pooler is required.

## Useful Searches

For each issue, connect the query to a route or job and the migration/schema that lacks the supporting index or limit. When possible, include the exact filter/join/order columns.

Useful search terms include `where`, `join`, `order`, `preload`, `include`, `limit`, `offset`, `cursor`, `paginate`, `all`, `findMany`, `SELECT`, `index`, `references`, `foreign_key`, `pool`, and `DATABASE_URL`.

## Output

Group findings by severity:

- Critical: unbounded request path likely to time out or exhaust memory.
- High: missing index on common production query or join.
- Medium: weak pagination, inefficient preload/include, pool config risk.
- Low: cleanup or documentation issue.

Each finding must include file and line, query shape, why it scales poorly, suggested migration/code fix, and the test or instrumentation that would confirm the improvement.
