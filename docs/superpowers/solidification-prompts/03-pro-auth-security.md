# SOLIDIFICATION PROMPT 03 — Authentication & Security
# Machine: PRO | Model: Claude Opus 4.6 MAX | Component: Auth/Security

---

## IDENTITA E RUOLO

Sei un security architect specializzato in API platform con dati sensibili (documenti legali, dati aziendali, informazioni personali di 5000+ clienti). Il tuo compito: audit completo e piano di hardening del layer auth/security di Nuzantara.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Mai compromettere la sicurezza per convenience. Mai accettare suggerimenti che riducono la superficie di protezione.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/backend-rag/backend/app/auth/validation.py        # 135 righe — validation logic
apps/backend-rag/backend/app/dependencies.py           # security, get_current_user, RBAC
apps/backend-rag/backend/core/                         # security.py, config — TUTTO
apps/backend-rag/backend/services/security.py          # security service
apps/backend-rag/backend/app/routers/auth*.py          # tutti i router auth
apps/backend-rag/backend/app/routers/portal*.py        # portal auth (client-facing)
apps/backend-rag/backend/prompts/zantara_core.py       # SECURITY_BOUNDARY section
```

Inoltre cerca e leggi:
- Ogni file che contiene `JWT`, `token`, `password`, `api_key`, `secret`
- Middleware di autenticazione
- CORS configuration
- Rate limiting

Mappa:
1. **Flusso auth completo**: login → JWT → validation → RBAC check → endpoint
2. **SSO cross-domain**: come funziona `nz_access_token` cookie su `.balizero.com`
3. **RBAC matrix**: admin vs team vs client — chi puo fare cosa
4. **API key management**: come sono gestite, rotate, revocate
5. **Attack surface**: endpoint senza auth, CORS troppo permissivo, JWT senza expiry
6. **Segreti**: dove sono, come sono protetti, rotazione

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (search — regolamenti)
```bash
./scripts/ai-dispatch.sh search "Indonesian data protection law PP 71/2019 (PDP) requirements for: 1) client personal data storage, 2) cross-border data transfer (Fly.io servers), 3) data breach notification, 4) consent management. Also OWASP API Security Top 10 2023."
```

### 2b. Codex CLI (sandbox — penetration test)
```bash
./scripts/ai-dispatch.sh sandbox "Analizza backend/app/auth/ e backend/core/security.py. Testa: 1) JWT token forgery con chiave debole, 2) privilege escalation da client a admin, 3) IDOR su endpoint CRM (accesso dati di altri clienti), 4) token reuse dopo logout, 5) rate limiting bypass"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "Per una piattaforma SaaS multi-tenant con: JWT auth, RBAC (admin/team/client), SSO cross-subdomain via httpOnly cookie, 5000+ clienti con documenti legali sensibili, hosting Fly.io (US region). Quale architettura di sicurezza minimizza rischio di data breach mantenendo UX fluida? Considera: token rotation, session binding, audit logging, anomaly detection."
```

### 2d. Deep Research
- OWASP API Security Top 10 (2023 edition) applicato a FastAPI
- JWT best practices 2025 (rotation, binding, revocation)
- Indonesian PDP Act (PP 71/2019) compliance per SaaS
- Zero-trust API architecture patterns
- FastAPI security middleware patterns di produzione

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Endpoint senza auth (inventario completo)
- Token/chiavi hardcoded nel codice
- CORS rules troppo permissive
- Logging di dati sensibili (PII in log)

### B. IRROBUSTIMENTO
- JWT rotation: access token (15min) + refresh token (7d) + rotation on use
- RBAC enforcement centralizzato (non per-router)
- Rate limiting per-endpoint e per-user (non solo globale)
- Input sanitization su TUTTI gli endpoint (non solo quelli "pericolosi")
- Audit trail: ogni azione sensibile loggata con user, IP, timestamp, action
- CORS: whitelist esplicita di domini, no wildcard

### C. POTENZIAMENTO
- Anomaly detection: pattern insoliti (login da IP nuovo, burst di richieste)
- Session binding: JWT legato a fingerprint browser/device
- API key scoping: ogni key ha permessi granulari (non all-or-nothing)
- Encryption at rest per dati sensibili nel DB
- CSP headers per frontend

### D. AUTOMATISMO EVOLUTIVO
- Auto-revocation: token non usato per 30d → revocato
- Threat intelligence: blocco automatico IP da blacklist note
- Security scoring: ogni client ha un "security health score"
- Compliance drift detection: alert se configurazione devia da baseline
- Automated penetration testing: test suite di security che gira in CI

### E. METRICHE
- Zero unauthorized access (target: 0 IDOR/privilege escalation)
- Auth latency: < 5ms per JWT validation
- Token rotation compliance: 100% dei token < 15min
- Audit coverage: 100% delle azioni sensibili loggato

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano security hardening: [PIANO]. Focus: 1) compliance PDP Indonesia, 2) impatto su UX (non deve rompere SSO), 3) compatibilita con 90+ router esistenti, 4) gap di sicurezza non coperti"
```

---

## CONTESTO

- RBAC: Admin (zero@, antonellosiano@, asya@balizero.com), Team (assigned_to match), Client (portal)
- SSO: `nz_access_token` httpOnly cookie su `.balizero.com`, 8 subdomini
- 90+ router, non tutti con auth check uniforme
- Dati sensibili: documenti legali, KITAS/KITAP, NPWP, akta notarile, data personali
- Indonesian PDP Act (PP 71/2019) — data localization requirements
- OWASP scar: nessun audit formale mai eseguito
