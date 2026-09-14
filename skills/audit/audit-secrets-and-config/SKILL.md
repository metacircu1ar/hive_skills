---
name: audit-secrets-and-config
description: Audit secrets, environment configuration, frontend bundles, startup validation, and webhook signature verification. Use when reviewing code for hardcoded API keys, exposed credentials, missing required environment variable checks, silent production misconfiguration, or forgeable webhook endpoints.
---

# Audit Secrets And Config

Find credentials and configuration paths that can leak, fail silently, or allow forged external events.

## Workflow

1. Search for committed secrets:
   - API keys, private keys, tokens, passwords, DSNs, OAuth client secrets, signing secrets, webhook secrets, database URLs, cloud credentials, and service account files.
   - Include frontend source, mobile source, server code, tests, config examples, docs, generated bundles, deployment files, CI config, and scripts.
2. Distinguish public identifiers from secrets:
   - Public client IDs and publishable keys can be allowed when the provider documents them as public.
   - Secret values in client or mobile bundles are always findings.
   - Redact secret values in reports; show only enough prefix/context to identify the file.
3. Inspect startup config validation:
   - Required env vars should be validated at boot with clear failures.
   - Production-only requirements should not silently fall back to development defaults.
   - Config parsing should validate type, enum values, URLs, and numeric ranges.
4. Inspect webhook endpoints:
   - Verify signature validation exists for providers such as Stripe, RevenueCat, GitHub, Apple, Google, Slack, and payment processors.
   - Verify the raw request body is used when the provider requires it.
   - Verify timestamp tolerance, replay protection where supported, and failure logging without leaking secrets.

## Useful Searches

Search for likely secret names and values with terms such as `api_key`, `apikey`, `secret`, `token`, `password`, `passwd`, `private_key`, `client_secret`, `webhook`, `signing`, `DATABASE_URL`, `AWS_`, `GCP_`, `GOOGLE_`, `STRIPE_`, `REVENUECAT_`, `SENTRY_`, and `BEGIN PRIVATE KEY`.

Use secret-scanning tools when available, but manually review hits because allowlisted test keys and public publishable keys are common.

## Output

Report three sections:

1. Exposed or hardcoded secrets.
2. Missing or weak env var validation.
3. Webhook signature verification gaps.

For each finding include file and line, secret type or config key, risk, remediation, and whether rotation is required. When a real secret appears committed, recommend immediate revocation/rotation and history cleanup without printing the full value.
