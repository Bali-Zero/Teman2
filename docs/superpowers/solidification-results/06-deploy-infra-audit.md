# SOLIDIFICATION 06 — Deploy & Infrastructure Audit

**Date:** 2026-04-06
**Component:** Fly.io, Dockerfile, CI/CD, backup, monitoring

## Findings: 1 CRITICAL, 3 HIGH, 6 MEDIUM, 5 LOW

## Fixes Applied (11)

| Fix | Severity | What |
|-----|----------|------|
| F1 | CRITICAL | Removed hardcoded DB password + Tigris credentials from fly-pg-backup.sh |
| F2 | HIGH | Removed nodejs/npm from Dockerfile (Python-only image, -70MB) |
| F5 | MEDIUM | rag process: `::` → `0.0.0.0` for consistent host binding |
| F6 | MEDIUM | kill_timeout: 30s → 60s (prevents killing in-flight RAG requests) |
| F10 | MEDIUM | intel-router-tests: removed `|| echo` test failure swallowing |
| F11 | LOW | docker-compose: fixed module path `app.main_cloud` → `backend.app.main_cloud` |
| F12 | LOW | docker-compose.test: pinned Qdrant `latest` → `v1.17.0` |
| F13 | LOW | monitoring compose: Grafana password hardcoded → env var |
| F14 | LOW | .dockerignore: removed fly.toml from Docker image |
| F15 | LOW | sonarqube.yml: fixed `--cov=src` → `--cov=backend` |

## Manual Actions Required

```bash
# Set backup credentials as env vars on Air (add to ~/.zshrc.secrets)
export AWS_ACCESS_KEY_ID="tid_..."  # from Tigris
export AWS_SECRET_ACCESS_KEY="tsec_..."
export FLY_PG_PASSWORD="..."  # current DB password

# Rotate Tigris credentials if repo has remote history
fly storage credentials rotate -a nuzantara-rag
```

## Deferred
- F3: training-data/ COPY in Dockerfile (needs decision: remove or unignore)
- F4: Migration job CI ordering (needs release_command re-enablement)
- F7: fly-health-check.sh creation (needs scripting)
- F8: CI requirements-prod.txt alignment
- F9: .secrets.baseline generation
