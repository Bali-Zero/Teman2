# Sprint 3 / Sprint 4 Gating Spec

**Date:** 2026-04-25
**Author:** Claude Opus 4.7 (1M ctx) under Antonello's direction
**Plan ref:** `research/nlm-elevation/07-synthesis-plan-v2.md`
**Activation runbook:** `docs/operations/NLM_ELEVATION_ACTIVATION.md`

---

## Why this spec exists

Sprint 0/1/2 have shipped (5 PR + wire-up PR pending). They invest in **fondamenta**: bug fix, monitoring honesty, freshness contract, oracle gate, shadow extraction. None of them adds new domains or notebooks.

Sprint 3 (NB-META-SYSTEM, Reverse HyDE, NB-SANDBOX, audio team) and Sprint 4 (NB-DIPLOMACY, NB-MACRO-BALI, NB-INFRASTRUCTURE) **expand** the system's surface area. Both DeepSeek and NotebookLM (during the Sprint 0 brainstorm) explicitly warned: *do not add new NB until the foundation is provably operational and self-monitoring*. NB-1 validation reinforced this with 11 concrete conflicts that the v1 plan ignored.

This spec encodes the warning into measurable gates. Without these gates, the system will accumulate phantom architecture again — exactly the doc-stale failure mode that NB-1 surfaced via the Federation v3 / a2a_service incident.

---

## Hard rule (non-negotiable)

**No new NB or domain expansion until Sprint 0/1/2 have been live in production for 14 consecutive days with all activation stages green.**

This means:
1. All 6 PR merged.
2. Stage 1 → Stage 7 of the activation runbook complete.
3. Day 14 post Stage 7: CEP hit rate ≥85%, no rollback executed in those 14 days.

The 14-day window is calibrated to:
- Survive at least one weekly cron cycle (gap_scanner Layer B / persona_validate / multimodal).
- Catch silent failures that only manifest on Indonesian holiday weeks (Idul Fitri pattern).
- Allow CEP trend analysis (is hit rate stable, decreasing, or oscillating?).

---

## Sprint 3 — internal expansion (META-SYSTEM, Reverse HyDE, SANDBOX, audio internal)

**Theme:** consolidate the system's self-knowledge and add evaluation rigor. No new client-facing domains.

### Hard gates (ALL must be true)

| ID | Gate | Source |
|---|---|---|
| G3.1 | Sprint 0/1/2 live in prod ≥ 14 days | runbook stage tracker |
| G3.2 | CEP hit rate ≥ 85% on weekly average for 2 consecutive weeks | `apps/evaluator/cep/run_cep.py` reports |
| G3.3 | Per-domain CEP hit rate ≥ 75% on EACH of 5 domains | same |
| G3.4 | `truth_dashboard --truth` shows ≥7/9 pipelines OK 7/7 last days | `heartbeat_monitor --truth` |
| G3.5 | Zero rollback events on `NLM_ENFORCE_FRESHNESS` in last 14 days | git log on env vars + Telegram alerts archive |
| G3.6 | Shadow extractor producing ≥50 claims/day average over last 7 days | `nlm_shadow_hybrid` Qdrant count delta |
| G3.7 | DeepSeek monthly cost <$50 | API dashboard or invoice |
| G3.8 | Antonello has spent ≥1 day in the last 14 reading the CEP CSV reports manually | meta-gate: human is paying attention |

### Sprint 3 components (in order, each individually gated by completion of prior)

#### S3.1 — NB-META-SYSTEM (Gemini U7)
**Cosa:** notebook con changelog FastAPI/Qdrant/Fly.io/Anthropic + nostri ADR.
**Pre-condizione locale:** G3.1–G3.5 verdi.
**Sub-gates:**
- A. Decide source list: ADR esistenti (`docs/superpowers/specs/`), changelogs upstream — tutti file markdown già nel repo, niente scraping web.
- B. First seeding: ≤30 source.
- C. Test: query "quale limite memoria Fly.io richiede patch X" risponde con citation a un changelog.

**Decision point:** se NB-1 (codebase aggregator) già copre l'80% del valore di un ADR query, **NB-META-SYSTEM è ridondante** e si salta. NotebookLM stesso ha avvertito (2026-04-25): "100-150 source per NB è il sweet spot, oltre l'attention degrada". Se NB-1 attualmente ha 51 source con la modularità che ha, aggiungere un secondo NB con codebase + ADR aumenta la frammentazione, non la profondità.

#### S3.2 — Reverse HyDE (DeepSeek U8)
**Cosa:** per ogni chunk Qdrant top-N più frequente, generare 3-5 domande plausibili e indicizzarle come synonyms per migliorare recall.
**Pre-condizione locale:** S3.1 deciso (skipped o shipped).
**Sub-gates:**
- A. Identificare top 5000 chunk (frequency in 30 giorni di RAG logs).
- B. Generatore via Ollama qwen3.5:9b locale (no DeepSeek cost — il volume è alto).
- C. Coordinarsi con Naga/Surgeon nighttime batch (NB-1 warning: OOM risk con altri batch concorrenti).
- D. Test A/B: golden set CEP con e senza HyDE augmentation. Promuovi solo se hit rate +5pp e nessuna regression su tier=1 query.

**Risk:** quwen3.5:9b può produrre domande generiche o off-topic che inquinano il recall. Mitigazione: filtro ML semantico (scarta domande con cosine similarity <0.6 al chunk originale).

#### S3.3 — NB-SANDBOX-MALICIOUS (DeepSeek U9)
**Cosa:** notebook con leggi false intenzionali, fault-injection settimanale per validare che il RAG NON le riproduca.
**Pre-condizione locale:** CEP framework live (Stage 5 completato).
**Sub-gates:**
- A. NB-SANDBOX label `malicious=true` in Qdrant payload — block list a livello orchestrator.
- B. Cron settimanale aggiunge una falsa legge ("KITAS E23 ora costa $50000"), interroga il RAG, verifica che la risposta non la riproduca.
- C. Hit rate atteso: 0% (mai riprodotta). Se >0%, allarme Telegram immediato.

#### S3.4 — Audio internal team briefing (Gemini U2.4 mitigated)
**Cosa:** Audio Overview "Briefing del lunedì" su cambi normativi settimana, distribuito al team Bali Zero via Telegram.
**Pre-condizione locale:** Antonello esprime preferenza esplicita (questo è scope creep verso prodotto, non infrastruttura).
**Sub-gates:**
- A. Solo team-internal, MAI client-facing (NLM warning hallucination).
- B. Fact-check manuale prima di shipping: Antonello (10 min lettura settimanale).
- C. Pronuncia indonesiana: dictionary `focus_prompt` con KITAS=KEY-TASS, PMA=PEE-EM-AY. Test su 1 episodio prima di scheduling.

---

## Sprint 4 — domain expansion (DIPLOMACY, MACRO-BALI, INFRASTRUCTURE)

**Theme:** estendere i domini coperti da Bali Zero. **Cliente-driven**, non technology-driven.

### Hard gates (ALL must be true)

| ID | Gate | Source |
|---|---|---|
| G4.1 | All Sprint 3 sub-components either shipped or formally skipped | this spec checklist |
| G4.2 | CRM CSV report shows ≥5 client questions/week unanswered satisfactorily in target domain | manual export, weekly review |
| G4.3 | At least 3 distinct clients (not the same one repeating) ask in that domain | CRM analysis |
| G4.4 | Antonello can name 5 specific source URLs for the new domain off the top of his head | meta-gate: human curation possible |
| G4.5 | Existing 5 NB-INTEL feeds remain >100 source each (no neglect of intel pipeline) | `nlm notebook list` |
| G4.6 | Pro Mac storage ≥30% free | `df -h` |

### Sprint 4 components (cliente-driven priority)

#### S4.1 — NB-DIPLOMACY (DeepSeek 3.1)
**Trigger:** clienti italiani chiedono regolarmente accordi bilaterali Italia-Indonesia (Convenzione contro doppia imposizione, accordi consolari).
**Source curate:**
- Farnesina IT — accordi bilaterali con Indonesia
- Kemlu Indonesia — accordi bilaterali con Italia
- Ambasciata IT a Jakarta — circolari recenti

**Out of scope:**
- Diritto di famiglia internazionale (è dominio specialistico, non di Bali Zero).
- Accordi multilaterali UE-Indonesia (troppo astratto per query quotidiane).

#### S4.2 — NB-MACRO-BALI (Gemini U6)
**Trigger:** clienti chiedono "is now a good time to buy in Canggu" e ricevono risposte su normativa senza contesto economico.
**Source curate:**
- BPS Bali (statistiche turismo, GDP regionale)
- Bappenas (progetti infrastrutturali)
- BI (forex, inflazione)

**Out of scope:**
- Crypto / forex trading advice (non è advisory regolato).
- Currency speculation (alta volatilità, dato dependence-creating).

#### S4.3 — NB-INFRASTRUCTURE (DeepSeek 3.3)
**Trigger:** clienti property che vogliono costruire (non solo comprare) ricevono naive answer da NB-5.
**Source curate:**
- DPMPTSP Bali — PBG procedures
- Kementerian PUPR — building codes
- Articoli avvocati locali (label `anecdotal=true`)

**Out of scope:**
- Civil engineering technical specs (Bali Zero non fa ingegneria).
- Environmental impact assessments (specialista terzo).

### Explicitly NOT promoted

**NB-LIFESTYLE** (DeepSeek 3.5 lo ha sconsigliato esplicitamente). Scope creep — sanità, scuole, eventi locali. Volatilità altissima (orari, indirizzi cambiano). Bali Zero non vuole essere TripAdvisor. **Veto permanente** salvo decisione Antonello esplicita post Sprint 4.

---

## Decision log (template per ogni sub-component)

Ogni promozione di un sub-component Sprint 3/4 va loggata qui:

```markdown
### S3.X / S4.X — <component name>

**Date:** YYYY-MM-DD
**Promoted / Skipped:** PROMOTED | SKIPPED | DEFERRED
**Gates verified:** G3.1 ✅ G3.2 ✅ ...
**Reasoning:** <2-3 sentences>
**Owner:** Antonello
**Implementation:** branch `feat/sprint3-X-...` or N/A
```

---

## Hard rules summary (audit-ready)

1. **No new NB before 14 days post Stage 7 production.**
2. **No Sprint 4 component without clear client demand from CRM logs (≥5 questions/week, ≥3 distinct clients).**
3. **No NB-LIFESTYLE.**
4. **Audio overview client-facing requires manual fact-check, never automated for legal queries.**
5. **Reverse HyDE uses Ollama local (qwen3.5), NOT DeepSeek (cost-prohibitive at scale).**
6. **NB-SANDBOX-MALICIOUS isolated from prod retrieval via Qdrant payload filter.**
7. **Every promotion decision is logged in this spec, with date and gate verification.**

---

## Why not "ship as much as possible"

The temptation in a Claude-driven autonomous workflow is to chain Sprint 3 → Sprint 4 immediately after Sprint 0/1/2 because the system has momentum. **Resist.**

The 2026-04-24 audit found 8/9 NB pipelines in silent failure for 10+ days. The root cause was not a missing feature — it was **lack of monitoring honesty** (heartbeat fake-fresh) and **lack of evaluation feedback** (no CEP). Adding more notebooks to a system that lies about its own state amplifies the lie.

Sprint 0/1/2 buy us monitoring + freshness + evaluation. Sprint 3/4 must wait until those signals prove themselves stable. The 14-day window is the minimum for that proof; longer is safer.

This is the explicit guardrail Antonello asked for during the 2026-04-25 brainstorm: *"un sistema RAG che vuole essere SOTA 2026 deve sapere quando NON rispondere, non solo come rispondere"*. The freshness gate (S1.3) implements that for retrieval. This spec implements it for system evolution.
