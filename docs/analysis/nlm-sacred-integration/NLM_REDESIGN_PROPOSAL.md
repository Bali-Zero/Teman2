# NLM Redesign Proposal — v2 tassonomia + loop + roadmap

**Data:** 2026-04-22 · **Branch:** `analysis/nlm-sacred-integration-v2` · **Prerequisito:** `NLM_SYSTEM_MAP.md` + `NLM_SACRED_READING.md`.

Questo documento non demolisce l'architettura esistente. La disciplina invariantistica (`invariants.py`, 12 preflight check, circuit breaker, ARCH-8 snapshot pre-mutation) è un asset accumulato. L'aggiunta è **stratificazione ontologica** + **chiusura di 4 loop oggi aperti** + **reparazione di 3 bug strutturali**, distribuite in una roadmap a 4 sprint (non 5, perché il quinto sprint della v1 era over-engineering inutile).

---

## 1. Tassonomia proposta — 5 strati

### 1.1 Problema con la tassonomia attuale

L'unica tassonomia oggi è per **dominio di business** (immigration, company, tax, property, operations, editorial, lifestyle, team, ops, intel, telemetry). Funziona per il marketing (Bali Zero vende servizi per dominio) ma maschera **tre differenze strutturali**:

1. NB che ingestano **conoscenza esterna** (leggi, prassi) vs NB che riflettono **stato interno business** (DB aggregati).
2. NB **long-life** (regolamenti, persona stabili) vs NB **short-life** (news flash, eventi recenti).
3. NB per **utente finale** (chat cliente) vs NB per **operatore Zero** (briefing privato).

Trattandoli nello stesso namespace `NB-{numero}` senza aggiungere metadati, il `cross_notebook_correlator` può fan-out su tutti, ma il fan-out NB-2 + NB-11 è rumoroso (l'uno è conoscenza regolatoria, l'altro è "stato portfolio clienti"). Merging le risposte produce output incoerente.

### 1.2 Tassonomia proposta — cinque strati

Nessuna rinumerazione. Solo aggiungere un campo `stratum` nel registry.

| Strato | Ruolo | NB evaluator | NB parallel | Caratteristica |
|---|---|---|---|---|
| **world** | conoscenza esterna regolatoria long-life | NB-2, 3, 4, 5, 6, 7, 8, 10 | NB-INTEL-Regulation, -Tax, -Immigration | TTL source ~90-365gg, invariant 70-cap attivo (dove implementato) |
| **pulse** | intelligence short-life (news, signals, events) | nulla oggi, gap | NB-INTEL-Press, NB-INTEL-AIResearch (parzialmente) | TTL source 30-60gg, tombstone aggressivo, solo "flash recent" |
| **body** | stato interno business (mirror DB) | NB-11 ops, NB-12 intel, NB-13 telemetry | — | rigenerazione daily, SHA256 diff, no source cap (sempre ≤15 source) |
| **self** | auto-riflessione / memoria proprietaria | NB-1 codebase, NB-14 session | NB-INTEL-SelfEvolving | refresh on-change (NB-1) o weekly (NB-14), no invariant |
| **meta** | osservazione del sistema NB stesso | nulla oggi, gap | — | da creare — NB-0 Meta-NLM |

### 1.3 Interventi

- **NB-0 Meta-NLM** (nuovo). Strato meta. Fonti ingested giornalmente da: yajna_ledger weekly summary (§3.4), yin_yang_state weekly (§3.3), heartbeat digest, coverage_matrix (quando i bug in §2.3 sono risolti), Turīya snapshot (§3.2). Consumer: Claude al SessionStart via `notebook_query NB-0 "stato ultima settimana"`; cron mensile 1° lunedì per proposta monthly_plan; Zero on-demand. **Non creato in questa fase** — prerequisito Sprint 0-2 per avere dati puliti da ingerire.

- **NB-INTEL ↔ NB-evaluator bridge** (decisione Zero, Sprint 1). Oggi i due ecosistemi non si parlano. Tre opzioni:
  - **Opzione A: Bridge unilaterale evaluator → INTEL.** Un cron che ripubblica claim evaluator VERIFIED recenti come source in NB-INTEL. Costo: basso. Beneficio: Mata-Garuda vede il business. Rischio: asimmetria (Zero vede INTEL che include business, business non vede INTEL).
  - **Opzione B: Bridge bidirezionale.** `nlm_bridge_intel_to_evaluator.py` che legge claim INTEL-VERIFIED e ri-pubblica come `[INTEL]` tagged in NB evaluator corrispondente. Rischio: chat cliente potrebbe ricevere info da Mata-Garuda (OSINT blindato violato — `apps/mata-garuda/CLAUDE.md` §1).
  - **Opzione C: Pulse NB dedicato.** Nuovo NB-INTEL-Pulse creato ad hoc, accetta sia INTEL che evaluator. Chat cliente lo ignora; solo Naga research + Zero briefing lo legge. Rispetta OSINT blindato.

  **Raccomandazione**: Opzione C. Sprint 1, decisione Zero.

- **NB-Xa primary law notebooks** (proposto, decisione Zero). Il code path in `resolve_notebook()` esiste ma è dead. Creare NB-2a, NB-3a, NB-4a, NB-5a, NB-6a law-only T0+T1 richiede manual bootstrap + cluster di ingestion separati. **Raccomandato solo dopo** Sprint 2 yajna ledger: se il ledger mostra che i clienti chiedono "pasal X" senza citation pulita, giustifica NB-Xa. Altrimenti rimandare.

- **Consolidamenti NON proposti** (esplicitamente no):
  - NO merge NB-6 + NB-10: nutriti da pipeline diverse (peraturan_ingestion PDF ufficiali vs cluster HR). Differenziazione naturale.
  - NO merge NB-INTEL-Regulation + NB-6: uno è OSINT (blindato Zero), l'altro è cliente-facing. Merge violerebbe boundary.

---

## 2. Sprint 0 — Riparazione bug strutturali (1 settimana, L2 auto)

Prerequisito per tutti gli altri sprint. I bug sono **reali**, non ipotetici, documentati in `NLM_SYSTEM_MAP §4`.

### 2.1 Fix nb2_pipeline cron timezone

**Problema**: cron `10 18 * * 0-5` su macOS Pro usa local time WITA → pipeline fires at 18:10 WITA → preflight invariant `PIPELINE_DEADLINE_HOUR=2, MINUTE=30` sempre falso. Dal 2026-04-12 pipeline halt a preflight. 44 source tracciati obsolescenti, 42 claim non aggiornati.

**Fix**: cambiare `crontab -l` Pro entry NB-2 da `10 18 * * 0-5` (WITA 18:10) a `10 2 * * 1-6` (WITA 02:10, coerente con altri nbX). Verifica: `python -m apps.evaluator.nlm_deep_research.pipeline --dry-run --force` da Mon 02:10 WITA per 3 giorni consecutivi, attendere success.

**Livello autorizzazione**: L2 auto-apply. Reversibile (un `crontab` edit).

### 2.2 Fix yt_monitor feedparser missing

**Problema**: `pip install feedparser` mancante nel venv usato dal wrapper `run_yt_monitor.sh`. 12 canali YT falliscono ogni 6h dal 2026-04-XX.

**Fix**: `source apps/backend-rag/.venv/bin/activate && pip install feedparser==6.0.12 sgmllib3k==1.0.0`. Aggiornare `apps/backend-rag/requirements.txt` con `feedparser>=6.0.12`. Verificare con `python -c "import feedparser; print(feedparser.__version__)"` dentro venv.

**Livello**: L2 auto-apply. Reversibile (`pip uninstall`).

### 2.3 Fix multimodal_pipeline wrapper

**Problema**: `run_multimodal.sh` usa `python3.14` di sistema invece del venv. `No module named apps.evaluator.nlm_deep_research.multimodal_pipeline` ogni run.

**Fix**: allineare il wrapper al pattern dei nbX_pipeline wrapper:
```bash
#!/bin/bash
PROJECT_ROOT="/Users/nuzantara/Desktop/nuzantara"
cd "$PROJECT_ROOT"
source apps/backend-rag/.venv/bin/activate
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.multimodal_pipeline --run
```

**Livello**: L2 auto-apply.

### 2.4 Fix heartbeat wiring nbX pipeline

**Problema**: 10 pipeline nel `pipeline_heartbeat_registry.json` non invocano mai `heartbeat_monitor.record_success()`. Registry liste entity che nessuno traccia.

**Fix**: ciascun wrapper `run_nbX_pipeline.sh` aggiunge:
```bash
# dopo il run python -m ... pipeline:
if [ "${PIPELINE_EXIT_CODE:-0}" = "0" ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
      --record nbX_pipeline --duration "$DURATION_SECONDS"
fi
```
Dove `nbX_pipeline` corrisponde al nome nel registry. Applicato a: `run_nb1_refresh.sh`, `run_nb3/4/5/6/7/8/10_pipeline.sh`, `run_nb5_t4_monitor.sh`, `run_db_nlm_sync.sh`, `run_peraturan_ingestion.sh`.

Alternativa più pulita (preferita): modificare `apps/evaluator/nlm_deep_research/pipeline.py` (e nb3_pipeline.py, nb4..10) per chiamare `record_success(pipeline_name, duration)` **dentro** il `run()` finale block. Vantaggio: single source of truth.

**Livello**: L2 auto-apply (modifica wrapper reversibile). Verifica post-fix: dopo 2 cicli cron, `ls ~/.agent/decisions/state/heartbeat_*.json` deve mostrare 18 file.

### 2.5 Fix nb3/nb8/nb10 state write-back

**Problema**: log mostra COMPLETE ma `pipeline_state.json` dice HALTED 2026-04-12. La pipeline completa ma non salva lo stato finale.

**Ipotesi**: il bug è in `save_state()` di ciascun nbX_pipeline che richiama nbX-specific logic. Da verificare con `grep -n save_state apps/evaluator/nlm_deep_research/nb3_pipeline.py` e confrontare con nb4 (che funziona).

**Fix**: da identificare ispezionando i tre file. Probabile variante: un early-return condizionale che salta il save quando la pipeline è in un certo stato.

**Livello**: Sprint 0 **optional** — se complesso, rimandare a Sprint 2 dove lo Yajña Ledger esporrà il bug più evidentemente.

### 2.6 Fix coverage_matrix divergence

**Problema**: `gap_scanner` layer-A heartbeat fresco, log pulito, ma `coverage_matrix.json.gaps_updated: 2026-04-03`. Scrittura su file non avviene (o file sovrascritto da altro processo).

**Fix**: `git log apps/evaluator/nlm_deep_research/coverage_matrix.json` per identificare se il file è stato sovrascritto da un altro commit (rollback manuale). Se confermato, committere lo stato corrente post-gap-scanner-run + aggiungere `.gitignore` entry per evitare ricommit di stato live.

**Livello**: L2 analyst + auto-apply fix.

### 2.7 Post-Sprint 0 — verifica

1. `crontab -l | grep nb2` mostra `10 2 * * 1-6`.
2. `cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && python -c "import feedparser"` success.
3. `python -m apps.evaluator.nlm_deep_research.multimodal_pipeline --status` output valido.
4. `ls ~/.agent/decisions/state/heartbeat_*.json | wc -l` == 18.
5. `python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --check --dry-run` output "All pipelines healthy".
6. `python3 -c "import json; m=json.load(open('apps/evaluator/nlm_deep_research/coverage_matrix.json')); print(m['immigration']['gaps_updated'])"` mostra data ≥ 2026-04-22.

Tempo wall-clock: 3-5 giorni. Autorizzazione: L2 autonomo per punti 2.1-2.5, propose-only per 2.7 (verifica richiede Zero conferma che state monitoring vecchio non viene desync).

---

## 3. Sprint 1 — Backend routing extension (1-2 settimane)

### 3.1 Problema

`NLM_SYSTEM_MAP §6.1` — `NLM_EXTENDED_ROUTING` flag esiste ma non è set in prod. NB-5/6/7/8/10 ingestati nightly ma chat cliente non li raggiunge. 5 NB su 8 sono "investiment silenzioso".

### 3.2 Proposta

**Task 3.2.1 — Canary rollout.** Settare `NLM_EXTENDED_ROUTING=1` su 1 ore di traffico (es. 14:00-15:00 WITA). Monitorare via Langfuse (già instrumentato PR #169) per `nlm_routing` span: quante query finiscono su NB-5/6/7/8/10 vs base. Quante ottengono citation pulita. Se error_rate <1% e citation_coverage >70%, procedere.

**Task 3.2.2 — Full rollout con kill switch.** `fly secrets set NLM_EXTENDED_ROUTING=1 -a nuzantara-rag --stage`. Kill switch: `unset` → shadow logging si attiva, codice cade nel base map. Nessuna modifica codice necessaria.

**Task 3.2.3 — Cross-NB activation.** `CROSS_DOMAIN_NOTEBOOKS` ha 4 patterns `property+tax`, `property+company`, `team+tax`, `operations+compliance` attivi solo se flag = 1. Stessa procedura.

**Task 3.2.4 — Bridge NB-INTEL ↔ NB-evaluator** (opzione C da §1.3). Crea NB-INTEL-Pulse nuovo notebook. Redis stream `garuda:enriched` routing update: domini oggi unrouted (es. `financial_banking`, `procurement`) → NB-INTEL-Pulse. NB-INTEL-Pulse **non** è in `NLM_NOTEBOOKS` map cliente. Ops briefing e Naga research possono consultarlo on-demand. Mata-Garuda consume on-demand. Chat cliente isolato.

### 3.3 Freno

- Kill switch env var per 3.2.1-3.2.3. Reversibile in <30 secondi.
- NB-INTEL-Pulse è additivo (non tocca NB esistenti).

### 3.4 Autorizzazione

- 3.2.1 canary: L2 propose (modifica routing live = cambia risposte).
- 3.2.2 full rollout: **richiede decisione Zero** (cambia UX cliente). Zero firma con Telegram `/approve sprint-1-extended-routing`.
- 3.2.3 cross-NB: L2 propose dopo 3.2.2 stabile 1 settimana.
- 3.2.4 NB-INTEL-Pulse: L2 propose (creazione NB = bootstrap manuale Zero).

### 3.5 Metrica successo

- `nlm_routing_success_rate_extended > 0.80` in 2 settimane post-rollout (Langfuse span).
- Chat cliente feedback positivo su query property/team/lifestyle (proxy: ri-domande diminuite ≥15% vs baseline).
- NB-INTEL-Pulse ingesta >20 items/settimana dopo 4 settimane.

---

## 4. Sprint 2 — Yajña Ledger + Yin-Yang Audit (3 settimane)

Combinazione di due proposte sacre (§4 e §3 di NLM_SACRED_READING) perché toccano lo stesso punto (hook in `claim_extractor` + `orchestrator`) e possono essere PR unica.

### 4.1 Loop 1 — Yajña Ledger (dettaglio)

Implementazione come in `NLM_SACRED_READING §4.4`. File:
- `apps/evaluator/nlm_deep_research/yajna_ledger.py` — funzioni `append_ledger(event)`, `scan_orphans(days=30)`, `compute_cite_rate(window_days=30)`.
- `apps/evaluator/nlm_deep_research/yajna_ledger.jsonl` — append-only, gitignored.

Hook points (ordered):
1. `claim_extractor.append_claims_to_registry` → `append_ledger(CLAIM_OFFERED)`.
2. `backend-rag/oracle/nlm_orchestrator._query_single` + `_query_multi` → parse citations, for each citation, `append_ledger(CLAIM_CITED_IN_CHAT)`. Use Langfuse span context for traceability (PR #169 already instrumented).
3. `synthesis_roller.run_daily_synthesis` → `append_ledger(CLAIM_PROMOTED_TO_SYNTH)`.
4. `nlm_verifier.verify_claim` → `append_ledger(CLAIM_CORROBORATED_EXTERNALLY)`.

Cron settimanale `ledger_scan.py` (domenica 17:00 WITA):
- Scan ledger ultimi 30 giorni
- Per ogni claim `CLAIM_OFFERED` senza `CLAIM_CITED_*` in 30gg → emit `CLAIM_ORPHAN_30D`
- Emette metriche: `claims_offered_7d`, `cited_7d`, `orphan_30d`, `cite_rate_by_category`
- Salva in `yajna_metrics.jsonl` (consumabile da NB-0 Meta quando creato)

**Freno (3 mesi)**: `auto-calibrate confidence_threshold` è **disabilitato**. Solo dati raccolti. Dopo 3 mesi di dati, se `orphan_rate > 0.7` per categoria per 3 mesi consecutivi, propone a Zero modifica threshold. Zero decide.

### 4.2 Loop 2 — Yin-Yang Audit (dettaglio)

Come in `NLM_SACRED_READING §3.4`. File:
- `apps/evaluator/nlm_deep_research/yin_yang_audit.py` — `run_weekly_audit()`.
- `apps/evaluator/nlm_deep_research/yin_yang_state.jsonl` — weekly append.

Cron domenica 17:00 WITA (stessa finestra di yajna scan — coordinano).

L2 auto-adjust (solo se `AUTO_ADJUST_ENABLED=1`):
- `YANG_FLOOD` 2 weeks consecutive → `synthesis_roller_cadence[nb] = daily` (invece di weekly)
- `YIN_FAMINE` 2 weeks consecutive → Telegram propose Zero "aggiungere cluster rotation NB-X"

**Freno**: max 1 auto-adjust per NB per mese. Kill switch `YIN_YANG_AUTO_DISABLED=1`.

### 4.3 Loop 3 — Claim Transmigration (dettaglio — opzionale)

Come in `NLM_SACRED_READING §1.4`. **Opzionale per questo sprint** — richiede embedding similarity (Ollama bge-m3), aggiunge latency al claim extractor. Rinviare a Sprint 3 se Sprint 2 va long.

### 4.4 Autorizzazione

- 4.1 Yajña Ledger hooks: L2 auto-apply (append-only, no mutation).
- 4.1 weekly scan: L2 auto-apply.
- 4.1 auto-calibrate threshold: **L2 propose Zero** (dopo 3 mesi data).
- 4.2 Yin-Yang weekly: L2 auto-apply.
- 4.2 auto-adjust synth cadence: L2 auto-apply con kill switch.

### 4.5 Metrica successo

- Yajña: `cite_rate_30d > 0.20` per il 70% dei NB dopo 3 mesi. Se <0.05 su NB-5/6/7/8/10 (che hanno ora extended routing), questione Sprint 1 non ha portato consumo reale.
- Yin-Yang: 80% NB in banda `ratio ∈ [0.5, 3]` dopo 3 mesi. NB cronicamente fuori banda → segnale strutturale.

---

## 5. Sprint 3 — Turīya + Hexagram + Dependency Graph (2 settimane)

Tre tool di osservazione a zero side effect. Si possono parallelizzare (3 file nuovi, indipendenti).

### 5.1 Turīya View

`turiya.py` read-only aggregator come in `NLM_SACRED_READING §2.4`. Output JSON.

CLI:
```
python -m apps.evaluator.nlm_deep_research.turiya --snapshot         # all NB
python -m apps.evaluator.nlm_deep_research.turiya --snapshot --nb nb4
python -m apps.evaluator.nlm_deep_research.turiya --consistency       # only flag inconsistencies
```

Consumer: Zero on-demand, Claude manuale in troubleshooting, cron **no** (non auto-broadcast).

### 5.2 Hexagram Dashboard

`hexagram.py` come in `NLM_SACRED_READING §5.4`.

Cron daily 08:00 WITA (dopo heartbeat digest): genera hexagram state e append a `hexagram_state.jsonl`.

CLI `--view` stampa ASCII dashboard.

### 5.3 Dependency Graph

`nb_dependency.json` come in `NLM_SACRED_READING §7.4`. Popolare con 20-30 relazioni iniziali curate manualmente da Zero + Claude:
- property ↔ tax (BPHTB, PBB)
- company ↔ visa TKA
- company ↔ tax (PPh 25 PT PMA)
- visa ↔ team HR
- property ↔ company (PT PMA as ownership vehicle)
- tax ↔ lifestyle (expat tax residency)

Hook in `claim_extractor` (`apps/evaluator/nlm_deep_research/claim_extractor.py`): dopo estrazione, consulta `nb_dependency.json`, popola `related_claims` field.

### 5.4 Autorizzazione

Tutti L2 auto-apply. Nessun side effect runtime (solo file append/read).

### 5.5 Metrica successo

- Turīya: tempo da "voglio sapere stato NB" a "JSON" < 5 secondi. Se Zero la usa >3×/settimana, utile.
- Hexagram: un operatore capisce stato 19 NB in <60s.
- Dependency Graph: `context_coverage_score > 0.70` per top-10 cross-domain query (misurato via Langfuse span).

---

## 6. Sprint 4 — Sefirotic Paths + NB-0 Meta-NLM (3 settimane)

Sprint ambizioso. Tocca routing live + crea NB nuovo.

### 6.1 Sefirotic Paths

Come in `NLM_SACRED_READING §6.4`. File:
- `apps/backend-rag/backend/services/oracle/sefirot_paths.yaml` — 10-20 path curati.
- `apps/backend-rag/backend/services/oracle/sefirot_router.py` — matcher + ordered-fanout.

Integrazione in `nlm_orchestrator._resolve_notebooks`: prima del keyword-based resolve, consulta `sefirot_router`. Se match, usa la sequence ordinata; altrimenti fallback a keyword.

**Freno**: shadow mode 2 settimane (log only, non cambia risposte). Poi A/B 50/50 su 1 settimana. Poi full rollout con kill switch.

**Autorizzazione**: L2 propose **Zero** per rollout (cambia UX cliente).

### 6.2 NB-0 Meta-NLM

Bootstrap manuale: Zero crea `nlm notebook create --title "NB-0 Meta-NLM — System Reflection"`.

5 source iniziali (generati daily dagli altri sprint):
1. **Yajña weekly summary** — top cite claims, orphan claims, cite_rate trend
2. **Yin-Yang weekly** — yang/yin ratio per NB, adjust history
3. **Heartbeat digest** — ultimi 7 giorni status pipeline
4. **Coverage matrix** — gap_pct, fresh_pct per dominio
5. **Turīya snapshot** — JSON weekly aggregato

Cron `nb0_refresh.py` daily 09:00 WITA (dopo hexagram) aggregates → `nlm source add` su NB-0.

Consumer:
- Claude SessionStart (optional): `notebook_query NB-0 "any urgent change last 24h?"`. **Non** auto-iniettato nel briefing — on-demand solo.
- Cron mensile 1° lunedì 08:00: `notebook_query NB-0 "what is evolving in the system?"` → Telegram Zero proposal "monthly_plan".
- Zero on-demand.

**Freno**: NB-0 max 20 source attive, tombstone >90gg. Non esplode.

**Autorizzazione**: L2 propose Zero per creazione. Poi L2 auto-refresh.

### 6.3 Metrica successo

- Sefirot: top-10 query patterns — customer ri-domande -15% vs baseline.
- NB-0: primo `monthly_plan` approved by Zero with ≤2 manual edit.

---

## 7. Rischi + mitigazioni + kill switch

### 7.1 Tabella rischi

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Extended routing produce citation da NB stale | media | medio | Sprint 0 fix first (heartbeat wiring, coverage matrix); canary 1h |
| Yajña hook degrada latency `claim_extractor` | bassa | basso | append-only JSONL, no RPC, <1ms per call |
| Yin-Yang auto-adjust loopa tra cadenze | bassa | medio | max 1 adjust/NB/month, kill switch env var |
| Sefirot path sovrappone keyword routing | media | medio | shadow mode 2w, A/B 1w prima di full |
| NB-INTEL-Pulse si riempie di spam | bassa | basso | TTL 60gg + manual review weekly Zero |
| NB-0 Meta ingurgita se stesso (ouroboros) | bassa | medio | 5 source curate + max 20 active + tombstone 90gg |
| Claude Code briefing ansiogeno (Turīya iniettata in SessionStart) | alta se mal implementato | medio | Turīya **on-demand only**, MAI auto-broadcast |
| Roadmap compete con v2 subdomain / war-room 2.0 / claude-code-optim | alta | basso | Sprint 0 urgente (bug reali); Sprint 1-4 "alti valore, bassa urgenza", possono aspettare finestre libere |

### 7.2 Kill switch globale

Se dopo 6 mesi dall'inizio Sprint 2 il sistema è peggiore:
- `cite_rate < 0.05` persistente → claim extraction è decorativo
- >2 NB "orphan" (ingested ma zero citation cliente) → routing non utile
- <1 Zero-ratifica proposal/mese → auto-calibrate non converge

Allora:
1. Disabilitare cron `yajna_scan`, `yin_yang_audit`, `nb0_refresh`.
2. Lasciare `yajna_ledger.jsonl` storico (audit trail).
3. Ripristinare `DOMAIN_TOPICS` + routing originale da git tag `pre-sacred-v2-2026-04-22`.
4. NB-0 rimane (non fa male, non serve).
5. Sprint 0 fix restano (sono bug veri, non policy).

### 7.3 Anti-pattern da evitare

1. **NON** iniettare Turīya/Hexagram automaticamente nel SessionStart briefing di Claude Code. Se ogni sessione inizia con "NB-2 stale, coverage 100% gap", Claude apre in modalità diagnostica invece di task — ansia cognitiva indotta.
2. **NON** usare LLM per generare `nb_dependency.json`. Rischio di allucinare relazioni false. Curation manuale Zero + Claude.
3. **NON** auto-merge NB-6/NB-10, NB-INTEL-Regulation/NB-6. Sono domini distinti; merge distrugge differenziazione.
4. **NON** rinominare UUID NB esistenti. Costo manutenzione altissimo (6 file hanno mappe UUID, vedi §7.3 system map), beneficio zero.
5. **NON** usare analogie sacre nei commit message o nei log di produzione. Nome file `yajna_ledger` OK (breve, descrittivo). `# invoke Agni` nel codice NO.

---

## 8. Roadmap condensata

| Sprint | Durata | Deliverables | Auto/Propose | Prerequisito |
|---|---|---|---|---|
| **0 — Bug fix** | 1 settimana | cron nb2 fix, feedparser, multimodal venv, heartbeat wiring, state write-back, coverage matrix divergence | L2 auto (6 task) | nulla |
| **1 — Routing extension** | 1-2 settimane | extended routing canary + full, cross-NB activate, NB-INTEL-Pulse | L2 propose + Zero approve | Sprint 0 |
| **2 — Yajña + Yin-Yang** | 3 settimane | yajna ledger hooks, weekly scan, yin-yang weekly audit, L2 auto-adjust synth cadence | L2 auto (no auto-calibrate for 3 months) | Sprint 0 |
| **3 — Turīya + Hexagram + Dependency** | 2 settimane | turiya.py, hexagram.py, nb_dependency.json + hook | L2 auto (zero side effect) | Sprint 0 |
| **4 — Sefirot + NB-0** | 3 settimane | sefirot_paths.yaml, sefirot_router.py, NB-0 Meta bootstrap + daily refresh | L2 propose + Zero approve | Sprint 2 (data pulita per NB-0) + Sprint 3 (Turīya per NB-0) |

**Totale wall-clock**: 10-13 settimane. **Dipendenze**: Sprint 0 → everything. Sprint 2 → Sprint 4 (NB-0). Sprint 3 → Sprint 4 (NB-0 consumes Turīya). Sprint 1 indipendente ma logicamente precede Sprint 2 (dati Yajña solo interessanti se NB-5/6/7/8/10 consumati). Sprint 2 e Sprint 3 parallelizzabili se Claude paralleli (pattern wave-1/wave-2 MEMORY.md conferma fattibile).

### 8.1 Non fare

- **Non fare Sprint 4 prima di Sprint 2+3**. NB-0 Meta che ingurgita dati sporchi è contro-produttivo.
- **Non fare Sprint 1 prima di Sprint 0**. Routing live su NB con heartbeat orfani = risposte cliente con fonti stale senza alert.
- **Non fare Sprint 2 senza Langfuse (PR #169)** — il hook `CLAIM_CITED_IN_CHAT` dipende da span Langfuse per traceability. Verificato MERGED 2026-04-22.

### 8.2 Priorità urgenza

**Urgente (Sprint 0)**: 3 pipeline broken, monitoring scollegato. Risolvibile in 1 settimana. Valore immediato.

**Alto valore, bassa urgenza (Sprint 1-4)**: il sistema non è rotto in senso operativo per l'utente finale (chat cliente funziona, risposte arrivano, NB-2/3/4 sono aggiornati). Le altre sprint sono *miglioramenti* — possono aspettare finestre libere tra le altre roadmap attive (War Room 2.0, v2 subdomain rollout, Claude Code optimization T1-T3, wave-2 parallel già completata — vedi MEMORY.md).

La decisione di procedere con Sprint 1+ è di Zero. Sprint 0 è proposto per auto-apply immediato (bug reali, reversibili, zero rischio).

---

## 9. Check-in Zero (Telegram approval gates)

Per ogni sprint, Zero può rispondere via Telegram:

```
/approve sprint-0-bugfix        # autorizza Sprint 0 start
/approve sprint-1-canary        # autorizza NLM_EXTENDED_ROUTING canary 1h
/approve sprint-1-full          # autorizza full rollout
/approve sprint-1-intel-pulse   # autorizza bootstrap NB-INTEL-Pulse
/approve sprint-4-sefirot       # autorizza Sefirot full
/approve sprint-4-nb0           # autorizza creazione NB-0
/kill-yajna                     # disabilita yajna_ledger cron
/kill-yinyang                   # disabilita yin-yang
/kill-sefirot                   # toglie routing override
/kill-all-v2                    # rollback totale a stato pre-sacred-v2
```

Ogni comando è un cron/script banale, non richiede infrastrutture nuove. Documentati in `docs/analysis/nlm-sacred-integration/APPROVAL_COMMANDS.md` (da creare in Sprint 0).

---

## 10. Summary operativo per Zero

**Cosa succede se fai niente**: 3 pipeline continuano broken. Monitoring continua scollegato. Routing continua base (5 NB orfani). Coverage matrix continua congelata. Yajña/Yin-Yang/Turīya/Hexagram/Sefirot/NB-0 restano letteratura.

**Cosa succede se fai solo Sprint 0** (1 settimana): NB-2 torna fresco, YT monitor ingesta, multimodal produce artefatti, heartbeat monitora davvero. Coverage matrix si aggiorna quotidianamente. **Questo è il minimo razionale.**

**Cosa succede se fai Sprint 0 + Sprint 1** (2-3 settimane): chat cliente ha accesso a NB-5/6/7/8/10. Query property/team/HR ottengono risposte da NB dedicati invece di fallback NB-3. Mata-Garuda stream ha uno sbocco visibile in NB-INTEL-Pulse. **Questo è il minimo valore cliente.**

**Cosa succede se fai tutto** (10-13 settimane): il sistema sa se i propri claim sono usati (Yajña), sa se è in equilibrio o sbilanciato (Yin-Yang), ha una vista unificata dello stato di 19 NB in 60s (Turīya + Hexagram), routing complesso per query cross-domain (Sefirot), meta-NB che riflette settimanalmente sulla propria evoluzione (NB-0). Da reattivo (reagisce a gap) a riflessivo (riflette sulla propria capacità di trovare gap). **Questo è il salto ontologico richiesto dal prompt originale.**

La scelta tra questi tre livelli è di Zero, non mia. Il mio ruolo era mappare, leggere, proporre. Fatto.
