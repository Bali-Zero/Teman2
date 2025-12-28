# Deployment Status

## Current Deployment

**Last Updated**: December 28, 2025

### Production Environment

- **App Name**: `nuzantara-rag`
- **Platform**: Fly.io
- **Region**: sin (Singapore)
- **URL**: https://nuzantara-rag.fly.dev/
- **Status**: ✅ **ACTIVE**

### Latest Deployment

- **Version**: 1073
- **Image**: `deployment-01KDH7M3D235J4QKEM25ZJYD6B`
- **Deployment Date**: December 28, 2025
- **Deployment Status**: ✅ **SUCCESS**

### Deployed Features

#### Test Coverage Improvements
- **Coverage**: 95.01% (Target: 90% - EXCEEDED!)
- **reasoning.py**: 96.30% coverage
- **feedback.py**: 89.61% coverage
- **72+ new tests** added
- **All critical paths** covered

#### Key Improvements
- Comprehensive edge case coverage
- Integration tests for complex scenarios
- Exact line coverage tests
- Citation handling tests
- Streaming mode tests
- Error handling tests

### Health Status

- **App Status**: ✅ Running
- **Health Endpoint**: `/api/health` - ✅ Responding
- **API Endpoints**: ✅ Accessible
- **Database**: ✅ Connected
- **Qdrant**: ⚠️ Minor warnings (non-critical)

### Monitoring

- **Logs**: `flyctl logs -a nuzantara-rag`
- **Status**: `flyctl status -a nuzantara-rag`
- **Metrics**: Available via Fly.io dashboard

### Deployment Process

1. **Pre-Deployment**:
   ```bash
   cd apps/backend-rag
   pytest --cov=services.rag.agentic.reasoning --cov=app.routers.feedback
   ```

2. **Deployment**:
   ```bash
   cd apps/backend-rag
   flyctl deploy -a nuzantara-rag
   ```

3. **Verification**:
   ```bash
   curl https://nuzantara-rag.fly.dev/api/health
   flyctl logs -a nuzantara-rag --no-tail
   ```

### Notes

- All deployments are manual (no CI/CD)
- Deployments are done from local machine
- Test coverage must be maintained above 90%
- Critical paths must be covered by tests


