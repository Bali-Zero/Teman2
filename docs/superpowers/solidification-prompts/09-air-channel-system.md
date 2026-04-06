# SOLIDIFICATION PROMPT 09 — Channel System
# Machine: AIR | Model: Claude Opus 4.6 MAX | Component: Channel System

---

## IDENTITA E RUOLO

Sei un architetto di sistemi di comunicazione multi-canale. Analizzi i 5 canali di Nuzantara — WhatsApp, Telegram, Instagram, Web, X/Twitter — attraverso cui 5000+ clienti comunicano con il business. Un canale giu = clienti che non ricevono risposte = revenue perso.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Non proporre unificazioni forzate se i canali hanno requisiti diversi. Ogni API esterna ha le sue regole.

**NOTA MACCHINA:** Sei su Air. Venv e `venv`. Path: `~/Projects/nuzantara/apps/backend-rag/`.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/backend-rag/backend/channels/                     # 2,317 righe totali
  twitter/adapter.py, formatter.py, config.py
  web/adapter.py, formatter.py, config.py
  telegram/adapter.py, formatter.py, config.py
  instagram/adapter.py, formatter.py, config.py
  router.py                                            # Channel routing
  optimizations.py                                     # Performance
  formatters/__init__.py                               # Base formatter

apps/backend-rag/backend/app/routers/whatsapp*.py      # WhatsApp webhook
apps/backend-rag/backend/app/routers/telegram*.py      # Telegram webhook
apps/backend-rag/backend/app/routers/instagram*.py     # Instagram webhook
apps/backend-rag/backend/app/routers/channels*.py      # Channel management
```

Cerca anche:
- WhatsApp integration (Meta Cloud API) — config, template, webhook verification
- Telegram bot config — token, webhook vs polling
- Message queue/retry pattern per delivery
- Rate limiting per canale

Mappa:
1. **Architettura adapter**: interfaccia comune tra canali? Quanto e uniforme?
2. **Message flow**: incoming → parse → normalize → RAG → format → send
3. **Delivery guarantee**: cosa succede se send fallisce? Retry? Dead letter?
4. **Rate limiting**: per canale, per utente, globale
5. **Formatter**: come si adatta la risposta RAG al formato del canale (markdown → WhatsApp, etc.)
6. **Ownership**: WhatsApp/Instagram/Web = Fly.io, Telegram = Pro OpenClaw — come coesistono?
7. **Status X/Twitter**: CRC broken — cosa significa esattamente?

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza il sistema canali in backend/channels/. Focus: 1) interfaccia adapter — tutti i canali implementano gli stessi metodi?, 2) error handling — cosa succede quando Meta API e down?, 3) message deduplication — stessa message viene processata due volte?, 4) formatter consistency — risposte RAG formattate correttamente per ogni canale?"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Testa i channel adapter: 1) simula webhook WhatsApp con payload malformato, 2) simula timeout su send Telegram, 3) verifica deduplication — stesso message_id due volte, 4) testa formatter con risposta RAG lunga (> 4096 char per Telegram, > 1024 per WhatsApp), 5) verifica che webhook verification (challenge) funzioni per WhatsApp e Instagram"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "Sistema multi-canale (WhatsApp, Telegram, Instagram, Web, X) per business services. Ownership mista: alcuni su cloud (Fly.io), Telegram su macchina locale (Pro via OpenClaw). Domande: 1) Come garantire delivery at-least-once senza message queue dedicato? 2) Pattern per graceful degradation quando un canale e down? 3) Come unificare analytics cross-channel (chi ha scritto cosa, da dove, quando)? 4) Come gestire il rate limiting di Meta API (WhatsApp 80 msg/s) senza perdere messaggi?"
```

### 2d. Deep Research
- WhatsApp Business API production patterns 2025
- Multi-channel messaging architecture patterns
- Message delivery guarantees without dedicated queue
- Channel-specific formatting best practices
- Telegram bot webhook vs polling: production trade-offs

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Unificare interfaccia adapter se incoerente
- Fix X/Twitter CRC (o rimuovere se non usato)
- Rimuovere codice morto nei formatter
- Consolidare config pattern tra canali

### B. IRROBUSTIMENTO
- Delivery retry: 3 tentativi con exponential backoff per ogni send
- Dead letter queue: messaggi non consegnabili → tabella PostgreSQL + alert
- Webhook idempotency: deduplication basata su message_id
- Rate limiting: per canale con token bucket
- Message size handling: auto-split per Telegram (4096), WhatsApp (1024)
- Webhook verification: robusto per WhatsApp e Instagram (Meta challenge)

### C. POTENZIAMENTO
- Unified inbox: vista aggregata di tutti i messaggi cross-channel
- Channel health dashboard: latenza, error rate, throughput per canale
- Smart routing: se WhatsApp e down, suggerisci canale alternativo
- Template management: template WhatsApp gestiti da DB, non hardcoded
- Rich media: supporto immagini/documenti cross-channel

### D. AUTOMATISMO EVOLUTIVO
- Channel health monitor: cron che verifica ogni canale ogni 5min
- Auto-reconnect: se webhook registration scade, auto-rinnova
- Analytics aggregation: metriche cross-channel giornaliere automatiche
- Pattern detection: identifica orari di picco per canale, ottimizza risorse
- Feedback loop: se un canale ha piu errori, riduce il rate e alert

### E. METRICHE
- Message delivery rate: > 99% per canale
- Response latency: < 5s da ricezione a risposta
- Channel uptime: > 99.5% per canale attivo
- Error rate: < 0.5% per canale
- Cross-channel consistency: stessa domanda = stessa risposta (quality check)

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione Channel System: [PIANO]. Focus: 1) compatibilita con ownership mista (Fly.io + Pro OpenClaw), 2) impatto su latenza risposta client, 3) Meta API compliance, 4) Telegram webhook vs polling trade-off"
```

---

## CONTESTO

- WhatsApp: ✅ Live, Fly.io, Gemini 3 Flash + RAG
- Telegram: ✅ Live, Pro OpenClaw (Opus 4.6 + SOUL.md), solo Pro polling
- Instagram: ✅ Live, Fly.io
- X/Twitter: ❌ CRC broken, Fly.io
- Web Chat: ✅ Live, Fly.io
- Google Chat, Slack: 🔧 Scaffold
- Air: solo sender (Telegram + WhatsApp), mai listener
- Channel formatters: markdown → canale-specifico
- Rate limits: WhatsApp 80msg/s, Telegram 30msg/s per bot, Instagram 200 call/h
