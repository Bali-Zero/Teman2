# Nuzantara Deployment Pipeline Architecture

## Overview

This document describes the complete deployment pipeline architecture for the Nuzantara platform.

## Pipeline Components

### 1. GitHub Actions Workflows

#### CI Workflow (`ci.yml`)
- **Trigger**: Pull requests, pushes to main/develop
- **Purpose**: Validate code quality and functionality
- **Jobs**:
  - Linting and formatting checks
  - Backend RAG tests (Python/pytest)
  - Node.js tests (Jest)
  - Security audits
  - Docker build validation
  - Coverage gate enforcement

#### CD Workflow (`deploy.yml`)
- **Trigger**: Push to main, manual dispatch
- **Purpose**: Automated deployment to Fly.io
- **Jobs**:
  - Pre-deployment validation
  - Backend RAG deployment
  - Mouth frontend deployment
  - Post-deployment health checks
  - Automatic rollback on failure

#### Monitoring Workflow (`monitoring.yml`)
- **Trigger**: Hourly schedule, manual dispatch
- **Purpose**: Continuous production monitoring
- **Jobs**:
  - Production health checks
  - Security vulnerability scanning
  - Performance benchmarking
  - Response time monitoring

### 2. Fly.io Configuration

#### Backend RAG (`apps/backend-rag/fly.toml`)
- **App Name**: nuzantara-rag
- **Region**: Singapore (sin)
- **Resources**: 2 CPUs, 2GB RAM
- **Health Check**: /health endpoint, 60s grace period
- **Strategy**: Rolling deployment

#### Mouth Frontend (`apps/mouth/fly.toml`)
- **App Name**: nuzantara-mouth
- **Region**: Singapore (sin)
- **Resources**: 2 CPUs, 1GB RAM
- **Health Check**: / endpoint, 30s grace period
- **Strategy**: Rolling deployment

### 3. Deployment Scripts

#### `validate-deployment.sh`
- Checks required tools
- Validates configuration files
- Verifies git status
- Optional Docker build test

#### `health-check.sh`
- Tests all service endpoints
- Measures response times
- Runs integration tests
- Reports status summary

#### `rollback.sh`
- Lists recent releases
- Interactive rollback interface
- Support for version-specific rollback
- Post-rollback health validation

#### `deploy-local.sh`
- Local Docker Compose management
- Service health monitoring
- Log viewing
- Cleanup utilities

## Deployment Flow

```
┌──────────────────────────────────────────────────────────┐
│                    Developer Workflow                     │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │  Create Feature  │
                  │     Branch       │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │   Create PR      │
                  └────────┬─────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                  CI Pipeline (ci.yml)                     │
├──────────────────────────────────────────────────────────┤
│  1. Lint & Format Check                                  │
│  2. Backend RAG Tests (Python + PostgreSQL + Redis)      │
│  3. Node.js Tests (Jest)                                 │
│  4. Security Audit (npm audit + safety)                  │
│  5. Docker Build Test                                    │
│  6. Coverage Gate                                        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
                   ┌──────────┐
                   │   Pass?  │
                   └──┬────┬──┘
                      │    │
                  Yes │    │ No
                      │    │
                      │    └──────> Fix Issues & Push
                      │
                      ▼
              ┌──────────────┐
              │  Merge to    │
              │     Main     │
              └──────┬───────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│               CD Pipeline (deploy.yml)                    │
├──────────────────────────────────────────────────────────┤
│  1. Pre-deployment Checks                                │
│     - Validate fly.toml files                            │
│     - Check environment variables                        │
│     - Run smoke tests                                    │
│                                                           │
│  2. Deploy Backend RAG                                   │
│     - Set secrets on Fly.io                              │
│     - Deploy with rolling strategy                       │
│     - Health check (10 retries, 10s interval)            │
│                                                           │
│  3. Deploy Mouth Frontend                                │
│     - Set secrets on Fly.io                              │
│     - Deploy with rolling strategy                       │
│     - Health check (10 retries, 10s interval)            │
│                                                           │
│  4. Post-deployment Validation                           │
│     - Integration tests                                  │
│     - Full system health check                           │
│     - Notify team                                        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
                   ┌──────────┐
                   │ Success? │
                   └──┬────┬──┘
                      │    │
                  Yes │    │ No
                      │    │
                      │    └──────> Automatic Rollback
                      │
                      ▼
              ┌──────────────┐
              │  Production  │
              │   Running    │
              └──────┬───────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│         Continuous Monitoring (monitoring.yml)            │
├──────────────────────────────────────────────────────────┤
│  - Hourly health checks                                  │
│  - Security vulnerability scans                          │
│  - Performance benchmarks                                │
│  - Response time monitoring                              │
└──────────────────────────────────────────────────────────┘
```

## Rollback Procedures

### Automatic Rollback

Triggered when:
- Health check fails after deployment
- Post-deployment validation fails
- Manual trigger via workflow dispatch

### Manual Rollback

```bash
# Method 1: Script
./scripts/deployment/rollback.sh

# Method 2: Fly.io CLI
flyctl releases rollback --app APP_NAME -y

# Method 3: GitHub Actions
# Re-run previous successful deployment workflow
```

## Monitoring & Alerting

### Built-in Monitoring

1. **Fly.io Health Checks**
   - Endpoint: /health (backend), / (frontend)
   - Interval: 30 seconds
   - Timeout: 10 seconds
   - Grace period: 30-60 seconds

2. **GitHub Actions Monitoring**
   - Hourly production health checks
   - Security vulnerability scans
   - Performance benchmarks

3. **Application Metrics**
   - Prometheus (port 9090)
   - Grafana (port 3001)
   - Jaeger tracing (port 16686)

### Custom Alerts

Configure alerts in Fly.io:

```bash
flyctl monitor --app APP_NAME \
  --check health \
  --notify email:team@example.com
```

## Security Considerations

### Secrets Management

- **Never commit secrets** to version control
- Use **GitHub Secrets** for CI/CD
- Use **Fly.io Secrets** for runtime
- Rotate secrets every 90 days

### Access Control

- **2FA required** for GitHub and Fly.io
- **Least privilege** principle for API keys
- **Branch protection** on main branch
- **Required reviews** for PRs

### Container Security

- Multi-stage Docker builds
- Non-root user in containers
- Minimal base images (alpine)
- Regular dependency updates

## Performance Optimization

### Deployment Speed

- Docker layer caching
- Parallel job execution
- Remote-only builds on Fly.io
- Rolling deployment strategy

### Application Performance

- 2 CPUs per VM
- Appropriate memory allocation
- Health check optimization
- Static asset caching

## Troubleshooting Guide

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Health check timeout | Deployment fails | Increase grace_period in fly.toml |
| Out of memory | Container crashes | Scale memory in fly.toml |
| Slow deployment | Takes >15 minutes | Check Docker layer caching |
| Failed tests | CI pipeline fails | Review test logs, fix issues |
| Secret not found | Runtime error | Verify secrets with `flyctl secrets list` |

### Debug Commands

```bash
# View deployment logs
flyctl logs --app APP_NAME -n 500

# SSH into container
flyctl ssh console --app APP_NAME

# Check VM status
flyctl status --app APP_NAME

# View release history
flyctl releases list --app APP_NAME

# Monitor real-time metrics
flyctl metrics --app APP_NAME
```

## Continuous Improvement

### Metrics to Track

- Deployment frequency
- Mean time to recovery (MTTR)
- Change failure rate
- Deployment duration
- Test coverage
- Security vulnerabilities

### Best Practices

1. Keep deployment scripts updated
2. Document all manual procedures
3. Test rollback procedures regularly
4. Monitor deployment metrics
5. Gather team feedback
6. Automate repetitive tasks

## Resources

- [Fly.io Documentation](https://fly.io/docs/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [DEPLOYMENT.md](../docs/DEPLOYMENT.md) - Full deployment guide
- [DEPLOYMENT_QUICKSTART.md](../DEPLOYMENT_QUICKSTART.md) - Quick reference

---

**Version**: 1.0.0  
**Last Updated**: 2025-12-28  
**Maintained By**: DevOps Team
