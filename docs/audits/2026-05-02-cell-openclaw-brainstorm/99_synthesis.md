# Sintesi cross-LLM brainstorm — 2 May 2026

**Reviewers:** Codex GPT-5.5 xhigh + Gemini 3.1 Pro + DeepSeek V4 Reasoner + Claude Opus 4.7 (originator)

## Quorum overview

| Domanda | Claude Opus | Codex GPT-5.5 | Gemini 3.1 Pro | DeepSeek V4 |
|---|---|---|---|---|
| Q1 cell+genoma×automazioni | promote 9 | CONCUR | CONCUR | PARTIAL |
| Q2 OpenClaw scope | 5 candidate, 3 condizioni | PARTIAL | PARTIAL | PARTIAL |
| Q3 Intel + WR2 | Intel-PARZIALE / WR2-TOTALE+3OC | PARTIAL | CONCUR | CONCUR |

3/4 review = CONCUR su Q1 e Q3. PARTIAL unanime su Q2. Questo significa: il piano macro è solido, le 3 condizioni OpenClaw vanno raffinate.

## Convergenze unanimi (4/4 reviewer)

1. **Delega selettiva è giusta** — promuovere ~9 automazioni, lasciare ~121 shell deterministico. Nessuno propone merge totale.
2. **OpenClaw NO su Intel Scraper main path** — pipeline lineare, LLM opzionale non gating, OpenClaw è overhead.
3. **WR2 = cell-organism mascherato** — il mapping (Trend=sensor, Consiglio=reasoner, Drafter=act, Validator=SafetyGate, Learner=reflection, L1-L4=connector/dream/mature) è preciso architetturalmente.
4. **3 zone WR2 NO-OpenClaw**: Consiglio multi-LLM diretto (valore della diversità), Drafter Claude OAuth (qualità tone), Imagen 4 (visual specifico).
5. **OpenClaw è SPOF**: tutti e 3 reviewer flaggano necessità di circuit-breaker fallback (Ollama locale, chiamate dirette API).

## Disagreements significativi → adottare

### A) **gap-scanner ESCLUSO da OpenClaw** (DeepSeek + Codex)
DeepSeek: "no tool call → Ollama locale qwen3.5:9b è gratis e più veloce". Codex: "deterministic scans + LLM labeling should stay shell". **Adottato**: gap-scanner resta cell-core (Genome utile per pattern di gap) ma SENZA OpenClaw.

### B) **3 condizioni OpenClaw → 4 condizioni** (Codex + DeepSeek)
Le 4 condizioni finali (must satisfy ALL):
1. H24 o high-frequency reasoning (>10 calls/giorno)
2. Multi-step tool loop (≥2 tool concatenati nella stessa sessione)
3. **Durable state changes future decisions** (non basta "cross-call state" — deve cambiare comportamento)
4. **Bounded/autonomous action surface con budget caps + kill switch** (Codex)

### C) **Intel Scraper cell-core "PARZIALE leggero"** non full (DeepSeek)
DeepSeek: "Intel non ha PulseLoop, è linear pipeline. Solo Genome integration come modulo leggero". Codex concorda implicitamente. **Adottato**: Intel-Scraper-cell ha solo Genome scar registry + HGT publisher, NO PulseLoop, NO Homeostasis (pipeline lineare daily). Più cheap di full cell.

### D) **HGT coordinator come "propose+audit+quarantine"**, NON merge diretto (Codex)
Critico: "Keep HGT coordinator out of the critical write path". HGT propone trascrizioni, le scrive in coda con confidence, **non merge automatico** in production cells. Approval gate via SafetyGate o Telegram review.

## Missed cases da incorporare

### Da Gemini
- **Shell-cell observability bridge**: le 121 shell devono emettere lightweight events a `events_outbox`/Redis Stream senza importare cell-core. Se db-backup fallisce 3x consecutivi, organism supervisor lo sa.
- **HGT noise filter**: 9 cell pubblicano simultaneamente → loop feedback. Filtro rigoroso per dominio nel `consumer.py`, blocco ≥10 uses + confidence>0.7 prima di propagare.
- **Council deadlock**: WR2 Consiglio se 1 LLM down → quorum 3/4 sufficiente per procedere.
- **State drift KG-Genome**: Learner aggiorna Genome senza invalidare KG → assunti disallineati. Tagging coordinato.
- **Intel→WR2 HGT cross-system**: scar di fonte fake registrata da Intel deve propagare a WR2 Trend-Hunter via HGT (non solo same-cell).

### Da DeepSeek
- Aggiungere `conversation-trainer` + `daily-ops` come cell candidate (loop iterativi con apprendimento).
- `kg-builder` OpenClaw solo per batch notturni bassa priorità (alta sensibilità qualità).
- WR2 Trend pre-filter: se MiniMax confidence <0.6, passa comunque a Consiglio (recall safety).

### Da Codex
- **"observed shell" tier**: tier intermedio tra full cell e pure shell — automazioni che emettono pulse-like events ma non importano cell-core. Best of both.
- **Cron-driven single-pulse cells** (vedi `seo_cell` pattern) sono migration model migliore di daemon per molti job.
- **Review Gate Telegram + OpenClaw**: Legge 5 resta hard human gate, ma OpenClaw può **preparare** reviewer diffs e risk notes (cheap pre-processing).
- **Research retrieval planning** (WR2): possibile 4° punto OpenClaw — sceglie dinamicamente Qdrant/web/KG probes prima del Consiglio.

## Lista finale aggiornata: cell candidate

| # | Cell | Tipo | OpenClaw? |
|---|---|---|---|
| 1 | system-doctor-cell | full cell-core | NO (basic), forse SÌ se evolve in multi-log triage |
| 2 | seo-guardian-cell | full cell-core (già `seo_cell` pattern) | SÌ MiniMax M2.7 |
| 3 | fact-checker-cell | full cell-core | SÌ MiniMax M2.7 |
| 4 | tech-orchestrator-cell | full cell-core con escalation Claude HIGH risk | SÌ Qwen3-Max + escalation Claude |
| 5 | gap-scanner-cell | full cell-core | **NO** (Ollama locale meglio) |
| 6 | kg-cell | full cell-core | NO (Ollama batch), eventuale OpenClaw per nightly |
| 7 | research-cell (NB pipelines orchestrator) | full cell-core | NO (NotebookLM esterno) |
| 8 | **intel-scraper-cell** | **leggero** (solo Genome + HGT publisher, no PulseLoop) | NO main path, possibile sì per anomaly triage offline |
| 9 | **war-room-organism** (con N sub-cell) | full cell-organism | SÌ 3-4 punti (L1 Connector, Learner M14, Trend pre-filter, eventuale Research retrieval planning) |
| 10 | **conversation-trainer-cell** | full cell-core (DeepSeek aggiunto) | SÌ se diventa loop iterativo persistente |
| 11 | **daily-ops-cell** | full cell-core (DeepSeek aggiunto) | SÌ DeepSeek-Reasoner |
| 12 | **HGT coordinator** (nuovo, non automation esistente) | propose+audit+quarantine | SÌ Kimi K2.6 |

## OpenClaw final list (post-cross-LLM)

5 → **6 candidate** (rimuovo gap-scanner, aggiungo conversation-trainer + daily-ops, aggiungo HGT come "propose-only"):

1. **fact-checker** (MiniMax M2.7) — multi-tool web search + claim extraction
2. **tech-orchestrator** (Qwen3-Max) — orchestrazione + escalation Claude HIGH risk
3. **seo-guardian-observe** (MiniMax M2.7) — pattern detection 40min cadence
4. **conversation-trainer** (DeepSeek-Reasoner) — Q&A pair generation con DB tool
5. **daily-ops** (DeepSeek-Reasoner) — multi-source report sintesi
6. **HGT coordinator** (Kimi K2.6) — **propose-only**, non merge diretto

**Stima costo riveduta** (DeepSeek osservazione corretta): se ogni candidate fa 50-100 calls/giorno → **$1-1.5/giorno = $30-45/mese**, non $10-15. Più realistico.

## Risk register consolidato (deve essere mitigato prima di shipping)

| Rischio | Reviewer | Mitigazione |
|---|---|---|
| OpenClaw SPOF | Gemini + DeepSeek | circuit-breaker timeout → fallback Ollama o direct API |
| Council deadlock WR2 | Gemini | quorum 3/4 sufficiente |
| State drift KG-Genome | Gemini | Learner aggiorna Genome → tag invalidation KG |
| HGT poisoning cross-cell | Codex + Gemini | propose-only, ≥10 uses + conf>0.7 prima di merge |
| Genome bloat | Gemini | monitor `decay_unused_skills(0.95)` aggressivo |
| Runaway loops OpenClaw | Codex | per-agent budgets + max-steps + trace IDs + kill switch |
| Hidden cost drift | Codex + DeepSeek | call ceilings + budget caps |
| WR2 publication latency | Codex | Legge 5 hard gate + async pre-processing OpenClaw |
| Intel scraper LLM gating | Codex | LLM resta optional, non bloccante per replayability |

## Implementation plan revisionato

**Sprint 1 (2-3 giorni):** intel-scraper-cell **leggero** (Genome + HGT publisher), nessun OpenClaw. È il proof-of-concept più semplice + ROI immediato (scar registry per fonti fake).

**Sprint 2 (1 settimana):** HGT coordinator standalone come "propose-only" service (Kimi K2.6 via OpenClaw). Audit log, no auto-merge. Test con Intel scraper events.

**Sprint 3 (2 settimane):** WR2 cell-organism mapping esplicito + 3 OpenClaw insertions (L1 Connector + Learner M14 + Trend pre-filter). Council resta diretto, Drafter resta Claude OAuth.

**Sprint 4 (2 settimane):** rimanenti 6 cell promotion (system-doctor, seo-guardian, fact-checker, tech-orch, conversation-trainer, daily-ops).

**Sprint 5+:** kg-cell, research-cell, eventuale Research retrieval planning OpenClaw, eventuale Layout QA browser/vision.

Total realistic timeline: ~6-8 settimane per full migration.
