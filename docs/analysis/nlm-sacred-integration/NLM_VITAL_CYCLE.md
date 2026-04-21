# NLM Vital Cycle — NB come organi viventi, non database

**Data:** 2026-04-22 · **Branch:** `analysis/nlm-sacred-integration` · **Autonomia:** L2 (propose → human-approve per irreversibile, auto-apply per reversibile) · **Vincolo:** zero API paid, solo OAuth MAX + Ollama local · **Scope:** sfruttare tutto il sistema esistente (evaluator + backend-rag + Mata-Garuda + Naga + scraper + CRM).

Questo documento sostituisce la roadmap 5-sprint scartata. È un unico piano eseguibile che parte da una **verifica diretta** dello stato (non dalla mappa della sessione precedente, che aveva buchi).

---

## 1. Cosa ho scoperto rileggendo il codice da zero

### 1.1 Esistono due ecosistemi NB separati che nessun documento menzionava

| Ecosistema                 | Path                                           | NB                                                                     | UUID immigration (esempio)             |
| -------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------- |
| **Evaluator / Bali Zero**  | `apps/evaluator/nlm_deep_research/`            | NB-2..8, NB-10, NB-11..13                                              | `cff93ab0-813a-42f2-a8de-36987e724271` |
| **Mata-Garuda / NB-INTEL** | `apps/mata-garuda/mata_garuda/config.py:22-40` | NB-INTEL-Immigration, Tax, Regulation, Press, AIResearch, SelfEvolving | `1ed02e54-542f-426a-94f8-53c5ffde4b7d` |

Sono **due NB immigration diversi**, due NB tax diversi. Non si parlano. Mata-Garuda ha il suo `NLM_DOMAIN_ROUTING` (config.py:33) che instrada enriched items dallo stream Redis `garuda:enriched` verso NB-INTEL-_. Il backend RAG (`nlm_orchestrator.py:22-32`) ha un terzo routing (`DOMAIN_NOTEBOOK_MAP_V2`) che copre solo 4 NB (NB-2, NB-3, NB-4) e non tocca né NB-5/6/7/8/10 né NB-INTEL-_.

**Conseguenza**: NB-5 property, NB-6 operations, NB-7 editorial, NB-8 lifestyle, NB-10 team — tutti **ingerito-ma-non-consumato** dal backend RAG di produzione. Il lavoro notturno delle loro pipeline non arriva mai a un cliente Bali Zero che chiede sul chat.

### 1.2 La sessione precedente aveva ipotizzato male su persona_validate

Log `persona_validate_20260419.log` riga per riga:

```
01:00:02 [PersonaEngine] Error listing sources for cff93ab0-...: [Errno 2] No such file or directory: 'nlm'
01:00:02 [PersonaEngine] [nb2_immigration] Persona MISSING — restoring...
01:00:02 [PersonaEngine] Error adding source to cff93ab0-...: [Errno 2] No such file or directory: 'nlm'
01:00:02 [PersonaEngine] [nb2_immigration] Failed to inject persona
... ripetuto per tutti i 7 NB ...
Validation: 0 OK, 0 restored, 7 missing/failed
```

Il bug NON è "Telegram token stale" come ipotizzato nella roadmap scartata. Il bug è:

- `persona_engine.py` chiama `subprocess.run(["nlm", ...])`
- Il wrapper `run_persona_validate.sh` fa `source "$HOME/.zshrc.secrets"` ma NON `source "$HOME/.zshrc"` — quindi la `PATH` del cron non contiene la directory dove vive il binario `nlm` (installato via pipx nel venv `nlm-bridge`).
- Dal 2026-04-12 (prima run dopo qualche cambiamento di PATH) i 7 NB hanno la persona "MISSING" e il ripristino fallisce silenziosamente.

Inoltre il wrapper fa `exit "$EXIT_CODE"` ma `persona_engine --validate` ritorna 0 anche quando 7/7 falliscono. Quindi `heartbeat --record persona_validate` viene registrato come success... ma il file `heartbeat_persona_validate.json` dice `last_success: 2026-04-03T21:48` — 19 giorni fa. Il cron gira, il log si scrive, lo script exit=0, eppure il heartbeat non si aggiorna. **Terzo bug sovrapposto**: probabile che `persona_engine` abbia cambiato path import dopo un refactor e `heartbeat_monitor --record` fallisca silenziosamente per questo.

**Morale**: la session map precedente non aveva letto il log esatto. Le 3 ipotesi "Telegram/preflight/persona" erano tutte sbagliate. Il bug vero è `PATH` nel cron environment.

### 1.3 Il coverage 100% GAP è uno snapshot congelato, non uno stato

`coverage_matrix.json` dice `coverage_updated: 2026-04-12T11:00`. Da allora nessuno scrive. Ma `gap_scanner` gira daily alle 21:30 WITA — il log mostra `Total gaps found: 35` del 2026-04-21. Lo heartbeat `heartbeat_gap_scanner.json` è OK `2026-04-21 21:35`.

Divergenza strutturale: `gap_scanner.py --layer-a` produce gap e probabilmente li scrive su `coverage_matrix.json [domain.gaps]`. Ma `gap_scanner_state.json` dice `layer_a_runs: 4` totali (non 10+ che dovrebbero essere). **Il gap_scanner ha un refactor a metà**: parte del dato va nel heartbeat e nel log, parte non va più nei file di stato vecchi. Il risultato è che nessun consumer downstream (Turīya view, sacred reading proposto) può leggere lo stato reale.

Il contenuto dei gap in matrix è anche **sporco di parsing**: invece delle domande estratte, contiene frammenti JSON raw tipo `"answer": ..."`, `"conversation_id": ..."`, `"sources_used": []`. Il gap_scanner sta catturando la response raw invece delle domande.

### 1.4 I claim funzionano benissimo (la sessione scorsa non li ha aperti)

`apps/evaluator/nlm_nb*_claims.jsonl` — NON nella dir `nlm_deep_research/` ma in `apps/evaluator/` una directory sopra. File presenti:

- nb2: 42 claim attivi, ultimo 2026-04-22 01:19
- nb3: 33, nb4: 12, nb5: 10, nb6: 10, nb7: 10, nb8: 10, nb10: 10
- schema: `claim_id`, `claim_text`, `category` (FEE_CHANGE, ELIGIBILITY_RULE, …), `confidence_class` (VERIFIED/MONITORING/…), `confidence_score`, `source_ids[]`, `extracted`, `status`, `geographic_scope`, `affected_visa_types[]`

I claim sono ricchi e strutturati. Sono il **sangue** del sistema. E oggi nessuno li consuma a valle — muoiono nel jsonl.

### 1.5 Consumer reali oggi (verificati grep)

Chi legge gli NB, `grep -rl "notebook_query\|NLM_NOTEBOOKS" apps/`:

| Consumer                                | File                                                                    | Modalità                                                                              | NB letti                                         |
| --------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Backend RAG `nlm_orchestrator`          | `apps/backend-rag/backend/services/oracle/nlm_orchestrator.py`          | single-NB + cross-NB fan-out per chat                                                 | NB-2, NB-3, NB-4 (no NB-5/6/7/8/10, no NB-INTEL) |
| `cross_notebook_correlator` (evaluator) | `apps/evaluator/nlm_deep_research/cross_notebook_correlator.py`         | fan-out multi-NB per query interne                                                    | NB-2..8, NB-10                                   |
| `cross_notebook_correlator` (backend)   | `apps/backend-rag/backend/services/oracle/cross_notebook_correlator.py` | mirror backend del sopra                                                              | idem                                             |
| `nlm_enrichment_service`                | oracle/                                                                 | enrichment post-RAG                                                                   | 4 NB come sopra                                  |
| `nlm_verifier`                          | `services/rag/nlm_verifier.py`                                          | verification claim RAG                                                                | scarso                                           |
| `ops_intelligence`                      | evaluator/                                                              | weekly briefing                                                                       | NB-11/12                                         |
| `naga/search_agents/domain_agent`       | `apps/backend-rag/backend/services/naga/search_agents/domain_agent.py`  | NLM come fonte di ricerca tra Brave/Exa                                               | immigration/tax/legal                            |
| **Mata-Garuda `nlm_feeder`**            | `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`                    | **nutrimento**: legge stream Redis `garuda:enriched`, `nlm source add` su NB-INTEL-\* | 6 NB-INTEL                                       |
| **Mata-Garuda `nlm_expander_agent`**    | `apps/mata-garuda/mata_garuda/agents/nlm_expander_agent.py`             | **L2 autonomy**: propone nuovi NB se un dominio produce >50 enriched/30d              | scan                                             |
| `bali-intel-scraper nlm_research_step`  | `apps/bali-intel-scraper/scripts/nlm_research_step.py`                  | ricerca per scraper editorial                                                         | NB-7 ish                                         |

**Punto chiave**: Mata-Garuda ha **già implementato L2 autonomy** per espansione NB. `nlm_expander_agent.py:22-24`:

> "CRITICAL: L2 autonomy — this agent PROPOSES, does NOT create. A human (Zero) decides via Telegram reply."

Questo è il pattern che devi generalizzare. Non inventare da zero. Copiare/estendere.

---

## 2. Visione: NB come organi viventi

### 2.1 Il principio

Un NB non è un database read-only consultabile. È un **organo**. Ha quattro caratteristiche vitali:

1. **Metabolismo**: ingerisce nutrienti (fonti, claim, enriched items) e produce metaboliti (synth, brief, coverage, citation in risposte RAG).
2. **Omeostasi**: mantiene la propria salute entro parametri (SVS per source, NHS per NB, coverage_pct, freshness). Se esce dai parametri, auto-corregge o chiede aiuto.
3. **Scambio**: riceve nutrimento da pipeline + agents + humans, e nutre a sua volta backend RAG + Naga + Claude sessions + briefing + scraper.
4. **Evoluzione**: il suo scope (topics, cluster, persona) cambia nel tempo in funzione di segnali di uso reale — non è hardcoded per sempre.

Oggi il sistema ha (1) e (2) parzialmente. Manca (3) asimmetrico (NB-5..10 non consumati dal backend, NB-INTEL non consumati dal chat) e manca (4) strutturato (topics hardcoded in `DOMAIN_TOPICS`).

### 2.2 Il ciclo nutrimento ↔ arricchimento ↔ consumo

```
                    [MONDO ESTERNO]
                 (leggi, news, social)
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  nb*_pipeline     peraturan_ingest   garuda enrich (stream)
  (cluster Q daily)  (PDF ufficiali)   (scraper + RSS + X)
        │                 │                 │
        └────────┬────────┴────────┬────────┘
                 ▼                 ▼
        ┌───────────────────────────────────┐
        │           [NB ORGANO]             │
        │  sources + synth + persona + NHS  │
        │  ──────────────────────────────   │
        │  claim_extractor → claims.jsonl   │  ← SANGUE
        │  synthesis_roller → compressione  │  ← SONNO
        │  invariants → 70 source cap       │  ← IMMUNITÀ
        │  persona_engine → identità        │  ← CARATTERE
        └─────────────┬─────────────────────┘
                      │
   ┌──────────────────┼──────────────────┬──────────────────┐
   ▼                  ▼                  ▼                  ▼
backend RAG        Naga agent         ops briefing     Claude session
(chat cliente)    (research loop)    (weekly exec)    (troubleshoot)
   │                  │                  │                  │
   └──────┬───────────┴──────┬───────────┴──────┬───────────┘
          ▼                  ▼                  ▼
    risposta cliente    report naga       telegram digest
    con citation        con citation      con insight
          │                  │                  │
          └────── FEEDBACK LOOP (chi consuma cosa) ───────┐
                                                          ▼
                            yajna_ledger.jsonl (append-only, L2)
                                          │
                                          ▼
                          [meta-loop mensile: chi è vivo, chi è zombie]
```

### 2.3 Strati ontologici (tassonomia)

Non cambio gli UUID. Aggiungo un layer di metadati nel registry:

| Strato                                           | Ruolo                                     | NB attuali (evaluator)                        | NB attuali (mata-garuda)                           |
| ------------------------------------------------ | ----------------------------------------- | --------------------------------------------- | -------------------------------------------------- |
| **world** — conoscenza esterna regolatoria       | ingerire legge/prassi                     | NB-2, 3, 4, 5, 6, 7, 8, 10                    | NB-INTEL-Immigration, -Tax, -Regulation, -Press    |
| **pulse** — intelligence short-life (news flash) | cattura eventi recenti prima che stagnino | (nulla — gap reale)                           | NB-INTEL-Press, NB-INTEL-AIResearch (parzialmente) |
| **body** — business mirror                       | riflettere stato DB Bali Zero             | NB-11 (ops), NB-12 (intel), NB-13 (telemetry) | —                                                  |
| **self** — auto-riflessione                      | Claude interroga se stesso                | NB-1 (codebase), NB-14 (session memory)       | NB-INTEL-SelfEvolving                              |
| **meta** — osservazione del sistema NB stesso    | Chi sta vivendo, chi muore                | (da creare: NB-0)                             | —                                                  |

Il gap più rumoroso: manca lo **strato pulse**. Le news social (X, government press releases) oggi entrano in NB-2 e NB-5 tramite `t4_monitor` (quando funziona), ma si stagnano nei source cap 70. Un NB press dedicato vivrebbe con TTL 30gg, tombstone aggressivo, solo "flash recent".

---

## 3. I bug strutturali da sanare prima di qualunque cosa

Sprint 0 = prerequisito assoluto, 1 settimana wall-clock, L2 autorizzato (tutti fix reversibili).

### 3.1 Fix PATH nei wrapper cron

File: `apps/evaluator/nlm_deep_research/scripts/run_persona_validate.sh`, ed eventualmente gli altri wrapper (da verificare uno a uno con `grep -L 'nlm source\|nlm query' scripts/*.sh`).

Fix:

```bash
# dopo: source "$HOME/.zshrc.secrets"
# aggiungere:
if [ -f "$HOME/.zshrc" ]; then
    set +u
    source "$HOME/.zshrc" 2>/dev/null || true
    set -u
fi
# oppure, se .zshrc è troppo pesante:
export PATH="$HOME/.local/bin:$HOME/.local/pipx/venvs/notebooklm-tools/bin:$PATH"
```

Verifica: `which nlm` dentro l'env del cron — usare un canary script che scrive il `PATH` in log prima del run.

**Livello L2**: auto-apply. È un fix reversibile (basta revert del file).

### 3.2 Fix exit code persona_validate

`persona_engine.py`: se `missing/failed > 0`, exit `2` invece di `0`. Cambia `apps/evaluator/nlm_deep_research/persona_engine.py` — se `status_report["missing"]` + `["failed"]` ≥ 1 → `sys.exit(2)`.

Side effect positivo: heartbeat non viene registrato come success, telegram alert scatta (vedi wrapper riga 60-67).

**Livello L2**: auto-apply.

### 3.3 Fix gap_scanner state write-back

`gap_scanner.py --layer-a` scrive su `heartbeat_gap_scanner.json` e sul log ma smette di aggiornare `gap_scanner_state.json` (layer_a_runs stuck a 4) e `coverage_matrix.json [domain.gaps]` (ultima data 2026-04-12). Verificare se è un bug o refactor — probabile che il file legacy non venga più scritto e il sistema nuovo scriva altrove.

**Azione**: aprire il file, leggere dove scrive oggi, riabilitare la scrittura su `coverage_matrix.json` come audit ledger anche se il percorso primario è cambiato.

**Livello L2**: auto-apply con diff review (non rischia dati già scritti, aggiunge solo write).

### 3.4 Fix coverage_matrix.gaps parsing

Il contenuto dei `gaps[]` è frammento JSON raw, non domande. Il parser estrae male — probabilmente regex sbagliata che cattura linee dell'output NLM invece delle domande dentro un blocco `## Questions` o simile.

**Azione**: leggere `_extract_gaps` in `gap_scanner.py`, far tornare una lista di domande pulite. Aggiungere test golden con un NLM response simulato.

**Livello L2**: auto-apply (fix interno al parser).

### 3.5 Fix multimodal_pipeline venv+module

`run_multimodal.sh` usa `python3.14` system invece del venv. Allineare al pattern di `run_nbX_pipeline.sh` (activate venv, `PYTHONPATH=.`, poi `python -m apps.evaluator.nlm_deep_research.multimodal_pipeline`).

**Livello L2**: auto-apply.

### 3.6 Fix feedparser in venv cron

`pip install feedparser` in `apps/backend-rag/.venv` (o nel venv che usano i wrapper). Riabilita `yt_monitor` e `t4_monitor`.

**Livello L2**: auto-apply.

### 3.7 Fix ClaimRecord source_ids error

Nel log `nlm-deep-research.log` c'è `ClaimRecord.__init__() missing 1 required positional argument: 'source_ids'`. Questo fa degradare un cluster a `DEGRADED_L2`. Probabile chiamata senza passare `source_ids=[]` default.

**Azione**: trovare il call site, passare `source_ids=source_ids or []`. Test ClaimRecord con empty list.

**Livello L2**: auto-apply.

### 3.8 Fix backend routing per NB-5/6/7/8/10

`nlm_orchestrator.py:22-32` ha solo 4 NB mappati. Aggiungere:

- `"property"` → NB-5 `d9438180-5e63-4e2a-a473-6061101f6a8d`
- `"operations"` → NB-6 `85207af3-352f-4554-8d2a-18f42cc541ba`
- `"editorial"` → NB-7 `f51ab8a0-50d0-49f1-a64f-ebc131fed7b8`
- `"lifestyle"` → NB-8 `4fd8cd0f-93f1-4e43-9c9e-86c0d581852c`
- `"team"` → NB-10 `f0307c2c-9220-4160-93c8-f4a6ef4a3b65`

**Livello**: questo è semi-irreversibile (cambia routing live in produzione, può far cambiare risposte cliente). **Richiede approvazione Zero** + rollout graduale con feature flag.

### 3.9 Connect NB-INTEL ↔ NB-evaluator

Oggi Mata-Garuda nutre NB-INTEL-Immigration (`1ed02e54-...`), e le pipeline evaluator nutrono NB-2 (`cff93ab0-...`). Sono due silos separati.

**Proposta**: un mediator `nlm_bridge_intel_to_evaluator.py` che:

1. Legge claim recenti (<7 giorni) da NB-INTEL-Immigration via `notebook_query` cercando claim VERIFIED.
2. Ripubblica come source note `[INTEL] …` in NB-2.
3. Append a `yajna_ledger.jsonl` per tracciare il flusso.

**Livello L2**: **propose** a Zero. Mata-Garuda ha già uno stream Redis — forse la soluzione migliore è farvi pubblicare anche i claim evaluator, così converge senza un bridge nuovo. **Decisione da prendere con Zero.**

---

## 4. Design del ciclo vitale L2 (dopo Sprint 0)

Quattro loop, non nove. Ognuno ha un **produttore**, un **consumatore**, un **freno**, un **kill switch**, una **metrica di successo**.

### Loop 1 — Yajña Ledger (il sangue che ritorna)

**Problema risolto**: oggi produciamo ~100 claim/giorno, nessuno sa se servono a qualcosa.

**Implementazione**:

- File `apps/evaluator/nlm_deep_research/yajna_ledger.jsonl` append-only.
- Hook in `claim_extractor.append_claims_to_registry` scrive riga `{ts, nb, claim_id, category, confidence, consumed_by:null, consumed_at:null, verified_by_later_rite:null}`.
- Hook in `nlm_orchestrator.query` **e** `nlm_enrichment_service` **e** `naga/domain_agent`: quando una risposta RAG cita una `source_id`, grep nel ledger il claim con quel source_id, aggiorna `consumed_by` + `consumed_at`.
- Cron settimanale `ledger_scan.py`:
  - Aggiorna `verified_by_later_rite` per claim confermati da synth successivo.
  - Emette metrica: `claims_produced_7d`, `claims_consumed_7d`, `consume_rate`, `orphan_rate_30d`.
  - Se `orphan_rate_30d > 0.7` per una categoria per 3 mesi consecutivi → **propone a Zero** di ridurre threshold confidence di quella categoria.

**Freno L2**: la calibrazione auto confidence NON è applicata. È solo una proposta Telegram. Zero approva con `/approve yajna-calibration-<id>`.

**Kill switch**: env var `YAJNA_LEDGER_DISABLED=1` → hook è no-op.

**Metrica successo**: dopo 3 mesi, `consume_rate > 0.2`. Se < 0.05 dopo 6 mesi, il sistema di claim extraction è decorativo — riprogettare.

### Loop 2 — Yin-Yang Balance (ingestione vs consumo)

**Problema risolto**: oggi ingestiamo 8 pipeline × cluster rotation, non sappiamo se il volume è sostenibile.

**Implementazione**:

- `yin_yang_audit.py` cron weekly domenica 17:00 WITA.
- Input per NB: claims_added_7d, sources_added_7d, nlm_queries_served_7d (da ledger).
- Output: ratio. Alert se outside `[0.3, 5]`.
- Output file: `apps/evaluator/nlm_deep_research/balance_state.jsonl` append.
- **L2 auto-apply**: se un NB ha `ratio > 5` per 2 settimane consecutive, il `synthesis_roller` per quel NB passa da weekly a daily (accelera digestione). Reversibile: se ratio rientra, torna a weekly.
- **L2 propose**: se `ratio < 0.3` (NB affamato), propone a Zero attivazione cluster extra per quel NB.

**Freno**: max 1 auto-adjust per NB per mese. Se più modifiche si accumulano, alert a Zero.

**Kill switch**: `YIN_YANG_AUTO_DISABLED=1`.

**Metrica successo**: dopo 3 mesi, ogni NB ha `1 ≤ ratio ≤ 3` (banda sana).

### Loop 3 — Curiosity Loop L2 (sostituisce gap_scanner attuale)

**Problema risolto**: oggi `gap_scanner` layer-A produce 35 gap/giorno, remediation ne fa 3/settimana, gli altri 34·7-3=235 gap muoiono non letti.

**Implementazione**:

- Riusare il **SYMBIOSIS Pilastro 6 Curiosity Loop** già esistente (MEMORY.md lo menziona LIVE dal 2026-04-16, 40 tests).
- Invece di far decidere al gap_scanner, passare il topic a Curiosity Loop che orchestra:
  1. Topic gap → research scheduled.
  2. Validation (via cross-LLM deliberation Consiglio v1 — già LIVE).
  3. Propose come `nlm source add` se validated.
- **L2 autoapply**: source add reversibile (ogni NB ha invariants e tombstone). Auto-apply per gap di confidence > 0.7.
- **L2 propose**: per confidence 0.5-0.7, propone a Zero via Telegram con link al research report.

**Freno**: max 10 topic/giorno processed (non 35 come ora). Priorità via SVS: topic con già 0 source prima di topic con 2-3 source stale.

**Kill switch**: disabilitare cron curiosity loop (è già opzionale).

**Metrica**: gap_pct per NB scende sotto 50% in 3 mesi (oggi è 100% per tutti — ma come §1.3 detto è un bug, va prima risolto 3.3+3.4).

### Loop 4 — NB Expander (estensione del Mata-Garuda esistente)

**Problema risolto**: oggi se emerge un dominio nuovo (es. "crypto regulation Indonesia") il sistema non lo nota — solo Mata-Garuda su stream `garuda:enriched`.

**Implementazione**:

- Estendere `nlm_expander_agent.py` (già L2!) per coprire ANCHE il mondo evaluator (non solo stream).
- Input aggiuntivo: claim categories distribution. Se per 2 mesi una categoria (es. `CRYPTO_POLICY`) produce >20 claim/mese in NB esistenti ma senza NB dedicato → propone NB-INTEL-Crypto.
- Mantiene L2 "PROPOSES, does NOT create" — Zero decide.

**Freno**: soglie già strutturate (>50 items in 30gg → proposal, da aumentare a >100 visto il volume evaluator).

**Kill switch**: già esiste.

**Metrica**: NB creati su proposta accettata in 1 anno. Target: 2-4 (non di più, over-expansion = diluizione).

---

## 5. Il NB che davvero manca: NB-0 Meta-NLM

Dopo i 4 loop sopra, l'unico NB nuovo proposto è **NB-0 Meta-NLM**.

**Fonti** (giornaliere cron 09:00 WITA):

1. `yajna_ledger` weekly summary (Loop 1).
2. `balance_state.jsonl` Yin-Yang (Loop 2).
3. `heartbeat digest` già esistente.
4. `coverage_matrix.json` quando il bug 3.3 è risolto.
5. claim aggregate per NB (count per category, trend).

**Consumer** (chi interroga NB-0):

- Claude al SessionStart: `notebook_query NB-0 "stato ultima settimana"` → risposta sintetica.
- Cron mensile 1° lunedì: `notebook_query NB-0 "cosa sta cambiando nel sistema"` → **proposta** monthly plan a Zero.
- Zero on-demand quando vuole audit.

**Livello L2**: il NB-0 è **create once manualmente** (Zero crea via `nlm notebook create`), poi i 5 source sono ingeriti auto-apply (reversibile).

**Freno**: NB-0 ha max 20 source attive, tombstone >90gg. Non esplode.

---

## 6. Priorità eseguibili

### Sprint 0 — fix immediati (status dopo esecuzione 2026-04-22)

| #   | Task                              | Status            | Note                                                                                                                                                                                                                       |
| --- | --------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 3.1 | Fix PATH wrapper persona_validate | ❌ non necessario | diagnosi sbagliata: `cron-runner.sh` esporta già PATH corretto. Repro manuale del wrapper ha girato 7/7 OK, heartbeat aggiornato 2026-04-22 03:52. Era regressione temporanea 12/19 aprile già auto-risolta.               |
| 3.2 | Fix exit code persona_validate    | ❌ non necessario | il codice già fa `sys.exit(1)` se `missing > 0` (riga 396-397). Exit code corretto.                                                                                                                                        |
| 3.3 | Fix gap_scanner state write       | 🟡 da indagare    | file mtime 2026-04-22 ma content data 2026-04-12. `_save_gap_state` appare chiamata dal codice; divergenza mtime/content indica overwrite da altro processo o race. Rimandato a Sprint 2 (yajna ledger vedrà il problema). |
| 3.4 | Fix coverage gaps parsing         | 🟡 da indagare    | `coverage_matrix.gaps[]` contiene frammenti JSON raw invece di domande. Bug di `_extract_gap_topics`. Richiede test golden con response NLM simulata. Rimandato con 3.3.                                                   |
| 3.5 | Fix multimodal venv+PROJECT_ROOT  | ✅ fatto          | `run_multimodal.sh`: `../../../../..` (5 livelli → `/Users/nuzantara/Desktop`) → `../../../..` (4 livelli → `nuzantara`). Aggiunto `PYTHONPATH=.` alla riga 51. Repro dry-run OK.                                          |
| 3.6 | pip install feedparser            | ✅ fatto          | `feedparser-6.0.12` + `sgmllib3k` in `apps/backend-rag/.venv`. Non cambio git, solo venv state.                                                                                                                            |
| 3.7 | Fix ClaimRecord source_ids        | ✅ fatto          | `pipeline.py:_consolidate`: `ClaimRecord.to_dict()` omette `source_ids=[]` (falsy), quindi serialize-deserialize perde il field → TypeError. Fix: re-inject default `{"source_ids": []}` prima dello splat.                |

**Risultato Sprint 0**: 3 fix applicati (3.5, 3.6, 3.7). 2 "fix" erano false positive (3.1, 3.2) — sistema già sano, la sessione precedente aveva sbagliato diagnosi. 2 bug reali rimandati (3.3, 3.4) perché richiedono indagine più profonda e non sono bloccanti per il chat cliente (i claim nuovi vanno ancora su jsonl correttamente, il gap_scanner gira e produce gap anche se lo state file lagga).

### Sprint 1 — consumer asimmetrico (1-2 settimane) — **richiede decisione Zero**

| #   | Task                                      | Auth                                            |
| --- | ----------------------------------------- | ----------------------------------------------- |
| 3.8 | Estendere backend routing a NB-5/6/7/8/10 | L2 propose → Zero approva per rollout live      |
| 3.9 | Bridge NB-INTEL ↔ NB-evaluator            | L2 propose: bridge o converge via stream Redis? |

### Sprint 2 — yajna ledger + yin-yang (3 settimane)

Loop 1 + Loop 2. Solo dopo Sprint 0 per avere dati puliti.

### Sprint 3 — curiosity loop + NB-0 (3 settimane)

Loop 3 + NB-0. Solo dopo Sprint 2 per avere ledger da aggregare.

### Sprint 4 — NB expander estensione (2 settimane)

Loop 4. Estensione dell'esistente `nlm_expander_agent.py`. Indipendente.

---

## 7. Cosa NON fare

- **Non creare NB-0 ora** senza prima sistemare i bug Sprint 0. NB-0 cattura meta-dati: se i meta-dati sono bacati (coverage congelata, heartbeat fantasma), NB-0 nutre garbage.
- **Non implementare Meta-Cycle Ollama mensile** come nella roadmap scartata. È over-engineering — Curiosity Loop + NB Expander già coprono il caso "sistema evolve da solo" con freni stringenti.
- **Non unire NB-6 e NB-10** come proponeva la roadmap scartata. Sono nutriti da pipeline diverse (NB-6 da peraturan_ingestion PDF ufficiali, NB-10 da cluster HR/team). Differenziazione naturale — mantenerla.
- **Non usare analogie sacre nel codice**. `yajna_ledger.jsonl` è OK come nome perché è breve e descrittivo. Ma nessuna riga di codice deve contenere `# invoke Agni` o `# offer havis`. Commento iniziale sul perché basta.
- **Non rinumerare gli UUID**. Costo manutenzione altissimo, zero beneficio funzionale.
- **Non espandere i cluster rotation** hardcoded senza una proposta Curiosity Loop validata.

---

## 8. Kill switch globale

Se in 6 mesi il sistema post-roadmap è peggiore del pre-roadmap (metrica: `consume_rate < 0.05`, `NB orphan > 2`, Zero ratifica < 1 proposta/mese):

1. Disabilitare cron yajna_scan, yin_yang_audit, curiosity_loop_nb.
2. Lasciare i file jsonl storici (audit trail).
3. Ripristinare `DOMAIN_TOPICS` hardcoded da tag git `pre-vital-cycle-2026-04-22`.
4. NB-0 resta (non fa male ma non serve).
5. I fix Sprint 0 restano (sono bug veri, non policy).

---

## 9. Sintesi esecutiva

- 7 bug strutturali reali. La roadmap scartata ne aveva identificati 3 con ipotesi sbagliate. Sprint 0 (1 settimana, L2 auto) li risolve tutti.
- 2 ecosistemi NB separati (evaluator + Mata-Garuda NB-INTEL) non si parlano. Sprint 1 decide se farli parlare o no, con Zero.
- 4 loop vitali (yajna, yin-yang, curiosity, expander) — 3 nuovi + 1 estensione di `nlm_expander_agent` già LIVE.
- 1 NB nuovo (NB-0 Meta-NLM) solo dopo che i dati sono puliti.
- Nessuna analogia sacra nel codice di produzione. Il ciclo vitale è **nella topologia** (chi nutre chi), non nei nomi.
- Ogni cambio ha kill switch. Ogni proposta L2 reversibile è auto-apply, ogni irreversibile è propose a Zero.

Il sistema NLM ha già l'impalcatura di un organismo. Il lavoro non è spiritualizzare — è **riparare le afferenze nervose interrotte** (consumer asimmetrici, heartbeat fantasma, parser bacati) e aggiungere **un solo loop di feedback reale** (yajna = "il mio sangue ritorna a me?"). Il resto fluisce da quello.

---

**Prossimo passo concreto**: approvi Sprint 0 (i 7 fix auto-apply)? Li eseguo ora, committo separatamente, e ti mando il diff. Dopo Sprint 0 decidiamo insieme Sprint 1 (routing backend + bridge intel).
