# SOLIDIFICATION 02 — App Bootstrap & Initialization Audit & Plan

**Date:** 2026-04-06
**Machine:** Pro (Opus 4.6 MAX)
**Component:** App Bootstrap (`backend/app/setup/`, `dependencies.py`, `fly.toml`)
**Scope:** ~8 files, boot layer imported by 90+ routers

---

## VALUTAZIONE CRITICA DEI FINDINGS

### ACCETTATI

| # | Finding | Severity | Azione |
|---|---------|----------|--------|
| F2 | Background init crash is silent — RuntimeError from _init_critical_services propagates as unhandled task exception, Fly.io never marks unhealthy | CRITICAL | Fix: catch in _background_init, set startup_failed flag, /health/ready returns 503 |
| F3 | rag process has NO Fly.io health check in fly.toml [[services]] block | CRITICAL | Fix: add [[services.http_checks]] to fly.toml |
| F4 | Qdrant down at boot registers DEGRADED not UNAVAILABLE — fail-fast doesn't fire | CRITICAL | Fix: change to UNAVAILABLE when Qdrant probe fails |
| F5 | Shutdown may exceed kill_timeout=30s (14 _safe_stop at 5s each = 70s worst case) | HIGH | Fix: reduce SHUTDOWN_TIMEOUT to 2s, parallel where safe |
| F6 | initialize_services_light() missing SSL stripping from DATABASE_URL | HIGH | Fix: extract DSN cleanup helper, share between light and full |
| F8 | get_qdrant_stats() early return inside for loop — only counts first collection | HIGH | Fix: move return outside loop |
| F10 | configure_logging() called twice → duplicate log handlers | MEDIUM | Fix: add _logging_configured guard |

### RIFIUTATI

| # | Finding | Motivazione |
|---|---------|-------------|
| F1 | Dockerfile CMD vs fly.toml mismatch | Non è un bug — Dockerfile CMD è fallback per local dev. fly.toml process split è autoritativo per Fly.io. Aggiungere commento nel Dockerfile è sufficiente, non un fix. |
| F7 | _agentic_rag_orchestrator has no close() in shutdown | L'orchestrator non tiene httpx client direttamente — delega a LLMGateway/SearchService che hanno già close(). Aggiungere un close() sarebbe dead code. |
| F9 | team_members registered in light but not monolith | La divergenza è intenzionale: monolith è legacy, api process è production. Il monolith non serve più. |
| F11 | Retry logic doesn't handle socket.gaierror | _is_transient_error() matcha "connection" nella string, copre DNS. Rischio reale zero. |
| F12 | rag_proxy body buffering per file upload | I file upload vanno al /api/upload router che è nel rag process direttamente, non attraverso il proxy. Proxy serve solo query RAG. |

---

## PIANO DI SOLIDIFICAZIONE

### Sprint 1 — Fix Critici (effort ~2h)

| ID | Task | File | Effort | Rischio |
|----|------|------|--------|---------|
| F2 | Catch RuntimeError in _background_init, set startup_failed, /health/ready → 503 | app_factory.py, health.py | M | BASSO |
| F3 | Add health check to rag process in fly.toml | fly.toml | S | BASSO |
| F4 | Qdrant probe fail → UNAVAILABLE (not DEGRADED) | service_initializer.py | S | MEDIO — potrebbe bloccare boot se Qdrant slow |
| F8 | Fix early return in get_qdrant_stats() | health.py | S | ZERO |

### Sprint 2 — Irrobustimento (effort ~2h)

| ID | Task | File | Effort | Rischio |
|----|------|------|--------|---------|
| F5 | Reduce SHUTDOWN_TIMEOUT to 2s | app_factory.py | S | BASSO |
| F6 | Extract DSN cleanup helper for light init | service_initializer.py | M | BASSO |
| F10 | Add _logging_configured guard | app_factory.py or logging_config.py | S | ZERO |

---

## METRICHE

| Metrica | Baseline | Target |
|---------|----------|--------|
| rag health check | NONE | ogni 30s |
| Silent init failure detection | 0% | 100% |
| Qdrant-down detection at boot | MISS | fail-fast |
| Shutdown time worst case | ~70s | <25s |
