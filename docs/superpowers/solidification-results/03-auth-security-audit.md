# SOLIDIFICATION 03 — Auth & Security Audit & Plan

**Date:** 2026-04-06
**Component:** Auth/Security Layer
**Scope:** JWT, RBAC, API keys, CORS, rate limiting, PII

## Findings Summary: 3 CRITICAL, 5 HIGH, 5 MEDIUM, 2 LOW

## Code Fixes Applied (this commit)

| Fix | Severity | What |
|-----|----------|------|
| F-2 | CRITICAL | Removed hardcoded `zantara-secret-2024` from 3 files. Now uses `NUZANTARA_API_KEY` env var. |
| F-5 | HIGH | Removed name-based admin role inference from API key content |
| F-6 | HIGH | Replaced `dict.get()` with `hmac.compare_digest` for constant-time API key validation |
| F-7 | HIGH | Removed `/api/agentic-rag/stream` and `/query` from public_endpoints |
| F-10 | MEDIUM | Guarded `dev_origins` CORS with `environment != "production"` check |
| F-11 | MEDIUM | Removed default `dev_scraper_key` from config |
| F-15 | LOW | Reduced API key content in warning logs |

## Fly.io Env Var Changes Required (manual)

```bash
# F-1: Enable JWT expiry enforcement (tokens already have exp claim)
fly secrets set JWT_ENFORCE_EXPIRY=true -a nuzantara-rag

# F-3: Enable token revocation (Redis-backed service already implemented)
fly secrets set ENABLE_TOKEN_REVOCATION=true -a nuzantara-rag

# F-2: Rotate API key (old one was in source code)
fly secrets set NUZANTARA_API_KEY=$(openssl rand -hex 32) -a nuzantara-rag
```

## Deferred (future sprint)

- F-4: Remove X-Debug-Key bypass (needs cron service account migration first)
- F-9: Account lockout in primary login router (needs integration with identity service)
- F-12: PII scanner required + recursive scan (needs presidio as required dep)
- F-8: Service account key audit (needs Google Cloud access)
