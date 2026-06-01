# MISSION BRIEF — Censimento + Deep Research Agentico Nuzantara

> Documento di calibrazione. OGNI LLM (Claude, Codex, agy, DeepSeek) legge questo PRIMA
> di iniziare, e lo ri-legge durante le deep-research query per restare allineato al fine.
> REGOLA D'ORO: leggere il CODICE REALE (grep/Read/file), MAI fidarsi della documentazione
> o della memoria. La doc mente, il codice no. Ogni numero/claim derivato da tool in-turn.

## CHI È NUZANTARA
Organismo AI per Bali Zero (agenzia indonesiana: immigration/visa/KITAS/KITAP, company
setup/PT-PMA/KBLI, tax, property). Backend Python/FastAPI su Fly.io + frontend Vercel.
"Organismo vivo" con 8 Leggi Symbiosis. RAG su Qdrant. ~11.699 clienti CRM.

## CENSIMENTO GREZZO (numeri VERI dal disco 2026-06-02, da espandere)
- **34** agenti in `~/.claude/agents/*.md` (definizioni Claude Code)
- **169** LaunchAgent `com.{nuzantara,balizero,cell}.*.plist` (daemon/cron)
- **17** chain MCP (`chain_*` tool: onboarding, compliance, daily-ops, intel-pipeline,
  journey, client-health, practice-lifecycle, weekly-report...)
- **75** servizi in `apps/backend-rag/backend/services/`
- **5** canali in `apps/backend-rag/backend/channels/` (WhatsApp, Telegram, IG, Web, +1)
- **33** app in `apps/` (backend-rag, mouth, cell, mata-garuda, war-room, crm-cell,
  team-agent, nlm-bridge, osint-nexus-ui, graph-engine, remediator, evaluator...)
- federation_orchestrator.py (LangGraph), agent_start.py (worktree broker), Workflow tool

## FASE 1 — MAPPATURA DEL SISTEMA AGENTICO (leggi il CODICE)

Censisci OGNI entità agentica (backend + frontend + tooling). Per ciascuna determina:

1. **OPERATIVO/FUNZIONANTE** — gira davvero? prova empirica (launchctl print active, log
   mtime recente, ultimo run, codice importato e raggiungibile, test verdi).
2. **ROTTO o MAI USATO** — binary_missing, daemon dead, 0 importer, branch quarantena
   (.disabled-*), TODO/stub, errore in log, scar aperta.
3. **MACRO-GRUPPI** — quali agenti formano un sottosistema coeso? (es. WR2-carousel =
   8 subagent; WR3-video = 8; CRM = N servizi; intel/OSINT = N; mata-garuda = N;
   Symbiosis/organism = N). Disegna la mappa dei gruppi.
4. **ZONE CARENTI** — dove c'è lavoro manuale/ripetitivo che NESSUN agente copre?
   (es. lead-qualification, document-OCR-triage, deadline-sentinel, onboarding...)

Metodo: `ls ~/.claude/agents/`, `Read` ogni .md; `launchctl print gui/$(id -u)/<label>`
per stato daemon; `grep -r` per import/usage; leggi `apps/backend-rag/backend/services/`,
`channels/`, `chain_*`; verifica `.disabled-*` quarantine; cross-check con
`organs_registry.yaml` e `cicatrix-scars.md` (scar = rotture note).

## FASE 2 — DEEP RESEARCH IMPONENTE (several queries, budget forte)

Dopo la mappa, ricerca a tappeto lo STATO-DELL'ARTE agentico 2026 CONNESSO a cosa può
fare Nuzantara. Spingi MOLTE query (30+), non poche. Aree:

- **Orchestration patterns** SOTA (oltre orchestrator-worker: hierarchical, blackboard,
  market/auction, graph-of-agents, swarm) — quale si applica a Nuzantara?
- **Agent memory** (long-term, episodic, semantic, reflection, MemGPT/Letta, knowledge-graph
  memory) — Nuzantara ha MOS, come potenziarlo?
- **Tool-use & function-calling** SOTA (parallel tools, tool-RAG, MCP ecosystem 2026)
- **Self-improvement** (Voyager skill-library, Reflexion, ADAS automated agent design,
  agent-as-optimizer) — Nuzantara ha Voyager+Reflexion, cosa manca?
- **Evals & observability** per agenti (LangSmith, trajectory eval, LLM-as-judge calibrato)
- **Multi-agent economics** (token cost, quando multi-agent perde, 15× chat finding)
- **Domain-specific agents** per legal/immigration/tax/RAG-legale (cosa fanno i leader?)
- **Vertical AI agents 2026** (cosa stanno costruendo le agenzie/legaltech/proptech?)
- **Game-changer tech**: computer-use agents, browser-agents (portali governativi),
  voice agents (WhatsApp), document-AI (akta/OCR), predictive (client churn/upsell)

Per OGNI tema: "esiste in Nuzantara? in che forma? gap vs SOTA? opportunità concreta?"
Cita fonti primarie (Anthropic, arXiv, framework docs), verifica le claim (adversarial).

## FASE 3 — PROPOSTE (5 liste azionabili)

1. **ELIMINARE** — agenti duplicati / rotti-non-vale-la-pena-aggiustare. Per ognuno:
   perché, cosa si perde (niente?), come rimuovere safe.
2. **MACRO-AGENTI da creare** — se esistono gruppi coesi senza un "comandante", proporre
   un macro-agente orchestratore che governa la zona (es. un "CRM-commander", un
   "Immigration-commander"). Zone mappate e governate, non sparse.
3. **RIPARARE** — agenti rotti che VALGONO la pena. Diagnosi + fix plan + effort.
4. **POTENZIARE** — agenti operativi che possono fare di più (memoria, tool, evals,
   self-improvement). Before/after.
5. **CREARE game-changer** — agenti nuovi ad alto impatto che oggi mancano. Per ognuno:
   problema risolto, ROI, tech SOTA che abilita, fit con Nuzantara.

## VINCOLI (Symbiosis + CLAUDE.md)
- Law 1: solo CLI/OAuth LLM, mai ANTHROPIC_API_KEY. DeepSeek API OK.
- Law 2: PII/OSINT mai fuori dal Pro, reasoning su dati sensibili solo Ollama locale.
- Law 5: organismo propone, Zero decide. Mai auto-publish/send.
- Law 7: numeri prima — ogni claim con evidenza, benchmark before/after.
- Anti-hallucination: codice reale, non doc/memoria. Tool in-turn per ogni numero.

## OUTPUT
Dossier strategico unico: mappa macro-gruppi + matrice (ogni agente × stato
operativo/rotto/duplicato/mai-usato) + 5 liste con priorità e ROI. Antonello legge e decide.
