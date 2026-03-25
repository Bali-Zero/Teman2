# Team Agent Assistants — Brainstorming Multi-Modello

> **Data:** 2026-03-25
> **Metodo:** 4 passaggi iterativi con 3 modelli AI in parallelo
> **Modelli:** Gemini 3.1 Pro (explore + search), DeepSeek R1 671b (reasoning), Codex 5.4 (sandbox)
> **Dispatch:** 11 chiamate AI totali via `ai-dispatch.sh v3`
> **Costo totale dispatch:** ~$0.05 (DeepSeek) + $0 (Gemini free) = ~$0.05
> **Status:** Solo idee — nessuna implementazione

---

## Indice

1. [Il Concept](#1-il-concept)
2. [Passaggio 1 — Ricognizione](#2-passaggio-1--ricognizione)
3. [Passaggio 2 — Design Architetturale](#3-passaggio-2--design-architetturale)
4. [Passaggio 3 — Stress Test](#4-passaggio-3--stress-test)
5. [Passaggio 4 — Convergenza Finale](#5-passaggio-4--convergenza-finale)
6. [Reality Check — Post-Review Multi-Modello](#6-reality-check--post-review-multi-modello)
7. [Architettura Definitiva (Corretta)](#7-architettura-definitiva-corretta)
8. [Decisioni Chiave](#8-decisioni-chiave)
9. [Pilot Plan — Damar (Rivisto)](#9-pilot-plan--damar-rivisto)
10. [Costi Reali](#10-costi-reali)
11. [Rischi Residui](#11-rischi-residui)
12. [Quick Wins](#12-quick-wins)
13. [Case Studies Esterni](#13-case-studies-esterni)
14. [Appendice — Output Raw per Modello](#14-appendice--output-raw-per-modello)

---

## 1. Il Concept

Ogni team member di Bali Zero (5→15 persone) riceve un **AI assistant personale** sul proprio Mac che:

- Risponde a domande su visa, tax, KBLI, compliance
- Esegue azioni CRM con permessi role-based (23-96 tools su 131 disponibili)
- Funziona offline con Ollama fallback
- Richiede approvazione umana (Telegram) per azioni ad alto impatto
- Costo compute marginale basso (~$3-5/mo per agent); **costo totale di ownership dominato da engineering e operations** (RC-10)

**Perché ora:** Gemini CLI ha un free tier generoso (non SLA enterprise — vedere RC-7), OpenClaw è gratis, MCP server con 131 tools già esiste, @Balizerobot Telegram è già in produzione. Il costo compute marginale è basso, ma il vero investimento è nel Permission Gateway e nell'infrastruttura di audit/approval.

---

## 2. Passaggio 1 — Ricognizione

_"Cosa esiste, best practice, opzioni di mercato"_

### 2.1 Gemini Explore — Infrastruttura esistente nel codebase

**Federation code (`apps/federation/`):**

- `a2a_service.py` — `CLIAgentExecutor` wrappa CLI tools come servizi A2A JSON-RPC
- `AGENT_CLI_COMMANDS` mappa agent ID → comandi bash (gemini-search, war-room-director, intel-pipeline)
- Resilienza NotebookLM: health check, 2 retry, fallback Qdrant RAG
- **Status:** PoC funzionante, nessun servizio in running

**War Room pipeline_v2.py — A2A nativo:**

- `call_agent()` usa httpx async per JSON-RPC 2.0 (`method: "message/send"`)
- Port mapping statico (8100-8108) con fallback su `discovery.AGENT_REGISTRY`
- **Collo di bottiglia:** State passing via filesystem (disco), non in-memory → vincola a singola macchina

**OpenClaw patterns:**

- Gateway su `loopback:18789`
- mcporter bridge per 129 tools MCP
- Cron jobs autonomi (Intel Scraper 03:00 WITA)
- Telegram polling su Pro (unico listener)

**ai-dispatch.sh v3:**

- Safety filter predittivo a 3 livelli (intent analysis, file protection, secret masking)
- Model cascading: Gemini 3.1 Pro → 2.5 Pro → 2.5 Flash (auto fallback su 429/404)
- Cache SHA-256 24h, invalidata su nuovi git commit

### 2.2 Gemini Search — Best practice 2026

**Protocollo dual-stack:**

- **A2A Protocol** (ora Linux Foundation): coordinamento inter-agent ("chiedi al Finance Agent il budget")
- **MCP**: esecuzione meccanica locale ("leggi config.json")
- A2A per coordinamento sociale, MCP per esecuzione meccanica

**Agent Card standard:**

- File JSON in `/.well-known/agent.json`
- Campi: `name`, `url`, `skills`, `authSchemes` (OAuth 2.1)
- FAIR scoring per discovery (Findability, Accessibility, Interoperability, Reusability)

**Security patterns:**

- OAuth 2.1 per tutte le comunicazioni HTTP
- Containerization/sandboxing obbligatorio
- OpenClaw per gateway federati (signed intents)

**Tooling comparison:**

| Feature  | Claude Code                        | Gemini CLI                            |
| -------- | ---------------------------------- | ------------------------------------- |
| Forza    | Architettura + multi-file refactor | Velocità, web grounding, Google Cloud |
| Context  | 200K (precisione)                  | 1M+ (codebase massivi)                |
| Best use | Engineering produzione             | Prototyping, ricerca                  |
| Costo    | Pay-per-use enterprise             | Free tier generoso                    |

### 2.3 DeepSeek R1 — Analisi architetturale profonda

**Architettura raccomandata: Hybrid A2A-MCP Bridge**

```
┌────────────────────────────────────────────┐
│           Supervisor Layer                  │
│  Claude Code (M4 Pro) → A2A Orchestrator   │
└──────────────────┬─────────────────────────┘
                   │ A2A Protocol (HTTP)
┌──────────────────▼─────────────────────────┐
│         Personal Agent Layer                │
│  [User Mac] → OpenClaw → A2A-Wrapped Agent │
│             ├─ Gemini CLI (Primary)         │
│             ├─ NuzMCP Client (Role-filtered)│
│             └─ Local KG Cache (Read-only)   │
└─────────────────────────────────────────────┘
```

**Trade-off matrix:**

| Approccio  | Pro                                     | Contro                                | Verdetto  |
| ---------- | --------------------------------------- | ------------------------------------- | --------- |
| Pure MCP   | Semplice, tools esistenti               | No supervisione, coordinamento debole | ❌        |
| Pure A2A   | Coordinamento forte                     | Reimplementare 131 tools              | ❌        |
| **Hybrid** | Meglio di entrambi, deploy incrementale | Complessità bridge layer              | ✅ **GO** |

**Role-based tool allocation (esempio visa_specialist):**

```yaml
tools:
  - crm_get_client_visa_status (scope: own_clients_only)
  - crm_update_visa_application (scope: own_clients_only)
  - documents_upload_visa_docs (scope: client_matching)
  - kg_query_visa_regulations (scope: public_knowledge)
  - rag_query_visa_faq (scope: public_knowledge)
  - send_client_update_email (scope: own_clients_only)
  - schedule_meeting_with_client (scope: own_clients_only)
  - time_tracking_log_hours (scope: personal_only)
  - task_update_visa_queue (scope: team_shared)
```

**Escalation basata su evidence scoring esistente:**

- `< 0.15` → ABSTAIN → Escalate a supervisor umano
- `0.15-0.60` → CAUTIOUS → Richiedi guidance supervisor A2A
- `> 0.60` → NORMAL → Esecuzione autonoma

**Costo stimato:** $0-5/mo per agent (Gemini CLI $0 + OpenClaw $0 + supervisor overhead $0.83)

### 2.4 Convergenze Passaggio 1

| Tema                  | Gemini Explore                             | Gemini Search                             | DeepSeek R1                     |
| --------------------- | ------------------------------------------ | ----------------------------------------- | ------------------------------- |
| **Architettura**      | Hybrid A2A+MCP (code in federation/)       | A2A per coordinamento, MCP per esecuzione | Hybrid Bridge ✅ unanime        |
| **Costo/agent**       | OpenClaw+Gemini gratis                     | Gemini CLI free tier                      | $0-5/mo                         |
| **Security**          | Safety filter in ai-dispatch               | OAuth 2.1, containerization               | 4-layer defense                 |
| **Gap**               | State-passing via filesystem, no discovery | Manca Agent Card                          | Revival federation/ PoC         |
| **Pattern riusabile** | CLIAgentExecutor, graceful degradation     | SKILL.md, FAIR scoring                    | Evidence scoring per escalation |

---

## 3. Passaggio 2 — Design Architetturale

_"Design specifico per Nuzantara"_

### 3.1 Agent Card Design (Gemini Explore)

Struttura standard basata su `a2a_service.py`:

**visa_specialist:**

- Tools: `get_visa_details`, `list_visa_types`, `get_portal_visa_status`, `track_compliance` (visa_expiry), `get_compliance_alerts`

**tax_consultant:**

- Tools: `ask_legal` (tax/TP), `track_compliance` (tax_filing/SPT), `get_compliance_alerts`, `get_revenue_analytics`

**company_setup:**

- Tools: `search_kbli`, `inspect_kbli`, `chat_kbli`, `create_practice` (pt_pma/cv), `ask_legal` (corporate)

**admin:**

- Tools: `list_clients`, `get_client_stats`, `get_team_productivity`, `list_pending_invoices`, `regenerate_invoice`

### 3.2 Discovery Protocol (Gemini Explore + Search)

**mDNS/Bonjour nativo macOS:**

- Service type: `_nuz-agent._tcp.local.`
- Service name: agent_id (es. `visa_specialist._nuz-agent._tcp.local.`)
- Libreria: `zeroconf` (Python)
- All'avvio → broadcast porta dinamica → orchestratore scopre agent online

**Caveat macOS 26 ("Tahoe"):**

- `NSNetService` è legacy → usare Network.framework (`NWBrowser`/`NWListener`)
- Local Network Privacy: richiede `NSLocalNetworkUsageDescription` + `NSBonjourServices` in Info.plist
- Per >20 agent: migrare a Redis Service Registry o HashiCorp Consul

### 3.3 State Management (Gemini Explore)

Sostituire filesystem-based state passing di `pipeline_v2.py`:

- **Redis (hot state):** Agent completa task → salva JSON in `task:{uuid}` → agent successivo preleva
- **PostgreSQL (audit + persistence):** Payload finali e delta significativi in tabella `task_execution_log` (JSONB)
- Solo porta 6379 Redis esposta su LAN

### 3.4 MCP Permission Gateway (DeepSeek R1)

**Pattern: Chain of Responsibility** — proxy che wrappa tutti i 131 tools senza modificarli

```python
# MCP Gateway Proxy (FastAPI port 8090)
class MCPPermissionDecorator:
    async def __call__(self, user_context, **kwargs):
        # 1. Check ruolo nel Knowledge Graph
        role_kg = await self._query_role_kg(user_context.role_id)
        if not role_kg.allowed_tools.get(self.tool_name):
            raise PermissionError(f"Tool {self.tool_name} non permesso")

        # 2. Apply client scope filtering
        filtered_kwargs = await self._apply_client_scope(
            user_context.client_ids, kwargs
        )

        # 3. Mask PII se necessario
        if role_kg.pii_mask_level > 0:
            filtered_kwargs = self._mask_pii(filtered_kwargs)

        # 4. Log audit trail
        await self._log_audit(user_context, self.tool_name, filtered_kwargs)

        # 5. Esegui tool originale (INVARIATO)
        return await self.tool(**filtered_kwargs)
```

**Vantaggio:** Zero modifica ai tools esistenti. Il proxy intercetta e filtra.

### 3.5 Task Routing — Gemini CLI vs Claude Code (DeepSeek R1)

```python
class TaskRouter:
    async def route_task(self, task):
        if task.requires_internet:
            return "claude_code"          # Solo Claude ha internet access
        if task.attachments > 5:
            return "claude_code"          # Multi-file processing
        if task.precision_required > 0.95:
            return "claude_code"          # Task critici
        if task.cost_sensitive:
            return "gemini_cli"           # Routine, gratis
        return "gemini_cli_with_fallback" # Default
```

**Claude Code (Supervisor):** approval workflow, ricerche web, analisi documenti multipli, task critici
**Gemini CLI (Agents):** query RAG routine, draft email, update KG semplici, notifiche

### 3.6 Offline Resilience (DeepSeek R1)

**Pattern: Offline-First con CRDT**

```
[Agent Offline]
  ├── Ollama locale (qwen3.5:9b, 4GB)
  ├── SQLite cache (subset KG + embeddings)
  ├── Pending operations queue (CRDT)
  └── Delta sync state (hash-based)

[Reconnection]
  ├── Push pending operations
  ├── Pull updates since last sync
  ├── Conflict resolution (timestamp + role priority)
  └── KG subset refresh se stale
```

**Sync protocol:**

1. Agent → Server: `SYNC_REQUEST {agent_id, last_sync_hash}`
2. Server → Agent: `SYNC_DELTA {operations[], kg_subset_delta[]}`
3. Agent → Server: `SYNC_CONFIRM {applied[], conflicts[]}`
4. Server → Agent: `SYNC_COMPLETE {new_hash}`

### 3.7 Human-in-the-Loop (DeepSeek R1)

**Pattern: Proposal → Approval → Execution**

High-impact actions: `send_email_to_client`, `update_application_status`, `submit_document_to_government`, `change_legal_entity`, `approve_payment`

**Escalation timeline:**

- 4h → Notifica reminder
- 12h → Escalate al manager
- 24h → Auto-reject con notifica

**Canali:** Telegram `/approve <id>` + macOS notification + email fallback

### 3.8 Knowledge Graph Sync (DeepSeek R1)

**Problema:** 56K nodi KG, ogni agent usa ~1-5K

**Soluzione: Role-Based Subgraph Extraction**

1. Analizza access pattern storici del ruolo
2. Identifica core entities frequentemente accessite
3. Espandi a 2-hop per contesto
4. Aggiungi nodi critici (sempre)
5. Filtra per client scope
6. Ottimizza: target <5.000 nodi

**Sync strategy:**

- Initial push: setup completo
- Delta push: <100 nodi modificati → push immediato
- Pull on demand: agent offline → online
- TTL invalidation: cache scade dopo 24h

### 3.9 Onboarding Script (Gemini Explore)

```bash
curl -sSL https://raw.githubusercontent.com/nuzantara/core/main/scripts/mac-bootstrap.sh | bash
```

Contenuto:

1. System deps: `brew install python redis node zeroconf`
2. Core tools: `npm install -g @google/gemini-cli && pip install openclaw nuzantara-mcp zeroconf`
3. A2A: `mkdir -p ~/.well-known/ && curl agent_card.json`
4. Auth: `.env.template` + prompt API keys
5. Daemon: `launchd` o `pm2` per avvio background

---

## 4. Passaggio 3 — Stress Test

_"Scenari critici e vulnerabilità"_

### 4.1 Attacco Interno — Permission Gateway Bypass

**Severity: CRITICAL**

**Vulnerabilità:** Team member modifica `mcp_url` per puntare direttamente al MCP server (bypass gateway).

**Scoperta dal codebase (Gemini Explore):**

- `hybrid_auth.py:65-130` ha lista massiccia di `public_endpoints` che bypassano auth
- Endpoint sensibili come `/api/whatsapp/conversations`, `/api/telegram/conversations` accessibili senza auth
- MCP server non ha RBAC interno — chiunque con stdio ha tutti i 96+ tools

**Mitigazione:**

```python
# MCP server deve richiedere JWT signed dal Gateway
async def handle_mcp_request(self, request):
    auth = request.headers.get("X-Agent-Signature")
    if not verify_jwt_signature(auth, expected_origin="gateway:8090"):
        raise HTTPException(403, "Direct MCP access blocked")
```

### 4.2 Cascading Failure — Supervisor Offline

**Severity: CRITICAL**

**Vulnerabilità:** Pro (supervisor) offline → tutti gli agent perdono supervisione + approval pending bloccate.

**Scoperta dal codebase:** Orchestrator tenta solo `localhost`, zero routing cross-machine. Air non ha capacità supervisor.

**Mitigazione:**

- Redis-based leader election con TTL 30s
- Air auto-promossa a supervisor temporaneo
- Approval fallback a Telegram admin diretto

### 4.3 Scale Test — 5 → 50 Agent

**Severity: MEDIUM**

**Bottleneck:**

- mDNS: broadcast storm con 50+ device
- Gateway: single-threaded FastAPI
- Redis: letture/scritture concorrenti

**Mitigazione:**

- <20 agent: mDNS ok
- > 20 agent: Redis Service Registry
- Gateway: replicas=3 con load balancer
- Redis: pool size 50

### 4.4 Data Leak — Laptop Rubato

**Severity: CRITICAL**

**Vulnerabilità:** SQLite locale con KG subset (dati 5000+ client) su laptop rubato.

**Mitigazione (Gemini Search confermato):**

- **SQLCipher**: AES-256 encryption del .db file
- **macOS Keychain**: passphrase SQLCipher in Keychain, MAI hardcoded
- **FileVault**: protegge solo a macchina spenta (non sufficiente da solo)
- **Remote wipe**: comando Telegram/admin panel → cancella db + invalida sessioni

### 4.5 Gemini CLI Rate Limit

**Severity: HIGH**

**Problema:** 15 RPM con 15 agent = 1 RPM ciascuno. Insufficiente per picchi.

**Mitigazione:**

- Priority queue: `client_emergency(0)` > `approval_required(1)` > `routine_query(2)` > `background_sync(3)`
- Routine + background → Ollama locale (scarica Gemini)
- API Key pooling o migrazione a Vertex AI per quotas più alte
- Semantic caching: query identiche cachate in Redis/SQLite

### 4.6 Conflitto KG Offline

**Severity: MEDIUM**

**Problema:** Due agent offline modificano stesso nodo (es. stato visa stesso client).

**Mitigazione:**

- Campi non-critici: Last Write Wins (timestamp)
- Campi critici (`visa_status`, `company_registration`, `tax_amount`): task di risoluzione umana
- Dashboard conflitti giornaliera

### 4.7 Regulatory — UU PDP / GDPR

**Severity: CRITICAL**

**Indonesia UU PDP (enforced Oct 2024):**

- ROPA compliance: log chi, quando, perché ha accesso ai dati
- WORM storage: log immutabili (Write Once, Read Many)
- Breach notification: 72 ore
- Sanzioni: fino al 2% del fatturato annuo

**Mitigazione:**

- PII redaction automatica nei log (regex: KTP, passport, email)
- Log retention policy: 30 giorni
- PostgreSQL con append-only per audit
- Geo-IP logging per compliance cross-border

### 4.8 Non-Technical Users

**Severity: MEDIUM (barriera adoption)**

**Problema:** Visa consultants non sanno usare il terminale.

**Scoperta dal codebase (Gemini Explore):**

- `apps/mouth/` — frontend Next.js già orientato ai clienti
- `apps/admin-dashboard/` — admin UI interna
- `@Balizerobot` Telegram — **GIÀ USATO** dall'orchestrazione per checkpoint e file output

**Mitigazione (Gemini Search):**

- **Telegram bot** come interfaccia primaria (app già installata su telefoni team)
- **Voice notes Telegram** → Whisper transcription → agent → risposta TTS
- Template buttons per query comuni ("Check Visa Status", "Extend Visa", "Client Follow-up")
- Zero nuova infrastruttura necessaria

### 4.9 Audit Esistente (Gemini Explore)

Il sistema ha già 3 livelli di audit:

1. **Backend API:** `activity_logging.py:149` traccia ogni chiamata API (tempo, status, IP, user)
2. **MCP Tools:** LangSmith tracing registrato in `server.py:89`
3. **Federation:** audit append-only JSONL in `ai-dispatch-output/audit.jsonl`

**Gap:** nessun audit centralizzato cross-layer, nessuna PII redaction automatica, nessun WORM storage.

---

## 5. Passaggio 4 — Convergenza Finale

_"Sintesi con raccomandazione e next steps"_

Tutti i risultati dei 3 passaggi precedenti sono stati sintetizzati nei capitoli seguenti.

---

## 6. Reality Check — Post-Review Multi-Modello

> Dopo il brainstorming, il documento è stato sottoposto a review indipendente da **Gemini 3.1 Pro** (deep think, via app), **Claude** (via app) e **ChatGPT** (TBD). Questo capitolo incorpora tutte le correzioni critiche identificate.

### Valutazione esterna

**Gemini 3.1 Pro (deep think):**

- Voto: **9.5/10** — "Architecture Decision Record di altissima qualità"
- Punti di forza: MCP Permission Gateway ("genialata"), pragmatismo UX Telegram, sicurezza UU PDP contestualizzata, Quick Wins operativi
- Verdetto: **GO — Approvato per esecuzione con 4 correzioni obbligatorie**

**Claude (via app):**

- Voto: Non numerico — "concept valido, timing buono"
- Punti di forza: metodo 4-passaggi ripetibile ($0.05), Hybrid A2A+MCP "scelta giusta", Telegram "decisione più importante"
- Critiche principali: costi dev sottostimati (3-4 mesi FT, non 4 settimane), CRDT sovra-ingegnerizzato, Ollama non ha qualità per tool calling, trust model JWT/stdio insufficiente
- Verdetto: **GO — Ma tagliare scope drasticamente per pilot (no offline/CRDT/SQLCipher/leader election)**

**ChatGPT (o1):**

- Voto: **8/10** (brainstorming strategico), **5.5/10** (blueprint esecutivo)
- Punti di forza: separazione A2A/MCP sensata, Permission Gateway "decisione migliore", pragmatismo Telegram, pilot singolo
- Critiche principali: documento mescola 4 generi (brainstorming/architecture/threat model/pilot plan), offline-first "prodotto a sé", "$3-5/mo" fuorviante (dev/ops dominano), KPI ottimistici, manca matrice irreversibilità
- Insight unico: **"Il Gateway È il prodotto"** — il moat difendibile è permissioning+audit+policy, non gli agent. Modelli e agent possono cambiare.
- Verdetto: **GO condizionale — Separare in 3 deliverable: ADR-001 scope pilot, threat model formale, evaluation plan**

### Sintesi convergente dei 3 reviewer

| Tema               | Gemini                 | Claude                          | ChatGPT                        | Consenso                  |
| ------------------ | ---------------------- | ------------------------------- | ------------------------------ | ------------------------- |
| Hybrid A2A+MCP     | ✅ Genialata           | ✅ Scelta giusta                | ✅ Sensato                     | 3/3 GO                    |
| Permission Gateway | ✅ Brillante           | ✅ Elegante                     | ✅ IL prodotto                 | 3/3 **Priorità assoluta** |
| Telegram UI        | ✅ Pragmatico          | ✅ Decisione più importante     | ✅ Bassa frizione              | 3/3                       |
| CRDT/Offline       | ⚠️ LWW pericoloso      | ❌ Sovra-ingegnerizzato         | ❌ Prodotto a sé               | 3/3 **Tagliare**          |
| Ollama fallback    | ⚠️ Air M1 swap death   | ❌ Gap qualità tool calling     | ⚠️ Solo continuità, non parità | 3/3 **Ridimensionare**    |
| Rate limit Gemini  | ⚠️ Insufficiente       | ❌ Sistema "perennemente rotto" | ⚠️ No SLA enterprise           | 3/3 **Budget Vertex AI**  |
| mDNS               | ⚠️ Coworking blocking  | —                               | ⚠️ Fragile, debugging          | 2/3 **Redis subito**      |
| Scope pilot        | ⚠️ Solo 5 tool lettura | ❌ 6-8 settimane non 4          | ❌ 20% della complessità       | 3/3 **Taglio drastico**   |
| Trust model        | —                      | ❌ Agent semi-trusted           | ⚠️ Perimetro incompleto        | 2/3 **Rafforzare**        |
| Monitoring         | —                      | ❌ Manca                        | —                              | 1/3 **Aggiungere**        |
| Costi opening      | —                      | ⚠️ Dev sottostimati             | ❌ "$3-5/mo" fuorviante        | 2/3 **Riformulare**       |
| Documenti separati | —                      | —                               | ❌ Mescola 4 generi            | 1/3 **Considerare**       |

### RC-1: Ollama su MacBook Air M1 — Limite Hardware

**Problema originale:** Il pilot prevedeva `qwen3.5:9b` su MacBook Air M1 di Damar.

**Reality check:** Un modello 9B richiede ~5.5-6GB RAM per inferenza. Su un Air M1 (8-16GB) con Chrome, macOS, Telegram e vector DB locale → swap death e thermal throttling. Il computer diventa inutilizzabile.

**Correzione:**

- Pilot: usare **qwen2.5:1.5b** o **qwen2.5:3b** quantizzati (Q4_K_M) → ~1-2GB RAM
- Limitare capacità offline a task non-generativi (lookup cache, template filling)
- Generazione complessa offline: queue per sync quando online
- Hardware minimo: 16GB RAM per agent con Ollama attivo

### RC-2: Offline DEVE essere Read-Only per dati CRM

**Problema originale:** CRDT sync con Last-Write-Wins per modifiche offline.

**Reality check:** LWW su dati CRM è pericolosissimo. Se Damar aggiorna offline il passaporto di un cliente e Tax Agent aggiorna l'email dello stesso cliente, il sync automatico rischia di sovrascrivere uno dei due → **data corruption silenziosa**.

**Correzione:**

- Offline = **Strictly Read-Only** per dati aziendali (client, practice, compliance)
- Scritture offline → **Event Sourcing**: accodate localmente, inviate al server al reconnect
- Conflitti di scrittura → revisione umana obbligatoria (Telegram notification)
- Cache locale: snapshot read-only rinfrescato ogni 4h quando online

```python
# Pattern corretto per offline writes
class OfflineWriteQueue:
    async def queue_write(self, action, data):
        """Accoda scrittura per sync successiva, NON esegue localmente"""
        self.pending_writes.append(PendingWrite(
            action=action,
            data=data,
            timestamp=time.time(),
            agent_id=self.agent_id,
            status="pending_sync"  # MAI "applied"
        ))
        # Mostra all'utente: "Modifica salvata, sarà applicata al riconnessione"

    async def sync_writes(self):
        """Al reconnect, invia al server con conflict check"""
        for write in self.pending_writes:
            server_version = await self.fetch_server_version(write.data.id)
            if server_version.updated_at > write.timestamp:
                # CONFLITTO: richiedi revisione umana
                await self.escalate_conflict(write, server_version)
            else:
                await self.apply_write(write)
```

### ~~RC-3: 15 RPM Gemini è insufficiente~~ → RISOLTO

**Problema originale:** 15 RPM condivisi tra tutti gli agent.

**Risolto (v3):** Con architettura federata (ogni Mac ha il SUO Gemini CLI col SUO account Google Workspace), ogni team member ha i propri 15 RPM indipendenti. 18 persone = 270 RPM totali. **Nessun Vertex AI necessario. Costo: $0.**

Il rate limit è stato un non-problema fin dall'inizio — bastava che ogni persona usasse il proprio account.

### RC-4: mDNS morto nei coworking — Redis Registry dal Giorno 1

**Problema originale:** mDNS/Bonjour per discovery fino a 20 agent, poi Redis.

**Reality check:** Negli uffici e coworking, Client/AP Isolation blocca i pacchetti broadcast UDP. mDNS non funziona. Gli agent non si scopriranno mai.

**Correzione:**

- Saltare mDNS completamente
- **Redis Service Registry in cloud** (Upstash free tier) fin dal Giorno 1
- Ogni agent al boot: `HSET agent:{id} host {ip} port {port} role {role} status online`
- TTL 60s con heartbeat → agent offline rimosso automaticamente
- Zero dipendenza dalla rete locale

### RC-5: Trust Model — Gateway è l'unico enforcement (Claude)

**Problema originale:** JWT header nel MCP server come protezione contro bypass diretto.

**Reality check (Claude):** Se l'agent gira sulla macchina dell'utente e il MCP è stdio, l'utente ha accesso fisico al processo. JWT su stdio è "security theater" — non puoi proteggere un segreto su una macchina che non controlli.

**Correzione:**

- **Assumere agent locale come semi-trusted** — non fully trusted
- **Gateway è l'UNICO punto di enforcement reale** — tutta la security vive lì
- JWT serve per identification (chi sei), non authorization (cosa puoi fare)
- Aggiungere **anomaly detection server-side**: rate limiting per agent, pattern detection (query burst, accesso client non assegnati), alerting automatico
- Nessun dato sensibile mai cachato sull'agent locale — solo risultati aggregati/anonimi

### RC-6: Monitoring/Observability manca (Claude)

**Problema originale:** Nessuna sezione su come monitorare 5-15 agent distribuiti.

**Reality check:** Con agent su macchine diverse, senza un health dashboard centralizzato sei cieco. Un agent può funzionare male per giorni senza che nessuno se ne accorga.

**Correzione — Agent Health Dashboard (dal Giorno 1):**

- Ogni agent invia heartbeat a Redis ogni 30s: `{agent_id, status, last_query_time, error_count, cache_hit_rate}`
- Dashboard centralizzata (può essere una pagina Telegram con `/status` o un pannello in `apps/admin-dashboard/`)
- Alert automatici: agent offline >5min, error rate >10%, query latency >60s
- LangSmith tracing già presente nel MCP server — estendere a tutti gli agent
- Weekly report automatico: query count per agent, tool usage distribution, escalation rate

### RC-7: Contingency "Gemini non più gratis" (Claude)

**Problema originale:** Nessun piano B se Google cambia pricing di Gemini CLI.

**Reality check:** Google ha storicamente cambiato pricing su prodotti gratuiti (Maps API, Firebase, etc.). Se Gemini CLI diventa a pagamento, l'economia del progetto cambia radicalmente.

**Contingency plan:**

- **Tier 1 (soft limit):** Gemini introduce quota ridotta → migrare task routine a Ollama locale, mantenere Gemini per task complessi
- **Tier 2 (paid, <$20/agent/mo):** Assorbire nel budget, rivalutare se >15 agent
- **Tier 3 (paid, >$50/agent/mo):** Migrare interamente a **Claude API via AI Gateway** (Vercel) o **Ollama qwen3.5:27b** su macchine con 32GB+
- **Monitoraggio:** Alert su announcement Google AI (RSS/Telegram) per early warning
- **Principio:** Non costruire feature che funzionano SOLO con Gemini CLI — mantenere astrazione provider nel Task Router

### RC-8: Scope Pilot drasticamente ridotto (Claude + Gemini convergono)

**Problema originale:** Pilot Damar in 4 settimane include Gateway + RBAC + SQLCipher + CRDT + leader election + Telegram approval.

**Reality check (Claude):** "3-4 mesi di sviluppo full-time prima che Damar sia in produzione con tutte le feature." Il pilot è troppo ambizioso.

**Correzione — Pilot Minimale (MVP):**

1. **Cosa INCLUDE:** Gemini CLI + 5 tool read-only (filtrati dal Gateway YAML) + Telegram approval
2. **Cosa ESCLUDE (v1):** Offline/CRDT, SQLCipher, leader election, KG sync, voice notes
3. **Timeline rivista:** 6-8 settimane (non 4), prime 3-4 settimane = solo infrastruttura Gateway
4. **Criterio di successo MVP:** Damar usa l'agent per 10 query/giorno per 2 settimane senza incidenti
5. **Dopo MVP:** Aggiungere layer uno alla volta (prima write tools, poi offline cache read-only, poi encryption)

### RC-9: Matrice di Irreversibilità per azioni agent (ChatGPT)

**Problema originale:** Azioni classificate solo come "alto impatto" con soglia evidence score.

**Reality check:** Una singola soglia non cattura la complessità. Inviare un'email sbagliata a un client è diverso da modificare una pratica legale — entrambe sono "alto impatto" ma la seconda è irreversibile.

**Correzione — Matrice a 5 dimensioni:**

| Dimensione              | Basso (0)      | Medio (1)           | Alto (2)               |
| ----------------------- | -------------- | ------------------- | ---------------------- |
| **Reversibilità**       | Undo immediato | Recuperabile in ore | Irreversibile          |
| **Impatto regolatorio** | Nessuno        | Warning interno     | Violazione UU PDP/KBLI |
| **Impatto economico**   | <$100          | $100-1000           | >$1000                 |
| **Esposizione PII**     | Nessuna        | Dati interni        | Dati client a terzi    |
| **Confidenza evidenza** | >0.60          | 0.15-0.60           | <0.15                  |

**Policy di approvazione basata su score composito:**

- Score 0-2: Esecuzione autonoma
- Score 3-5: Approval singolo (Telegram)
- Score 6-8: Approval + review supervisor
- Score 9-10: Blocco + escalation umana obbligatoria

Esempio: "Invia email reminder scadenza visa" = reversibilità(1) + regolatorio(0) + economico(0) + PII(1) + confidenza(0) = **2 → autonomo**
Esempio: "Modifica stato pratica PT PMA" = reversibilità(2) + regolatorio(2) + economico(2) + PII(1) + confidenza(1) = **8 → approval + review**

### RC-10: Il Gateway È il Prodotto (ChatGPT — insight strategico)

**Insight:** Il valore difendibile del sistema non sono "tanti agent con Gemini gratis". Gli agent e i modelli possono cambiare (Gemini → Claude → Ollama → qualsiasi cosa). Il valore è:

- **Permission Gateway** — chi può fare cosa, su quali client
- **Audit trail** — log immutabile di ogni azione agent
- **Policy enforcement** — matrice irreversibilità, escalation
- **Approval workflow** — human-in-the-loop calibrato per rischio

**Implicazione architetturale:** Il Gateway va trattato come prodotto interno, non come glue code. Investire in: test coverage, documentazione API, monitoring dedicato, upgrade path chiaro.

### RC-11: KPI — Primi 30 giorni = misurare, non targettare (ChatGPT)

**Problema originale:** "Human approval rate <10%" come KPI target.

**Reality check:** Per task visa/tax/company con impatto operativo e regolatorio, 10% approval è irrealistico al lancio. Non si sa ancora quali task l'agent gestirà bene autonomamente.

**Correzione:**

- **Giorni 1-30:** Approval umana su **tutte** le write action — misurare, non targettare
- **Giorni 31-60:** Identificare le 3-5 classi di task dove l'agent ha >95% accuracy → rendere autonome
- **Giorni 61-90:** Ridurre approval progressivamente, classe per classe
- Target realistico post-90 giorni: ~30% autonomo, non 90%

### RC-12: 3 Deliverable successivi (ChatGPT — roadmap)

Il brainstorming va ora trasformato in 3 documenti separati:

**1. ADR-001 — Scope del Pilot**

- Un solo ruolo (visa_specialist)
- Un solo canale (Telegram)
- Una sola classe di task (query informative + draft email)
- Nessun offline write
- 10-15 tool ad alto valore, non 23

**2. Threat Model Formale**

- Asset: dati 5000+ client, credenziali agent, approval tokens
- Trust boundaries: agent locale (semi-trusted), Gateway (trusted), backend (trusted)
- Attacker types: insider (team member curioso), device theft, prompt injection
- Abuse cases: tool misuse via prompt injection, approval fatigue (auto-approve senza leggere), credential theft
- Mitigazioni obbligatorie prima del pilot

**3. Evaluation Plan**

- 30 task reali di Damar (registrati manualmente oggi come baseline)
- Rubric accuracy: risposta corretta, tool corretto, timing corretto
- Rubric safety: nessun accesso client non assegnato, nessuna PII leak, nessuna azione non autorizzata
- Tempo medio: agent vs umano
- Incidenti / near misses

### Impatto sulle sezioni successive

Le correzioni RC-1→RC-12 + discussione v3 sono integrate nelle sezioni 7-14. I cambiamenti principali:

- **Architettura v3:** 18 Mac sudditi (ognuno il suo OpenClaw + Gemini CLI + Baileys) + 1 Air padrone (Super Node) + 1 Pro framework
- **Rate limit RISOLTO:** 18 account × 15 RPM = 270 RPM. Zero Vertex AI. Costo $0.
- **WhatsApp via Baileys:** ogni nodo ha Baileys collegato al WhatsApp del team member (la SUA SIM). Non servono Business API.
- **Controllo:** Air è operator.admin, vede tutto, comanda tutto, revoca chiunque. Team member sono role:node.
- **Se il Mac è chiuso:** l'agent non risponde. In questa fase non c'è H24. Messaggi in coda, processati alla riapertura.
- Pilot Damar: 10-15 tool lettura+scrittura, 1 mese, KPI = misurare non targettare
- Offline: strictly read-only, NO CRDT nel pilot
- Monitoring: agent health dashboard obbligatorio dal Giorno 1
- Next steps: 3 deliverable separati (ADR-001, Threat Model, Evaluation Plan)

---

## 7. Architettura Definitiva (Corretta v3 — post-discussione)

> Dopo le review + discussione diretta con il founder, l'architettura è stata radicalmente semplificata.
> Principi: ogni team member ha il suo stack completo sul suo Mac. Air è il padrone. Pro fa il framework.

### Il Modello: 18 Mac sudditi + 1 Air padrone + 1 Pro framework

```
┌─────────────────────────────────────────────────────────────────────────┐
│              AIR — SUPER NODE / PADRONE UNIVERSALE (H24)                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  OpenClaw Master (operator.admin)                               │   │
│  │  • Vede TUTTE le conversazioni WhatsApp di ogni nodo            │   │
│  │  • Può inviare comandi a qualsiasi nodo                         │   │
│  │  • Può revocare accesso istantaneamente                         │   │
│  │  • Audit centralizzato (PostgreSQL)                             │   │
│  │  • Heartbeat monitoring (chi è online/offline)                  │   │
│  │  • Cron job scheduling per tutti i nodi                         │   │
│  │  • MCP Permission Gateway (RBAC, PII redaction)                 │   │
│  │  • Board Dashboard (analytics, intel extraction)                │   │
│  └──────────────────────────┬──────────────────────────────────────┘   │
│                              │                                         │
│  Risorse: 16GB RAM (dedicato), 12 cron job, gateway :18789             │
│  Costo: $0 (già in funzione H24)                                      │
└──────────────────────────────┼─────────────────────────────────────────┘
                               │ LAN / Tailscale
    ┌──────────┬───────────────┼───────────────┬──────────────┐
    ▼          ▼               ▼               ▼              ▼
┌────────┐ ┌────────┐    ┌────────┐    ┌────────┐     ┌────────┐
│ Damar  │ │ Tax 1  │    │ Setup  │    │ Admin  │     │ ...×18 │
│ Mac    │ │ Mac    │    │ Mac    │    │ Mac    │     │ Mac    │
│        │ │        │    │        │    │        │     │        │
│OpenClaw│ │OpenClaw│    │OpenClaw│    │OpenClaw│     │OpenClaw│
│(suddito│ │(suddito│    │(suddito│    │(suddito│     │(suddito│
│ role:  │ │ role:  │    │ role:  │    │ role:  │     │ role:  │
│ node)  │ │ node)  │    │ node)  │    │ node)  │     │ node)  │
│        │ │        │    │        │    │        │     │        │
│Gemini  │ │Gemini  │    │Gemini  │    │Gemini  │     │Gemini  │
│CLI     │ │CLI     │    │CLI     │    │CLI     │     │CLI     │
│(SUO    │ │(SUO    │    │(SUO    │    │(SUO    │     │(SUO    │
│account)│ │account)│    │account)│    │account)│     │account)│
│15 RPM  │ │15 RPM  │    │15 RPM  │    │15 RPM  │     │15 RPM  │
│        │ │        │    │        │    │        │     │        │
│Baileys │ │Baileys │    │Baileys │    │Baileys │     │Baileys │
│(SUO WA)│ │(SUO WA)│    │(SUO WA)│    │(SUO WA)│     │(SUO WA)│
│(SUA SIM│ │(SUA SIM│    │(SUA SIM│    │(SUA SIM│     │(SUA SIM│
└────────┘ └────────┘    └────────┘    └────────┘     └────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│              PRO — FRAMEWORK & AUTOMAZIONI (dev machine)                │
│  • Claude Code (Opus 4.6) — sviluppo, refactor, deploy                │
│  • ai-dispatch.sh — federation CLI                                     │
│  • Pipeline: intel scraper, war room, NLM, evaluator                   │
│  • MCP server development & testing                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Proprietà di ogni livello

**Air (Padrone) — cosa PUÒ fare:**

- `openclaw system presence` → chi è online adesso
- `openclaw devices revoke` → taglia un nodo istantaneamente
- `openclaw devices rotate` → ruota token di sicurezza
- Leggere tutte le conversazioni WhatsApp dei nodi (operator.admin)
- Inviare comandi a qualsiasi nodo
- Schedulare cron job che girano sui nodi
- Aggregare analytics e estrarre intel dalle conversazioni
- Bloccare tool specifici per ruolo via Permission Gateway

**Mac del team (Sudditi) — cosa POSSONO fare:**

- Chattare su WhatsApp col proprio assistente
- Usare solo i tool assegnati al proprio ruolo
- Vedere solo i propri clienti (scope filter)

**Mac del team — cosa NON possono fare:**

- Accedere a tool di altri ruoli
- Vedere client non assegnati a loro
- Leggere conversazioni di altri nodi
- Modificare i propri permessi (config sta su Air)
- Connettersi al Gateway senza token pairato
- Continuare a operare se il token viene revocato

**Se chiudono il Mac:** l'agent non risponde fino alla riapertura. I messaggi WhatsApp restano nella chat, l'agent li processa quando il Mac riapre. In questa fase non c'è H24.

### Interfaccia utente: WhatsApp via Baileys

- Ogni nodo ha Baileys collegato al WhatsApp del team member (la SUA SIM, il SUO telefono)
- Baileys = sessione WhatsApp Web aggiuntiva, il telefono funziona normalmente
- Il team member scrive dal telefono al suo WhatsApp → Baileys riceve sul suo Mac → OpenClaw processa → risponde nella stessa chat
- Se la sessione Baileys cade → QR rescan in 30 secondi
- Per il team member: è come avere un contatto "Zantara AI" che risponde alle domande di lavoro

### Rate limit: risolto by design

18 Mac × 15 RPM Gemini ciascuno (account Google Workspace proprio) = **270 RPM totali**
Zero collo di bottiglia. Zero Vertex AI necessario. Zero costo.

### Costi reali (v3)

| Voce             | Costo/mese                            |
| ---------------- | ------------------------------------- |
| Gemini CLI × 18  | $0 (ogni account ha il suo free tier) |
| OpenClaw × 18    | $0 (locale su ogni Mac)               |
| Baileys × 18     | $0 (open source)                      |
| Air (Super Node) | $0 (già acceso H24)                   |
| Pro (framework)  | $0 (già in uso)                       |
| Redis Upstash    | $0 (free tier)                        |
| **TOTALE INFRA** | **$0**                                |

L'unico costo è il tempo di Zero per setup e manutenzione.

---

## 8. Decisioni Chiave

### Top 5 (consenso unanime 3+ modelli)

| #   | Decisione                          | Pro                                           | Contro              | Consenso | Verdetto               |
| --- | ---------------------------------- | --------------------------------------------- | ------------------- | -------- | ---------------------- |
| 1   | **Hybrid A2A+MCP**                 | Coordinamento A2A + 131 tools MCP             | Complessità bridge  | 3/3      | ✅ Implementa          |
| 2   | **MCP Permission Gateway** con JWT | RBAC senza toccare tools, audit centralizzato | JWT management      | 3/3      | ✅ Implementa          |
| 3   | **Gemini CLI free** come primario  | $0/agent, 1M ctx                              | 15 RPM limit        | 3/3      | ✅ Con Ollama fallback |
| 4   | **Telegram @Balizerobot** per HitL | Zero nuova infrastruttura, già testato        | Singola piattaforma | 3/3      | ✅ Estendi             |
| 5   | **SQLCipher + Keychain** offline   | Laptop rubato = dati sicuri                   | Sync complexity     | 2/3      | ✅ Implementa          |

### Decisioni secondarie

| Decisione                 | Soglia                  | Azione                           |
| ------------------------- | ----------------------- | -------------------------------- |
| ~~mDNS → Redis Registry~~ | ~~>20 agent~~           | **RC-4: Redis dal Giorno 1**     |
| Gateway replicas          | >15 agent               | Scale a 3 replicas               |
| ~~Vertex AI migration~~   | ~~Rate limit blocking~~ | **RC-3: Vertex AI dal Giorno 1** |
| Voice notes (Whisper)     | Adoption <50%           | Aggiungi per non-tech            |

---

## 9. Pilot Plan — Damar (Rivisto)

> **RC applicati:** RC-1 (modello ridotto), RC-2 (read-only offline), RC-3 (Vertex AI), RC-4 (Redis registry)

### Fase 1: Setup (Giorno 1-3)

| Step         | Azione                                                               |
| ------------ | -------------------------------------------------------------------- |
| Hardware     | MacBook Air M1 di Damar (**verificare: minimo 16GB RAM**)            |
| Python       | `brew install python@3.11` + venv                                    |
| SQLCipher    | `brew install sqlcipher`                                             |
| Ollama       | `brew install ollama && ollama pull qwen2.5:1.5b` **(RC-1: NOT 9b)** |
| Redis client | `brew install redis`                                                 |
| Repo         | Clone `nuzantara-agent-assistants`                                   |
| Config       | `.env` con JWT_SECRET, macOS Keychain per encryption key             |
| Telegram     | @Balizerobot webhook per Damar                                       |
| Vertex AI    | Service account con quota adeguata **(RC-3)**                        |

### Fase 2: Configurazione (Giorno 4-5)

| Step           | Azione                                                                           |
| -------------- | -------------------------------------------------------------------------------- |
| Gateway        | Avvia MCP Permission Gateway (port 8090) su Pro                                  |
| Redis Registry | Registra Damar in Upstash Redis **(RC-4: no mDNS)**                              |
| Tools          | **Solo 5 tool in LETTURA** inizialmente (non 23) — vedi Gemini review            |
| Offline mode   | Configurare read-only cache + event sourcing queue **(RC-2)**                    |
| Test           | `curl -H "Authorization: Bearer <JWT>" http://gateway:8090/tools` → solo 5 tools |

### Fase 3: Test Scenari (Giorno 6-10)

**Scenario 1 — Consultazione visa turistica:**

- Input: "Cliente Brasiliano, 30 giorni, turismo"
- Expected: `check_requirements`, `calculate_fee`, `timeline_estimate`
- Human approval: Telegram → `/approve <id>`

**Scenario 2 — Offline mode:**

- Disconnetti internet
- Query: "Requisiti visa business 6 mesi"
- Expected: Risposta da cache SQLCipher (con evidence scoring)
- Sync al reconnect

**Scenario 3 — Rate limit:**

- 20 richieste in 1 minuto
- Expected: Priority queue, fallback Ollama

### Fase 4: Pilot Reale (Giorno 11-20)

- 5-10 casi client reali supervisionati
- Feedback quotidiano da Damar
- Aggiustamenti tool subset

### Criteri di Successo (KPI — rivisti per RC-11)

**Giorni 1-30: MISURARE, non targettare**

| Metrica                 | Obiettivo Giorno 1-30    | Target Post-90 giorni |
| ----------------------- | ------------------------ | --------------------- |
| Tempo risposta (online) | Misurare baseline        | <30s                  |
| Accuracy tool calling   | Misurare baseline        | >95%                  |
| Human approval rate     | **100% su write action** | ~30% autonomo         |
| Query/giorno            | 5-10 (ramp up graduale)  | 20+                   |
| Incidenti sicurezza     | Zero                     | Zero                  |
| Data leak               | Zero                     | Zero                  |

**Nota (RC-11):** Non targettare "approval <10%" dal giorno 1. Primi 30 giorni = approval su tutto, poi ridurre classe per classe basandosi sui dati reali.

### Timeline

| Settimana | Focus                              |
| --------- | ---------------------------------- |
| 1         | Setup + config                     |
| 2         | Test intensivo scenari             |
| 3         | Pilot con client reali (5-10 casi) |
| 4         | Valutazione e scaling plan         |

---

## 10. Costi Reali

### Per 5 Agent

| Voce                          | Costo/mese                     |
| ----------------------------- | ------------------------------ |
| Gemini CLI × 5                | $0 (ogni Mac il suo free tier) |
| Claude API (supervisor)       | $20                            |
| Fly.io Gateway (2GB)          | $20                            |
| PostgreSQL audit (1GB)        | $10                            |
| Redis Upstash                 | $0 (free tier)                 |
| Elettricità (~$5/agent)       | $25                            |
| **Subtotale infra**           | **$55**                        |
| Sviluppo/maintenance (20h/wk) | $4,000                         |
| **TOTALE**                    | **~$4,055**                    |

### Per 10 Agent

| Voce                 | Costo/mese                     |
| -------------------- | ------------------------------ |
| Gemini CLI × 10      | $0 (ogni Mac il suo free tier) |
| Claude API           | $40                            |
| Fly.io Gateway (4GB) | $40                            |
| PostgreSQL (2GB)     | $20                            |
| Redis Upstash        | $10                            |
| Elettricità          | $50                            |
| **Subtotale infra**  | **$70**                        |
| Sviluppo (30h/wk)    | $6,000                         |
| **TOTALE**           | **~$6,070**                    |

### Per 15 Agent

| Voce                  | Costo/mese                     |
| --------------------- | ------------------------------ |
| Gemini CLI × 15       | $0 (ogni Mac il suo free tier) |
| Claude API            | $60                            |
| Fly.io Gateway + LB   | $60                            |
| PostgreSQL (4GB)      | $40                            |
| Redis Upstash         | $20                            |
| Elettricità           | $75                            |
| **Subtotale infra**   | **$155**                       |
| Sviluppo (40h/wk)     | $8,000                         |
| Training (una tantum) | $1,350                         |
| **TOTALE**            | **~$8,155 + $1,350 setup**     |

### Costi nascosti

| Voce                             | Stima                    |
| -------------------------------- | ------------------------ |
| Training per agente (3h × tasso) | $90-150/agent una tantum |
| Consulente legale UU PDP/GDPR    | $2,000 una tantum        |
| Backup S3/Tigris audit logs      | $50/mo                   |
| Monitoring (Datadog/Sentry)      | $100/mo per 15 agent     |

### Costo marginale per agent: ~$3.50/mo (solo infra)

Il costo dominante è sviluppo e manutenzione, non infrastruttura.

---

## 11. Rischi Residui

### 1. JWT Secret Compromise

**Rischio:** Se JWT_SECRET compromesso, tutti gli agent sono vulnerabili.
**Monitoraggio:** Alert su rotation >30 giorni, audit tutte le richieste gateway.
**Mitigazione:** JWT automatic rotation ogni 7 giorni.

### 2. Offline Sync Conflict

**Rischio:** Due agent modificano stesso record offline → data corruption.
**Monitoraggio:** Flag automatico su campi critici, dashboard conflitti giornaliera.
**Mitigazione:** LWW per non-critici, human review per critici (`visa_status`, `tax_id`).

### 3. Compliance Cross-Border

**Rischio:** Client EU → agent Indonesia → server Singapore (3 giurisdizioni).
**Monitoraggio:** Geo-IP logging per ogni richiesta, PII detection pre-storage.
**Mitigazione:** Encryption in-transit, WORM storage, auto-redaction PII.

---

## 12. Quick Wins

Tre cose implementabili **oggi** con l'infrastruttura esistente, senza nuovo codice significativo.

### 11.1 JWT su MCP Server (2 ore)

```python
# apps/nuzantara-mcp/nuzantara_mcp/server.py
# Aggiungi all'inizio di ogni tool handler:
def tool_handler(self, request):
    jwt = request.headers.get("Authorization")
    if not verify_jwt(jwt, self.role):
        return {"error": "Unauthorized"}
```

Blocca bypass diretto al MCP server.

### 11.2 Telegram Approval Flow (1 ora)

```python
# Estendi apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py
# Il bot esiste già, aggiungi:
if decision_needs_human(evidence_score < 0.15):
    await telegram_request_approval(agent_id, query, context)
```

Human-in-the-loop senza nuova infrastruttura.

### 11.3 RBAC YAML Config (30 minuti)

```yaml
# backend/config/agent_roles.yaml
visa_specialist:
  - "check_visa_requirements"
  - "calculate_visa_fee"
  - "submit_visa_application"
  # ... 20 altri tools

tax_consultant:
  - "ask_legal_tax"
  - "track_compliance_tax"
  # ... 17 altri tools
```

Limita tool exposure per ruolo senza riscrivere MCP.

---

## 13. Case Studies Esterni

### 12.1 Algo Insights — 6 Agenti OpenClaw

- 6 agenti specializzati (Chief of Staff, Engineer, Reviewer, etc.)
- Gestiscono 2 newsletter + 1 repository GitHub autonomamente
- Interfaccia: Telegram
- Risparmio: 6 ore/giorno di lavoro manuale
- Pattern: modelli ibridi (heavy per coordinamento, light per routine)

### 12.2 Healthcare Compliance — 13 Agenti

- Sistema di 13 agenti per monitoraggio deadlines legali
- Pattern "Heartbeat" cron per check periodici
- Successo: prevenuto una penalità identificando email auditor non letta dopo 6 giorni

### 12.3 Felix Craft — Autonomous Entrepreneur

- Agente con budget $1,000
- Ha lanciato un info-product + marketplace ("Claw Mart")
- Revenue: >$62,000 in 3 settimane
- Paga autonomamente i propri costi API

### 12.4 A2A Protocol in Enterprise

- Loan Approval Workflow: RiskAssessment + Compliance agents via A2A
- IT Helpdesk: troubleshooting agents senza condividere credenziali
- Standard: OAuth 2.1 Client Credentials per M2M auth
- Sfida: discovery decentralizzata resta friction point

### 12.5 Pattern Comuni 2026

- **UI primaria:** Telegram/Slack (non web dashboard)
- **Memory:** `MEMORY.md` files (pattern Anthropic)
- **Modelli:** Ibridi — heavy per coordinamento, light per routine
- **Protocollo:** A2A per coordinamento orizzontale, MCP per integrazione verticale

---

## 14. Appendice — Output Raw per Modello

### Dispatch log

| #   | Passaggio | Modello          | Comando   | Durata  | Parole | Costo   |
| --- | --------- | ---------------- | --------- | ------- | ------ | ------- |
| 1   | P1        | Gemini 3.1 Pro   | explore   | 122s    | 918    | $0      |
| 2   | P1        | Gemini 3.1 Pro   | search    | 53s     | 857    | $0      |
| 3   | P1        | DeepSeek R1 671b | reasoning | 145s    | 1,090  | $0.012  |
| 4   | P1        | Codex 5.4        | sandbox   | 300s ⏰ | —      | timeout |
| 5   | P2        | Gemini 3.1 Pro   | explore   | 178s    | 682    | $0      |
| 6   | P2        | DeepSeek R1 671b | reasoning | 234s    | 1,642  | $0.015  |
| 7   | P2        | Gemini 3.1 Pro   | search    | 114s    | 815    | $0      |
| 8   | P3        | DeepSeek R1 671b | reasoning | 77s     | 916    | $0.006  |
| 9   | P3        | Gemini 3.1 Pro   | search    | 112s    | 1,194  | $0      |
| 10  | P3        | Gemini 3.1 Pro   | explore   | 148s    | 821    | $0      |
| 11  | P4        | DeepSeek R1 671b | reasoning | 201s    | 1,490  | $0.015  |
| 12  | P4        | Gemini 3.1 Pro   | search    | 83s     | 1,018  | $0      |

**Totale:** 12 dispatch, ~1,771s (29.5 min), ~10,443 parole, ~$0.048

### File salvati

Tutti gli output raw sono in `ai-dispatch-output/` con hash SHA-256:

- `20260325-082904-gemini-explore-4b3c2fe7.md`
- `20260325-082759-gemini-search-53fad033.md`
- `20260325-082936-deepseek-reasoning-*.md`
- `20260325-083604-gemini-explore-4e19ca02.md`
- `20260325-083517-gemini-search-54490338.md`
- `20260325-083714-deepseek-reasoning-*.md`
- `20260325-083952-gemini-search-99ae2033.md`
- `20260325-084036-gemini-explore-caca142a.md`
- `20260325-084233-gemini-search-d8b7a57b.md`
- `20260325-084429-deepseek-reasoning-*.md`

---

_Generato il 2026-03-25 da Claude Code (Opus 4.6) con brainstorming multi-modello a 4 passaggi._
