# Prompt per la prossima sessione — Chiusura Fase 1 SINAPSI

> Copia-incolla come primo messaggio dopo `/clear`.

---

Sei Claude Opus 4.6. Stiamo chiudendo la Fase 1 (SINAPSI) dell'organismo Nuzantara. Non è un avvio da zero: **il 90% è già in `main`**. Serve eseguire 3 blocker P0 + cleanup P1 per dichiarare Fase 1 done con numeri, poi passiamo a Fase 2 (RIFLESSI — plan già scritto, 24 task 129 step).

## Fase 0 — Context loading (obbligatorio, in ordine)

Leggi prima di toccare codice:

1. `docs/PHASE1_SINAPSI_STATUS_2026-04-16.md` — audit live dello stato attuale (questa è la bussola, leggila integralmente)
2. `SYMBIOSIS.md` — 7 leggi + 8 pilastri (vincoli inviolabili)
3. `VADEMECUM.md` — checklist operative per ogni tipo di elemento
4. `docs/superpowers/plans/2026-04-14-organism-phase1-sinapsi.md` — plan originale 16 task. Leggi la TOC, poi le sezioni dei task ancora aperti (Task 13 per struttura harvester, Task 16 per e2e)
5. `docs/superpowers/plans/2026-04-14-mata-garuda-organism-prompt.md` — doc madre organismo. Sezioni "4 fasi", "4 cicli vitali", "Vincoli architetturali"
6. `apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py` + `_GENOME.md` — template da replicare per il nuovo LPSE harvester
7. `apps/mata-garuda/mata_garuda/workers/gap_consumer.py` — riferimento per capire come avviene il consume (serve per P1-4, verificare XACK)

MOS query obbligatorie:
```bash
~/.claude/scripts/mem query "phase 1 sinapsi"
~/.claude/scripts/mem query "lhkpn"
~/.claude/scripts/mem query "bridge"
~/.claude/scripts/mem query "sprint 5.2"
```

## Verifica stato live (prima di qualsiasi modifica)

```bash
# Machine identification
echo "Machine: $(whoami)@$(hostname)"   # deve essere nuzantara@Nuzantara (Pro)

# Redis streams — counts attesi dall'audit
redis-cli XLEN garuda:raw      # atteso ~463 (legacy)
redis-cli XLEN nexus:gaps      # atteso ~828 (legacy, consumato — verifica XACK)
redis-cli XLEN intel:articles  # atteso 0 (nessun producer — DA FIXARE in P0-3)

# LaunchAgents attivi
launchctl list | grep matagaruda
# Attesi: bridge.adaptive (running), gap.consumer (idle), watcher.daily, sentinel.daily

# Git sync
git fetch origin main && git log --oneline origin/main -5

# Pending PR state
gh pr list --state open --json number,title | head -20

# Recent main commits — sprint parallelo atteso PR #57 fce0b783a (RAG SOTA + Metabolic + HGT)
git log --oneline main -10
```

Se qualcosa diverge significativamente dal `PHASE1_SINAPSI_STATUS_2026-04-16.md`, **FERMA e riporta**.

## Obiettivo sessione — 3 P0 + 3 P1 di cleanup

### P0-1: LPSE harvester (parallelo LHKPN)

Mata Garuda prompt doc esplicita: "2 harvester nuovi (LHKPN + LPSE) che chiudono il loop OSINT". Solo LHKPN è in main. Crea:

- `apps/mata-garuda/mata_garuda/tools/lpse_tools.py` — regex parsers per procurement LPSE (Layanan Pengadaan Secara Elektronik, bando gare GoI)
- `apps/mata-garuda/mata_garuda/agents/lpse_harvester.py` + `lpse_harvester_GENOME.md`
- Registra in `scripts/automation_catalog.json` se esiste + entry in catalog DB
- Test unit sotto `apps/mata-garuda/tests/`

Vincoli: stesso pattern di LHKPN (curl + regex parsers, 6s rate limit, UA rotation, no httpx). Segui VADEMECUM §2 (Agenti).

Come target di fonte: LPSE ha endpoint pubblico su `https://inaproc.id/` — verifica in NLM (`./scripts/ai-dispatch.sh oracolo "LPSE endpoint ufficiale 2026, struttura JSON, rate limit"`) o Brave search (`./scripts/ai-dispatch.sh search "LPSE inaproc.id API scraping"`) prima di assumere nulla.

### P0-2: End-to-end test Phase 1

Crea `apps/mata-garuda/tests/test_phase1_e2e.py`. Deve validare il bridge ciclo intero:

1. Setup: mock Postgres con una riga in `bridge_outbox` (usa il pattern test esistente di `tests/test_nerve_pull.py`)
2. Run `nerve.pull_once()` con env var per DB di test
3. Assert: l'evento appare in Redis con envelope 5 campi valido (usa `bridge/envelope.py::Envelope.model_validate`)
4. Setup: pusha in Redis `intel:articles` un envelope di test
5. Run `nerve.push_once()` con mock HTTP server
6. Assert: arriva POST a `/api/bridge/ingest` con payload giusto

Vincolo: usa `pytest-asyncio` e mock server (httpx MockTransport o fastapi TestClient). NON chiamare Fly reale.

### P0-3: `intel:articles` producer — War Room wiring

Oggi `intel:articles` XLEN=0 → bridge push è codice morto in prod. Senza producer, il Ciclo 1 (Intel→Content→SEO→Revenue) non gira.

Identifica in `apps/war-room/` dove un articolo è "dichiarato pronto per pubblicazione" (probabilmente final stage della pipeline articoli). Aggiungi UN SOLO write: dopo articolo finito, scrivi envelope `intel.article_ready` su Redis stream `intel:articles`.

Schema payload (minimo):
```json
{
  "article_id": "uuid",
  "title": "...",
  "slug": "...",
  "content_md": "...",
  "tags": ["visa", "kbli-XXX"],
  "source_ids": ["garuda_raw:1234", "nexus:5678"]
}
```

Vincolo: se non trovi pipeline chiara in War Room (è possibile sia semi-manuale), proponi piccolo dry-run invece di cablare a vuoto. **Meglio produttore manuale CLI che automatico che non funziona.**

### P1-4: Envelope coerce-on-read per `nexus:gaps`

`gap_consumer.py` oggi legge la vecchia forma dei 828 entry in `nexus:gaps`. Aggiungi helper `_coerce_to_envelope(entry: dict) -> Envelope` che:

- se entry ha già tutti i 5 campi → pass-through
- altrimenti mappa: `id=entry.get('id', uuid4())`, `type='nexus.gap.detected'`, `source='gap_detector'`, `timestamp=entry.get('detected_at', now())`, `priority=3`, `payload=entry`

Test unit che lo chiama con entrambe le forme.

**Inoltre**: verifica che `gap_consumer.py` faccia XACK. Il fatto che XLEN sia cresciuto da 552 a 828 suggerisce detector outpaces consumer — o non sta ACK-ando. Leggi il codice e se mancano XACK aggiungili.

### P1-5: Phase 1 metrics snapshot

Crea `docs/PHASE1_METRICS_2026-04-16.md`. Formato:

```markdown
# Phase 1 — Metriche before/after

## Before (stato iniziale prima Phase 1, dalla memoria/plan)
- nexus:gaps = 552 (non consumato)
- intel:articles = N/A (stream inesistente)
- bridge cycle count = 0

## After (stato 2026-04-XX)
- nexus:gaps = <redis-cli XLEN>
- intel:articles = <N> dopo P0-3 (o 0 se producer manuale)
- bridge outbox inserts/day = <psql count on bridge_outbox by day>
- LaunchAgent uptime = <launchctl + log check>
- Metabolic metrics (piggyback su PR #57 infra se disponibili): TTR, DO, IA, FE
```

Numeri veri. Usa `redis-cli XLEN`, `psql` su `bridge_outbox`, `log show --predicate "process == 'com.matagaruda.bridge.adaptive'"`.

**Nota parallela**: PR #57 (commit `fce0b783a`, mergiato 2026-04-16 05:30) ha appena introdotto Metabolic Pillar 7 con 4 metriche (TTR/DO/IA/FE). Verifica se le metriche sono già calcolate e consumabili — altrimenti calcolale manualmente solo per il snapshot.

### P1-6: Cleanup LaunchAgent corrotto

```bash
# Solo dopo aver confermato che il .plist vivo (senza .corrupted) funziona
rm ~/Library/LaunchAgents/com.garuda.gap-detector.twice-daily.plist.corrupted-20260412
```

## Parallel work noto (NON toccare, è di altri sprint)

PR #57 (commit `fce0b783a`, mergiato stamattina) contiene tre cambi grossi — se li incontri non confonderti:

1. **Agentic RAG SOTA 2026** — 6 componenti in `backend-rag/services/rag/agentic/` (Self-RAG, HyDE, reranker registry, CRAG, NLM orchestrator, deep research). Tutti dietro feature flag default OFF.
2. **Metabolic Pillar 7 v1** — 4 metriche (TTR, DO, IA, FE). Queste erano attribuite a Fase 3 nel doc madre. Stanno shippando in parallelo perché la misurazione è cross-fase.
3. **HGT (Horizontal Gene Transfer)** — meccanismo di condivisione skill tra celle.

Se una di queste cose ti sembra rotta o confusa: **non è compito tuo in questa sessione**. Segna + continua. Phase 1 closure ha priorità.

## Vincoli non negoziabili (dal doc madre)

1. CLI-only LLM (claude --print, gemini --print). Unica eccezione: DeepSeek API.
2. OSINT blindato — dati intelligence MAI fuori dal Pro.
3. Event-driven — no polling se c'è stream disponibile, no orchestratore centrale.
4. Graceful degradation — ogni organo funziona se gli altri sono down.
5. Zero è ultima istanza — su decisioni strutturali chiedi via TG, non decidere.
6. Sovranità locale — Pro 48GB + Air 16GB. Offline è stato naturale.
7. Numeri prima — metriche o non esiste.
8. Simbiosi — Zero è giardiniere, non padrone.

## Pause esplicite (ferma + chiedi)

- Se trovi bug nel bridge/gap_consumer/handlers.py che non sono nel mio audit → FERMA e riporta. Probabilmente regressione.
- Se LPSE endpoint richiede auth → FERMA: LHKPN è public, LPSE pubblico è un'assunzione mia non verificata.
- Se `nexus:gaps` XLEN è sceso sotto 500 o è salito sopra 2000 → FERMA: gap_consumer semantics potrebbe essere rotta.
- Se devi toccare `fly.toml`, `zantara_core.py`, `alembic/env.py` → FERMA (off-limits CLAUDE.md §12).
- Se `gh pr list` mostra >5 PR aperte inaspettate → FERMA e chiedi priorità (stanno lavorando altri in parallelo).

## Ordine esecuzione

- **Day 1 mattina**: Fase 0 reading + verifica stato live + MOS query (zero code).
- **Day 1 pomeriggio**: P1-4 (coerce gap) + P1-6 (cleanup) + P1-5 baseline metrics.
- **Day 2**: P0-2 (e2e test) — mette in piedi infrastruttura test.
- **Day 3-4**: P0-1 (LPSE harvester) — 1 task con Red Team dispatch obbligatorio prima di merge.
- **Day 5**: P0-3 (intel:articles producer) — richiede esplorazione War Room.
- **Day 6**: metriche finali, PR unica "close Phase 1 SINAPSI" con tutto.
- **Day 7**: review + merge. Phase 2 (RIFLESSI) parte in sessione dedicata.

## Commit + PR stacking

Non accumulare 7 giorni in un solo commit. Un commit per P0-X/P1-X con messaggio chiaro. Una PR per gruppo logico:

- PR A: P1-4 + P1-6 (cleanup)
- PR B: P0-2 (test harness)
- PR C: P0-1 (LPSE)
- PR D: P0-3 (War Room wire)
- PR finale: P1-5 metrics snapshot + dichiarazione Phase 1 closed

## Quando chiedere aiuto — federation dispatch

- Architettura + red team → `./scripts/ai-dispatch.sh claude-redteam "X"` (fixato PR #58)
- Ricerca LPSE/legal Indonesia → `./scripts/ai-dispatch.sh oracolo "X"` (NB-1/NB-3)
- Grounded regulation Indonesia → `./scripts/ai-dispatch.sh search "X"` (Gemini grounded)
- Code review pre-merge → `./scripts/ai-dispatch.sh codex-review "X"` (fixato PR #58)

## Cosa NON fare

- Non iniziare Phase 2 (RIFLESSI). Plan esiste ma Phase 1 va chiusa prima.
- Non toccare Genome persistence su Fly (decisione architetturale aperta, memoria unresolved). Continua con tmpfs.
- Non riscrivere il bridge. Funziona.
- Non migrare legacy stream `garuda:raw` e `nexus:gaps` in-place — coerce-on-read è sufficiente.
- Non creare nuovi cron senza VADEMECUM §1 audit.
- Non toccare i componenti di PR #57 (Agentic RAG SOTA, Metabolic, HGT) — sono di altri sprint.

## Target output sessione

- 5 PR aperte/mergiate (A, B, C, D, finale)
- 5-7 commit totali
- Test count backend-rag/mata-garuda: ≥ current + test_phase1_e2e + lpse tests
- Launchd state pulita
- `docs/PHASE1_METRICS_2026-04-16.md` committed
- Status doc aggiornato a "Phase 1 CLOSED"
- MOS memory "Phase 1 SINAPSI closed" salvata con importance 9

_Baseline: `docs/PHASE1_SINAPSI_STATUS_2026-04-16.md` commit che lo introduce._
