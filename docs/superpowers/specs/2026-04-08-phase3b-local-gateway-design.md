# Phase 3B — Local Gateway: Widget → Gemini CLI

> **Data:** 2026-04-08
> **Metodo:** Brainstorming multi-modello (Gemini Explore + DeepSeek Reasoning + Claude Giudice + NB-1 validation)
> **Decisione:** Opzione A — Local HTTP Gateway che spawna Gemini CLI headless
> **Status:** Design spec — da approvare prima di implementazione

---

## 1. Problema

Il widget workspace su `kita.balizero.com` (`WorkspaceAssistant.tsx`) chiama il backend RAG centralizzato su Fly.io (`POST /api/agentic-rag/workspace-stream`). Deve invece connettersi al Gemini CLI locale del team member, autenticato col proprio account Google Workspace (@balizero.com), con `server_agent.py` come MCP server filtrato per ruolo.

### Perché cambiare

| Aspetto | Oggi (backend RAG) | Domani (local gateway) |
|---------|--------------------|-----------------------|
| Costo LLM | Gemini API a pagamento su Fly.io | $0 (Gemini CLI free tier) |
| Modello | Gemini 2.5 Flash (backend) | Gemini 3 Flash (CLI Auto routing, apr 2026) |
| RPM | Condiviso | 60 RPM indipendenti per team member (960 totali per 16) |
| Tool disponibili | 9 nel ReAct loop | 37-96 via MCP server_agent.py |
| Tool calling | Backend orchestrator | Gemini CLI nativo (ReAct loop interno) |
| Contesto Google | Nessuno | Account Workspace del team member |
| Fallback | Nessuno | Gemma 4 via Ollama locale |

---

## 2. Architettura

```
kita.balizero.com (Vercel, HTTPS)
  │
  │ fetch("https://127.0.0.1:8090/v1/chat", SSE)
  │ (127.0.0.1 è secure context — no mixed content block)
  │ CORS: Access-Control-Allow-Origin: https://kita.balizero.com
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│  zantara-gateway (Python, ~250 righe, porta 8090)       │
│  TLS: mkcert localhost cert                             │
│  Auth: HMAC token nel header (installato da admin)      │
│                                                         │
│  ┌─ Primario: Gemini CLI ──────────────────────────┐    │
│  │ gemini -p "{query}" -o stream-json -y           │    │
│  │   --allowed-mcp-server-names nuzantara          │    │
│  │ Modello: Gemini 3 Flash (Auto routing, 60 RPM)  │    │
│  │ → agent loop completo con 37-96 MCP tool        │    │
│  │ → NDJSON stdout convertito a SSE                │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─ Fallback: Ollama Gemma 4 + MCP tool ───────────┐    │
│  │ POST http://localhost:11434/api/chat            │    │
│  │ model: gemma4:e2b (8GB) / gemma4:e4b (16GB)    │    │
│  │ tools: definizioni da server_agent.py via MCP   │    │
│  │ → mini ReAct loop nel gateway (max 3 iter)      │    │
│  │ → se tool calling fallisce 2x → knowledge-only  │    │
│  │ → streaming JSON convertito a SSE               │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─ Health ────────────────────────────────────────┐    │
│  │ GET /health → {"status","gemini","ollama","role"}│    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
  │
  │ stdio
  ▼
┌─────────────────────────────────────────────────────────┐
│  server_agent.py (MCP server, già esistente)            │
│  AGENT_ROLE=visa_specialist → 37 tool                   │
│  NUZANTARA_API_KEY=<token> → autentica su Fly.io        │
│  I tool chiamano il backend Fly.io via HTTPS            │
└─────────────────────────────────────────────────────────┘
```

### Data flow per una query

1. Team member digita nel widget su `kita.balizero.com`
2. Widget fa `fetch("https://127.0.0.1:8090/v1/chat", {method: "POST", headers: {"X-Gateway-Token": "..."}, body: {query, session_id, conversation_history}})`
3. Gateway verifica HMAC token
4. Gateway spawna: `gemini -p "{enriched_query}" -o stream-json -y --allowed-mcp-server-names nuzantara`
5. Gemini CLI avvia il suo ReAct loop interno:
   - Legge i tool da `server_agent.py` (filtrati per ruolo)
   - Decide quale tool chiamare
   - Esegue il tool via stdio → tool chiama backend Fly.io
   - Legge il risultato, decide se servono altri tool
   - Produce risposta finale
6. Gateway legge NDJSON da stdout, converte a SSE (`data: {"type":"token","data":"..."}`)
7. Widget riceve SSE, renderizza in streaming (stesso pattern di oggi)

### Fallback chain

```
Gemini CLI (60 RPM con Gemini 3 Flash via Auto routing, $0, tool calling completo)
  │ se exit code != 0 o timeout 60s
  ▼
Ollama Gemma 4 + MCP tool (illimitato, $0, mini ReAct loop nel gateway)
  │ max 3 iterazioni tool per query
  │ se tool calling fallisce 2x consecutivi → degrada a knowledge-only
  │ se Ollama non risponde
  ▼
Errore: "Assistente temporaneamente non disponibile"
```

Il fallback Ollama ha accesso agli stessi MCP tool di Gemini CLI, via `server_agent.py` (stesso stdio, stesso filtro per ruolo). La differenza è che il ReAct loop è gestito dal gateway (~50 righe) invece che dal CLI internamente:

1. Gateway chiama Ollama `/api/chat` con `tools` parameter (definizioni tool da MCP)
2. Gemma 4 decide tool call → gateway esegue via MCP SDK (stdio) → feed result back
3. Loop fino a risposta finale o max 3 iterazioni
4. Se il modello è troppo piccolo (e2b) e il tool calling fallisce 2 volte consecutive nella stessa query, il gateway degrada a knowledge-only per quella query (niente tool, solo LLM response)

---

## 3. Modifiche al widget (WorkspaceAssistant.tsx)

Cambio minimo — solo l'URL di destinazione:

```typescript
// Oggi
const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL; // nuzantara-rag.fly.dev
const res = await fetch(`${BACKEND}/api/agentic-rag/workspace-stream`, ...);

// Domani — dual path
const LOCAL_GATEWAY = "https://127.0.0.1:8090";
const CLOUD_BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL;

async function chat(query: string) {
  try {
    // Prova gateway locale
    const res = await fetch(`${LOCAL_GATEWAY}/v1/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Gateway-Token": getGatewayToken(), // da localStorage
      },
      body: JSON.stringify({ query, session_id, conversation_history }),
    });
    if (!res.ok) throw new Error(`Gateway error: ${res.status}`);
    return res; // SSE stream
  } catch {
    // Fallback al backend RAG su Fly.io (come oggi)
    return fetch(`${CLOUD_BACKEND}/api/agentic-rag/workspace-stream`, {
      credentials: "include", // JWT cookie
      ...
    });
  }
}
```

Il widget prova localhost prima. Se il gateway non risponde (Mac spento, non configurato), cade sul backend RAG esistente. Zero regressione per chi non ha il gateway.

### Config senza redeploy

Il gateway token viene salvato in `localStorage` al primo accesso. Il team member fa:
1. Apre `kita.balizero.com`
2. Widget mostra "Configura assistente locale" (se nessun token in localStorage)
3. Team member inserisce il token (fornito da Zero durante setup)
4. Widget salva in localStorage, usa per tutte le richieste successive

Nessuna env var Vercel, nessun redeploy. Se la porta cambia, il gateway token encoding include la porta.

---

## 4. Endpoint del gateway

### POST /v1/chat

```
Request:
  Headers: X-Gateway-Token: <hmac_token>
  Body: {
    "query": "Tampilkan klien saya yang visa-nya expire bulan ini",
    "session_id": "ws_damar",
    "conversation_history": [{"role": "user", "content": "..."}, ...]
  }

Response: SSE stream
  data: {"type": "token", "data": "Berikut"}
  data: {"type": "token", "data": " klien"}
  data: {"type": "tool_call", "data": {"name": "get_expiry_alerts", "args": {}}}
  data: {"type": "tool_result", "data": {"name": "get_expiry_alerts", "result": "..."}}
  data: {"type": "token", "data": " yang expire..."}
  data: [DONE]
```

Il formato SSE è identico a quello che il widget già parsa (`type: "token"` con `data` stringa). Tool call/result sono eventi opzionali per mostrare al team member cosa sta facendo l'agent.

### GET /health

```
Response: {
  "status": "ok",
  "gemini_cli": true,
  "ollama": true,
  "ollama_model": "gemma4:e4b",
  "role": "visa_specialist",
  "agent_name": "Damar",
  "version": "1.0.0"
}
```

### GET /v1/config

```
Response: {
  "role": "visa_specialist",
  "agent_name": "Damar",
  "tools_count": 37,
  "primary_llm": "gemini-cli",
  "fallback_llm": "gemma4:e4b"
}
```

---

## 5. Warning NB-1 — Mitigazioni

### W1: Identity senza JWT

**Problema:** Il backend RAG oggi deriva l'identità dal JWT cookie server-side. Il gateway locale non ha JWT — chi garantisce che il team member non spoofi il ruolo?

**Mitigazione:**
- `AGENT_ROLE` è nella config installata dall'admin (script `install.sh`), non modificabile dal team member senza conoscenze tecniche
- Il gateway token (HMAC) è generato dall'admin e include il role nel payload — il gateway lo verifica
- I tool MCP chiamano Fly.io con `NUZANTARA_API_KEY` specifico per team member — il backend può verificare che il token corrisponde al ruolo dichiarato
- **Defense in depth ridotta** rispetto a JWT server-side, ma adeguata per il threat model (team member non-tecnico, non adversarial)

**Acceptance criteria:** Se un team member cambia `AGENT_ROLE` nella config locale, i tool MCP continueranno a funzionare solo se il suo `NUZANTARA_API_KEY` è autorizzato per quel ruolo sul backend. Il backend è l'ultimo baluardo.

### W2: Max 7 tool per LLM (degradation)

**Problema:** NB-1 cita "Max 7 MCP tools per Captain. LLMs degrade with >7 tools." Il visa_specialist ha 37 tool.

**Mitigazione:**
- Gemini CLI (2.5 Flash, 1M context) gestisce 37 tool meglio dei modelli più piccoli — il vincolo "max 7" era per i Captain nel sistema autonomo H24, non per un CLI interattivo
- Il vincolo "max 7" era specifico per l'architettura autonomous-agents-v2 (LangGraph Captains), non per tool calling diretto
- Gemma 4 in fallback ha tool calling nativo ma con 37 tool potrebbe degradare — in fallback però non ha tool, quindi il problema non si pone
- **Monitoring:** logghiamo tool_call accuracy nei primi 30 giorni. Se sotto 90%, riduciamo il tool set

### W3: Irreversibility guard

**Problema:** `resilience.py` definisce `IRREVERSIBLE_ENDPOINTS` che richiedono `confirm=True`.

**Mitigazione:**
- Gemini CLI con `-y` (YOLO mode) auto-approva tutto — ma `server_agent.py` ha già i write tool limitati (7 per visa_specialist)
- I write tool del team member sono a basso rischio: `log_interaction`, `update_practice_status`, `send_portal_message`
- Tool ad alto rischio (`create_client`, `create_practice`) sono solo per `executive_consultant`
- **Phase 3B scope:** non implementiamo approval Telegram nel gateway. Se serve, il team member chiede a Zero via `federation_send`. Approval flow sarà Phase 4.

---

## 6. Setup per team member

### Prerequisiti (installati da `install.sh`)

| Componente | Come | RAM |
|-----------|------|-----|
| Gemini CLI | `npm install -g @google/gemini-cli` | ~50MB |
| Node.js | `brew install node` | ~100MB |
| Python 3.11 | `brew install python@3.11` | ~100MB |
| nuzantara-mcp venv | `python3 -m venv .venv && pip install fastmcp httpx` | ~200MB |
| Ollama + Gemma 4 | `brew install ollama && ollama pull gemma4:e2b` | ~4GB (e2b) / ~6GB (e4b) |
| mkcert | `brew install mkcert && mkcert -install && mkcert localhost 127.0.0.1` | ~5MB |
| zantara-gateway | Singolo file Python, copiato da repo | ~50KB |
| **Totale** | | **~4.5GB** (e2b) / **~6.5GB** (e4b) |

Su Mac 8GB: e2b (4.5GB totale) lascia ~3.5GB per macOS + Chrome + gateway.
Su Mac 16GB: e4b (6.5GB totale) lascia ~9.5GB.

### Script di installazione (estensione di `install.sh`)

Lo script Damar esistente (`scripts/damar-node/install.sh`) viene esteso con:

```bash
# ─── 7. mkcert per TLS locale ────────────────────────────────────────────────
brew install mkcert 2>/dev/null || true
mkcert -install
mkdir -p "$HOME/.zantara-gateway"
mkcert -cert-file "$HOME/.zantara-gateway/cert.pem" \
       -key-file "$HOME/.zantara-gateway/key.pem" \
       localhost 127.0.0.1

# ─── 8. Gateway locale ───────────────────────────────────────────────────────
cp "$PROJECT_DIR/scripts/zantara-gateway/gateway.py" "$HOME/.zantara-gateway/"
cp "$PROJECT_DIR/scripts/zantara-gateway/config.json" "$HOME/.zantara-gateway/"

# Configura il gateway per questo team member
cat > "$HOME/.zantara-gateway/config.json" << CONFIG
{
  "port": 8090,
  "role": "visa_specialist",
  "agent_name": "Damar",
  "gateway_token": "$(python3 -c 'import secrets; print(secrets.token_hex(32))')",
  "gemini_cli": {
    "allowed_mcp_servers": ["nuzantara"],
    "timeout_seconds": 60,
    "yolo": true
  },
  "ollama": {
    "model": "gemma4:e2b",
    "url": "http://localhost:11434"
  },
  "cors": {
    "allowed_origins": ["https://kita.balizero.com"]
  },
  "tls": {
    "cert": "$HOME/.zantara-gateway/cert.pem",
    "key": "$HOME/.zantara-gateway/key.pem"
  }
}
CONFIG

# ─── 9. launchd auto-start ───────────────────────────────────────────────────
cat > "$HOME/Library/LaunchAgents/com.balizero.zantara-gateway.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.balizero.zantara-gateway</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(which python3)</string>
    <string>$HOME/.zantara-gateway/gateway.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.zantara-gateway/stdout.log</string>
  <key>StandardErrorPath</key><string>$HOME/.zantara-gateway/stderr.log</string>
</dict>
</plist>
PLIST

launchctl load "$HOME/Library/LaunchAgents/com.balizero.zantara-gateway.plist"
```

### Setup completo in un comando

```bash
curl -sL https://raw.githubusercontent.com/Balizero1987/Teman2/main/scripts/install-node.sh | DAMAR_TOKEN=xxx bash
```

L'admin (Zero) fornisce il token. Il team member esegue un comando. Tutto il resto è automatico.

---

## 7. Gemini CLI: opzioni headless verificate

```
gemini -p "{query}" -o stream-json -y --allowed-mcp-server-names nuzantara
```

| Flag | Significato | Verificato |
|------|------------|-----------|
| `-p "query"` | Headless mode, non-interactive | ✅ v0.36.0 |
| `-o stream-json` | Output NDJSON streaming su stdout | ✅ v0.36.0 |
| `-y` / `--yolo` | Auto-approva tutti i tool call | ✅ v0.36.0 |
| `--allowed-mcp-server-names` | Limita a MCP servers specificati | ✅ v0.36.0 |
| `--approval-mode yolo` | Alternativa a `-y` | ✅ v0.36.0 |

**Nota importante:** Gemini CLI in `-p` mode esegue il **ReAct loop completo** internamente — chiama tool, legge risultati, decide il prossimo passo, e loop fino alla risposta finale. Il gateway non deve implementare nessun agent loop.

**Modello:** Non specificare `--model`. Il CLI usa Auto routing che seleziona **Gemini 3 Flash** (aprile 2026) automaticamente. Free tier: 60 RPM, 1000 req/day per account. Con 16 team member @balizero.com = **960 RPM totali, $0.**

| Modello disponibile | Free tier | RPM | Note |
|---------------------|----------|-----|------|
| Gemini 3 Flash (default Auto) | ✅ | 60 | Raccomandato, usato dal CLI |
| Gemini 3.1 Pro | ❌ paid only | — | Non disponibile free |
| Gemini 2.5 Pro | ✅ | 5 | Fallback manuale se serve |

### NDJSON output format (stream-json)

> **⚠ DA VERIFICARE:** Il formato esatto dell'NDJSON non è stato verificato empiricamente (auth bloccava il test). I field names sotto sono basati su pattern comuni di Gemini CLI ma devono essere confermati durante la fase Build (Giorno 1). Il gateway dovrà adattare il parser al formato reale.

Ogni riga è un JSON object (formato stimato):

```jsonl
{"type":"textDelta","text":"Berikut "}
{"type":"textDelta","text":"klien "}
{"type":"toolCallStart","toolName":"get_expiry_alerts","args":{}}
{"type":"toolCallEnd","toolName":"get_expiry_alerts","result":"..."}
{"type":"textDelta","text":"yang expire..."}
{"type":"done"}
```

Il gateway converte a SSE:

```
data: {"type":"token","data":"Berikut "}
data: {"type":"token","data":"klien "}
data: {"type":"tool_call","data":{"name":"get_expiry_alerts"}}
data: {"type":"token","data":"yang expire..."}
data: [DONE]
```

---

## 8. Mixed content: verifica tecnica

**Fatto:** `127.0.0.1` è classificato come "potentially trustworthy origin" nella [W3C Secure Contexts spec](https://w3c.github.io/webappsec-secure-contexts/). Chrome, Safari, Firefox lo rispettano.

**Ma:** Ci sono report di inconsistenza tra `localhost` e `127.0.0.1`. Per sicurezza usiamo `127.0.0.1` esplicitamente nel fetch.

**Doppia garanzia:** mkcert genera un certificato TLS locale. Il gateway serve HTTPS. Il browser vede `https://127.0.0.1:8090` — nessun mixed content possibile.

**CORS:** Il gateway risponde con:
```
Access-Control-Allow-Origin: https://kita.balizero.com
Access-Control-Allow-Methods: POST, GET, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-Gateway-Token
Access-Control-Max-Age: 86400
```

---

## 9. File da creare/modificare

| File | Azione | Descrizione |
|------|--------|------------|
| `scripts/zantara-gateway/gateway.py` | **NUOVO** | Gateway HTTP locale (~250 righe) |
| `scripts/zantara-gateway/config.json` | **NUOVO** | Template config per team member |
| `scripts/install-node.sh` | **NUOVO** | Script generico (estende damar install.sh) |
| `apps/mouth/src/components/workspace/WorkspaceAssistant.tsx` | **MODIFICA** | Dual path: localhost prima, Fly.io fallback |
| `apps/mouth/src/components/workspace/GatewayConfig.tsx` | **NUOVO** | UI per inserire gateway token (una tantum) |

### File NON modificati

- `server_agent.py` — già funzionante, zero cambi
- `team_agent_config.py` — già funzionante, zero cambi
- `agentic_rag.py` — endpoint `/workspace-stream` resta per fallback
- Backend Fly.io — nessuna modifica

---

## 10. Rischi e mitigazioni

| Rischio | Severità | Mitigazione |
|---------|---------|-------------|
| Gemini CLI pre-1.0, breaking change in `-p` o `-o` | MEDIUM | Pinnare versione in `install.sh`. Testare prima di aggiornare. |
| mkcert cert scade (default 2y 3mo) | LOW | `launchd` script rigenera ogni anno |
| Team member non fa `gemini auth login` | HIGH | `install.sh` lo guida passo passo. `/health` endpoint verifica auth. |
| 37 tool degradano Gemini CLI tool calling | MEDIUM | Monitor accuracy 30 giorni. Ridurre se necessario. |
| Mac spento = assistente offline | ACCETTATO | Widget cade su backend RAG Fly.io. Team member informato. |
| Ollama mangia RAM su Mac 8GB | MEDIUM | e2b (4GB) testato. Se swap: disabilita Ollama, solo Gemini CLI. |

---

## 11. Metriche di successo (primi 30 giorni)

Coerente con RC-11 del brainstorming 25 marzo: **misurare, non targettare.**

| Metrica | Cosa misurare |
|---------|--------------|
| Gateway uptime | % tempo in cui `/health` risponde OK |
| Gemini CLI success rate | % query che completano senza fallback |
| Fallback rate | % query che cadono su Ollama |
| Tool calling accuracy | % tool call corretti (manual review su 50 query campione) |
| Latency p50/p95 | Tempo da query a primo token |
| Query/giorno per team member | Adozione naturale |

---

## 12. Pilot plan

| Fase | Giorni | Chi | Cosa |
|------|--------|-----|------|
| **Build** | 1-3 | Zero | Scrivere `gateway.py`, test su Pro |
| **Pilot Damar** | 4-10 | Zero + Damar | Installare su Mac Damar, 10 query/giorno supervisionate |
| **Validazione** | 11-15 | Zero | Review metriche, fix issues |
| **Rollout 5** | 16-25 | Zero | Estendere a 5 team member (executive_consultant) |
| **Rollout all** | 26-40 | Zero | Tutti i 16 team member |

### Criterio go/no-go dopo pilot Damar

- Gateway uptime > 95%
- Gemini CLI success rate > 80%
- Zero incidenti sicurezza
- Damar usa l'assistente volontariamente (non forzato)

---

## 13. Decisioni architetturali (ADR log)

| # | Decisione | Alternativa scartata | Motivo |
|---|-----------|---------------------|--------|
| 1 | Gemini CLI subprocess (non API) | Gemini API diretta | CLI ha ReAct loop + MCP tool gratis. API è solo LLM senza tool. |
| 2 | mkcert TLS (non plain HTTP) | `http://127.0.0.1` senza TLS | Garanzia zero mixed content su tutti i browser. 2 minuti setup. |
| 3 | `127.0.0.1` (non `localhost`) | `localhost` | `127.0.0.1` ha garanzia secure context universale. `localhost` no. |
| 4 | Spawn per request (non persistent) | Gemini CLI long-running process | Isolamento totale tra request. Pattern ffmpeg. Nessun state leak. |
| 5 | HMAC token (non JWT) | JWT locale | HMAC è sufficiente per auth locale. JWT è overkill senza server di emissione. |
| 6 | launchd (non pm2) | pm2, brew services | Nativo macOS. Zero dipendenze extra. |
| 7 | SSE (non WebSocket) | WebSocket | Widget già parsa SSE. Meno complessità. Unidirezionale è sufficiente. |
| 8 | Fallback Ollama con tool + degradation | Ollama senza tool | Gemma 4 ha tool calling nativo. Stessi MCP tool, mini ReAct loop (~50 righe). Degrada a knowledge-only solo se tool calling fallisce 2x. |
| 9 | Widget dual-path (local + cloud) | Solo local | Zero regressione. Chi non ha gateway usa il backend RAG come oggi. |

---

## 14. Relazione con architetture esistenti

### VASSAL (Phase 1-3)

VASSAL ha aggiunto ToolAuthorizer e ConfirmationService sul path backend RAG. Il gateway locale **bypassa** questo path — il tool filtering avviene in `server_agent.py` via `ROLE_TOOLS`, che è il mirror client-side di `team_agent_config.py`. Le due implementazioni sono allineate ma indipendenti.

### Agent Mesh V1 (Damar)

Agent Mesh V1 ha 3 canali per Damar: workspace widget, Telegram, Gemini CLI diretto. Questa spec modifica solo il canale 1 (workspace widget) per usare lo stesso stack del canale 3 (Gemini CLI). Il canale 2 (Telegram) resta invariato.

### Brainstorming 25 marzo

Questa spec implementa un sottoinsieme dell'architettura "18 Mac sudditi + Air padrone + Pro framework". Specificamente:
- ✅ Ogni Mac ha Gemini CLI col proprio account
- ✅ `server_agent.py` filtrato per ruolo
- ✅ Ollama fallback
- ⏳ Air come Super Node (non in scope Phase 3B)
- ⏳ Baileys WhatsApp (non in scope Phase 3B)
- ⏳ Redis Service Registry (non necessario per localhost)
- ❌ CRDT/offline (scartato per sempre, come da RC-2)
