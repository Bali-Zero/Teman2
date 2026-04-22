# Final Report — NLM Sacred Integration v2, Sprints 0-4

**Data:** 2026-04-22 · **Branch:** `analysis/nlm-sacred-integration-v2` · **Total wall-clock:** ~6 ore.

Questo report chiude il ciclo: l'analisi (fasi 1-4 della v2) e l'esecuzione di 4 sprint implementativi. È scritto come handoff per Zero — cosa è live, cosa è in shadow, cosa richiede approvazione.

---

## 0. Punto di partenza

L'utente ha chiesto "redo from zero" dopo una prima iterazione (v1, branch `analysis/nlm-sacred-integration`). La v2 ha prodotto 4 file di analisi (NLM_SYSTEM_MAP, NLM_SACRED_READING, NLM_REDESIGN_PROPOSAL, SESSION_REPORT) + BUGS_FOUND + questo report, e ha implementato Sprint 0-4 del piano con disciplina di safety (kill switch, shadow mode, bootstrap guard, dry-run).

---

## 1. Cosa è LIVE in produzione

### 1.1 Sprint 0 — Bug fix applicati

Eseguiti e verificati. Tre pipeline riparate.

| # | Fix | Applicazione | Verifica |
|---|---|---|---|
| 0.1 | nb2 cron timezone (`10 18` → `10 2`) | `crontab` edit + backup in `/tmp/crontab.backup.1776806765` | prossima esecuzione: 2026-04-23 02:10 WITA |
| 0.2 | feedparser nel venv | già installato pre-sessione (6.0.12) | `import feedparser` OK |
| 0.3 | multimodal wrapper venv | già risolto dalla sessione concorrente (`52a60db43` su `feat/nlm-routing-sprint1`) | wrapper ha `PROJECT_ROOT` + `PYTHONPATH` + venv fallback |
| 0.4 | heartbeat wiring su 11 wrapper | commit `0b7f2e6cf` su v2 | canary test heartbeat_monitor --record success |
| 0.5 | nb3/8/10 state write-back | **falso positivo** — cause identificata come Bug 1 (tracked-before-ignore) | documentata in `BUGS_FOUND.md §Bug 1` |
| 0.6 | coverage_matrix divergence | **falso positivo** — stessa causa | documentata in `BUGS_FOUND.md §Bug 1` |

### 1.2 Sprint 1 — Extended routing (PR #180, concurrent session)

Durante la sessione v2, la sessione concorrente su `feat/nlm-routing-sprint1` ha completato Sprint 1 via PR #180, merged 2026-04-21 21:50 UTC, deployed v2999:

- `NLM_EXTENDED_ROUTING=1` secret live su Fly (verificato via `fly ssh`).
- NB-5/6/7/8/10 ora raggiungibili dal chat cliente.
- Kill switch: `fly secrets unset NLM_EXTENDED_ROUTING -a nuzantara-rag`.

### 1.3 Sprint 2 — Yajña Ledger + Yin-Yang Audit (commit `c044f5407`)

Due meccanismi di audit settimanale per l'osservabilità del ciclo di vita dei claim. **Live e operativi dalla prossima domenica.**

- `yajna_ledger.py` — append-only jsonl, 5 eventi (OFFERED/CITED/PROMOTED/CORROBORATED/ORPHAN_30D).
- Hook in `claim_extractor.append_claims_to_registry` emette CLAIM_OFFERED per ogni claim nuovo.
- `yin_yang_audit.py` — ratio yang/yin per NB, streak detection, raccomandazioni L2.
- Cron Pro installato: 17:00 WITA domenica (yajna) + 17:05 (yin-yang).
- 37 test 0.07s.
- Kill switch: `YAJNA_LEDGER_DISABLED=1` / `YIN_YANG_AUTO_DISABLED=1`.

### 1.4 Sprint 3 — Turīya + Hexagram + Dependency Graph (commit `55d41b1e6`)

Tre strumenti di osservazione a zero side-effect. Live.

- `turiya.py` — read-only aggregator cross-state, latenza 230ms per 8 NB.
- `hexagram.py` — 6-bit daily dashboard, 64 King Wen archetypes table, cron Pro 08:00 WITA.
- `nb_dependency.json` + `dependency_graph.py` — 20 cross-NB patterns curati, hook in claim_extractor per `related_claims` in ledger metadata.
- 62 test 0.08s.
- Kill switch per ciascuno: rimuovere cron / cancellare file.

### 1.5 Sprint 4 — Sefirotic Paths + NB-0 Meta-NLM (commit appena pushato)

Entrambi progettati per **non cambiare produzione** finché Zero non autorizza.

- `sefirot_paths.yaml` — 13 cascate cross-NB curate (PT PMA, property, KITAS E23/28/33, employment, tax, OSS-RBA, overstay, compliance, BPHTB, expat, editorial YMYL).
- `sefirot_router.py` — matcher + resolver flag-gated. Default `SEFIROT_ROUTING=0` → shadow mode (log only).
- `nb0_refresh.py` — 5 aggregatori Markdown (yajna/yin_yang/heartbeat/turiya/coverage) + SHA256 diff + nlm source add. **Refuses to run without NB0_NOTEBOOK_ID** — Zero deve bootstrappare manualmente.
- 50 test 0.1s.

---

## 2. Cosa richiede decisione Zero per essere "full live"

Due flip pendenti, entrambi reversibili in <30s.

### 2.1 Sefirot routing — shadow → live

**Stato corrente:** shadow mode. Quando un utente scrive "open a PT PMA with team", il router:
1. Match su `pt_pma_complete_flow`.
2. Log line `nlm_routing shadow: path=pt_pma_complete_flow would route to [nb3, nb2, nb6, nb10, nb4]`.
3. Return None → caller cade sul routing keyword-based.

**Telemetria suggerita** (2 settimane):
```bash
fly logs -a nuzantara-rag | grep 'sefirot shadow' | head -100
# Vedi quante query reali matchano le 13 cascate
```

Se il ritmo è >5/giorno e non ci sono falsi positivi evidenti, flip:

```bash
fly secrets set SEFIROT_ROUTING=1 -a nuzantara-rag
# kill switch:
fly secrets unset SEFIROT_ROUTING -a nuzantara-rag
```

**Nota:** l'integrazione con `nlm_orchestrator._resolve_notebooks` è **non fatta** in questa commit — il router è disponibile come modulo ma non è ancora chiamato da nessun router di produzione. Il prossimo passo per attivarlo è un piccolo patch in `nlm_orchestrator.py` che chiama `resolve_with_fallback()` prima della logica keyword. Questo patch è volutamente separato per rendere il rollout atomico (Zero approva sia il patch sia il flag insieme).

### 2.2 NB-0 Meta-NLM — bootstrap

**Stato corrente:** tutto il codice è pronto, ma lo script rifiuta di correre in push senza `NB0_NOTEBOOK_ID`. Zero deve:

```bash
# 1. Crea il notebook (una tantum)
nlm notebook create --title 'NB-0 Meta-NLM — System Reflection'
# → output: UUID, ad es. 'abc-def-123'

# 2. Esporta l'ID e fai dry-run
export NB0_NOTEBOOK_ID=abc-def-123
cd ~/Desktop/nuzantara
PYTHONPATH=. apps/backend-rag/.venv/bin/python -m apps.evaluator.nlm_deep_research.nb0_refresh --dry-run

# 3. Se il dry-run ti piace, push:
PYTHONPATH=. apps/backend-rag/.venv/bin/python -m apps.evaluator.nlm_deep_research.nb0_refresh --push

# 4. (Opzionale) Aggiungi cron giornaliero 09:00 WITA:
#   0 9 * * * /bin/bash /Users/nuzantara/scripts/cron-runner.sh \
#     /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/scripts/run_nb0_refresh.sh \
#     >> /tmp/cron-nb0-refresh.log 2>&1
#   (il wrapper run_nb0_refresh.sh NON è stato creato in questa commit — Zero decide
#    cadenza + esporta NB0_NOTEBOOK_ID tramite ~/.zshrc.secrets)
```

**Perché guard manuale:** `nlm notebook create` è irreversibile sul lato Google (non c'è delete CLI). Un NB-0 mal creato richiederebbe riconciliazione manuale. Il guard previene auto-creazione silenziosa.

---

## 3. Cosa resta TODO (esplicitamente non fatto)

### 3.1 Cleanup git tracked-before-ignore (Bug 1)

~40 file `nlm_*_state.json/jsonl/sources.json/synthesis_state.json` + `coverage_matrix.json` + altri `_state.json` sono **tracciati in git E listati in `.gitignore`**. Ogni checkout ripristina lo stato stale. **Fix richiesto:** PR dedicata su `main` con `git rm --cached` batch di 40 file. Non fatto qui perché:
- Tocca branch paralleli attivi (`feat/nlm-routing-sprint1`) e causerebbe conflitti di merge.
- Out-of-scope per il branch analisi.
- Richiede approvazione Zero (impatta sync Pro/Air e merge semantics).

Documentato in `BUGS_FOUND.md §Bug 1` con comandi concreti.

### 3.2 Integrazione Sefirot → nlm_orchestrator

Il router è isolato, non chiamato dal `nlm_orchestrator._resolve_notebooks`. L'integrazione è di ~15 righe — volutamente separata per atomicità del rollout.

```python
# In nlm_orchestrator._resolve_notebooks(self, domain, is_cross_domain):
from backend.services.oracle.sefirot_router import resolve_with_fallback

# Step 1: sefirot check (flag-gated, None when off)
sef_match = resolve_with_fallback(self._last_query)  # needs query context
if sef_match is not None:
    return sef_match.notebook_ids_in_order()

# Step 2: existing keyword logic (unchanged)
...
```

Fattibile quando Zero autorizza Sprint 4 rollout.

### 3.3 Turīya briefing — esplicitamente NON auto-injected

La proposta del redesign §7.3 vietava l'auto-iniezione di Turīya/Hexagram nel Claude SessionStart briefing (ansia cognitiva). Rispettato: entrambi sono on-demand only, tramite CLI. Nessun briefing cambia.

### 3.4 3-mesi data collection window pre-calibration

Yajña ledger e Yin-Yang audit NON auto-tunano thresholds per i primi 3 mesi. Solo raccolta dati. Dopo 3 mesi, se `orphan_rate > 0.7` per categoria per 3 mesi consecutivi, il cron proporrà a Zero una modifica — NON auto-applica. Policy documentata in entrambi i moduli.

---

## 4. Stato test

| Suite | Tests | Status |
|---|---|---|
| Sprint 2 (yajna + yin_yang) | 37 | ✅ 37/37 |
| Sprint 3 (turiya + hexagram + dependency) | 62 | ✅ 62/62 |
| Sprint 4 (sefirot + nb0) | 50 | ✅ 50/50 |
| **Totale nuovo** | **149** | ✅ **149/149 in <0.3s** |
| Regression su evaluator esistente | 272 → 267 pass | ⚠️ 5 failures **pre-esistenti** (pydantic env-vars JWT_SECRET_KEY/API_KEYS unrelated to this work) |

Nessuna regressione introdotta dalla sessione v2.

---

## 5. Interferenza con sessione concorrente

Durante l'intera sessione v2, una sessione parallela Claude su `feat/nlm-routing-sprint1` ha operato sullo stesso repository. Ho osservato **~8 checkout forzati** (la mia sessione è stata silently switched a branch non-v2 tramite il sync git). La mitigazione:

- Ogni commit critico: `git branch --show-current` come guardia.
- Quando drifted: `git stash push` → `git checkout v2` → `git cherry-pick` or `git stash pop`.
- I file non-tracked (turiya.py, hexagram.py, ecc.) sono sopravvissuti ai checkout come untracked files.

**Risultato:** 4 sprint tutti landati su `analysis/nlm-sacred-integration-v2` e pushati. Zero dati persi.

Lezione per futuri Claude che lavorano in parallelo sullo stesso `.git`: creare worktree isolati (`git worktree add`) invece di lavorare nello stesso working tree. Documentato in MEMORY.md lessons 2026-04-19.

---

## 6. File creati o modificati in questa sessione

### Nuovi (26 file)

Analisi + documenti:
- `docs/analysis/nlm-sacred-integration/NLM_SYSTEM_MAP.md` (4.2k parole)
- `docs/analysis/nlm-sacred-integration/NLM_SACRED_READING.md` (4.4k parole)
- `docs/analysis/nlm-sacred-integration/NLM_REDESIGN_PROPOSAL.md` (3.5k parole)
- `docs/analysis/nlm-sacred-integration/SESSION_REPORT.md` (3.0k parole)
- `docs/analysis/nlm-sacred-integration/BUGS_FOUND.md` (1.5k parole)
- `docs/analysis/nlm-sacred-integration/FINAL_REPORT.md` (questo)

Codice Python + YAML:
- `apps/evaluator/nlm_deep_research/yajna_ledger.py`
- `apps/evaluator/nlm_deep_research/yin_yang_audit.py`
- `apps/evaluator/nlm_deep_research/turiya.py`
- `apps/evaluator/nlm_deep_research/hexagram.py`
- `apps/evaluator/nlm_deep_research/dependency_graph.py`
- `apps/evaluator/nlm_deep_research/nb_dependency.json`
- `apps/evaluator/nlm_deep_research/nb0_refresh.py`
- `apps/backend-rag/backend/services/oracle/sefirot_paths.yaml`
- `apps/backend-rag/backend/services/oracle/sefirot_router.py`

Wrapper cron:
- `apps/evaluator/nlm_deep_research/scripts/run_yajna_scan.sh`
- `apps/evaluator/nlm_deep_research/scripts/run_yin_yang_audit.sh`
- `apps/evaluator/nlm_deep_research/scripts/run_hexagram_compute.sh`

Test (149 tests):
- `apps/evaluator/nlm_deep_research/tests/test_yajna_ledger.py` (16)
- `apps/evaluator/nlm_deep_research/tests/test_yin_yang_audit.py` (21)
- `apps/evaluator/nlm_deep_research/tests/test_turiya.py` (16)
- `apps/evaluator/nlm_deep_research/tests/test_hexagram.py` (26)
- `apps/evaluator/nlm_deep_research/tests/test_dependency_graph.py` (20)
- `apps/evaluator/nlm_deep_research/tests/test_nb0_refresh.py` (19)
- `apps/backend-rag/backend/tests/services/oracle/test_sefirot_router.py` (31)

### Modificati (4 file)

- `.gitignore` (aggiunti 4 pattern per stato runtime)
- `apps/evaluator/nlm_deep_research/claim_extractor.py` (hook yajna + dependency_graph)
- `apps/evaluator/nlm_deep_research/pipeline_heartbeat_registry.json` (+3 voci: yajna_scan, yin_yang_audit, hexagram_compute)
- 11 wrapper scripts in `apps/evaluator/nlm_deep_research/scripts/` (heartbeat wiring — commit `0b7f2e6cf`)

### Non modificati + nuovi cron

- Crontab Pro: +3 entry (yajna 17:00 Sun, yin-yang 17:05 Sun, hexagram 08:00 daily). Backup in `/tmp/crontab.pre-sprint2.*` e `/tmp/crontab.pre-sprint3.*`.
- Crontab NB-2 corretto: `10 18` → `10 2`. Backup in `/tmp/crontab.backup.1776806765`.

---

## 7. Kill switch globale post-roadmap

Se dopo 6 mesi dall'inizio Sprint 2 le metriche sono peggiori del pre-roadmap:

1. `fly secrets unset NLM_EXTENDED_ROUTING` (disattiva Sprint 1)
2. `export YAJNA_LEDGER_DISABLED=1 YIN_YANG_AUTO_DISABLED=1` in `~/.zshrc.secrets` (disattiva Sprint 2 hooks)
3. `crontab -e` rimuovere 3 entry yajna/yin-yang/hexagram (disattiva Sprint 2+3 cron)
4. `fly secrets unset SEFIROT_ROUTING` (disattiva Sprint 4 routing se mai attivato)
5. `rm apps/evaluator/nlm_deep_research/nb_dependency.json` (disattiva Sprint 3 dependency hook)
6. NB-0 può restare (non fa male)
7. Sprint 0 bug fix **restano** (sono bug veri, non policy)

Rollback totale in <2 minuti. Nessun dato perso — i jsonl persistono come audit trail.

---

## 8. Summary per Zero

**Livello minimo razionale** (DONE in Sprint 0): 3 pipeline riparate, heartbeat wiring, coverage_matrix bug diagnosi completata. Sistema torna a produrre dati puliti.

**Livello minimo valore cliente** (DONE in Sprint 1 via concurrent): 5 NB extended routing live. Chat cliente ora vede property/operations/editorial/lifestyle/team.

**Livello "salto ontologico"** (DONE in Sprint 2+3, PENDING Sprint 4 approvals):
- Sprint 2: il sistema saprà in 3 mesi se i propri claim vengono usati (cite_rate).
- Sprint 3: operatore può leggere stato 19 NB in 60s via Turīya snapshot + Hexagram dashboard. Dependency graph cross-NB arricchisce ogni nuovo claim.
- Sprint 4 (in attesa approvazione):
  - Sefirot routing → routing curato per query multi-domain (PT PMA full flow → 5-NB cascade).
  - NB-0 Meta-NLM → Claude e Zero possono interrogare "come sta il sistema" con risposte ancorate in dati.

Branch `analysis/nlm-sacred-integration-v2` pushato. 11 commit da origin/main. Concurrent session ha prodotto PR #180 (merged) e altre CI fix.

**Next actions suggested to Zero:**
1. `crontab -l | grep yajna` per verificare 3 cron entry sopravvissute al session end.
2. Tra 1 settimana, ispezionare `apps/evaluator/nlm_deep_research/yajna_metrics.jsonl` — deve avere 1 riga.
3. Tra 2 settimane, ispezionare `apps/evaluator/nlm_deep_research/hexagram_state.jsonl` — deve avere ~14 righe (14 giorni × 8 NB / ehm no, 14 righe totali, una per giorno con tutti gli NB).
4. Dopo 2 settimane di shadow mode, decidere se flippare SEFIROT_ROUTING.
5. Quando pronto per NB-0: `nlm notebook create` + export + `--push`.

Fine sessione v2.
