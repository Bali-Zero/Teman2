# Deployment Status - Nuzantara

**Data:** 2026-02-07  
**Status:** 🟡 IN PROGRESS

---

## Current State

### Running Containers (Original Stack)

```
✅ nuzantara-backend     (port 8080)  - UP 41 hours
✅ nuzantara-postgres    (port 5432)  - UP 41 hours
✅ nuzantara-redis       (port 6379)  - UP 41 hours
✅ nuzantara-grafana     (port 3001)  - UP 42 hours
✅ nuzantara-qdrant      (port 6333)  - UP 42 hours
```

### New Optimizations Ready

- ✅ Backend code optimized (Rate Limiting, Brotli, Query Cache)
- ✅ Frontend code optimized (React Query, Loading/Error states)
- ✅ Database migration ready
- ✅ Dockerfile.optimized ready
- ✅ docker-compose.production.yml ready

---

## Deployment Steps (Manual)

### Step 1: Database Migration ✅

```bash
# Backup first
PGPASSWORD=postgres pg_dump -h localhost -p 5432 -U postgres bali_intel > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migration
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres bali_intel -f apps/bali-intel-scraper/migrations/001_add_performance_indexes.sql
```

### Step 2: Backend Deploy

```bash
cd apps/bali-intel-scraper

# Build new image
docker build -f Dockerfile.optimized -t bali-intel:v2 .

# Test new container
docker run -d \
  --name bali-intel-test \
  -p 8000:8000 \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=5432 \
  -e DB_NAME=bali_intel \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  -e REDIS_HOST=host.docker.internal \
  -e REDIS_PORT=6379 \
  bali-intel:v2

# Verify
curl http://localhost:8000/health/live
```

### Step 3: Frontend Build

```bash
cd apps/mouth
npm install
npm run build
# Deploy .next folder to web server
```

### Step 4: Switch Traffic

```bash
# Stop old backend
docker stop nuzantara-backend
docker rm nuzantara-backend

# Start new backend with new compose
docker-compose -f docker-compose.production.yml up -d backend
```

---

## Quick Deploy Script

Esegui:

```bash
./deploy_docker_compose.sh
```

Oppure passi manuali:

```bash
# 1. Backup
docker-compose exec postgres pg_dump -U postgres bali_intel > backup.sql

# 2. Migration
docker-compose exec postgres psql -U postgres bali_intel -f /docker-entrypoint-initdb.d/001_add_performance_indexes.sql

# 3. Build
cd apps/bali-intel-scraper && docker build -f Dockerfile.optimized -t bali-intel:latest .

# 4. Deploy
docker-compose -f docker-compose.production.yml up -d
```

---

## Verification Checklist

- [ ] API responding on port 8000
- [ ] Rate limiting headers present (X-RateLimit-Limit)
- [ ] Brotli compression working (Content-Encoding: br)
- [ ] Database indexes created
- [ ] Frontend build successful
- [ ] React Query hooks working
- [ ] All health checks passing

---

## Rollback

If issues:

```bash
# Stop new containers
docker-compose -f docker-compose.production.yml down

# Restore old backend
docker start nuzantara-backend

# Restore database if needed
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres bali_intel < backup.sql
```

---

## Scripts Created

1. `deploy_production.sh` - Full deployment with backup/rollback
2. `deploy_docker_compose.sh` - Docker compose based deployment
3. `rollback_production.sh` - Emergency rollback
4. `docker-compose.production.yml` - Production compose configuration

---

**Next Action:** Run `./deploy_docker_compose.sh` or follow manual steps above.
