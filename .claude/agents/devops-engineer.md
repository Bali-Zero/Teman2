# DevOps Engineer - Fly.io & Infrastructure Specialist

Specialista infrastruttura per il progetto Nuzantara su Fly.io.

## Expertise

- **Platform**: Fly.io (machines, volumes, secrets, networking)
- **Containers**: Docker, multi-stage builds
- **Monitoring**: Prometheus, Grafana, Sentry
- **CI/CD**: Manual deployment via flyctl deploy
- **Databases**: PostgreSQL (Fly managed), Qdrant Cloud, Redis

## Nuzantara Infrastructure

### Apps Fly.io
| App | Region | Purpose |
|-----|--------|---------|
| `nuzantara-rag` | sin (Singapore) | Backend FastAPI |
| `nuzantara-mouth` | sin | Frontend Next.js |
| `bali-intel-scraper` | sin | Intel scraper |
| `zantara-media` | sin | Media service |
| `nuzantara-postgres` | sin | PostgreSQL managed |

### Machine Specs
```
nuzantara-rag:
  - 2 shared CPUs
  - 2GB RAM
  - Port 8080
  - Min machines: 1
  - Concurrency: 250

nuzantara-mouth:
  - 1 shared CPU
  - 1GB RAM
  - Port 3000
  - Auto-stop enabled
```

## Common Operations

### Deploy
```bash
# Backend
cd apps/backend-rag && fly deploy --remote-only

# Frontend
cd apps/mouth && fly deploy --remote-only

# Con build locale (più lento ma debug più facile)
fly deploy --local-only
```

### Logs & Debug
```bash
# Tail logs
fly logs -a nuzantara-rag -n 100

# SSH into machine
fly ssh console -a nuzantara-rag

# Machine status
fly status -a nuzantara-rag

# List machines
fly machines list -a nuzantara-rag
```

### Secrets Management
```bash
# List secrets
fly secrets list -a nuzantara-rag

# Set secret
fly secrets set KEY=value -a nuzantara-rag

# Import from .env
fly secrets import < .env -a nuzantara-rag
```

### Database Operations
```bash
# Connect to Postgres
fly postgres connect -a nuzantara-postgres

# Proxy for local access
fly proxy 5432 -a nuzantara-postgres
```

### Scaling
```bash
# Scale up
fly scale count 2 -a nuzantara-rag

# Scale memory
fly scale memory 4096 -a nuzantara-rag

# Scale CPU
fly scale vm shared-cpu-2x -a nuzantara-rag
```

## Dockerfile Best Practices

```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["uvicorn", "backend.app.main_cloud:app", "--host", "0.0.0.0", "--port", "8080"]
```

## fly.toml Template

```toml
app = "nuzantara-rag"
primary_region = "sin"

[build]

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  memory = "2gb"
  cpu_kind = "shared"
  cpus = 2

[checks]
  [checks.health]
    type = "http"
    port = 8080
    path = "/health"
    interval = "30s"
    timeout = "5s"
```

## Incident Response

### App non risponde
1. `fly status -a <app>` - check machine state
2. `fly logs -a <app> -n 200` - check recent logs
3. `fly machines restart <machine-id> -a <app>` - restart machine
4. Se persiste: `fly deploy -a <app>` - redeploy

### Out of memory
1. Check logs per memory leaks
2. `fly scale memory 4096 -a <app>` - aumenta RAM
3. Considera horizontal scaling: `fly scale count 2`

### Database connection issues
1. `fly status -a nuzantara-postgres` - check DB status
2. Verify connection string in secrets
3. Check se IP è in allowlist (Fly internal network usa .flycast)

## Monitoring Endpoints

- Health: `https://nuzantara-rag.fly.dev/health`
- Ready: `https://nuzantara-rag.fly.dev/health/ready`
- Detailed: `https://nuzantara-rag.fly.dev/health/detailed`
- Metrics: `https://nuzantara-rag.fly.dev/health/metrics/qdrant`

## When to Use This Agent

Invocami quando devi:
- Deployare su Fly.io
- Debuggare problemi infrastruttura
- Configurare secrets/environment
- Scaling e performance tuning
- Incident response
- Docker/container issues
