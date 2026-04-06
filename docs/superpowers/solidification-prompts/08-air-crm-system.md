# SOLIDIFICATION PROMPT 08 — CRM System
# Machine: AIR | Model: Claude Opus 4.6 MAX | Component: CRM System

---

## IDENTITA E RUOLO

Sei un architetto CRM per sistemi di produzione con 5000+ clienti. Analizzi il CRM di Nuzantara — client lifecycle, practice management, journey orchestration, compliance tracking, document management. Il CRM e il cuore del business: errori qui impattano clienti reali e revenue.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Non semplificare dove la complessita e necessaria (compliance, audit trail). Non aggiungere complessita dove il business non la richiede.

**NOTA MACCHINA:** Sei su Air. Venv e `venv`. Path: `~/Projects/nuzantara/apps/backend-rag/`.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/backend-rag/backend/services/crm/                 # 6,341 righe, 20+ file
  enhanced_crm_service.py                              # Main CRM operations
  process_automation_service.py                        # Workflow automation
  ai_crm_extractor.py                                  # AI data extraction
  lead_assignment_agent.py                             # Lead routing
  practice_status_listener.py                          # Practice lifecycle (PG LISTEN/NOTIFY)
  stale_practice_notifier.py                           # Inactive practice alerts
  document_categorizer.py                              # Doc classification
  enrichment.py                                        # Data enrichment
  cache_manager.py, cache_query.py                     # Caching
  query_optimizer.py                                   # DB query optimization
  validators.py                                        # Data validation
  welcome/welcome_practice_service.py                  # Welcome workflows

apps/backend-rag/backend/app/routers/crm*.py           # CRM router
apps/backend-rag/backend/app/routers/portal*.py        # Portal (client-facing)
apps/backend-rag/backend/app/routers/practices*.py     # Practices
apps/backend-rag/backend/app/routers/journey*.py       # Journeys
apps/backend-rag/backend/app/routers/compliance*.py    # Compliance
```

Mappa:
1. **Client lifecycle**: creazione → onboarding → active → compliance → renewal
2. **Practice states**: quali stati esistono, transizioni valide, chi puo cambiare stato
3. **Journey engine**: come funziona step-by-step, cosa succede se un step fallisce
4. **Compliance tracking**: deadline, alert multi-livello, escalation
5. **RBAC enforcement**: admin vs team vs client — ogni endpoint e protetto?
6. **Data flow**: CRM → Portal → Channel (notifiche) → risposta client
7. **Cache strategy**: cosa viene cached, invalidation corretta?
8. **AI integration**: dove il CRM usa AI (extractor, lead assignment, categorizer)

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza il CRM in backend/services/crm/. Focus: 1) stati della practice — state machine esplicita o implicita?, 2) RBAC su ogni endpoint CRM — ci sono buchi?, 3) cache invalidation — quando il client cambia, tutti i cache si invalidano?, 4) AI extractor — quando fallisce, cosa succede al workflow?, 5) lead_assignment_agent — logica di routing e testata?"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Testa il CRM: 1) crea un client con dati minimi — validazione funziona?, 2) transizione practice da stato A a stato C (skip B) — e permesso?, 3) journey con step che fallisce — il journey si blocca o continua?, 4) compliance alert — cosa succede con scadenza gia passata?, 5) cache invalidation — modifica client e verifica che la lista clienti rifletta il cambiamento"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "CRM per servizi legali/visa con: practice management (stati multipli), journey engine (multi-step), compliance tracking (scadenze legali), 5000+ clienti. Domande: 1) State machine esplicita con transizioni validate vs implicita — quale approccio per un CRM che gestisce visa/company? 2) Come gestire compliance deadlines che cambiano retroattivamente (nuova legge)? 3) Pattern per audit trail che non impatta performance? 4) Come prevenire race condition quando due team member modificano lo stesso client?"
```

### 2d. Deep Research
- CRM state machine patterns for legal/immigration services
- Practice management systems architecture
- Compliance tracking with multi-level alerts
- Audit trail patterns per GDPR/PDP compliance
- Cache invalidation strategies for CRM data

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- State machine esplicita per Practice (se oggi e implicita)
- Rimuovere logica duplicata tra enhanced_crm_service e altri servizi
- Unificare pattern di validazione (validators.py usato ovunque?)
- Cleanup assigned_to='company_extract_import' (residuo bulk import)

### B. IRROBUSTIMENTO
- Practice state machine: transizioni validate, no skip di stati
- Optimistic locking: versioning su client/practice per prevenire race condition
- Audit trail: ogni modifica a client/practice loggata con chi, quando, cosa
- Compliance: deadline tracking con buffer (alert 90d, 60d, 30d, 7d, 1d prima)
- RBAC: enforce su OGNI endpoint, non solo quelli "importanti"
- Input validation: schema validation su tutti gli input CRM

### C. POTENZIAMENTO
- Client health score: aggregato da compliance, document completeness, payment status
- Predictive analytics: predici quali clienti avranno problemi di compliance
- Batch operations: operazioni su gruppi di clienti (es. rinnovi in blocco)
- Client timeline: vista unificata di tutte le interazioni/documenti/pratiche
- Smart assignment: lead routing basato su carico di lavoro team + specializzazione

### D. AUTOMATISMO EVOLUTIVO
- Auto-escalation: se un team member non agisce su una pratica per X giorni → escalation
- Compliance auto-check: cron che verifica scadenze e genera alert automaticamente
- Document completeness checker: identifica documenti mancanti per tipo di pratica
- Stale practice auto-notification: notifica automatica clienti con pratiche ferme
- Client journey optimization: analizza quale journey ha piu successo e suggerisce miglioramenti

### E. METRICHE
- Practice resolution time: target per tipo di pratica
- Compliance on-time rate: > 95%
- Data completeness: > 90% dei campi client compilati
- RBAC coverage: 100% degli endpoint protetti
- Cache hit rate: > 80% per liste clienti

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione CRM: [PIANO]. Focus: 1) impatto su 5000+ clienti esistenti, 2) compliance con normativa indonesiana, 3) compatibilita con portal client, 4) rischi nella state machine migration"
```

---

## CONTESTO

- 5000+ clienti, ~2070 companies, ~1803 company_docs
- Kill switch visa notifier: `system_settings.visa_expiry_notifier_enabled`
- Notifier LIVE: alert via Telegram a team member assegnati
- Practice types: visa (KITAS/KITAP/etc), company setup, tax, property
- Portal: client-facing dashboard su my.balizero.com
- SSO: nz_access_token cookie cross-domain
- RBAC: Admin (3 users), Team, Client
- Scar: `_current_user` prefix = cosmetic, NOT enforcing
- Cache namespaces: zantara:crm_clients_stats:*, zantara:crm_practices:*
