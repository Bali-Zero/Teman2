# Agent Mesh Vision — Nuzantara Team AI Infrastructure

> **Data:** 2026-04-03
> **Autore:** Claude Opus 4.6 (Air) per Zero
> **Tipo:** Documento di visione architetturale
> **Status:** Bozza per review — nessun codice di implementazione

---

## 0. Premessa: Cosa Esiste Oggi

Prima di progettare il futuro, mappiamo esattamente cosa c'è.

### Infrastruttura Attiva

```
┌──────────────────────────────────────────────────────────────────┐
│ PRO (M4 Pro, 48GB) — Il Re                                      │
│ • Claude Code (Opus 4.6, Max x20, $200/mo)                      │
│ • OpenClaw: main(Opus) + coder(Qwen27b) — Telegram listener     │
│ • ai-dispatch.sh v3: Gemini CLI, Codex, DeepSeek                │
│ • Federation orchestrator (LangGraph + Qwen 9b classifier)      │
│ • Pipeline: Intel Scraper, War Room, NLM, Evaluator             │
└──────────────┬───────────────────────────────────────────────────┘
               │ SSH + git sync (post-commit hook)
┌──────────────▼───────────────────────────────────────────────────┐
│ AIR (M4, 16GB) — Il Vicario (H24)                               │
│ • Claude Code (Opus 4.6, Max x5, $100/mo)                       │
│ • OpenClaw: main(Opus) + coder(Qwen27b) + qa-visual(Gemini)     │
│ • 12 cron job (test, sentinel, canary, drive, doctor...)         │
│ • Telegram sender only (no polling)                              │
│ • Escalation: shared/escalations.json → Pro reads               │
└──────────────┬───────────────────────────────────────────────────┘
               │ Fly.io (internet)
┌──────────────▼───────────────────────────────────────────────────┐
│ FLY.IO — 3 app                                                   │
│ • nuzantara-rag: FastAPI, 90 routers, 253 services               │
│ • nuzantara-postgres: relational DB                              │
│ • nuzantara-qdrant: 93K vectors, 10 collections                 │
│ • Channels: WhatsApp, Instagram, Web Chat (Gemini 3 Flash)      │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ MCP SERVER (131 tools, 8 chain, 10 prompt, 5 risorse)           │
│ • 8 Workflow Chains (deterministiche, no LLM):                   │
│   1. Daily Ops Autopilot (expiry→WA→agents→intel→email)          │
│   2. New Client Onboarding (CRM→KBLI→visa→Drive→plan→msg)       │
│   3. Practice Lifecycle Manager                                  │
│   4. Intel Pipeline Autopilot                                    │
│   5. Weekly Report Generator                                     │
│   6. Client Health Monitor                                       │
│   7. Compliance Autopilot                                        │
│   8. Journey Accelerator                                         │
└──────────────────────────────────────────────────────────────────┘
```

### Krisna Node — Primo Tentativo (Esiste ma Non Attivo)

```
scripts/krisna-node/
├── install.sh      — Setup Gemini CLI + MCP su Mac Krisna
├── PANDUAN-KRISNA.md — Guida in indonesiano, 60 righe
```

- Installa Gemini CLI + NuzMCP via stdio
- NESSUN Permission Gateway (accesso pieno a tutti i 131 tools)
- NESSUN audit, NESSUN scope filtering, NESSUN approval flow
- JWT hardcoded nello script di installazione
- Non risulta mai stato deployato (Krisna non usa terminale)

### The Generals — Pianificati Mai Realizzati

```
service_initializer.py:815-834 — CodingGeneral + IntelligenceGeneral
```

- Import da `backend.generals.coding_general` e `backend.generals.intelligence_general`
- Ma `apps/backend-rag/backend/generals/` NON ESISTE (directory mancante)
- Il servizio si registra come DEGRADED e fallisce silenziosamente
- Concept: polling loop background per task coding e intelligence
- **Stato: morto. Nessun file, nessun codice, nessun piano.**

### Brainstorm 25 Marzo — Riassunto Critico

Il documento `2026-03-25-team-agent-assistants-brainstorm.md` (1100+ righe, 4 modelli AI) ha prodotto un'architettura target V3 con review incrociata. I punti chiave:

- **3/3 GO** su: Hybrid A2A+MCP, Permission Gateway, Telegram UI
- **3/3 TAGLIARE**: CRDT/offline writes, Ollama come fallback primario
- **Insight ChatGPT**: "Il Gateway È il Prodotto" — il moat è permissioning+audit, non gli agent
- **Pilot Damar**: previsto, mai iniziato
- **Costo reale**: $0 infra (Gemini free + OpenClaw free), costo dominante = tempo Zero

---

## 1. Le Domande — Analisi Strutturata

### INTERAZIONE: Come i team member accedono all'agente?

I team member (Krisna, Damar, etc.) non sono developer. L'interfaccia deve essere a frizione zero.

#### Opzione A: Terminale (Gemini CLI REPL)

```
Pro:  Già pronto (install.sh esiste), $0, accesso diretto a MCP
Con:  Team NON usa il terminale — barriera fatale
      Richiede cd + gemini ogni mattina — nessuno lo farà
      Nessuna notifica push, nessun mobile
Voto: ❌ Eliminato per adoption (confermato dal brainstorm §4.8)
```

#### Opzione B: Bot Telegram Personale (un bot per team member)

```
Pro:  App GIÀ installata sui telefoni del team
      Notifiche push native, voice notes, foto documenti
      @Balizerobot esiste e funziona già
      Mobile-first (il team lavora dal telefono 80% del tempo)
      Template buttons per azioni comuni
Con:  Un solo bot condiviso (tutti vedono lo stesso @Balizerobot)
      Routing: serve mapping chat_id → ruolo → permessi
      Nessun rich UI (tabelle, grafici, form)
Voto: ✅ PRIMARIO — frizione più bassa possibile
```

#### Opzione C: WhatsApp via Baileys (il brainstorm V3 propone questo)

```
Pro:  Interfaccia più naturale di tutte (scrivono su WA ogni giorno)
      Ogni team member usa il SUO numero, il SUO telefono
      Air legge tutte le conversazioni (operator.admin)
Con:  Baileys = reverse-engineering di WA Web (non ufficiale)
      Rischio ban account (Meta ha crackdown periodici)
      QR rescan frequente se sessione cade
      Se Mac chiuso → agent offline (no H24)
      Dati client transitano su server Meta (compliance UU PDP?)
Voto: ⚠️ RISCHIOSO — vale come esperimento, non come primario
```

#### Opzione D: Web UI integrata (kita.balizero.com/assistant)

```
Pro:  Rich UI: tabelle, form, grafici, drag-drop documenti
      Integrato dove il team GIÀ lavora (kita = workspace)
      SSO esistente (nz_access_token cookie)
      RBAC già implementato nel backend
Con:  Serve sviluppo frontend (~2-3 settimane)
      Non ha notifiche push (serve PWA o web push)
      Desktop-only (non ideale per mobile)
Voto: ✅ SECONDARIO — per task complessi e dashboard
```

#### Opzione E: Command Palette (Cmd+K) nel browser

```
Pro:  Elegante, non invasivo, pattern familiare
Con:  Richiede che il team tenga kita aperto nel browser
      Non ha persistence conversazionale
      Nessuna notifica, nessun mobile
Voto: ❌ Troppo tecnico per questo team
```

**DECISIONE PROPOSTA:**

```
Primario:   Telegram @Balizerobot (1 bot, routing per chat_id)
Secondario: Web UI su kita.balizero.com/assistant (per task complessi)
Scartati:   Terminale, Cmd+K
Sperimentale: WhatsApp via Baileys (solo se Telegram insufficiente)
```

### INTERAZIONE: Come rendere l'agente "integrato" e non "un'app separata"

L'agente deve vivere dove il team member sta già lavorando. Due pattern:

**Pattern 1: Push proattivo (l'agente ti trova)**

- Mattina ore 8: summary automatico su Telegram ("3 scadenze oggi, 1 client nuovo")
- Client scrive su WA e non rispondi entro 10min: agent ti notifica su Telegram
- Compliance rate scende sotto 95%: alert + suggerimento azione

**Pattern 2: Pull naturale (tu trovi l'agente)**

- Stai su kita/clients → sidebar "Ask Zantara" context-aware ("cosa manca a questo client?")
- Stai su Telegram → scrivi al bot come scrivi a un collega

L'integrazione non è tecnica, è comportamentale. L'agente deve **interrompere** quando serve e **aspettare** quando non serve.

### INTERAZIONE: Gemini CLI non-interactive per automazioni

Gemini CLI è un REPL. Per standing orders e cron job, serve esecuzione non-interactive.

```
Opzione A: Gemini CLI --prompt "task" (se supportato)
           Pro: Nativo, semplice
           Con: Non confermato che esista questa flag

Opzione B: echo "task" | gemini (pipe stdin)
           Pro: Funziona con qualsiasi REPL
           Con: Fragile, parsing output complesso

Opzione C: NON usare Gemini CLI per automazioni
           Usare backend API + MCP tools direttamente
           Le 8 chain MCP SONO GIÀ non-interactive
           Le standing orders passano per Air cron → chain MCP
           Pro: Affidabile, già funzionante, auditabile
           Con: Gemini CLI diventa solo per uso interattivo team

DECISIONE PROPOSTA: Opzione C
  - Gemini CLI = interfaccia interattiva per team member (via terminale, se lo usano)
  - Standing orders = cron Air → chain MCP → Telegram report
  - Il "cervello" delle automazioni è il backend, non Gemini CLI
```

---

### MULTI-AGENT: Delega tra agenti

**Scenario:** L'agente di Krisna trova un caso complesso → come lo passa a Zero (Opus)?

```
OGGI (funziona già):
  Krisna scrive su Telegram → @Balizerobot (Pro OpenClaw, Opus 4.6)
  → Se Opus non sa rispondere → ABSTAIN (evidence < 0.15)
  → Risponde: "Questo caso richiede analisi di Zero, lo notifico"
  → Salva in shared/escalations.json
  → Pro legge a session start → Zero gestisce

DOMANI (con Agent Mesh):
  Krisna scrive su Telegram → routing per chat_id
  → Backend identifica: ruolo=visa_consultant, client_id=X
  → Query a NuzMCP con token RBAC di Krisna (solo read sui suoi client)
  → Se confidence < 0.15: escalation automatica
  → Crea ticket in CRM con context completo
  → Notifica Zero su Telegram con one-tap approve/reject
  → Zero approva → agent Krisna riceve istruzioni e risponde al client
```

**Differenza chiave:** oggi è manuale (shared/escalations.json), domani è automatico con context preservato.

### MULTI-AGENT: Conflitti concorrenti

**Scenario:** Due agenti modificano lo stesso client contemporaneamente.

```
SOLUZIONE: Il backend È GIÀ il single point of truth.

1. Non c'è cache locale scrivibile (decisione brainstorm: offline = read-only)
2. Ogni azione passa per il backend API (Fly.io)
3. Il backend ha locking ottimistico (updated_at check)
4. Se conflitto: secondo write fallisce → agent riprova → o escalation

Non serve CRDT. Non serve consensus distribuito.
Il database PostgreSQL su Fly.io È il lock manager.
```

### MULTI-AGENT: Air come always-on agent

Air è acceso H24. Già esegue 12 cron job. Il salto è:

```
OGGI:  Air esegue script predefiniti (drive poll, canary, sentinel)
DOMANI: Air esegue standing orders PER OGNI TEAM MEMBER

Esempio mattina:
  07:00 — chain_daily_ops_autopilot (già esiste come Chain 1)
  07:30 — Per ogni team member:
          → chain_client_health_monitor(assigned_to=krisna)
          → Genera summary personalizzato
          → Invia su Telegram a Krisna
  08:00 — chain_compliance_autopilot (già esiste come Chain 7)
          → Se compliance < 95% per qualcuno → alert individuale
```

Air non ha bisogno di un "agent" nuovo. Ha bisogno di **parametrizzare le chain esistenti per team member**.

### MULTI-AGENT: 4 nodi federation → 4 agenti?

```
OGGI: 2 nodi (Pro + Air)
BRAINSTORM: 18 Mac sudditi + 1 Air padrone + 1 Pro framework

REALTÀ:
  - Pro e Air sono già nodi federation funzionanti
  - Krisna ha uno script di setup mai usato
  - Damar non ha niente
  - Il team ha 18 persone ma non 18 Mac dedicati

PROPOSTA: NON aggiungere nodi fisici per ora
  4 nodi logici, 2 nodi fisici:

  ┌─────────────────────────────────────────────────┐
  │ PRO (fisico) — Zero's agent + framework dev     │
  │ AIR (fisico) — Standing orders + cron + H24     │
  │ KRISNA (logico) — Chat_id routing via Telegram  │
  │ DAMAR (logico) — Chat_id routing via Telegram   │
  └─────────────────────────────────────────────────┘

  Krisna e Damar NON hanno un agent locale.
  Scrivono su Telegram → routing per chat_id → backend via MCP.
  L'intelligenza è centralizzata (backend + MCP).

  Se in futuro serve autonomia locale (offline, tool calling locale):
  → Allora deploy OpenClaw + Gemini CLI sul loro Mac.
  → Ma SOLO dopo aver validato che Telegram funziona.
```

---

### STANDING ORDERS: Implementazione

#### "Ogni mattina alle 8, check i miei client e mandami summary su Telegram"

```
COME: Già quasi possibile oggi.

1. Air cron (launchd) alle 08:00 WITA
2. Invoca: chain_client_health_monitor(assigned_to="krisna@balizero.com")
   (Chain 6 già esiste, serve solo parametrizzare assigned_to)
3. Risultato → formatta come messaggio Telegram
4. Invia via @Balizerobot a chat_id di Krisna

COSA MANCA:
- Mapping team_member → telegram_chat_id (tabella messaging_users esiste ma non popolata)
- Parametro assigned_to nelle chain (alcune lo hanno, altre no)
- Template messaggio personalizzato per Telegram
- Cron job parametrico su Air (oggi le chain girano per "tutti")

STIMA: 1-2 giorni di lavoro (non settimane)
```

#### "Se un client mi scrive su WA e non rispondo entro 10 minuti, l'agente risponde per me con un ack"

```
COME: Serve modifica al channel handler WhatsApp.

1. Client scrive su WA → backend Fly.io riceve (già funziona)
2. Backend controlla: assigned_to = krisna
3. Avvia timer 10 minuti (Redis key con TTL)
4. Se Krisna risponde entro 10min → cancella timer
5. Se timer scade → agent invia ack automatico:
   "Hi [name], thanks for your message. Our consultant Krisna
    will get back to you shortly. In the meantime, is there
    anything specific I can help with?"

COSA MANCA:
- Timer logic nel WA adapter (oggi risponde subito con Gemini Flash)
- Mapping WA conversation → assigned consultant
- Fallback: se consultant non risponde in 1h → escalation a manager
- Config per-consultant: chi vuole auto-ack e chi no

RISCHIO: Client potrebbe non volere risposta da bot
MITIGAZIONE: Auto-ack solo come acknowledgment, non come risposta
            sostanziale. Sempre firmato "Zantara AI Assistant".

STIMA: 3-5 giorni (serve modifica al WA adapter + testing)
```

#### "Mantieni compliance rate dei miei clienti sopra 95% come obiettivo continuo"

```
COME: Chain 7 (Compliance Autopilot) già esiste.

1. Cron giornaliero → chain_compliance_autopilot()
2. Calcola compliance rate per assigned_to
3. Se < 95% per Krisna:
   a. Identifica client con compliance bassa
   b. Genera lista azioni (rinnovi scaduti, documenti mancanti)
   c. Invia alert su Telegram con lista prioritizzata
   d. Se azioni automatizzabili (es. reminder WA): esegue
4. Weekly trend: "Krisna: 93% → 96% (+3%)" su report settimanale

COSA MANCA:
- Compliance rate per-consultant (oggi è globale)
- Soglia configurabile per consultant
- Azioni automatiche graduate (reminder → escalation → alert manager)

STIMA: 2-3 giorni (la chain esiste, serve parametrizzazione)
```

---

### EVOLUZIONE: Chain → Skill degli agenti

```
OGGI: 8 chain = tool MCP invocabili da Claude Code
      chain_daily_ops_autopilot() = un tool tra 131

DOMANI: Le chain diventano "competenze" dell'Agent Mesh
       L'agent di ogni team member può invocare le chain
       ma SOLO quelle permesse dal suo ruolo

MAPPING:
  Chain 1 (Daily Ops)      → admin only
  Chain 2 (Client Onboard) → tutti i consultant
  Chain 3 (Practice Mgmt)  → consultant + manager
  Chain 4 (Intel Pipeline)  → admin only
  Chain 5 (Weekly Report)  → admin only
  Chain 6 (Client Health)  → ogni consultant per i SUOI client
  Chain 7 (Compliance)     → ogni consultant per i SUOI client
  Chain 8 (Journey Accel)  → consultant + manager

Le chain NON cambiano. Cambia CHI può invocarle e con quale scope.
```

### EVOLUZIONE: The Generals → Assorbiti

```
The Generals (CodingGeneral, IntelligenceGeneral) non esistono.
Il directory backend/generals/ non è mai stato creato.
service_initializer.py importa e fallisce silenziosamente.

PROPOSTA: Non implementarli. Il loro concept è assorbito da:
  - CodingGeneral → Core Guardian V3 (già funzionante, gira ogni 3h)
  - IntelligenceGeneral → Intel Pipeline (Chain 4) + War Room

Rimuovere il codice morto da service_initializer.py:800-838.
```

### EVOLUZIONE: Scalabilità

```
Aggiungere un nuovo team member:

1. Creare utente nel CRM (email + ruolo)
2. Ottenere telegram_chat_id (team member scrive /start a @Balizerobot)
3. INSERT INTO messaging_users (user_id, telegram_chat_id, channel)
4. Definire role_permissions (quali tool può usare)
5. Aggiungere al cron di Air per standing orders personalizzati

TEMPO: ~15 minuti di setup. Zero codice nuovo.

Se serve agent locale (futuro):
  → scripts/install-node.sh con parametri (nome, email, ruolo)
  → Template install.sh di Krisna generalizzato
  → TEMPO: ~30 minuti + setup Mac
```

### EVOLUZIONE: Rischio Maggiore

```
RISCHIO #1: COMPLESSITÀ PREMATURA

Il brainstorm del 25 marzo ha 1100 righe.
L'architettura V3 prevede 18 Mac con OpenClaw, Baileys, Redis Registry,
Permission Gateway, SQLCipher, mDNS, leader election.

Ma il team ha 18 persone e ZERO di loro usa un agent oggi.

Il rischio non è tecnico. È di costruire un'infrastruttura sofisticata
che nessuno usa. Il 90% del valore viene dal 10% più semplice:
  → Telegram bot che risponde a domande sui propri client
  → Summary mattutino automatico
  → Alert scadenze

MITIGAZIONE: Costruire il minimo, validare l'uso, poi espandere.
Non costruire il Permission Gateway prima di avere un utente.

RISCHIO #2: SINGLE POINT OF FAILURE (Air)

Se Air va giù → niente standing orders, niente cron, niente monitoring.
Air è un MacBook Air M4, non un server.

MITIGAZIONE:
  - Fly.io backend può eseguire le stesse chain (non dipende da Air)
  - Telegram alert se Air heartbeat manca
  - Standing orders critiche duplicate su Fly.io cron
```

---

## 2. Architettura Target

### Diagramma — Agent Mesh V1 (Minimo Vitale)

```
                    ┌─────────────────────────────┐
                    │       TELEGRAM               │
                    │    @Balizerobot              │
                    │  (1 bot, routing per         │
                    │   chat_id → ruolo)           │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  ROUTING LAYER (nuovo)       │
                    │                              │
                    │  chat_id → team_member       │
                    │  team_member → ruolo         │
                    │  ruolo → tool_permissions    │
                    │  ruolo → client_scope        │
                    │                              │
                    │  Dove: backend Fly.io        │
                    │  (router telegram esistente  │
                    │   + permission middleware)    │
                    └──────────┬──────────────────┘
                               │
          ┌────────────────────┼─────────────────────┐
          │                    │                      │
  ┌───────▼──────┐   ┌───────▼──────┐    ┌─────────▼────────┐
  │ NuzMCP       │   │ Backend API  │    │ Knowledge        │
  │ (131 tools   │   │ (90 routers) │    │ (Qdrant + KG)    │
  │  RBAC-filtered│  │              │    │                  │
  │  per ruolo)  │   │              │    │                  │
  └──────────────┘   └──────────────┘    └──────────────────┘

                    ┌─────────────────────────────┐
                    │  AIR (H24)                   │
                    │                              │
                    │  Cron standing orders:        │
                    │  • 07:30 health per member    │
                    │  • Chain 7 compliance daily   │
                    │  • Weekly report venerdì      │
                    │                              │
                    │  Risultati → Telegram per     │
                    │  ogni team member             │
                    └─────────────────────────────┘

                    ┌─────────────────────────────┐
                    │  PRO (dev)                   │
                    │                              │
                    │  • Sviluppo Permission Layer │
                    │  • Monitoring & debugging    │
                    │  • Escalation handling       │
                    │  • Model refinement          │
                    └─────────────────────────────┘
```

### Differenze con Brainstorm V3

| Brainstorm V3 (marzo)              | Agent Mesh V1 (proposta)             | Perché                          |
| ---------------------------------- | ------------------------------------ | ------------------------------- |
| 18 Mac con OpenClaw + Gemini CLI   | 0 Mac nuovi, routing Telegram        | Validare prima di scalare       |
| Baileys WhatsApp per-member        | @Balizerobot Telegram condiviso      | Meno rischio ban, già funziona  |
| Permission Gateway (FastAPI :8090) | Permission middleware nel backend    | Meno infra, stessa sicurezza    |
| Redis Service Registry (Upstash)   | Nessun service registry              | Non servono nodi da scoprire    |
| SQLCipher + offline cache          | Zero offline (tutto server-side)     | Team è sempre online in ufficio |
| A2A Protocol inter-agent           | Nessun A2A (1 backend centralizzato) | Un solo cervello, non tanti     |
| mDNS / Bonjour discovery           | Nessun discovery                     | Nessun nodo da scoprire         |

**Principio guida:** Ogni componente del brainstorm V3 è un'opzione futura,
non un requisito V1. Se Telegram + chain parametrizzate copre l'80% del valore,
non costruiamo il 100% dell'infrastruttura.

---

## 3. Decisioni da Prendere

### D1: Routing Telegram — 1 Bot vs N Bot

**Opzione A: 1 bot (@Balizerobot), routing per chat_id**

```
Pro:  Zero setup aggiuntivo, bot già live
      Routing: tabella chat_id → team_member → permissions
Con:  Tutti usano lo stesso bot (confusione?)
      Se bot down → tutti offline
```

**Opzione B: N bot (1 per team member)**

```
Pro:  Isolamento totale, UX più chiara
      Se un bot cade, gli altri funzionano
Con:  Serve creare 18 bot su BotFather
      18 token da gestire, 18 webhook/polling
      Infra complicata
```

**Raccomandazione:** Opzione A. Un bot, routing per chat_id. Se nasce confusione,
migrare a B è facile (lo stesso backend risponde a N token).

### D2: Dove Vive il Permission Layer

**Opzione A: Middleware nel backend FastAPI (preferita)**

```
Pro:  Zero infra nuova, RBAC CRM già esiste
      Stessa codebase, stesso deploy
Con:  Accoppiato al backend (se cambi backend, perdi permissions)
```

**Opzione B: Gateway separato (FastAPI :8090)**

```
Pro:  Decoupled, testabile indipendentemente
      "Il Gateway È il Prodotto" (insight ChatGPT)
Con:  Ancora un servizio da hostare, mantenere, monitorare
      Overhead di rete per ogni call
```

**Raccomandazione:** Opzione A per V1. Il backend ha già `hybrid_auth.py` e RBAC.
Aggiungere un decorator `@requires_role("visa_consultant")` sui tool MCP è più
semplice che costruire un proxy separato. Se in futuro serve decoupling → Gateway.

### D3: Gemini CLI per Team — Sì o No

**Opzione A: Sì, come canale opzionale**

```
Pro:  Già pronto (install.sh Krisna)
      1M context, gratis, tool calling
Con:  Team non usa terminale
      Doppia manutenzione (Telegram + CLI)
```

**Opzione B: No, solo Telegram + Web UI**

```
Pro:  Un solo canale da mantenere (Telegram)
      Meno complessità, meno supporto
Con:  Perde la potenza del CLI (file handling, code review)
```

**Raccomandazione:** No per V1. Gemini CLI rimane strumento per Zero/developer.
Il team interagisce solo via Telegram e Web UI.

### D4: Standing Orders — Cron Air vs Backend Scheduler

**Opzione A: Cron Air (launchd) — preferita**

```
Pro:  Già funziona per 12 job, affidabile
      Non consuma risorse Fly.io
Con:  SPOF (Air down = no standing orders)
```

**Opzione B: Backend autonomous scheduler (su Fly.io)**

```
Pro:  Sempre online (Fly.io), no SPOF
      Già esiste scaffold (service_initializer:800+, Generals)
Con:  Fly.io auto_stop: se nessun traffico → cold start 35s
      Costa risorse condivise con API
```

**Raccomandazione:** Opzione A con fallback B. Air primario, se Air heartbeat
manca >5min → Fly.io prende over (trigger via health check).

### D5: Prima vs Dopo per Krisna e Damar

Non una decisione tecnica, ma il criterio di successo.

**KRISNA (Executive Consultant) — Prima:**

```
Mattina: Apre laptop, apre CRM, scorre manualmente la lista clienti
         Chiede a Zero via Telegram: "Che scadenze ho oggi?"
         Cerca email vecchie per capire stato pratiche
         30-45 minuti per avere il quadro della giornata
```

**KRISNA — Dopo (Agent Mesh V1):**

```
Mattina: Riceve su Telegram alle 07:30:
         "Buongiorno Krisna. Oggi:
          • 3 documenti in scadenza (30gg): [client A], [client B], [client C]
          • 1 pratica bloccata: [client D] — manca AHU da imigrasi
          • 2 follow-up da fare: [client E] (visa approval), [client F] (invoice)
          Il tuo compliance rate: 94% (-1% da ieri)"

         Scrive: "Dettagli client D"
         Riceve: timeline completa della pratica con ultimo stato

         Scrive: "Manda reminder a client A per il passaporto"
         Agent: "Invio reminder WA a [client A]? [Approva] [Modifica]"
         Krisna: tappa [Approva]

Tempo per avere il quadro: 2 minuti.
```

**DAMAR (Visa Specialist) — Prima:**

```
Cliente chiede su WA: "What documents do I need for KITAS sponsor?"
Damar: Cerca nelle email precedenti, chiede a Krisna, chiede a Zero
       Tempo risposta: 30min - 2h (dipende da chi è disponibile)
       Rischio: risposta incompleta o sbagliata
```

**DAMAR — Dopo (Agent Mesh V1):**

```
Cliente chiede su WA → se Damar non risponde in 10min:
Agent auto-ack: "Thanks [name], Damar will follow up shortly."

Damar apre Telegram, scrive: "Requisiti KITAS sponsor per Australian"
Agent: risposta strutturata da RAG + KG (confidence 0.85)
       con lista documenti, timeline, costi Bali Zero

Damar copia-incolla al cliente (o approva invio diretto).
Tempo risposta: 5 minuti.
```

---

## 4. I 5 Prototipi Minimi di Validazione

Ogni prototipo è indipendente, testabile in isolamento, e valida un'ipotesi specifica.

### P1: Routing Telegram per Team Member (2-3 giorni)

**Valida:** Il team scrive a @Balizerobot e riceve risposte personalizzate per ruolo.

**Cosa costruire:**

- Tabella `agent_team_members(telegram_chat_id, email, role, tool_permissions[], client_scope)`
- Middleware nel Telegram adapter: `chat_id → team_member → inject role context`
- Risposte filtrate: Krisna vede solo i suoi client, Damar solo i suoi

**Criterio successo:** Krisna e Damar scrivono domande e ricevono risposte con dati reali dei LORO client.

### P2: Summary Mattutino Personalizzato (1-2 giorni)

**Valida:** Il team trova utile ricevere un briefing automatico ogni mattina.

**Cosa costruire:**

- Cron Air 07:30 → chiama `chain_client_health_monitor(assigned_to=email)` per ogni member
- Formatta output come messaggio Telegram leggibile
- Invia via @Balizerobot a ogni chat_id

**Criterio successo:** Krisna dice "utile" dopo 5 giorni consecutivi di summary.

### P3: Permission Layer (2-3 giorni)

**Valida:** Il RBAC funziona — ogni ruolo vede solo i tool e i client permessi.

**Cosa costruire:**

- Decorator `@role_required(roles, client_scope)` nel MCP server
- Config YAML: `visa_specialist: [get_client, get_practice, get_visa_details, ...]`
- Audit log: chi ha chiamato quale tool su quale client

**Criterio successo:** Krisna NON può vedere i client di Damar. Nessuno può chiamare `send_email` senza approvazione.

### P4: Auto-Ack WhatsApp (3-4 giorni)

**Valida:** I client ricevono acknowledgment rapido anche se il consultant non risponde subito.

**Cosa costruire:**

- Timer Redis nel WA adapter: `client scrive → 10min TTL → se nessuna risposta consultant → ack`
- Ack template: "Thanks [name], [consultant] will follow up shortly."
- Notifica Telegram al consultant: "Client [name] ti ha scritto 10min fa, non hai risposto"

**Criterio successo:** Tempo medio di primo contatto scende da >30min a <10min.

### P5: Compliance Alert Individuale (1-2 giorni)

**Valida:** L'alert proattivo su compliance motiva il team a mantenere i client aggiornati.

**Cosa costruire:**

- `chain_compliance_autopilot()` con filtro `assigned_to`
- Se compliance < 95% → Telegram alert con lista azioni specifiche
- Trend settimanale: "+3%" o "-2%" rispetto a settimana scorsa

**Criterio successo:** Compliance rate medio sale dopo 2 settimane di alert.

---

## 5. Roadmap in 3 Fasi

### Fase 1: "Telegram Funziona" (Settimana 1-2)

```
Obiettivo: Il team scrive su Telegram e riceve risposte utili.

Deliverable:
  □ P1: Routing Telegram per chat_id → ruolo → client scope
  □ P2: Summary mattutino personalizzato (cron Air)
  □ P5: Compliance alert individuale

Risultato: Krisna e Damar ricevono briefing ogni mattina
           e possono fare domande sui propri client via Telegram.

Rischio: @Balizerobot polling conflitto Pro ↔ Fly.io
         → Soluzione: Pro rimane unico poller, backend Fly.io
           invia via API, non polling.
```

### Fase 2: "Permessi e Automazione" (Settimana 3-4)

```
Obiettivo: Azioni write con approval, auto-ack WA.

Deliverable:
  □ P3: Permission layer (RBAC per tool + client scope)
  □ P4: Auto-ack WhatsApp (timer 10min)
  □ Approval flow: Telegram inline buttons [Approva] [Rifiuta]
  □ Audit log: chi ha fatto cosa su quale client

Risultato: Il team può eseguire azioni (reminder, update status)
           con approval via Telegram. Client ricevono ack rapido.

Rischio: Permission troppo restrittive → team frustrato
         → Soluzione: partire permissivi, stringere dopo dati
```

### Fase 3: "Web UI e Intelligence" (Settimana 5-6)

```
Obiettivo: Dashboard integrata per task complessi.

Deliverable:
  □ kita.balizero.com/assistant — chat context-aware
  □ Dashboard per-consultant: i miei client, le mie scadenze
  □ Trend analytics: compliance over time, response time
  □ Feedback loop: agent suggerisce azioni basate su pattern

Risultato: Il team ha un'interfaccia completa per gestire
           client, pratiche e compliance con AI integrata.

Rischio: Scope creep frontend
         → Soluzione: MVP sidebar chat, non app completa
```

---

## 6. Relazione con Componenti Esistenti

```
COMPONENTE ESISTENTE          → RUOLO NELL'AGENT MESH
────────────────────────────────────────────────────────
8 Chain MCP                   → Skill invocabili dagli agent (parametrizzate per ruolo)
Federation Orchestrator       → Rimane per task complessi (multi-agent dispatch)
ai-dispatch.sh                → Rimane per Zero (developer tool, non team tool)
OpenClaw (Pro)                → Rimane come Telegram listener per @Balizerobot
OpenClaw (Air)                → Rimane come cron runner per standing orders
The Generals                  → DEPRECATI (rimuovere codice morto)
A2A code (apps/federation/)   → DORMIENTE (risvegliare solo se serve inter-agent)
Core Guardian V3              → Rimane indipendente (code quality, non team tool)
CRM RBAC esistente            → BASE per il Permission Layer (estendere, non rifare)
```

---

## 7. Rischio Più Grande e Mitigazione

**Il rischio più grande non è tecnico. È l'adoption.**

Il brainstorm di marzo ha prodotto 1100 righe di architettura. Ma:

- Krisna non ha mai usato il suo install.sh
- Damar non ha mai interagito con un agent
- Il team lavora con WhatsApp, email e CRM manuale da 5+ anni

Se costruiamo un sistema sofisticato che il team ignora, è un fallimento
indipendentemente dalla qualità tecnica.

**Mitigazione: Deploy Incrementale con Feedback Loop**

```
Settimana 1: Solo summary mattutino su Telegram (push, non pull)
             → Il team non deve fare NIENTE, solo leggere
             → Misura: quanti lo leggono? Chiedono follow-up?

Settimana 2: Se feedback positivo → abilita domande via Telegram
             → Il team può chiedere, ma non è obbligato
             → Misura: quante domande? Qualità risposte?

Settimana 3: Se uso attivo → abilita azioni con approval
             → Il team può agire tramite l'agent
             → Misura: azioni/giorno? Approval rate?

Se a qualsiasi punto il team non usa il tool → STOP.
Non costruire il Permission Gateway se nessuno scrive al bot.
```

---

## 8. Nota su The Generals e A2A

### The Generals: Rimuovere

`backend/generals/` non esiste. `service_initializer.py` importa e fallisce silenziosamente. Il concept (polling loop per task coding e intelligence) è coperto da:

- **Core Guardian V3** → monitora code quality automaticamente
- **Chain 4 (Intel Pipeline)** → gestisce intelligence gathering
- **War Room** → orchestrazione operativa

**Azione:** Rimuovere le righe 800-838 da `service_initializer.py`. Nessuna funzionalità persa.

### A2A Protocol: Tenere Dormiente

`apps/federation/` ha codice PoC per A2A (JSON-RPC 2.0). Non è in uso. Non cancellarlo — se in futuro servono agent distribuiti su Mac diversi, il PoC è il punto di partenza. Ma per V1, un backend centralizzato basta.

---

---

## Appendice A: Scoperte Tecniche Profonde (Fase 2 esplorazione)

### A.1 MCP Server — Architettura Reale

Il server MCP (`apps/nuzantara-mcp/nuzantara_mcp/server.py`, 169 righe) usa **stdio transport**.
Ogni connessione è un processo separato. NON serve multiple connessioni simultanee — ogni
client (Claude Code, OpenClaw, Gemini CLI) lancia il suo processo MCP.

**Implicazione per Agent Mesh:** Ogni team member agent può lanciare il suo processo MCP
con il SUO token JWT. Non serve un gateway. La separazione è naturale.

```
Damar's Gemini CLI → spawna processo MCP → MCP usa DAMAR_JWT → backend filtra per ruolo
Krisna's Gemini CLI → spawna processo MCP → MCP usa KRISNA_JWT → backend filtra per ruolo
```

**Auth attuale:** Il server invia `Authorization: Bearer {API_KEY}` e `X-API-Key` su ogni
chiamata HTTP al backend. Il backend valida via `hybrid_auth.py`. Nessun RBAC per-tool
nel MCP — tutto il filtering è backend-side.

### A.2 Tool Inventory Completo (105+ tool in 22 moduli)

| #   | Modulo            | Tool                                                | Rischio per Team          |
| --- | ----------------- | --------------------------------------------------- | ------------------------- |
| 1   | CRM (12)          | list/create/update clients, practices, interactions | create/update = WRITE     |
| 2   | Portal (6)        | dashboard, visa status, messages                    | READ-safe                 |
| 3   | Intel (8)         | search, approve, publish staging                    | approve/publish = WRITE   |
| 4   | Content (6)       | compose, publish articles                           | publish = WRITE           |
| 5   | Analytics (8)     | revenue, completion, SLA, productivity              | READ-safe                 |
| 6   | Knowledge (8)     | KBLI, legal, visa, langgraph                        | READ-safe                 |
| 7   | Comms (6)         | WhatsApp, email, Telegram, portal                   | SEND = HIGH RISK          |
| 8   | Drive (5)         | list, search, create folders                        | create = WRITE            |
| 9   | Sheets (4)        | read, write, update, find                           | write/update = WRITE      |
| 10  | Compliance (4)    | track, alerts, list                                 | READ-safe                 |
| 11  | Invoicing (3)     | create, get, regenerate                             | create = WRITE            |
| 12  | Journey (4)       | create, get, complete step, next steps              | create/complete = WRITE   |
| 13  | Pricing (3)       | calculate, list, search                             | READ-safe                 |
| 14  | Workflows (8)     | create/execute plan, approve step, agents           | execute = CRITICAL        |
| 15  | Admin (4)         | system management, audit                            | ADMIN ONLY                |
| 16  | Health (3)        | check backend, qdrant, db                           | READ-safe                 |
| 17  | Federation (4)    | send, inbox, mark read, status                      | send = WRITE              |
| 18  | Memory (4)        | save, recall, list, delete episodes                 | delete = WRITE            |
| 19  | Legal (2)         | ingest regulation, status                           | ingest = WRITE            |
| 20  | LangSmith (3)     | runs, detail, stats                                 | READ-safe                 |
| 21  | Google Bridge (1) | upload to NLM                                       | WRITE                     |
| 22  | Chains (8)        | 8 autopilot chain                                   | MIXED (hanno side-effect) |

**Per Damar (visa_specialist), proposta V1:**

- READ: list_clients, get_client, get_practice, get_visa_details, list_visa_types,
  get_client_timeline, get_portal_visa_status, get_compliance_alerts, calculate_pricing,
  search_kbli, ask_legal, check_health (~30 tool)
- WRITE con approval: send_whatsapp, send_email, update_practice_status, log_interaction
- BLOCCATI: admin, execute*plan, delete*\*, create_execution_plan, federation_send,
  publish_article, ingest_regulation

### A.3 Execution Plans — Safety Level Già Implementati

Il sistema di execution plan (`workflows.py`) ha GIÀ 3 livelli:

- **SAFE**: esecuzione automatica
- **CRITICAL**: pausa per approvazione (`approve_step`)
- **IRREVERSIBLE**: doppia conferma

Questo è ESATTAMENTE il pattern di approval che serve per Agent Mesh.
Il team member invoca `create_execution_plan("Rinnova KITAS per client X")` →
il sistema crea un piano con step SAFE/CRITICAL/IRREVERSIBLE →
step SAFE eseguiti automaticamente, CRITICAL mandano notifica Telegram per approve.

**Non serve costruire un approval system nuovo. Esiste già.**

### A.4 Tool Executor — Pipeline Esistente

`tool_executor.py` ha un routing a 2 livelli:

1. Se `tool_name in zantara_tool_names` → esecuzione Python diretta (pricing, team data)
2. Se `mcp_client.is_mcp_tool(tool_name)` → esecuzione via MCP protocol

Il backend (`mcp_client_service.py`) è un CLIENT MCP che si connette a server MCP
esterni (filesystem, memory, brave-search). Tutti commentati — mai attivati in produzione.

**Implicazione:** Il backend sa già invocare tool MCP. Ma per Agent Mesh non serve
questo percorso. Ogni agent ha il SUO processo MCP client (Gemini CLI, Claude Code).
Il backend è il TARGET, non l'orchestratore.

### A.5 hybrid_auth.py — Modello di Permessi

Auth a 3 livelli:

1. **API Key** (`X-API-Key`) — service-to-service, bypass DB
2. **JWT Header** (`Authorization: Bearer`) — frontend session
3. **JWT Cookie** (`nz_access_token`) — SSO/portal

**55+ endpoint pubblici** (webhook, health, KBLI, blog, portal invite).
Il resto richiede auth.

**Problema per Agent Mesh:** Oggi il JWT contiene `sub` (user_id), `email`, `role`.
Ma il backend non filtra le risposte per `assigned_to`. Se Damar ha un JWT valido,
può chiamare `/api/crm/clients/` e vedere TUTTI i client, non solo i suoi 19.

**Soluzione necessaria:** Middleware che intercetta le risposte CRM e filtra per
`assigned_to = current_user.email`. Oppure: query parameter `?assigned_to=damar@balizero.com`
iniettato automaticamente dal MCP server quando il token è di Damar.

### A.6 MCP Server Lite — Precedente per Tool Filtering

`server_lite.py` (88 righe) riduce i tool da 105 a 63 per Antigravity IDE.
Rimuove 37 tool in 10 categorie.

**Questo è il pattern esatto per Agent Mesh:** creare varianti del server filtrate
per ruolo. `server_visa_specialist.py` che registra solo i 30 tool permessi a Damar.
Oppure un unico server con `AGENT_ROLE` env var che filtra al momento della registrazione.

---

_Fine documento di visione. Aggiornato con appendice tecnica. Pronto per review e implementazione._
