# Deployment Status

## Current Deployment

**Last Updated**: December 28, 2025 (15:12 UTC)

### Production Environment

| Service | Platform | URL | Status |
|---------|----------|-----|--------|
| **Backend RAG** | Fly.io | https://nuzantara-rag.fly.dev | ✅ ACTIVE |
| **Frontend Mouth** | Fly.io | https://nuzantara-mouth.fly.dev | ✅ ACTIVE |

### Latest Deployment

- **Backend Version**: deployment-01KDJMNHA485BXGF8DEXCV3Y31
- **Frontend Version**: deployment-01KDJMW9JZNASJQGDEZK210KBD
- **Deployment Date**: December 28, 2025
- **Deployment Status**: ✅ **SUCCESS**

### Deployed Features (This Session)

#### 1. Token Tracking & LLM Cost Observability
- New `pricing.py` module for comprehensive LLM cost tracking
- Support for OpenAI, Anthropic, Google, and local models
- 28 tests with 93.62% coverage

#### 2. Frontend Type Safety Improvements
- Created `IApiClient` interface for type-safe dependency injection
- Removed 48+ `as any` casts from production code
- All domain API modules now use typed interface
- Fixed agents page to use `api.get<T>()` and `api.post<T>()`

#### 3. CI/CD Pipeline Fixes
- Removed `continue-on-error` from ESLint and TypeScript checks
- Fixed pre-deployment tests in deploy.yml (removed `|| true`)
- CI pipeline now properly fails on lint/type/test errors

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
| Frontend TypeScript | 567 tests passing | ✅ All green |
| LLM Pricing | 93.62% | ✅ New module |

### Monitoring

```bash
# Backend logs
fly logs -a nuzantara-rag

# Frontend logs
fly logs -a nuzantara-mouth

# Status check
fly status -a nuzantara-rag
fly status -a nuzantara-mouth
```

### Deployment Commands

```bash
# Backend
cd apps/backend-rag && fly deploy --remote-only

# Frontend
cd apps/mouth && fly deploy --remote-only

# Health check
curl https://nuzantara-rag.fly.dev/health | jq
```

### Notes

- CI/CD workflows now properly configured in `.github/workflows/`
- TypeScript compiles with 0 errors
- All `as any` casts removed from frontend API client
