# Brainstorm cross-LLM — Cell+Genoma+Organism × Automazioni × OpenClaw

**Data:** 2 May 2026
**Reviewer:** GPT-5.5 (Codex CLI xhigh) + Gemini 3.1 Pro (CLI) + DeepSeek V4 Reasoner (direct API)
**Owner:** Antonello Siano / Bali Zero / Nuzantara
**Conduttore:** Claude Opus 4.7

---

## Contesto del sistema (per arrivare a discussione informata)

### Cell-core framework (già implementato in `packages/cell-core/`)

Framework biological-lifecycle con 11 moduli:

- **`pulse.py`**: PulseLoop (sense→think→act→reflect→dream→mature). `single_pulse()` atomico, `run()` con `homeostasis.recommended_pulse_interval()`.
- **`genome.py`**: SQLite + FTS5. Schema `genome(id, cell_origin, type [skill|pattern|scar|insight|trajectory], scope [Project|Personal], procedure, precondition, success_criterion, valid_from, valid_to, confidence, uses, last_used, inherited_from, outcome, tokens, duration_ms, tags, tier, domain)`. APIs: `record_skill`, `record_scar`, `record_trajectory`, `inherit_genome`, `apply_inherited_genome`, `silence_skill`. Confidence start 0.5-0.9, +0.02/use cap 1.0, decay esponenziale `decay_unused_skills(0.95)`. Tier1 promotion 100+uses+0.85conf, tier2 30+uses+0.70conf. 11 domini canonici (visa/tax/kbli/property/legal/crm/news/architecture/rag/graph/generic).
- **`hgt/`** (Horizontal Gene Transfer): `publisher.py` broadcast Redis Stream `cell:skills` per skill conf≥0.7 scope=Project type≠scar. `consumer.py` subscribe by domain filter, integra con decay 0.9. `feedback.py` child→parent vertical feedback. Degrada gracefully se Redis offline.
- **`safety.py`**: SafetyGate async + DNALoader/DNAInterpreter (rules engine).
- **`reasoner.py`**: ReasonerFramework multi-tier (fast/slow).
- **`homeostasis.py`**: HomeostaticController + TrendDetector (stress/energy → adaptive interval).
- **`lifecycle.py`**: Maturation (age-based state transitions).
- **`identity.py`**: SelfModel/Manager (cell self-awareness).
- **`metabolic/`**: MetabolicStore + TrendAnalyzer (energy/attention).
- **`observability/`**: PulseMetrics + CellMetricsExporter.
- **`observatory.py`**: `emit_pulse_observed()` → PG `events_outbox` + `pg_notify('cell_pulse_observed')`. Opt-in `CELL_OBSERVATORY_EMIT=true`. **Critical**: zero dipendenze da backend-rag.

**3 cell vere oggi LIVE su Pro**:
- `apps/cell` (organism cell, generic) — LaunchAgent
- `apps/organism` (metacell supervisor + control panel `:1819` + scheduled-tick) — LaunchAgent
- `apps/cell-observatory-collector` (listener PG + classifier MiniMax via OpenRouter) — LaunchAgent
- `apps/evaluator/seo_cell` (cron-driven, single-pulse runs, NON daemon)

### OpenClaw runtime (post-cleanup di oggi)

Gateway Node.js loopback `127.0.0.1:18789`, KeepAlive=true, 129 mcporter tools, Telegram channel @Balizerobot.
Routing α (post-test):

- `agents.list[main]` (telegram/classifier H24): `openrouter/minimax/minimax-m2.7` → Kimi K2.6 → DeepSeek V4 chat → Ollama qwen3.5:9b
- `agents.list[coder]` (code reasoning): `openrouter/qwen/qwen3-max` → Qwen3.6 Plus → Kimi K2.6 → DeepSeek-Reasoner → Ollama
- imageModel: `ollama/qwen2.5vl:7b` → Qwen3-VL-235B-thinking

Costi misurati (test reali): MiniMax M2.7 $0.0003, Qwen3-Max $0.0006, Kimi K2.6 $0.0011, DeepSeek $0.0001-$0.0002.
**Stima totale steady-state: $6-10/mese tutti i layer attivi.**

### 130 automazioni Pro (90 cron + 70 LaunchAgents)

Categorizzate:
- **A) Sensor/observability** (8): system-doctor, log-anomaly-detector, fly-watcher, client-health, sentinel, heartbeat-check, oss-monitor, coverage-trend
- **B) Pipeline/ingestion** (15): NB1-10, gap-scanner, peraturan, garuda-indexer, kb-ingest, vision-doc-extractor, imigrasi-monitor
- **C) LLM-in-loop oggi** (7): system-doctor (Claude OAuth optional), tech-orchestrator (Claude bounded), fact-checker (Claude synth), nlm-deep-research (NotebookLM), kg-builder, conversation-trainer, daily-ops, seo-guardian-observe (40min)
- **D) Maintenance** (10): cache-cleanup, mos-maintenance, db-backup, qdrant-snapshot, fly-backup, ttl-sweep
- **E) Notification** (5): federation-alert-dispatcher, automap-telegram, telegram-bots

**Hard rule**: zero ANTHROPIC_API_KEY pay-as-you-go (Antonello ha 3 Claude MAX x20 OAuth). DeepSeek API ($0.01/query) e altri Chinese-frontier (MiniMax M2.7, Kimi K2.6, Qwen3-Max via OpenRouter, GLM 5.1) sono OK perché flat-cost. Claude/Codex/Gemini CLI restano per task grandi (1M context, code review big, architecture). OpenClaw è per cheap-frontier H24.

### Intel Scraper

`apps/bali-intel-scraper/`. Daily 03:00 WITA. Pipeline: news sources → Ollama qwen3.5:9b classify → Claude OAuth enrichment (optional) → Gemini SEO validation → Qdrant `balizero_news` collection → GitHub publish. State in Qdrant + EventBus PG. **Linear 6-stage, no agentic chaining, LLM optional non gating**. Output: `~/.agent/decisions/state/intel_scraper.last.json` + GitHub repo.

### War Room 2.0

`apps/war-room/`. 14-module pipeline editoriale. Trend-Hunter cron 2h → Intake → Research (Qdrant + web_search) → **Consiglio multi-LLM** (Claude+Gemini+DeepSeek+NotebookLM votano 7 registri narrativi) → Drafter Claude → Validator Ollama gemma4 + Claude legal → Imagen 4 visual → Layout QA → **Review Gate Telegram (Legge 5, attesa Zero)** → Publisher → Measurer CRM → Learner DeepSeek. State: Qdrant ResearchDossier (10-consumer fanout), EventBus, KG 108K nodes 242K edges. Sprint 1-12 + 13-20 IMPLEMENTATA. 758 unit test. Sprint 15-18 (cognitive L1-L4: Connector, Anomaly, Strategos, Oracle) roadmap futuro.

---

## 3 domande sul tavolo (rispondere a TUTTE e tre con reasoning concreto)

### Q1) Fondere cell+genoma+organism con automazioni? Ha senso?

Antonello chiede se il framework biologico (PulseLoop + Genome + HGT + Homeostasis + SafetyGate + Reflection) debba diventare il "sostrato comune" delle automazioni Pro, o se vada lasciato come opt-in selettivo solo per pochi casi.

Mia analisi corrente (Claude Opus 4.7):
- PRO: 7-9 automazioni hanno struttura `sense→think→act` denegata ma mancano Genome/HGT/Homeostasis (system-doctor, seo-guardian, fact-checker, tech-orchestrator, gap-scanner, kg-builder, research, intel-scraper, war-room).
- CONTRO: 121 automazioni sono ETL/healthcheck/maintenance pure dove cell-core è overhead pure.
- Verdetto provvisorio: "delega selettiva" — promuovere 9 automazioni a cell, lasciare 121 come shell. NON merge totale.

**Cosa rispondi?** Concorda? Errori nel reasoning? Casi che ho missed? Quale soglia per "promote to cell"?

### Q2) Dove aggiungere OpenClaw alle automazioni? Perché è meglio?

Antonello ha vincolato: OpenClaw va riservato a cheap-frontier H24, non per task big (Claude/Codex/Gemini CLI restano).

Mia analisi corrente (Claude Opus 4.7):
- 3 condizioni necessarie e congiunte per OpenClaw: (1) reasoning H24, (2) stato cross-call persistente, (3) multi-tool agentic loop. Se manca anche solo una, OpenClaw è overhead.
- 5 candidate concrete: fact-checker, tech-orchestrator, seo-guardian-observe, gap-scanner, HGT cross-cell coordinator (nuovo).
- Stima costo totale ~$0.30-0.50/giorno = $10-15/mese.
- Le altre 125 automazioni: shell deterministico è meglio (debuggabile, fast, predictable).

**Cosa rispondi?** Le 3 condizioni sono quelle giuste? Le 5 candidate sono quelle giuste o ne manco/aggiungo? Costo realistico?

### Q3) Intel Scraper e WR2: cell? OpenClaw?

Mia analisi corrente (Claude Opus 4.7):

- **Intel Scraper**: cell-core PARZIALE (Homeostasi + Genome scar + HGT publisher). OpenClaw NO (pipeline lineare, no agentic, no multi-tool loop).
- **War Room 2.0**: cell-core SÌ TOTALE (è già cell-organism mascherato — Trend-Hunter=sensor, Consiglio=reasoner, Drafter=act, Validator=SafetyGate, Learner=reflection, L1 Connector=HGT, L2-L4=dream/mature). OpenClaw SÌ PARZIALE per 3 punti: (a) L1 Connector cross-dossier thesis (Kimi K2.6), (b) Learner M14 feedback loop notturno (DeepSeek-Reasoner), (c) Trend-Hunter intake pre-filter (MiniMax M2.7) per ridurre carico Consiglio.
- Le 3 zone Consiglio + Drafter + Visual restano dirette (no OpenClaw mediation): valore della diversità multi-LLM, qualità tone Claude OAuth, specificità Imagen 4.

**Cosa rispondi?** Intel scraper OpenClaw davvero NO? WR2 i 3 punti OpenClaw sono giusti, ne manco/aggiungo? Cell-core mapping di WR2 è corretto?

---

## Output richiesto

Per ognuna delle 3 domande, rispondi in formato:

```
## Q[N] — [titolo]

### Verdict
[CONCUR | DISAGREE | PARTIAL] con il reasoning di Claude Opus

### Reasoning (max 300 parole)
[Punti specifici, citando gli elementi del briefing]

### Disagreements (se PARTIAL/DISAGREE)
[Specifico: cosa cambieresti, perché, evidenza]

### Missed cases (se ne hai)
[Cosa Claude Opus non ha considerato]

### Risk callouts
[Rischi tecnici/operativi non mitigati]
```

Sii diretto, niente cortesie. Se vedi un errore nel mio reasoning, dillo. Se ho missed una cosa importante, segnalalo.
