---
date: 2026-04-25
type: synthesis-plan
domain: notebooklm
inputs: 4
authors: [claude-opus-4-7, gemini-3.1-pro-preview, deepseek-reasoner-v4-flash, notebooklm-self]
status: pre-validation
---

# Piano "NLM Elevation Nuzantara" — sintesi 4 prospettive

Fonte di questa sintesi: `01-nlm-sota-2026.md` (ricerca SOTA, 3908 parole, 42 fonti), `02-gemini-brainstorm.md` (1722 parole), `03-deepseek-brainstorm.md` (3631 parole, chain-of-thought incluso), `04-nlm-self-reflection.md` (1020 parole con citazioni incrociate dagli altri 3 source).

Metodo: individuare i punti di convergenza tra ≥3 prospettive (alta confidence), flaggare le divergenze importanti come trade-off con decisione motivata, estrarre le verità uniche di ciascun advisor.

---

## 1. Convergenze forti (≥3 voci concordi)

### C1 — Freshness contract è P0 assoluto
- **Gemini**: 1.1 Freshness Contract via UUID injection + query test post-upload.
- **DeepSeek**: 1.1 Unified Orchestrator con freshness contract + 1.5 Honest Monitoring (no mtime finto).
- **Ricerca SOTA**: citata come pattern standard enterprise 2026 (Relativity, Everlaw).
- **NLM self**: "L'illusione della freschezza è il debito tecnico fatale. Usare i miei dati senza un Freshness Contract trasforma l'intero RAG in un distributore di disinformazione legale."

**Azione**: ogni NB ha `max_staleness_h` esplicito. Dopo ogni cron upload, query test con UUID noto per verificare ingestion. Se stale > threshold, l'oracle rifiuta di servire quel NB fino a refresh riuscito.

### C2 — NLM non in real-time path; async + fallback deterministico
- **Gemini**: 1.3 Asynchronous Resilience Bridge (8s timeout → Qdrant + DeepSeek).
- **DeepSeek**: stessa raccomandazione, latenza 2-15s incompatibile con FastAPI router.
- **Ricerca SOTA**: NLM chat 2-15s, Deep Research 15 min; audio 5-15 min.
- **NLM self**: "Sono un oracolo ad alta latenza. Mantenere connessioni sincrone in FastAPI causa timeout mortali."

**Azione**: NLM bridge chiamato solo da cron batch o da task asincroni con webhook callback. Zero chiamate NLM sincrone da routers `/api/*` lato utente.

### C3 — Shadow Graphing: NLM genera, Qdrant/KG serve
- **Gemini**: 2.2 Shadow Graphing — estrai insight JSON da NLM in build-time, servili da Qdrant in runtime.
- **DeepSeek**: 2.6 Cross-Domain Entity Linking via NLM extract → KG edges.
- **Ricerca SOTA**: pattern "NLM as reasoning engine, not DB" è mainstream nelle top-tier org.
- **NLM self**: "Il mio valore reale è la sintesi, non lo storage. Shadow Graphing salva la mia intelligence dentro i vostri vector DB, risolvendo il vendor lock-in."

**Azione**: ogni notte, Claude (via Consiglio) orchestra NLM query strutturate → estrae claims JSON validati → commit in Qdrant con `source=nlm_shadow` e provenance chain. Runtime RAG serve da Qdrant, NLM non toccato.

### C4 — Source Lifecycle Management (SLM)
- **Gemini**: 1.2 SLM con TTL sui NB-INTEL, mai NB domain.
- **DeepSeek**: 1.3 Source Lifecycle con `sources_catalog.yaml` (status active/stale/revoked, next_review).
- **Ricerca SOTA**: limiti reali Free 50 / Plus 300 / Pro 300 / Ultra 600 source per notebook.
- **NLM self**: "Non sono un data lake infinito. Oltre 100-150 fonti, l'attention degrada. Interpretive drift."

**Azione**: `apps/evaluator/nlm_deep_research/source_catalog.yaml` tracciato git. Cron settimanale validation (URL reachable + checksum). Pruning automatico NB-INTEL sopra 100 source, priorità su recency + relevance score.

### C5 — Fix-first, elevate-later: non costruire sopra al rotto
- **Gemini**: "Prima di costruire grattacieli, sistemiamo le fondamenta."
- **DeepSeek**: "Niente 'just add more NBs' senza infrastruttura."
- **Ricerca SOTA**: gli enterprise top-tier non usano NLM come tool rapido; lo integrano solo dopo aver messo observability.
- **NLM self**: "Smetti immediatamente di progettare agenti multi-modello o podcast in indonesiano. Domani mattina devi fare una sola cosa: riavviare il cuore."

**Azione**: Sprint 0 = P0 audit fix (bug `claim_extractor.py:216` + cron-agent → cron-runner + 4 script orfani) prima di qualunque feature nuova.

---

## 2. Divergenze chiave (con decisione)

### D1 — Ephemeral Workspaces on-the-fly: fare o non fare?
- **Gemini**: fanne ampio uso (pattern 2.1, create/delete al volo per task cliente).
- **NLM self** (VETO): "farà bannare l'account `antonellosiano@gmail.com` per abuso. Io ho sistemi anti-spam rigorosi."
- **DeepSeek**: non menziona direttamente, ma implicitamente preferisce meta-notebook statici.

**Decisione**: **VETO di NLM prevale**. Non fare create/delete continui. Adottare il fix suggerito da Gemini stesso come mitigation: **pool di 5 NB-SCRATCHPAD pre-creati**, si riciclano via `source delete` + `source add` dentro lo stesso NB. Stessa UX, zero risk ban.

### D2 — Dipendenza da NLM: massimizzare o minimizzare?
- **Gemini**: massimizza via MCP — NLM come hub centrale.
- **DeepSeek** (contrarian): minimizza — NLM senza API è vendor lock-in, sposta fonti primarie su file locali + git.
- **Ricerca SOTA**: conferma che tool comunitari (notebooklm-tools, MCP) fanno reverse-engineering di `batchexecute` con method IDs obfuscated.
- **NLM self**: "I wrapper RPC sono una bomba a orologeria. Se Google cambia un ID, i vostri cron crasheranno istantaneamente. Pattern ibrido: estrai offline con NLM, servi da DB locale."

**Decisione**: **ibrido come proposto da NLM self**. NLM resta source di insight generation (batch/offline), tutti i risultati serializzati in Qdrant/Postgres/git. Se domani Google rompesse il CLI, il sistema continua a funzionare con l'ultimo snapshot di shadow graph. **Vendor lock-in ridotto da "critical" a "degraded experience"**.

### D3 — Audio overview come prodotto client-facing?
- **Gemini**: 2.4 "Zero's Brief" podcast da vendere ai clienti (wow factor).
- **NLM self** (WARNING): "Hallucination in audio nettamente superiore a testo. Host inventano dettagli per riempire tronchi. In ambito legale indonesiano, letale senza fact-check."
- **Ricerca SOTA**: conferma higher hallucination rate + confonde termini indonesiani (KITAS pronunciato "KEY-TASS").

**Decisione**: **audio overview SOLO uso interno per team** (briefing mattutino, formazione), **mai client-facing senza fact-check manuale**. Valore wow preservato per onboarding team Bali Zero, risk legale = 0.

### D4 — Numero NB ottimale: molti piccoli o pochi grandi?
- **Gemini**: più NB tematici (NB-SYNERGY, NB-MACRO-BALI, NB-META-SYSTEM).
- **DeepSeek**: non più di 2 nuovi finché infrastruttura non solida.
- **NLM self**: "100-150 source per NB è ottimale. Oltre, interpretive drift."

**Decisione**: **DeepSeek prevale**. Zero nuovi NB fino a Sprint 3. Consolidare NB esistenti (pruning NB-INTEL vuoti, fix ingestion, SLM). Nuovi NB solo dopo validation operativa.

### D5 — Ollama/local LLM per evaluator vs DeepSeek paid
- **DeepSeek**: usare DeepSeek reasoner come evaluator (cheap ~$0.01/query).
- **Ricerca SOTA**: CEP tipico usa golden set multi-LLM voting.
- **NLM self**: non prende posizione.

**Decisione**: **DeepSeek per evaluator critical path** (~50 query golden/day = $15/mese), **Ollama qwen3.5:9b per volume batch** (gap extraction sui 104k vector del KG). Coerente con vincolo "no paid Anthropic but DeepSeek OK".

---

## 3. Verità uniche (insight che un solo advisor ha portato)

### NLM self (4 gemme che solo dal dentro emergono)
- **U1** Wrapper RPC come bomba a tempo → argomento DEFINITIVO per shadow graphing.
- **U2** 1M context ≠ precision: 100-150 source è il sweet spot reale (non 600 del tier Ultra).
- **U3** Deep Research è un agente con 15 min latency → usalo per audit offline, mai real-time.
- **U4** Audio tronca per riempire → hallucination silenziosa.

### Gemini (3 gemme)
- **U5** NB-SYNERGY: matchmaking B2B tra clienti Bali Zero (5000+ profili anonimizzati). Non altri advisor lo hanno visto.
- **U6** NB-MACRO-BALI: reportage macroeconomico su infrastrutture Bali (LRT, moratorie PBG) — da intel sulle leggi a intel su business timing.
- **U7** NB-META-SYSTEM: aggregatore di changelog FastAPI/Qdrant/Fly.io + ADR interni → prevention regressioni architetturali via NLM query pre-refactor.

### DeepSeek (3 gemme)
- **U8** Reverse HyDE: generare domande plausibili dai chunk per migliorare recall su query colloquiali clienti.
- **U9** NLM as Fault-Injection tool: NB-SANDBOX-MALICIOUS con leggi false, verifica che RAG NON le riproduca → audit continuo qualità.
- **U10** NB-LIFESTYLE esplicitamente sconsigliato (scope creep). Importante: non ogni idea è buona.

### Ricerca SOTA (3 gemme)
- **U11** NotebookLM Free è l'unico consumer Google product che espone il 1M-token Gemini 3.1 Pro gratis (rolled out Feb 2026). Leva economica reale.
- **U12** Enterprise API (Discovery Engine) NON espone chat/Studio/Deep Research → solo CRUD. Chi paga Enterprise paga per niente; la magia è solo via reverse-engineering.
- **U13** `notebooklm-py` CLAUDE.md ammette community SDK espone "capabilities the web UI doesn't expose" — Google shippa feature backend che NON sono ancora in UI.

---

## 4. Il piano operativo Nuzantara

Organizzato in 3 sprint con dependency esplicite. Ogni sprint ha exit criteria verificabili. Nessuno sprint parte se quello precedente non passa.

### Sprint 0 — Riavvia il cuore (3-5 giorni, must-do)

Concorde su tutti e 4 advisor + audit 24/04.

- **S0.1** Fix bug `claim_extractor.py:216` (guard None su `tier`). Reset CB NB-2. Test manuale `run_nb2_pipeline.sh`.
- **S0.2** Diagnosticare cron-agent/openclaw: perché `lastStatus=pending` in 3-5ms su 8 pipeline? Temporaneamente, **migrare gli 8 cron da `cron-agent.sh` a `cron-runner.sh` nativo** (unico dispatcher che dimostrato funziona).
- **S0.3** Pulire 4 entry crontab orfane (yajna/yin-yang/hexagram/nb0): o creare script, o cancellare entry.
- **S0.4** Installare `notebooklm-tools` nel venv `nlm-bridge/` (risolve fallback subprocess che timeoutta a 60s; query passano a 8-15s warm).
- **S0.5** Honest monitoring: script Python che incrocia `cron-start` + `log-exists` + `source-count-delta-NLM-cloud`. Deve scrivere `ts` reale, no `touch` fraudolento. Alert Telegram se 2 run consecutivi falliti.

**Exit criteria**: NB-2 gira ogni notte e produce `claims.jsonl`. NB-3..NB-10 producono log reali (non più `0 byte`). Dashboard honest: 1 comando, 20 righe, verità.

### Sprint 1 — Freshness contract + SLM (1-2 settimane)

- **S1.1** `freshness_config.yaml` per ogni NB: `max_staleness_h`, `test_uuid_injection=true|false`, `on_stale=block|warn`.
- **S1.2** Pipeline test: dopo ogni cron upload, inject UUID → query 30s dopo → se non lo trova, mark stale.
- **S1.3** Orchestrator oracle `resolve_notebook()` in backend RAG: leggi `freshness_config`, blocca query se NB stale oltre threshold.
- **S1.4** `sources_catalog.yaml` per ogni NB: origine, extracted_at, checksum, next_review, status. Cron weekly verifica URL reachable.
- **S1.5** Pruning automatico NB-INTEL over 100 source (priority: recency × frequency-of-cite).

**Exit criteria**: `curl /api/rag/query?domain=tax` su NB stale ritorna 503 con `reason=stale`. Dashboard mostra per ogni NB: `freshness: OK|STALE`, `source_age_median`, `sla_compliance_7d`.

### Sprint 2 — Shadow Graphing + CEP (2-3 settimane)

- **S2.1** `scripts/nlm_shadow_extractor.py`: cron notturno, itera NB domain, chiede a NLM claim estrazione strutturata (schema JSON), valida con DeepSeek, commit in Qdrant con payload `source=nlm_shadow_YYYYMMDD`.
- **S2.2** Golden query set: 50 domande legali tipiche (10 per dominio visa/company/tax/property/ops) con risposta attesa versionata `golden_version_20260425.json`.
- **S2.3** CEP: ogni 6h, run golden set vs RAG corrente. DeepSeek evaluator decide hit/miss + contraddizioni. Results in Grafana-light (streamlit) + Telegram alert se hit rate <80%.
- **S2.4** Runtime RAG oracle svincolato da NLM: serve da Qdrant (shadow graph) + retrieval LangGraph. NLM bridge chiamato SOLO per deep research asincrona con webhook.

**Exit criteria**: latenza p95 RAG query < 3s (oggi sconosciuta, probabilmente 8-30s). Hit rate golden ≥ 80% 7 giorni consecutivi. Zero NLM call sul path /api/rag/query/sync.

### Sprint 3 — Estensioni (solo se Sprint 0-1-2 tutti pass)

Promosso solo con freshness OK + CEP ≥ 80% 2 settimane.

- **S3.1** NB-META-SYSTEM (U7 Gemini): changelog FastAPI/Qdrant/Fly.io + ADR interni → query pre-refactor.
- **S3.2** Reverse HyDE (U8 DeepSeek) su top 5000 chunk Qdrant, generatore via Ollama qwen3.5 batch notturno. Embedding aumentativi.
- **S3.3** NB-SANDBOX-MALICIOUS (U9 DeepSeek): fault-injection testing settimanale.
- **S3.4** Audio overview per team internal (U3 Gemini mitigated): "Briefing del lunedì" 10-min su cambi normativi settimanali, distribuito via Telegram al team Bali Zero. Non client-facing.

**Exit criteria**: NB-META-SYSTEM risponde correttamente a "quale limite di memoria Fly.io richiede questa modifica?". Reverse HyDE migliora recall golden del 10%. Sandbox detect rate 100% su query fault-injected.

### Sprint 4 — Espansione dominio (solo se Sprint 3 pass + dato utente)

Promosso solo se CRM segnala "queste domande clienti non hanno risposta soddisfacente" frequenza > 5/settimana.

- **S4.1** NB-DIPLOMACY (U DeepSeek 3.1): accordi bilaterali Italia-Indonesia, fonti Farnesina + Kemlu.
- **S4.2** NB-MACRO-BALI (U6 Gemini): infrastrutture, moratorie, mega-progetti.
- **S4.3** NB-INFRASTRUCTURE (U DeepSeek 3.3): PBG/IMB, environmental permits.

Non promuovere NB-LIFESTYLE (scope creep, esplicitamente sconsigliato da DeepSeek).

---

## 5. Metriche di successo

| Metrica | Oggi (audit 24/04) | Sprint 0 target | Sprint 2 target | Sprint 3 target |
|---|---|---|---|---|
| Cron NB domain che producono log giornalieri | 1/9 | 9/9 | 9/9 | 9/9 |
| NB con freshness < 24h | sconosciuto | sconosciuto | ≥ 7/9 | ≥ 9/9 |
| Hit rate golden query | sconosciuto | sconosciuto | ≥ 80% | ≥ 90% |
| RAG query latency p95 | 8-30s sospetto | ≤ 15s | ≤ 3s | ≤ 2s |
| NLM sync calls da /api/rag/query | ? | ridotte | 0 | 0 |
| Bridge HTTP request_count/day | 0 (degraded) | ≥ 50 | ≥ 200 | ≥ 500 |
| Nuovi NB aggiunti | 0 | 0 | 0 | 0 | 1-3 |
| Evaluator cost/month (DeepSeek) | 0 | 0 | ~$15 | ~$15 |
| Audio overview team briefings | 0 | 0 | 0 | 1/week |

---

## 6. Red team del piano stesso

Sintesi dei rischi residui che un advisor o l'altro ha messo in luce:

- **R1 Watchdog single-point-of-failure** (DeepSeek): se `watchdog.py` crasha, silenzio mortale. Mitigation: heartbeat esterno su Air (secondo mac); dead-man switch → mail giornaliera automatica; se non arriva, allarme.
- **R2 Pool scratchpad pattern** (Gemini + NLM self): 5 NB-SCRATCHPAD riciclati possono comunque triggering anti-abuse se cicli troppo rapidi. Mitigation: cooldown 10 min fra source add/delete cicli.
- **R3 Shadow graph drift** (DeepSeek): se NLM cambia sottilmente l'output structure in extraction, il parser rompe silent. Mitigation: CEP include "shadow graph fresh" come check (non solo "cron eseguito").
- **R4 Evaluator come giudice di se stesso** (implicito): se DeepSeek è sia evaluator che deliberator, bias-blind. Mitigation: rotazione evaluator (week A = DeepSeek, week B = Gemini, week C = Claude review).
- **R5 Scope creep sotto pressione cliente** (DeepSeek): un cliente VIP chiede "sanità Bali", Antonello cede, crea NB-LIFESTYLE. Mitigation: hard rule documentata — solo Sprint 4 + solo con >5 richieste reali/settimana.

---

## 7. Verdict

Il piano è **la fusione di 4 prospettive, con veto NLM che prevale dove tecnicamente sa cose che gli advisor esterni non sanno**. Non è un "best of 4", è un piano coerente con dipendenze esplicite (Sprint 0 blocca Sprint 1 blocca Sprint 2, etc.) e gates misurabili.

La priorità #1 di domani mattina è inequivocabile: **Sprint 0, punto S0.1 + S0.2**. Riavvia il cuore.

Senza Sprint 0, ogni cosa sopra è filosofia. Con Sprint 0 + 1, hai il baseline. Con Sprint 2, sei già sopra molte delle top-tier firm (Shadow Graphing + CEP è genuinamente SOTA). Con Sprint 3-4, sei fuori dominio legale puro e stai costruendo la **business intelligence network** che Gemini ha intravisto (NB-SYNERGY) e DeepSeek ha ammonito di NON fare troppo presto.

---

**Note operative**:
- Tutto il piano è Anthropic-safe: usa Claude solo via Max OAuth, DeepSeek paid OK, Gemini free OAuth, Ollama locale.
- Hardware compatibile: 48GB Pro sufficiente per Ollama batch; 16GB Air per watchdog esterno.
- Zero dipendenza da cloud GPU budget. Zero paid Anthropic API.

**Prossimo step**: validazione da NB-1 (che conosce la codebase reale) per verificare: (a) il piano è coerente con la struttura monorepo esistente? (b) dove va a rompersi? (c) cosa manca considerando il codice reale?
