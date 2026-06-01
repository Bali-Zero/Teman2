# FASE 2 BRIEF — Deep Research Agentico (calibrato sui findings REALI della FASE 1)

> Ogni LLM legge questo + il MISSION-BRIEF. La FASE 1 ha mappato il codice reale.
> Questi sono i PROBLEMI VERI emersi — la ricerca deve connettere SOTA agentico 2026
> a QUESTI problemi specifici di Nuzantara, non a problemi generici.

## STATO REALE DEL SISTEMA AGENTICO (FASE 1, verificato sul codice)

~241 entità censite. ~65% operativo. Problemi concreti:

### Auto-miglioramento ROTTO a ogni giunto (il buco più strategico)
- `agent-library-evolver` (Voyager/EvoSkill): generation=0, MAI evoluto una volta.
  DEEPSEEK_API_KEY mancante, 3 run falliti di fila. Frontier congelato.
- `wr3.reflexion`: morto al lancio (OS_REASON_CODESIGNING, interprete .venv non parte).
- `wr2.reflexion`: vivo ma A VUOTO (carousel_runs=0, la pipeline non lo alimenta).
- `federation_orchestrator.py`: graph.compile() SENZA checkpointer, idle dal 2026-05-08,
  human_checkpoint = input() bloccante (non interrupt LangGraph durabile).
→ Architettura sofisticata (Voyager+Reflexion+anti-self-justification) ma il LOOP NON SI
  CHIUDE. Domanda di ricerca: come SOTA 2026 chiude il loop di self-improvement in produzione?

### organism supervisor: shadow mode (decide ma non agisce)
- `com.nuzantara.organism.supervisor`: consuma 92k eventi Redis, attua ZERO. W1
  LLM-tiers-disabled. Brain che osserva ma non muove le mani.
→ Ricerca: pattern observe→decide→act sicuri (Law 5), quando un organism deve attuare.

### Frontend: agenti assenti dove servono ai clienti
- "Ask Zantara" FAB pubblico = pulsante MORTO (widget completo solo in .backup) → funnel
  lead spento.
- Portale cliente: solo messaggistica umana, NESSUN copilot (il team ne ha uno su ogni
  pagina workspace). Asimmetria cliente/team.
- KBLI-navigator, dashboard: read-only su AI, nessun agente conversazionale.
→ Ricerca: customer-facing AI agents (copilot portale, lead-qualifier, RAG-chat pubblico)
  SOTA 2026 per legal/immigration/proptech.

### Duplicati (5 relazioni — candidati eliminazione/merge)
- wr2-brief-interpreter ≈ wr3-brief-interpreter (stesso ruolo NB-grounding, 2 pipeline)
- wr2-external-bench ≈ wr3-editorial-bench (stesso design SOTA-bench)
- canva_renderer v1 (legacy) vs v2 (solo v2 importato)
- wa-mirror vs wa-mirror-launcher (solo launcher live)
- namespace com.balizero.* vs com.nuzantara.* (orphan dup, no reconciliation job)
→ Ricerca: quando merge-agenti vs tenere separati; macro-agente che astrae N pipeline.

### Macro-gruppi SENZA comandante (zone non governate)
- mata-garuda OSINT (40+ harvester scattered, no orchestratore, KG morto 2 entità/0 rel)
- nuzantara-mcp chains (8 chain code-complete ma NESSUNA auto-invocata)
- intel-lake, sentinel, monitors, wa-mirror = peer scattered
→ Ricerca: macro-agente/supervisor pattern per governare zone scattered; knowledge-graph
  agentico (perché il KG mata-garuda è morto? come i leader fanno KG-memory?).

### WR3 video pipeline: INCERTO al 100% (13 agenti mai a regime)
- wr3.supervisor ROTTO (binary missing), .openclaw/bin/wr3/ cancellato, no episodic-log.
→ Ricerca: vale la pena? o è over-engineering? cosa fa SOTA video-agent 2026?

## LE 30+ QUERY (aree — spingi MOLTE query per area, budget forte)

Per OGNI area: "esiste in Nuzantara? in che forma (cita FASE 1)? gap vs SOTA? opportunità?"

1. **Self-improvement loop in produzione** (Voyager, Reflexion, ADAS, agent-as-optimizer,
   curriculum, skill-library che cresce davvero) — come si chiude il loop? checkpointer durabile?
2. **Agent memory SOTA 2026** (MemGPT/Letta, episodic+semantic, knowledge-graph memory,
   reflection-into-memory) — Nuzantara ha MOS + KG morto, come potenziare?
3. **Observe→decide→act** safe autonomy (organism che attua, approval-gate, Law-5 patterns,
   human-in-the-loop durabile LangGraph interrupt)
4. **Customer-facing agents** (portale copilot, lead-qualifier conversazionale, RAG-chat
   pubblico) per legal/immigration/tax/proptech — cosa fanno i leader?
5. **Macro-agent / supervisor topology** (governare zone scattered, orchestrator-of-
   orchestrators, hierarchical agent org)
6. **Knowledge-graph agentico** (perché KG muore? GraphRAG, entity-resolution agents,
   come legaltech costruisce KG vivi)
7. **Multi-agent consolidation** (quando merge agenti duplicati, abstraction layer su N
   pipeline, DRY per agenti)
8. **Document-AI agents** (akta/OCR/contract-extraction) per immigration/company
9. **Browser/computer-use agents** (portali governativi indonesiani, automazione form)
10. **Voice/WhatsApp agents** (il canale #1 di Bali Zero — SOTA conversational)
11. **Predictive agents** (client-churn, upsell, deadline-sentinel)
12. **Agent evals/observability** (trajectory eval, LLM-judge calibrato, LangSmith 2026)
13. **Game-changer 2026** — cosa di NUOVO è uscito che Nuzantara potrebbe cavalcare?

## RUOLO PER LLM (FASE 2)
- **agy Gemini 1M**: ingestion long-context di paper/repo SOTA, le query 1-6 (architettura)
- **Codex GPT-5.5**: query 7-12 (implementazione, document-AI, browser, evals — code-grounded)
- **DeepSeek V4 Pro**: query su numeri/economics (multi-agent cost, ROI, quando-non-conviene)
- **Claude (Workflow)**: orchestrazione + query 4,10,11,13 (customer/voice/predictive/game-changer)
  + sintesi finale

## OUTPUT FASE 2
Ogni LLM scrive i suoi findings in research/agent-craft/census-raw/fase2-<llm>.md.
Poi sintesi → research/agent-craft/census-raw/fase2-synthesis.md: per ogni area, SOTA +
fit-Nuzantara + opportunità concreta con ROI. Questo alimenta la FASE 3 (le 5 liste).
