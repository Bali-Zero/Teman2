# SOLIDIFICATION PROMPT 11 — MCP Server
# Machine: AIR | Model: Claude Opus 4.6 MAX | Component: MCP Server

---

## IDENTITA E RUOLO

Sei un architetto di tool server MCP (Model Context Protocol) di produzione. Analizzi il server MCP di Nuzantara — 131 tools, 24 moduli, 10 prompts, 5 resources, 8 workflow chains. E l'interfaccia principale tra AI agent e il sistema. Un tool rotto = l'AI non puo operare.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Non aggiungere tool se non servono. La vera potenza e nella qualita di ogni tool, non nella quantita. 131 tool e gia molto — valuta se alcuni vanno uniti o rimossi.

**NOTA MACCHINA:** Sei su Air. Venv e `venv`. Path: `~/Projects/nuzantara/apps/nuzantara-mcp/`.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/nuzantara-mcp/nuzantara_mcp/
  tools/                                               # 24 moduli tool
    admin.py, analytics.py, comms.py, compliance.py
    content.py, crm.py, drive.py, federation.py
    google_bridge.py, health.py, intel.py, invoicing.py
    journey.py, knowledge.py, langsmith.py, legal.py
    memory.py, naga.py, portal.py, pricing.py
    prime.py, sheets.py, workflows.py
    + altri
  prompts/                                             # 10 prompt templates
  resources/                                           # 5 resources
  chains/                                              # 8 workflow chains
  server.py                                            # Server entry point
  config.py                                            # Configurazione
```

Mappa:
1. **Tool inventory**: ogni tool, cosa fa, input/output, dipendenze backend
2. **Error handling**: cosa succede quando un tool fallisce? Il client riceve errore strutturato?
3. **Tool overlap**: tool che fanno cose simili o duplicate
4. **Input validation**: ogni tool valida i suoi input?
5. **Performance**: tool che fanno chiamate lente (LLM, external API) — c'e timeout?
6. **Chain architecture**: come funzionano gli 8 workflow chain, sono robusti?
7. **Resource management**: connection lifecycle, cleanup
8. **Testing**: ci sono test per i tool? Coverage?

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza il MCP server in apps/nuzantara-mcp/. Focus: 1) tool che non vengono mai chiamati (dead tools), 2) tool con error handling mancante, 3) chain workflow — sono idempotenti?, 4) overlap tra tool simili (es. search_intel vs search_kbli vs search_emails), 5) tool che fanno troppe cose (violano single responsibility)"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Testa il MCP server: 1) chiama ogni tool con input vuoto — gestisce gracefully?, 2) chiama tool con input malformato — errore strutturato?, 3) chiama tool durante backend down — timeout e retry?, 4) chain workflow — cosa succede se uno step fallisce a meta?, 5) resource cleanup — connection leak dopo N chiamate?"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "MCP server con 131 tool, 8 workflow chain, usato da Claude Code + OpenClaw + potenzialmente altri client. Domande: 1) Qual e il numero ottimale di tool per un MCP server? (cognitive load per l'AI che li usa) 2) Come organizzare tool in namespace gerarchici per ridurre ambiguita? 3) Pattern per tool composition (tool che chiama tool) senza creare dipendenze circolari? 4) Come implementare circuit breaker per tool che dipendono da external API?"
```

### 2d. Deep Research
- MCP (Model Context Protocol) best practices 2025-2026
- Tool server architecture at scale
- Workflow chain patterns (saga, choreography)
- MCP tool testing patterns
- AI tool design: naming, description, parameter design per massimizzare LLM tool use accuracy

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Inventario: ogni tool con usage stats (quante volte chiamato nell'ultima settimana)
- Rimuovere dead tools (mai chiamati)
- Unire tool overlap (es. 3 search diversi → 1 search con filtro)
- Rinominare tool con naming inconsistente
- Pulire description: ogni tool deve avere description chiara per l'AI

### B. IRROBUSTIMENTO
- Error handling uniforme: ogni tool ritorna `{success: bool, data/error, metadata}`
- Input validation: schema validation su ogni tool input
- Timeout: 30s default, 60s per tool che chiamano LLM, 5s per health
- Circuit breaker: tool con external dependency ha CB (3 fail → open 60s)
- Rate limiting: per tool e per user (evita abuse)
- Retry: automatico per errori transient (network, 503)

### C. POTENZIAMENTO
- Tool analytics: tracking di latency, success rate, usage per tool
- Namespace organization: `crm.*`, `intel.*`, `admin.*` per chiarezza
- Tool composition: tool che orchestrano altri tool (macro-tool)
- Streaming: tool che producono output incrementale (es. search results)
- Context enrichment: tool che aggiungono automaticamente contesto rilevante

### D. AUTOMATISMO EVOLUTIVO
- Auto-documentation: genera docs da codice (input/output schema, examples)
- Health monitoring: cron che testa ogni tool ogni ora
- Performance regression: alert se un tool diventa piu lento del suo p95 storico
- Usage-based optimization: tool piu usati → ottimizzati prima
- Tool suggestion: basato su query pattern, suggerisci tool che l'AI non ha usato

### E. METRICHE
- Tool success rate: > 99% per tool
- Tool latency p95: < 5s per CRUD, < 30s per LLM-based
- Input validation coverage: 100%
- Error message quality: ogni errore e azionabile (non generico)
- AI tool selection accuracy: > 90% (l'AI sceglie il tool giusto)

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione MCP Server: [PIANO]. Focus: 1) impatto su Claude Code e OpenClaw (131→? tool), 2) backward compatibility se rinomini tool, 3) chain workflow robustezza, 4) cognitive load per l'AI con troppi tool"
```

---

## CONTESTO

- MCP v2.1: 131 tools (era 109), 10 prompts, 5 resources, 8 chains
- Usato da: Claude Code (Pro), OpenClaw (Pro+Air), potenzialmente Gemini CLI
- Backend dependency: quasi tutti i tool chiamano il backend RAG via HTTP
- Chains: daily_ops_autopilot, compliance_autopilot, intel_pipeline, new_client_onboarding, client_health_monitor, practice_lifecycle_check, weekly_report, journey_accelerator
- mcporter bridge: 129 tool accessibili anche da OpenClaw
- Tool description quality: variabile — alcuni chiari, altri ambigui per l'AI
