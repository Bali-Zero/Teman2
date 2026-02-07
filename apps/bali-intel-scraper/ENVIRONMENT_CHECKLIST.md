# Pre-Deployment Checklist

## Required Environment Variables

Create a `.env` file in the project root with the following:

```bash
# Database Configuration
DB_PASSWORD=your_secure_password_here

# Redis Configuration (optional)
REDIS_PASSWORD=

# AI Service API Keys (REQUIRED)
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Monitoring (optional)
SENTRY_DSN=https://xxx@yyy.ingest.sentry.io/zzz
GRAFANA_PASSWORD=admin

# Application Settings
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO
```

## Prerequisites

- [ ] Docker 20.10+ installed
- [ ] Docker Compose 2.0+ installed
- [ ] At least 4GB RAM available
- [ ] At least 10GB disk space
- [ ] Ports 80, 443, 8000, 3000, 9090 available

## Deployment Steps

1. **Clone/Copy the project**

   ```bash
   cd apps/bali-intel-scraper
   ```

2. **Create environment file**

   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Run deployment**

   ```bash
   ./scripts/deploy.sh deploy
   ```

4. **Verify deployment**
   - Health check: http://localhost:8000/health/live
   - API docs: http://localhost:8000/docs
   - Grafana: http://localhost:3000
   - Prometheus: http://localhost:9090

## Post-Deployment

- [ ] API responds to health checks
- [ ] Database migrations applied
- [ ] Redis connection successful
- [ ] Grafana dashboards loaded
- [ ] No critical alerts in Prometheus

## Troubleshooting

If deployment fails:

1. Check logs: `docker-compose logs -f`
2. Verify environment variables: `cat .env`
3. Check disk space: `df -h`
4. Check memory: `free -h`
5. Restart services: `docker-compose restart`
