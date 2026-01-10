# Deployment Status

## Current Deployment

**Last Updated**: December 29, 2025 (02:15 UTC)

### Production Environment

| Service | Platform | URL | Status |
|---------|----------|-----|--------|
| **Backend RAG** | Fly.io | https://nuzantara-rag.fly.dev | ✅ ACTIVE |
| **Frontend** | Vercel | https://www.balizero.com | ✅ ACTIVE |

### Latest Deployment

- **Backend Version**: v1090 (deployment-01KDK1RA88G58ZK7AN5TVA1MQ1)
- **Frontend Version**: deployment-01KDJMW9JZNASJQGDEZK210KBD
- **Deployment Date**: December 29, 2025
- **Deployment Status**: ✅ **SUCCESS**

### Deployed Features (This Session)

#### 1. 🛡️ Red Team Security Hardening - 100% Survival Rate

**Results**: 50/50 adversarial tests passed (was 47/50)

| Fix | Issue | Solution |
|-----|-------|----------|
| PI-001 | Prompt Injection | Added `detect_prompt_injection()` security gate in orchestrator |
| RC-004 | Router Confusion | Added Indonesian tax terms (pph, ppn, npwp) to BUSINESS_KEYWORDS |
| EM-002 | Evaluator Bug | Fixed false positive with negation pattern detection |

**Security Enhancements**:
- New `<security_boundary>` section in system prompt
- Prompt injection detection with 20+ attack patterns
- Off-topic request blocking (jokes, stories, roleplay)
- Security gate in both sync and async RAG paths

#### 2. Observability Stack Documentation
- Added section 4.8 to AI_ONBOARDING.md
- Added monitoring diagram to SYSTEM_MAP_4D.md
- New ALERTS_RUNBOOK.md with 12 alert runbooks

#### 3. Token Tracking & LLM Cost Observability
- New `pricing.py` module for comprehensive LLM cost tracking
- Support for OpenAI, Anthropic, Google, and local models
- 28 tests with 93.62% coverage

#### 4. Frontend Type Safety Improvements
- Created `IApiClient` interface for type-safe dependency injection
- Removed 48+ `as any` casts from production code
- All domain API modules now use typed interface

### Health Status

- **Backend Health**: ✅ Healthy
  - Database: Qdrant (6 collections, 53,822 documents)
  - Embeddings: OpenAI text-embedding-3-small (1536 dimensions)
- **Frontend**: ✅ HTTP 200
- **API Endpoints**: ✅ Accessible

### Test Coverage

| Module | Coverage | Status |
|--------|----------|--------|
| Backend Python | 95.01% | ✅ Exceeds 90% target |
| reasoning.py | 96.44% | ✅ Exceeds 95% target |
| llm_gateway.py | 99.01% | ✅ Exceeds 95% target |
| prompt_builder.py | 40.33% | ✅ Security tests added |
| Frontend TypeScript | 567 tests passing | ✅ All green |
| LLM Pricing | 93.62% | ✅ New module |
| **Red Team Security** | 100% (50/50) | ✅ All attacks blocked |

### Monitoring

```bash
# Backend logs (Fly.io)
fly logs -a nuzantara-rag

# Status check
fly status -a nuzantara-rag

# Frontend monitoring - use Vercel dashboard
# https://vercel.com/dashboard
```

### Deployment Commands

```bash
# Backend (Fly.io)
cd apps/backend-rag && fly deploy --remote-only

# Frontend (Vercel)
cd apps/mouth && vercel deploy --prod

# Health check
curl https://nuzantara-rag.fly.dev/health | jq
curl -I https://www.balizero.com
```

### Notes

- CI/CD workflows now properly configured in `.github/workflows/`
- TypeScript compiles with 0 errors
- All `as any` casts removed from frontend API client
