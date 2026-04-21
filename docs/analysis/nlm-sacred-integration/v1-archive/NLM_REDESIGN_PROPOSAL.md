# NLM Redesign Proposal — Tassonomia, loop cognitivi, roadmap

**Data:** 2026-04-22 · **Branch:** `analysis/nlm-sacred-integration` · **Base:** NLM_SYSTEM_MAP.md + NLM_SACRED_READING.md. Ogni sezione presume la lettura dei due documenti precedenti.

---

## 0. Orientamento

La **Fase 1** ha mappato 11 NB, 20+ automazioni, 5 cicli di feedback aperti, ridondanze strutturali, consumer mancanti. La **Fase 2** ha ricondotto questi gap a una tassonomia di 7 proposte ancorate a tradizioni sapienziali. La **Fase 3** organizza il tutto in una proposta di riorganizzazione eseguibile.

La proposta è **conservativa per scelta**: non rompe l'architettura esistente, aggiunge layer di osservazione e feedback. Il sistema NLM ha già molta disciplina invariantistica (`invariants.py`, preflight 12-check, circuit breaker, ARCH-8 snapshot pre-mutation); questa disciplina è un asset. Demolire per ricostruire sarebbe perdita netta.

Tuttavia la tassonomia dei NB e il routing backend hanno asimmetrie strutturali documentate (§7 mappa + NB-10 non routabile, primary law NB-Xa mai creati, overlap NB-6/NB-10) che meritano consolidamento. Inoltre 3 automazioni sono oggi broken per dipendenze mancanti — non un "rischio residuo" ma un "costo visibile" da sanare come prerequisito.

---

## 1. Tassonomia proposta dei NotebookLM

### 1.1 Il problema con la tassonomia attuale

La tassonomia esistente è **per dominio** (immigration / company / tax / property / operations / editorial / lifestyle / team / ops / intel / telemetry). Questo è chiaro e allineato al business (Bali Zero vende servizi per dominio). Ma mescola livelli ontologici:

- NB-2..NB-8 + NB-10 sono **domini di conoscenza esterna** (leggi, prassi, contenuti).
- NB-11/12/13 sono **viste interne del business** (pipeline, compliance, telemetry).
- NB-1 è **il sé del codice** (meta).
- NB-14 è **la memoria delle proprie sessioni** (meta).

Trattarli alla stessa stregua nel namespace `NB-{numero}` maschera la differenza strutturale. Il `cross_notebook_correlator` può teoricamente fan-out su tutti — ma NB-11 e NB-2 sono cose diverse e fonderne le risposte è rumoroso.

### 1.2 Tassonomia proposta — 4 strati ontologici

**Strato 1 — Mondo (External Knowledge NBs)** — conoscenza che l'organismo ingerisce dal mondo:

- NB-2 Immigration, NB-3 Company, NB-4 Tax, NB-5 Property, NB-6 Operations & Compliance, NB-7 Editorial, NB-8 Lifestyle, NB-10 Team Guides.
- **Pattern di ingestion:** L1/L2 query scheduled + gap_scanner + freshness scan.
- **Consumer principale:** backend RAG via `resolve_notebook()`.

**Strato 2 — Corpo (Business Mirror NBs)** — rappresentazione strutturata del business state:

- NB-11 Ops Live, NB-12 Business Intelligence, NB-13 System Telemetry.
- **Pattern di ingestion:** `db_to_nlm_sync` da Postgres (narrativa Markdown SHA-256 deduplicata).
- **Consumer principale:** `ops_intelligence.py` weekly briefing + eventualmente dashboard operativa.

**Strato 3 — Sé (Self-Reflection NBs)** — l'organismo che guarda se stesso:

- NB-1 Codebase, NB-14 Claude Session Memory.
- **Pattern di ingestion:** bundle regeneration + SQLite dump.
- **Consumer principale:** Claude stesso via `notebook_query` in session bootstrap + troubleshooting.

**Strato 4 (proposto) — Riflesso (Meta-Cognitive NBs)** — il sistema che osserva se stesso come sistema. **Oggi inesistente come NB.** Proposta: creare **NB-0 Meta-NLM** che riceve come fonti:

- Lo snapshot quotidiano del daily hexagram dashboard (Fase 2 §5.4).
- Il monthly plan proposto dal Meta-Cycle (Fase 2 §7.3).
- Il yajna_ledger aggregato (Fase 2 §4.4).
- I synth_signals mensili (Fase 2 §1.4).
- I log di `consciousness_view --contradictions` (Fase 2 §2.4).

Quando un Claude futuro interroga "come è cambiato il sistema NLM negli ultimi 6 mesi?", NB-0 risponde. Quando Zero chiede "dove stiamo allocando risorse di gap_scanner a vuoto?", NB-0 risponde. È la dimensione che oggi vive solo in file locali disaggregati — aggregare in NB-0 rende la meta-cognizione **interrogabile come qualunque altra knowledge base**.

### 1.3 Ridenominazione semantica

La numerazione `NB-2..NB-14` è **storicizzata** (riflette l'ordine cronologico di creazione) ma non semantica. Proposta: **non rinumerare** (il costo di cambio UUID/label è alto, i consumer sono dispersi in 10+ file) ma aggiungere **alias di strato** nel registry:

```python
# nlm_notebook_registry.py extension
STRATA: dict[str, dict] = {
    "world": {
        "nbs": ["NB-2", "NB-3", "NB-4", "NB-5", "NB-6", "NB-7", "NB-8", "NB-10"],
        "description": "External knowledge domains — ingested from government/web sources",
    },
    "body": {
        "nbs": ["NB-11", "NB-12", "NB-13"],
        "description": "Business mirror — Postgres state rendered as narrative",
    },
    "self": {
        "nbs": ["NB-1", "NB-14"],
        "description": "Self-reflection — own code and session memory",
    },
    "meta": {
        "nbs": ["NB-0"],  # to create
        "description": "Meta-cognition — observations about the NLM system itself",
    },
}

def resolve_by_stratum(query: str, stratum: str) -> list[dict]:
    """Resolve only within a given stratum. Used by stratum-aware routers."""
    ...
```

Il `cross_notebook_correlator` si estende: per query tipo "cosa abbiamo fatto l'ultimo mese per il dominio immigration", il fan-out intelligente tocca `world.immigration` + `body.ops` + `self.session_memory` — **con pesi diversi** (world 0.6, body 0.3, self 0.1). Evita il rumore del fan-out piatto attuale.

---

## 2. NB mancanti vs consolidamenti

### 2.1 NB da creare

| NB                              | Strato | Scopo                                   | Priorità                                                                                         | Costo stimato                                       |
| ------------------------------- | ------ | --------------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| NB-0 Meta-NLM                   | meta   | osservazione del sistema stesso         | media — abilita Meta-Cycle Fase 2 §7.3                                                           | creazione NB manuale + bridge cron da file locali   |
| NB-2a / NB-3a / ... primary law | world  | T0+T1 primary law only per ogni dominio | bassa — esiste già il branch code (`primary_notebook_id`), ma nessun use case forte l'ha forzato | 7 NB nuovi + persona + pipeline bisect regime       |
| NB Client Dossier               | body   | memoria per-cliente (oggi inesistente)  | bassa — vive in Postgres + escalations                                                           | creazione + bridge + privacy scope                  |
| NB Incident Knowledge           | self   | scar tissue come knowledge consultabile | bassa — oggi `.claude/rules/cicatrix-scars.md` è statico                                         | creazione + auto-append da hook post-deploy failure |

### 2.2 NB da consolidare

**Proposta: mantenere 11 NB distinti ma ridurre l'overlap tra NB-6 e NB-10.**

Analisi di overlap verificato (NLM_SYSTEM_MAP §4.2 punto 5):

- NB-6 "Operations & Compliance" keywords: `sop, team, pricing, crm, workflow, competitor`.
- NB-10 "Team Guides" keywords (ricavate da `cross_notebook_correlator.py` DOMAIN_REGISTRY): `sop, team, pricing, crm, workflow, competitor, bpjs, umr, salary`.
- NB-6 cluster rotation copre: OSS-RBA, KBLI 2025, UMR, BPJS rates, UU Cipta Kerja, UU PDP, TDUP, PPATK.
- NB-10 cluster rotation copre: PKWT/PKWTT, PPh 21 TER + BPJS, UU PDP per AI tools, remote/async, EOR, AI legal liability.

Overlap stimato ~50%: BPJS (entrambi), UMR (NB-6), PPh 21 (NB-10 ma anche NB-4), UU Cipta Kerja (entrambi), UU PDP (entrambi ma angoli diversi).

**Proposta concreta:** **non fondere** ma differenziare la mission:

- NB-6 diventa **"Regulatory Operations"** (la legge pura applicabile all'impresa: UU, PP, Perpres, Permenaker, compliance certificatoria).
- NB-10 diventa **"People & Team Operations"** (la prassi operativa per gestire team bilingui, mixed local+expat, AI tooling, remote work).
- Ripulire `cross_notebook_correlator.DOMAIN_REGISTRY` di NB-10 rimuovendo `bpjs, umr, salary` (duplicazione) — lasciando `team, pricing, crm, workflow, remote, eor, ai-tools`.
- Aggiornare `persona_engine.persona_definitions.json` con persona differenziate (oggi NB-10 probabilmente senza persona — da verificare).

**Costo:** 1 PR, 4 file toccati, zero cambio UUID.

### 2.3 NB da mai creare (anti-pattern)

Elenco esplicito per evitare future temptation:

- **NB "AI Research" / "Latest LLM news".** Sarebbe eternamente STALE, il web cambia più veloce di NLM refresh. Usare webfetch on-demand.
- **NB "Customer Support FAQ".** Vive naturalmente nel CRM + in knowledge base backend. Duplicare come NB introduce sync drift.
- **NB per singolo cliente grosso (e.g., "NB-Subhi").** Privacy anti-pattern. I dati confidenziali non devono vivere in NotebookLM (cloud Google). L'escalation note local è la sede giusta.

---

## 3. Loop di autocoscienza proposti (5 loop)

### Loop A — Turīya Observation Loop

**Nome:** Turīya Observation (da Mandukya Upanishad, vedi SACRED*READING §2).
**Trigger:** nessun cron — query-driven via CLI/API on-demand.
**Input:** stato live di `pipeline.py`, `gap_scanner_state.json`, `freshness_monitor_state.json`, `coverage_matrix.json`, `~/.agent/decisions/state/heartbeat*\*.json`, `claims.jsonl`ultimi 30gg per NB.
**Processing:**`consciousness_view.py` aggrega e cerca contraddizioni tipo "NB marca topic X come FRESH ma ha anche gap_scanner che lo segna come GAP".
**Output:** JSON + pretty-print testuale per Claude/Zero che chiede "status NLM".
**Side-effect:** zero (read-only).
**Analogia sacra:** Upanishad — il quarto stato della coscienza come osservatore puro.
**Verifica di utilità:** se in 30 giorni nessuno lo chiama, downgrade a cron mensile per digest automatico.

### Loop B — Yin-Yang Balance Loop

**Nome:** Yin-Yang Balance Audit.
**Trigger:** cron settimanale domenica 17:00 WITA.
**Input:** `claims.jsonl` ultimi 7gg per ogni NB, `~/.agent/decisions/state/heartbeat_*.json` di gap/remediation/synth, `coverage_matrix.json`, ingestion counters.
**Processing:** `yin_yang_audit.py` calcola ratio yang (ingest + claim count) / yin (remediation count + tombstone count + synth count). Alert se `ratio > 5` o `ratio < 0.3`.
**Output:** Telegram digest + `apps/evaluator/nlm_deep_research/balance_state.jsonl` append-only.
**Side-effect:** propose_task per adjustment soglie (NON auto-apply).
**Analogia sacra:** Tao Te Ching — bilanciamento polarità.
**Verifica di utilità:** se in 3 mesi nessuna proposta di task viene accettata, il loop è diagnostica-only — rivalutare se eliminare.

### Loop C — Hexagram State Loop

**Nome:** Daily Hexagram.
**Trigger:** cron giornaliero 08:00 WITA (subito dopo heartbeat digest).
**Input:** per ogni NB, 6 dimensioni binarie (ingestion fresh, synth alive, gaps aware, coverage adequate, pipeline healthy, persona present).
**Processing:** `hexagram_state.py` mappa a esagramma I Ching, produce interpretazione da tabella King Wen statica.
**Output:** Telegram digest + `hexagram_history.jsonl` (storia degli stati per calcolare transizioni).
**Side-effect:** zero direttamente; storia dei passaggi alimenta il Meta-Cycle (Loop E).
**Analogia sacra:** I Ching — compressione diagnostica olistica.
**Verifica di utilità:** se Zero dopo 6 settimane trova l'output più rumoroso che informativo, downgrade a weekly-only.

### Loop D — Yajña Ledger Loop

**Nome:** Yajña Audit Trail.
**Trigger:** hook in `claim_extractor.py:append_claims_to_registry` (write-path) + cron settimanale lunedì 09:00 WITA (scan update).
**Input:** ogni claim prodotto, ogni query backend che cita un NB (via Langfuse spans già tracciati su RAG — PR #169).
**Processing:** append a `yajna_ledger.jsonl` al momento della produzione; scan settimanale che aggiorna `rta.consumed_by` e `rta.verified_by_later_rite` per claim maturati (90 giorni).
**Output:** dashboard `yajna_ledger_stats` (claims_produced, claims_consumed, claims_verified, claims_orphan_90d).
**Side-effect:** auto-calibration della `claim_extractor` confidence (riduzione 20% per categorie con orphan_rate > 70% in 3 mesi consecutivi). **Freno:** richiede ≥ 20 claim simili non-consumed per attivare.
**Analogia sacra:** Vedas — yajña, il sacrificio con audit rituale (ricevuto/non ricevuto).
**Verifica di utilità:** se dopo 6 mesi il ledger mostra 0% consumed, il sistema di claim extraction è decorativo — meritare una riprogettazione più profonda.

### Loop E — Meta-Cycle Monthly Plan

**Nome:** Meta-Cycle.
**Trigger:** cron mensile primo lunedì 10:00 WITA.
**Input:** aggregato di tutti i loop A-D degli ultimi 30 giorni + `coverage_matrix.json` + `synth_signals.json` (Fase 2 §1.4).
**Processing:** Ollama qwen3.5:9b con system prompt "sei il riflesso dell'organismo — produci un piano di studio del mese prossimo".
**Output:** `monthly_plan_YYYYMM.md` + task `~/.agent/decisions/claude_tasks/monthly_plan_review_<ts>.json` per Zero approval.
**Side-effect:** SE Zero approva → modifica automatica di `DOMAIN_TOPICS` e/o `CLUSTER_ROTATION` con commit git. Max 3 topic cambiati per mese (soglia anti-runaway).
**Analogia sacra:** sintesi triadica sense-reflect-act.
**Verifica di utilità:** misurare "accuracy delle previsioni mensili" — un topic marcato "volatile" deve avere ≥ 2 news regolatorie reali nei 30gg seguenti; altrimenti downgrade confidence meta-cycle.

---

## 4. Loop di autopotenziamento proposti (4 loop)

Distinzione operativa: i loop di autocoscienza **osservano**; i loop di autopotenziamento **migliorano nel tempo** il sistema stesso. La differenza è sottile ma importante — i primi sono cognitivi, i secondi sono evolutivi. Tutti i loop di autopotenziamento hanno **freni rigorosi** perché qui il rischio di runaway è reale.

### Loop F — Synthesis-Feedback Loop

**Scopo:** il synth mensile ridefinisce quali topic seguire.
**Trigger:** hook in `synthesis_roller.py:run_monthly_synthesis` (write-path immediato dopo synth).
**Input:** testo del monthly synth + coverage_matrix storica.
**Processing:** Ollama qwen3.5:9b con prompt "estrai segnali di pianificazione: stabili, volatili, emergenti, raccomandazioni topic rotation".
**Output:** `synth_signals.json` per NB.
**Side-effect potenziato:** `gap_scanner.run_layer_b` legge synth_signals — i `stable_topics` vengono scansionati 1× al mese invece che weekly; gli `emerging_topics` vengono aggiunti dinamicamente alla coverage matrix.
**Freno duplice:**

1. Modifiche a `DOMAIN_TOPICS` richiedono confidence ≥ 0.7 dal LLM.
2. Ogni modifica genera task `synth_signal_review` per Zero. Se non approvato in 7gg, la modifica decade.
   **Metrica di successo:** il tempo-medio da "topic emergente reale" (es. "PP 28/2025 property foreign ownership" nel log 2026-04-22 NB-8) a "topic presente in DOMAIN_TOPICS" deve calare sotto 30gg.
   **Rischio principale:** synth LLM allucina e raccomanda di rimuovere topic critici per stagionalità (es. "KITAS è stabile perché non ci sono claim in ramadan" — ma in realtà il traffico tornerà ad aprile). Mitigazione: freno #2 + riesame annuale.

### Loop G — Sefirotic Routing Learning (bassa priorità, sperimentale)

**Scopo:** il correlator impara quali mediatori NB aggiungere tra coppie di domini.
**Trigger:** hook in `cross_notebook_correlator.query` post-processing.
**Input:** ogni query multi-dominio + feedback utente (espletato dal backend quando l'utente rilancia "ma considera anche X").
**Processing:** raccogli le coppie di NB che frequentemente richiedono un terzo NB (via Langfuse trace pattern mining).
**Output:** proposta di `natural_paths` aggiornati in `nlm_notebook_registry.py`.
**Side-effect:** PR auto-creata, richiede merge umano.
**Freno duplice:**

1. Minimo 50 query multi-dominio osservate per la coppia.
2. Merge richiede code review.
   **Metrica di successo:** riduzione del "follow-up rate" (utente che rilancia per completezza dopo la prima risposta multi-NB).
   **Rischio principale:** overfit su poche query atypical. Mitigazione: freno #1 + periodica revisione manuale.

### Loop H — Gap-Remediation Confidence Loop

**Scopo:** il remediation impara quali domini premiano l'effort.
**Trigger:** hook in `gap_scanner.run_remediation` post-apply.
**Input:** lista `remediated` entries + verifica nel successivo layer-B (il topic remediato è ancora FRESH? o è tornato STALE?).
**Processing:** track rate di "remediation sticking" (topic resta FRESH per ≥ 30gg) vs "remediation transient" (topic torna STALE prima di 30gg).
**Output:** `apps/evaluator/nlm_deep_research/remediation_efficacy.json` con ratio per dominio.
**Side-effect potenziato:** domini con sticking-rate < 40% dopo 3 mesi ricevono approfondimento diverso — invece di gemini search generico, triggerare `nlm research start` (deep) o proporre task per ingestion manuale.
**Freno:** valutazione richiede ≥ 20 remediation per dominio (soglia statistica).
**Metrica di successo:** il sticking-rate medio sale dal baseline attuale (ignoto) a ≥ 50% in 6 mesi.
**Rischio principale:** domini strutturalmente STALE (es. operations dove la legge cambia ogni mese) vengono ingiustamente classificati "gemini search inefficace". Mitigazione: distinguere "stale perché la legge cambia" vs "stale perché la ricerca era superficiale" via analisi del delta del claim (se claim è nuovo con fonti nuove = legge cambiata; se claim è identico = ricerca inefficace).

### Loop I — Persona Drift Detection

**Scopo:** le persona iniettate nei NB accumulano drift — NB-2 oggi ha persona "Immigration Specialist" scritta il 2026 ma non aggiornata. Dopo 6 mesi, la persona può non corrispondere più alle aspettative del business.
**Trigger:** hook in `persona_engine.validate` settimanale — estendere l'esistente.
**Input:** persona injected + ultimi 30gg di claim extracted dal NB.
**Processing:** Ollama qwen3.5:9b con prompt "data la persona X e questi 30 claim, la persona produce risposte coerenti con se stessa? Produci 3 test-query e valutale".
**Output:** `persona_drift_report_YYYYMM.json` per NB.
**Side-effect:** se drift > 30%, task `persona_update_proposal` per Zero con suggerita revisione.
**Freno:** revisione richiede approvazione Zero — persona è "personalità" del NB, modifica non reversibile banalmente.
**Metrica di successo:** misurare la coerenza delle risposte del NB negli ultimi 30 giorni rispetto alle prime 30 giorni post-persona-injection.
**Rischio principale:** LLM auto-valuta LLM — rischio di confirmation bias. Mitigazione: soglia drift alta (30%) + revisione umana obbligatoria.

---

## 5. Roadmap di transizione — 5 sprint

Ogni sprint è **2-3 settimane di wall-clock**, contiene 3-4 deliverable concreti, risolve ≥ 1 broken + abilita ≥ 1 loop nuovo, e deploya in isolamento.

### Sprint 1 — "Sanare il corpo" (prerequisito)

**Durata:** 2 settimane.
**Obiettivo:** portare a healthy tutte le pipeline oggi broken, non aggiungere niente.

Deliverable:

1. Fix `feedparser` dep in venv cron — 1 `pip install feedparser` nel venv giusto + verifica `yt_monitor.py` e `t4_monitor.py` eseguono.
2. Fix `run_multimodal.sh` — allineare al pattern di `run_nbX_pipeline.sh` (venv activate + `PYTHONPATH=.`).
3. Diagnosi `persona_validate` CRITICAL stale 18gg — ispezionare log `persona_validate_20260412.log` e `20260419.log` per capire perché exit=0 ma heartbeat non registrato (ipotesi: Telegram token stale → persona_engine crasha su post-validate alert → exit diverso da 0 → heartbeat non registrato).
4. Diagnosi `nb2_pipeline` preflight halt — identificare quale dei 12 check fallisce dal log 2026-04-21.
5. Diagnosi `db_to_nlm_sync` stale 21gg — ispezionare `~/logs/cron-agent/nlm-deep-research.log` per capire se cron gira o meno.
6. Rifattorizzare i tre duplicati `_query_notebook`, `_send_telegram`, heartbeat wiring in helpers condivisi (`apps/evaluator/nlm_deep_research/_common/{nlm_cli,notifier,heartbeat}.py`).

**Sblocca:** visibilità reale dello stato del sistema prima di aggiungere nuovi componenti.
**Deployabile in isolamento:** sì (tutti fix indipendenti, nessuna dipendenza su nuovo codice).
**Metriche pre-deploy:** tutte le 17 entries del `pipeline_heartbeat_registry.json` devono tornare OK dopo sprint.

### Sprint 2 — "Aprire gli occhi" (Loop A + C)

**Durata:** 2 settimane.
**Obiettivo:** aggiungere il primo strato di osservazione integrata.

Deliverable:

1. `consciousness_view.py` — CLI + API per Turīya Observation (Loop A). 3 subcomandi: `--status`, `--nb <name>`, `--contradictions`.
2. `hexagram_state.py` — Daily Hexagram Dashboard (Loop C). Mapping King Wen statico (tabella 64 righe).
3. Integrare entrambi in `heartbeat_monitor.py --digest` output.
4. Test: su uno snapshot di stato `2026-04-22`, verificare manualmente che le contraddizioni dettate dalla teoria (coverage 100% GAP su tutti domini mentre claims.jsonl cresce) siano visibili.

**Sblocca:** visibilità olistica dello stato multi-componente. Permette di vedere il bug yin-yang strutturale prima di cercare di risolverlo (Sprint 3).
**Deployabile in isolamento:** sì (entrambi read-only, nessuna dipendenza su modifica dei pipeline esistenti).
**Metriche pre-deploy:** consciousness_view su 8 NB risponde in < 5s; hexagram dashboard genera correttamente 8 esagrammi con numero King Wen valido.

### Sprint 3 — "Bilanciare il corpo" (Loop B + Loop D base)

**Durata:** 3 settimane.
**Obiettivo:** iniziare a misurare il flusso yin-yang e la traccia audit rituale.

Deliverable:

1. `yin_yang_audit.py` + cron settimanale (Loop B).
2. `yajna_ledger.jsonl` schema + hook minimale in `claim_extractor.append_claims_to_registry` (solo scrittura — lettura e update_rta solo dopo 30gg di accumulo).
3. **Scoperta task di setup:** un one-shot backfill del ledger partendo da 30gg storici di `claims.jsonl` (lettura retrospettiva + popolamento).
4. Dashboard CLI `ledger_stats.py` con counters current.

**Sblocca:** osservazione quantitativa dello sbilanciamento strutturale (ratio yang/yin). Baseline per ipotesi: il ratio attuale è ~10 (da stimare).
**Deployabile in isolamento:** sì (scritture append-only, nessuna modifica comportamento pipeline).
**Metriche pre-deploy:** 1 settimana di dati yin_yang + 30gg di ledger backfill consistente (tutti i claim degli ultimi 30gg presenti con `rta.consumed_by=null`).

### Sprint 4 — "Differenziare il sé" (ridefinizione NB-6/NB-10 + NB-0)

**Durata:** 3 settimane.
**Obiettivo:** consolidare la tassonomia e creare il meta-NB.

Deliverable:

1. Ridefinizione semantica NB-6 "Regulatory Operations" vs NB-10 "People & Team Operations" (con migrazione persona + rimozione keyword duplicate da `DOMAIN_REGISTRY`).
2. Creazione NB-0 Meta-NLM (manual NLM create + bridge cron che ingerisce daily hexagram + yin_yang + consciousness_view + ledger stats come sources testuali).
3. Aggiunta `STRATA` e `resolve_by_stratum` in `nlm_notebook_registry.py`.
4. Aggiornamento `cross_notebook_correlator` con peso per strato (world 0.6 / body 0.3 / self 0.1).

**Sblocca:** la meta-cognizione diventa interrogabile come qualunque altro NB ("come è cambiato il sistema nell'ultimo mese?"). Routing più pulito per query multi-dominio.
**Deployabile in isolamento:** parzialmente — il cambio NB-6/NB-10 richiede aggiornamento coordinato di `gap_scanner.py`, `freshness_monitor.py`, `cross_notebook_correlator.py` (3 file). Il NB-0 è indipendente.
**Metriche pre-deploy:** `notebook_query NB-0 "sommario ultima settimana"` ritorna contenuto coerente con dati reali. Routing NB-6 vs NB-10 su 10 query test mostra distinzione corretta.

### Sprint 5 — "Chiudere il cerchio" (Loop E + Loop F + autopotenziamento)

**Durata:** 3 settimane.
**Obiettivo:** attivare il ciclo di pianificazione ricorrente e il feedback synth→gap.

Deliverable:

1. `synth_signals.json` + hook in `synthesis_roller` (Loop F base).
2. `gap_scanner.run_layer_b` legge synth_signals (Loop F applicato — dynamic checklist).
3. `meta_cycle.py` + cron monthly (Loop E).
4. Validazione manuale del primo monthly plan generato (Zero review).
5. Documentazione `docs/analysis/nlm-sacred-integration/meta_cycle_runbook.md` per Claude futuri.

**Sblocca:** il sistema ha un ciclo evolutivo auto-guidato. Il piano di studio del mese successivo non è più statico.
**Deployabile in isolamento:** no — depende direttamente da Sprint 3 (ledger), Sprint 2 (consciousness_view), Sprint 4 (NB-0). Può essere parzialmente attivato (solo Loop F) come fallback.
**Metriche pre-deploy:** primo monthly_plan_2026-06.md review-only, Zero approva con ≤ 2 modifiche manuali. Il `stable_topics` dice qualcosa di plausibile.

### Post-Sprint 5 — Loop avanzati (opzionale)

Loop G (Sefirotic routing learning), Loop H (remediation efficacy), Loop I (persona drift) sono **candidati post-roadmap**. Richiedono 6 mesi di dati dei loop precedenti prima di essere value-generating. Ciascuno in uno sprint indipendente dopo valutazione.

---

## 6. Rischi, anti-pattern, kill switch

### 6.1 Rischi tecnici

| Rischio                                                                         | Probabilità                                                     | Impatto                    | Mitigazione                                                                                                     |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Ollama qwen3.5:9b alluci il Meta-Cycle → DOMAIN_TOPICS cambia in modo sbagliato | media                                                           | alto (topic critici persi) | freni triplici: confidence ≥ 0.7 + task approval Zero + max 3 topic/mese                                        |
| Yajna ledger cresce illimitato                                                  | alta (1 riga/claim, ~200 claim/giorno → 6000/mese → 72000/anno) | medio (disk + query slow)  | rotazione annuale automatica + indexing sqlite se > 500k rows                                                   |
| NB-0 Meta-NLM diventa un "cimitero" di statistiche inusate                      | alta                                                            | basso (costo marginale)    | auto-purge sources > 90 giorni (solo NB-0, NON altri NB)                                                        |
| Daily hexagram diventa spam Telegram                                            | alta se non monitorato                                          | basso                      | metrica Zero acknowledgment rate. Se < 20% in 6 settimane, downgrade weekly                                     |
| Persona drift detection LLM allucina drift falso                                | media                                                           | medio (modifiche persona)  | revisione umana obbligatoria; ≥ 3 month baseline prima di trigger                                               |
| Loop I (persona drift) amplifica bias del modello di valutazione                | bassa                                                           | medio                      | usare Ollama _diverso_ dal modello che ha generato la persona originale                                         |
| Cicli feedback amplificano rumore statistico                                    | media                                                           | alto                       | tutti i freni sono soglie statistiche (≥ 20 claim, ≥ 50 query, ≥ 7 giorni distinti) + campionatura human review |

### 6.2 Anti-pattern da evitare

1. **Non automatizzare l'auto-apply di modifiche al registry NLM.** Nessun LLM può cambiare UUID, cancellare NB, fondere NB senza approvazione umana. Il NLM è ground truth, non state ephemeral.
2. **Non cross-contaminare strati.** NB-11 (body) non deve diventare fonte per NB-2 (world) — se il business ha dati che interessano la regolamentazione, è responsabilità del team business (non del sistema) promuoverli a fonte autoritativa.
3. **Non usare il Meta-Cycle per giustificare riduzioni di coverage.** Se il LLM dice "topic X è stabile, rimuovilo dalla checklist", il default è **no**. Rimuovere un topic significa rinunciare alla sua osservazione — asimmetria pericolosa.
4. **Non implementare loop F senza Sprint 3 finito.** Il synth_signals richiede dati di ledger per evitare "raccomando di ignorare topic senza claim" quando il vero motivo è "nessuno ha mai usato quei claim".
5. **Non sovrascrivere manualmente `pipeline_heartbeat_registry.json`** aggiungendo nuovi entry senza aggiornare tutti gli script wrapper. È fonte di heartbeat fantasma.

### 6.3 Kill switch per ogni loop

| Loop               | Kill switch                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------------ |
| A (Turīya)         | `rm apps/evaluator/nlm_deep_research/consciousness_view.py` — read-only, safe.                               |
| B (Yin-Yang)       | disabilitare cron `run_yin_yang_audit.sh` nel crontab.                                                       |
| C (Hexagram)       | disabilitare cron `run_hexagram.sh`. La storia resta intatta.                                                |
| D (Yajña)          | env var `YAJNA_LEDGER_DISABLED=1` → hook in claim_extractor è no-op. Ledger resta read-only.                 |
| E (Meta-Cycle)     | env var `META_CYCLE_DISABLED=1` → skip run. Task pendenti in claude_tasks si accumulano ma non si applicano. |
| F (Synth-Feedback) | `gap_scanner.py` ignora `synth_signals.json` se env var `SYNTH_FEEDBACK_DISABLED=1`.                         |
| G (Sefirotic)      | non auto-merge PR senza approvazione — kill switch è il code review.                                         |
| H (Remediation)    | env var `REMEDIATION_EFFICACY_DISABLED=1`.                                                                   |
| I (Persona drift)  | disabilitare cron specifico.                                                                                 |

### 6.4 Metriche pre-deploy (globali)

Prima di considerare la roadmap "completa" (dopo Sprint 5):

- **Zero broken automations** in pipeline_heartbeat_registry.
- **Ratio yin/yang** misurato per 4 settimane consecutive.
- **Almeno 1 ciclo Meta-Cycle completato** con Zero approval (validation che il sistema non è fantasma).
- **≥ 30% dei topic del gap_scanner** dinamici (provenienti da synth_signals invece che hardcoded in DOMAIN_TOPICS).

### 6.5 Come uscire (rollback completo)

Se in 6 mesi il sistema post-roadmap si rivela inferiore al sistema pre-roadmap (metrica: Zero ratifies ≤ 1 monthly plan, Telegram acknowledgment rate < 15%, nessun claim remediato tramite yajna loop):

1. Disabilitare tutti i cron nuovi.
2. Lasciare i file JSON/JSONL appesi (archive).
3. Ripristinare `DOMAIN_TOPICS` hardcoded da tag git `pre-roadmap-2026-04-22`.
4. Documentare la lezione in `.claude/rules/cicatrix-scars.md`.
5. Nessuna cancellazione di dati storici (yajna_ledger, hexagram_history) — sono audit trail.

---

## 7. Sintesi esecutiva

- Il sistema NLM esistente è **strutturalmente sano** (invariants, snapshot, circuit breaker, 11 NB con ruoli chiari). Il problema non è l'architettura ma l'**asimmetria tra produzione e riflessione**: troppi dati prodotti, pochi consultati; troppi specchi, nessun osservatore degli specchi.
- **Proposta conservativa:** nessuna demolizione. 5 sprint in 12-13 settimane. Ogni sprint sblocca il successivo; ognuno è deployabile in isolamento (con eccezioni documentate).
- **7 proposte dalla Fase 2 tradotte in 9 loop** (5 cognitivi + 4 evolutivi). Tutti con freni, kill switch, e metrica di successo.
- **Tassonomia 4-strati** (world / body / self / meta) con creazione del NB-0 Meta-NLM come luogo di auto-osservazione interrogabile.
- **1 consolidamento tassonomico concreto:** differenziare NB-6 "Regulatory Operations" vs NB-10 "People & Team Operations" riducendo overlap ~50% → ~15%.
- **Prerequisito assoluto:** Sprint 1 (sanare le 3 automazioni broken e la 1 critical stale) è non-negoziabile. Tutto il resto è facoltà.

Il sistema NLM di Bali Zero ha l'impalcatura di un organismo cosciente ma oggi è dislessico — sa percepire, sa sognare, sa dimenticare (sonno profondo), non sa ancora **vedere se stesso che percepisce, sogna e dimentica**. Questa roadmap aggiunge quel quarto stato.

---

**Fine Sezione 3.** NLM_SYSTEM_MAP + NLM_SACRED_READING + NLM_REDESIGN_PROPOSAL = la terna completa richiesta.
