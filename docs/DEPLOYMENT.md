# Nuzantara Deployment Guide

Comprehensive guide for deploying the Nuzantara platform to production using Fly.io and GitHub Actions.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [CI/CD Pipeline](#cicd-pipeline)
- [Manual Deployment](#manual-deployment)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Rollback Procedures](#rollback-procedures)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The Nuzantara platform uses a modern CI/CD pipeline with:

- **Continuous Integration**: Automated testing, linting, and validation on every PR
- **Continuous Deployment**: Automated deployment to Fly.io on merge to main
- **Health Checks**: Automated post-deployment validation
- **Rollback**: One-command rollback to previous versions

### Architecture

```
┌─────────────────┐
│   GitHub Repo   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ GitHub Actions  │
│   CI/CD         │
└────────┬────────┘
         │
         ├─────────────────┬─────────────────┐
         ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Backend RAG  │  │    Mouth     │  │  Other Apps  │
│  (Fly.io)    │  │  (Fly.io)    │  │  (Fly.io)    │
└──────────────┘  └──────────────┘  └──────────────┘
```

## 📦 Prerequisites

### Required Tools

- **Git**: Version control
- **Docker**: Container runtime
- **Node.js 20+**: For npm workspaces
- **Fly.io CLI**: For manual deployments
- **jq**: JSON processing (for scripts)

### Installation

```bash
# Install Fly.io CLI
curl -L https://fly.io/install.sh | sh

# Verify installations
docker --version
node --version
flyctl version
jq --version
```

### Required Secrets

Configure these secrets in your GitHub repository (Settings → Secrets and variables → Actions):

```
FLY_API_TOKEN          # Your Fly.io API token
OPENAI_API_KEY         # OpenAI API key
ANTHROPIC_API_KEY      # Anthropic API key
GOOGLE_API_KEY         # Google Gemini API key
DATABASE_URL           # PostgreSQL connection string
REDIS_URL              # Redis connection string
JWT_SECRET             # JWT signing secret
NEXT_PUBLIC_API_URL    # Frontend API endpoint
```

## 🚀 Quick Start

### 1. Validate Your Setup

```bash
# Run pre-deployment validation
./scripts/deployment/validate-deployment.sh
```

### 2. Test Locally

```bash
# Start all services locally
./scripts/deployment/deploy-local.sh

# Option 2: Start in background
docker-compose up -d

# Check health
curl http://localhost:8080/health | jq .
```

### 3. Deploy to Production

**Option A: Automatic (Recommended)**
```bash
# Merge to main branch
git checkout main
git merge develop
git push origin main

# GitHub Actions will automatically deploy
```

**Option B: Manual**
```bash
# Deploy backend
cd apps/backend-rag
flyctl deploy

# Deploy frontend
cd apps/mouth
flyctl deploy
```

## 🔄 CI/CD Pipeline

### Workflow Overview

The platform uses two main workflows:

#### 1. CI Workflow (`ci.yml`)

Triggered on: Pull requests and pushes to `main` and `develop`

**Jobs:**
- **Lint**: ESLint, Prettier, TypeScript checks
- **Test Backend RAG**: Python/pytest with PostgreSQL and Redis
- **Test Node.js**: Jest tests with coverage
- **Security Audit**: npm audit and Python safety checks
- **Docker Build**: Test Docker image builds
- **Coverage Gate**: Ensure coverage thresholds are met

#### 2. CD Workflow (`deploy.yml`)

Triggered on: Push to `main` or manual dispatch

**Jobs:**
- **Pre-deploy Checks**: Validate configuration and environment
- **Deploy Backend RAG**: Deploy Python FastAPI service
- **Deploy Mouth**: Deploy Next.js frontend
- **Post-deploy Validation**: Integration tests and health checks
- **Rollback** (if needed): Automatic rollback on failure

### Workflow Status

Check workflow status:
- GitHub Actions tab: https://github.com/YOUR_ORG/nuzantara/actions
- Status badges in README.md

### Manual Workflow Trigger

```bash
# Using GitHub CLI
gh workflow run deploy.yml -f environment=production -f service=all

# Or use GitHub UI: Actions → Deploy → Run workflow
```

## 🛠️ Manual Deployment

### Deploy Backend RAG

```bash
cd apps/backend-rag

# Set secrets (first time only)
flyctl secrets set \
  OPENAI_API_KEY="your-key" \
  ANTHROPIC_API_KEY="your-key" \
  GOOGLE_API_KEY="your-key" \
  DATABASE_URL="your-db-url" \
  REDIS_URL="your-redis-url" \
  JWT_SECRET="your-secret" \
  --app nuzantara-rag

# Deploy
flyctl deploy --remote-only --strategy rolling

# Check status
flyctl status --app nuzantara-rag

# View logs
flyctl logs --app nuzantara-rag
```

### Deploy Mouth Frontend

```bash
cd apps/mouth

# Set secrets
flyctl secrets set \
  NEXT_PUBLIC_API_URL="https://nuzantara-rag.fly.dev" \
  --app nuzantara-mouth

# Deploy
flyctl deploy --remote-only --strategy rolling

# Check status
flyctl status --app nuzantara-mouth
```

### Zero-Downtime Deployment

The pipeline uses **rolling deployment** strategy:

1. New version is deployed alongside old version
2. Health checks verify new version is healthy
3. Traffic gradually shifts to new version
4. Old version is shut down

## 🏥 Monitoring & Health Checks

### Automated Health Checks

Run comprehensive health checks:

```bash
./scripts/deployment/health-check.sh
```

### Manual Health Checks

```bash
# Backend RAG
curl https://nuzantara-rag.fly.dev/health | jq .

# Frontend
curl -I https://nuzantara-mouth.fly.dev

# With retry logic
for i in {1..5}; do
  curl -f https://nuzantara-rag.fly.dev/health && break
  sleep 5
done
```

### Monitoring Tools

**Fly.io Dashboard**
- Metrics: https://fly.io/dashboard/YOUR_ORG/monitoring
- Logs: `flyctl logs --app APP_NAME`
- Metrics: `flyctl metrics --app APP_NAME`

**Application Monitoring**
- Prometheus: http://localhost:9090 (local)
- Grafana: http://localhost:3001 (local)
- Jaeger: http://localhost:16686 (local)

### Alerts

Configure alerts in Fly.io:

```bash
# Set up alerts for health check failures
flyctl monitor --app nuzantara-rag \
  --check health \
  --notify email:your@email.com
```

## ⏮️ Rollback Procedures

### Automated Rollback

Rollback is automatic if deployment fails health checks.

### Manual Rollback

**Option A: Using Script**
```bash
./scripts/deployment/rollback.sh
```

**Option B: Using Fly.io CLI**
```bash
# List releases
flyctl releases list --app nuzantara-rag

# Rollback to previous version
flyctl releases rollback --app nuzantara-rag -y

# Rollback to specific version
flyctl releases rollback --app nuzantara-rag --version v42 -y
```

**Option C: Via GitHub Actions**
```bash
# Re-run the previous successful deployment workflow
gh workflow run deploy.yml -f environment=production
```

### Post-Rollback Validation

```bash
# Run health checks
./scripts/deployment/health-check.sh

# Check application logs
flyctl logs --app nuzantara-rag -n 100
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Deployment Fails with "Health Check Timeout"

**Cause**: Application takes too long to start

**Solution**:
```bash
# Increase health check grace period in fly.toml
[checks.health]
  grace_period = "120s"  # Increase from 60s

# Or check application logs
flyctl logs --app nuzantara-rag
```

#### 2. "Out of Memory" Errors

**Cause**: Insufficient memory allocation

**Solution**:
```bash
# Scale up VM memory in fly.toml
[[vm]]
  memory_mb = 2048  # Increase from 1024
```

#### 3. Database Connection Errors

**Cause**: Invalid DATABASE_URL or firewall rules

**Solution**:
```bash
# Verify secret
flyctl secrets list --app nuzantara-rag

# Update secret
flyctl secrets set DATABASE_URL="new-url" --app nuzantara-rag
```

#### 4. Docker Build Fails Locally

**Cause**: Missing dependencies or Docker configuration

**Solution**:
```bash
# Clean Docker cache
docker system prune -af

# Rebuild without cache
docker-compose build --no-cache

# Check Dockerfile syntax
docker build --dry-run -t test apps/backend-rag
```

### Debug Commands

```bash
# View detailed deployment logs
flyctl logs --app nuzantara-rag -n 500

# SSH into running container
flyctl ssh console --app nuzantara-rag

# Check VM status
flyctl status --app nuzantara-rag

# View releases history
flyctl releases list --app nuzantara-rag

# Check secrets (names only)
flyctl secrets list --app nuzantara-rag

# Monitor real-time metrics
flyctl metrics --app nuzantara-rag
```

### Getting Help

1. **Check logs**: `flyctl logs --app APP_NAME`
2. **GitHub Issues**: Create an issue with deployment logs
3. **Fly.io Community**: https://community.fly.io/
4. **Documentation**: https://fly.io/docs/

## 📚 Additional Resources

- [Fly.io Documentation](https://fly.io/docs/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Nuzantara README](../README.md)

## 🔐 Security Best Practices

1. **Never commit secrets**: Use GitHub Secrets and Fly.io Secrets
2. **Rotate secrets regularly**: Update API keys every 90 days
3. **Use least privilege**: Grant minimum required permissions
4. **Enable 2FA**: On GitHub and Fly.io accounts
5. **Monitor logs**: Regularly review deployment and application logs
6. **Scan for vulnerabilities**: Run `npm audit` and `safety check`

## 📝 Deployment Checklist

Before deploying to production:

- [ ] All tests pass locally
- [ ] Code reviewed and approved
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Backup created
- [ ] Monitoring configured
- [ ] Rollback plan documented
- [ ] Team notified of deployment
- [ ] Health checks passing
- [ ] Documentation updated

---

**Last Updated**: 2025-12-28  
**Version**: 1.0.0
