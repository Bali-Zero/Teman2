# Nuzantara Service Level Objectives (SLO)

**Last Updated:** 2026-04-06
**Review Cadence:** Monthly

## Availability

| Service | Target | Measurement | Allowed Downtime/Year |
|---------|--------|-------------|----------------------|
| Backend API (nuzantara-rag) | 99.5% | Fly.io health checks (30s interval) + fly-health-check.sh (30min cron) | 43h 48min |
| Frontend (Vercel) | 99.9% | Vercel status page | 8h 46min |
| Database (PostgreSQL) | 99.5% | fly status checks | 43h 48min |
| Vector DB (Qdrant Cloud) | 99.5% | /healthz API check (fly-health-check.sh) | 43h 48min |
| Redis | 99.0% | TCP check (fly-health-check.sh) | 87h 36min |

## Latency

| Endpoint | p50 Target | p95 Target | p99 Target |
|----------|-----------|-----------|-----------|
| /health | <100ms | <500ms | <1s |
| /api/chat (RAG query) | <2s | <5s | <10s |
| /api/kbli/* | <500ms | <1s | <2s |
| /api/crm/* | <300ms | <1s | <2s |
| Frontend page load (kita.balizero.com) | <2s | <4s | <8s |

## Recovery

| Metric | Target | Current | Notes |
|--------|--------|---------|-------|
| MTTR (Mean Time To Recovery) | <15min | ~15-30min | Auto-rollback in CI + auto-restart in health script |
| Backup RTO (PostgreSQL) | <1h | Untested | Daily pg_dump to Tigris, restore verify added (B2) |
| Backup RTO (Qdrant) | <2h | Untested | Daily snapshot to Tigris |
| Backup RPO (data loss window) | <24h | 24h | Daily backups at 03:00 WITA |

## Deploy

| Metric | Target | Current |
|--------|--------|---------|
| Deploy frequency | >=1/day | ~2-3/week |
| Deploy success rate | >95% | ~95% (auto-rollback catches failures) |
| Rollback time | <5min | ~2min (automatic via fly-deploy.yml) |
| Pre-deploy gate time | <5min | ~3min (82 core tests + lint + import chain) |

## Error Budget

With 99.5% availability target:
- **Monthly budget:** 3h 39min downtime
- **Weekly budget:** ~50min downtime
- **If budget exhausted:** freeze non-critical deploys, focus on reliability

## Monitoring Stack

| What | How | Alert Channel | Frequency |
|------|-----|---------------|-----------|
| Backend health | fly-health-check.sh | Telegram | */30min 24h |
| Deploy status | fly-deploy.yml post-deploy-health | Telegram | Every deploy |
| Backup status | fly-pg-backup.sh + fly-qdrant-backup.sh | Telegram | Daily 03:00 |
| RAG quality | rag_canary.py | Telegram | */6h |
| SSL expiry | system_doctor.py | Telegram | Daily 08:00 |
| Cost | fly-cost-alert.sh | Telegram | Weekly Monday |
| Dependencies | Dependabot | GitHub PRs | Weekly Monday |
| Security | Snyk + CodeQL + Bandit | GitHub | Every PR + weekly |

## Budget Constraint

Infrastructure budget: **$40-60/month**. SLO targets are calibrated for this budget.

| Upgrade | Trigger | Cost Impact |
|---------|---------|-------------|
| Multi-region | Revenue >$5K/mo or SLA contract | +$35/mo |
| Dedicated CPU | p95 >3s or memory >80% sustained | +$20-40/mo |
| Higher availability (99.9%) | >10K clients or SLA contract | Requires multi-region |
