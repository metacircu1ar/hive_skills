---
name: audit-type-safety
description: Audit TypeScript codebases for type-safety bypasses and weak typing. Use when reviewing TS or TSX files for any, untyped function signatures, unchecked external data, ts-ignore or ts-expect-error comments without justification, generated code that bypasses the type system, or launch readiness.
---

# Audit Type Safety

Find TypeScript code paths where the type system was bypassed or weakened enough to hide real defects.

## Workflow

1. Establish the compiler baseline:
   - Read `tsconfig` files and package scripts.
   - Check strictness settings such as `strict`, `noImplicitAny`, `strictNullChecks`, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes`.
   - Run the repository's typecheck command if available and practical.
2. Search for bypasses:
   - Explicit `any`, implicit any from untyped parameters, unsafe casts, double casts through `unknown`, `as any`, non-null assertions, disabled lint rules, and `@ts-ignore` or `@ts-expect-error`.
   - Treat `@ts-expect-error` without a clear nearby explanation as a finding.
3. Review external data boundaries:
   - API responses, server request bodies, JSON parsing, storage reads, environment variables, feature flags, URL params, and third-party SDK data.
   - Prefer runtime parsing/validation at boundaries and typed internal values after parsing.
4. Review AI-generated or copied code paths:
   - Look for generated directories, comments, broad casts, untyped helpers, or large code additions that disabled checks.
   - Flag places where generated code accepts unvalidated data or erases types.
5. Prioritize by blast radius:
   - Shared utilities, API clients, auth/payment code, data models, and user-input paths rank above isolated UI glue.

## Useful Searches

Use fast searches such as:

```bash
rg -n "\bany\b|as any|@ts-ignore|@ts-expect-error|eslint-disable|// @ts-|unknown as|!\." --glob '*.{ts,tsx}'
rg -n "function [^(]+\([^)]*\)|=>|JSON\.parse|fetch\(" --glob '*.{ts,tsx}'
```

Tune searches to the repository to avoid noise.

## Output

Group findings by category:

- Compiler configuration gaps.
- Explicit type bypasses.
- Untyped public/shared function signatures.
- Unchecked external data.
- Generated or copied code bypasses.

Each finding must include file and line, why the type checker cannot protect the code, a concrete safer type or parser pattern, and whether an automated typecheck/lint rule can prevent recurrence.
