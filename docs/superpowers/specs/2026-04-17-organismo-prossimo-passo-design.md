# Organismo — Prossimo passo (T0-Pro baseline + parità metabolica)

**Status:** v2 — post federation review (Codex GPT-5.4 xhigh + Gemini 2.5 Pro + DeepSeek R1)
**Date:** 2026-04-17
**Author:** Zero + Claude Opus 4.7 (1M context)
**Sprint:** Post-lean-libri-sacri (Sprint 5.1.5 chiuso)
**Stimated effort:** 1-2 ore (scope minimo) + 7 giorni di accumulo automatico

**v2 changelog:** integrate 4 findings (F1 idempotence, F3 T0-bootstrap, F4 test_cmd semantico, F5 2-col schema `collector_host`+`metric_scope`); 3 minori (F6 SPOF nota, F7 staggering motivo, F8 venv fallback); rigettati F10 (DeepSeek: cross-machine lock non esiste, DB locali), F11 (Gemini: status column duplica metadata JSON), F9 (Codex: comparator out-of-scope intenzionale §6).

---

## 0. TL;DR

Pro non misura il proprio metabolismo. Air sì. Asimmetria viola Legge #7 (Numeri prima): futuri cambi all'organismo (HGT, Phase 2 consolidation, Curiosity Loop) richiedono before/after Pro che oggi non abbiamo.

Fissiamo **T0-Pro(bootstrap)** oggi con il primo rollup manuale + installiamo cron locale. 2 task auto-verificanti in `~/.agent/decisions/claude_tasks/` bloccano dimenticanza: verifica T+1 e consolidamento T0-Pro(7d-median) T+7.

Schema DB evolve a 2 colonne semantiche (**`collector_host`** + **`metric_scope`**, insight da Codex review F5): 1 row = 1 fatto coerente. Air scrive 2 row/giorno (`scope='global'` per TTR/DO + `scope='host'` per IA/FE); Pro scrive 1 row/giorno (`scope='host'` per IA/FE). I 3 snapshot Air esistenti vengono espansi in 6 row via script one-shot.

**Scope minimo:** no nuove metriche, no nuovi organi, no nuovi libri. Solo parità infrastrutturale Pro↔Air + schema v2 + 2 reminder scritti.

---

## 1. Problema

### 1.1 Asimmetria misurata oggi (2026-04-17)

| Asset                                       | Pro                   | Air                                                    |
| ------------------------------------------- | --------------------- | ------------------------------------------------------ |
| `scripts/metabolic_rollup.py`               | ✅ presente           | ✅ presente                                            |
| `packages/cell-core/cell_core/metabolic/`   | ✅ 4 moduli           | ✅ 4 moduli                                            |
| LaunchAgent `com.cell.metabolic-rollup`     | ❌ **mancante**       | ✅ attivo (23:30 WITA)                                 |
| LaunchAgent `com.cell.genome-decay`         | ❌ (out of scope qui) | ✅ attivo (02:30 WITA)                                 |
| DB `~/.agent/decisions/organism_metrics.db` | ❌ non esiste         | ✅ 3 snapshot (2026-04-15..16)                         |
| `METABOLIC_PG_DSN` in secrets               | ❌ assente            | (config via fly-pg-tunnel Air)                         |
| `MOS SQLite` (fonte IA)                     | ✅ popolato           | ✅ popolato                                            |
| `shared/escalations_pro.jsonl` (fonte FE)   | ✅ 5636 righe         | (questo file è di Pro, Air ha `escalations_air.jsonl`) |

### 1.2 Il T0 scritto in SYMBIOSIS è solo-Air

SYMBIOSIS §"Dove siamo" riporta:

> Misura — Implementato v1 (2026-04-16). T0 baseline: TTR=869, DO=2.21, IA=1.0, FE=0.01

Questi 4 numeri vengono da Air (snapshot `2026-04-15T19:38:27.619903+00:00`). Pro non ha mai scritto uno snapshot. Conseguenze:

- Non è un T0 dell'organismo — è un T0 di Air.
- Tutto ciò che in futuro viene fatto su Pro (HGT publisher/consumer in MG, nuove cellule, Phase 2 consolidation su cell-core Pro) non ha numeri Pro di confronto.
- Legge #7 parzialmente violata: "Se non ha un benchmark before/after, non è un'evoluzione".

### 1.3 Dicotomia metriche sistema vs macchina

I 4 metric definiti in `packages/cell-core/cell_core/metabolic/definitions.py` leggono fonti di **natura diversa**:

| Metrica | Fonte                                 | Scope semantico        | Nota                                    |
| ------- | ------------------------------------- | ---------------------- | --------------------------------------- |
| **TTR** | PG `cell_pulse_log` (Fly prod)        | **global** — organismo | Shared PG, misurato da chi ha il tunnel |
| **DO**  | PG `kg_nodes`/`kg_edges` (Fly prod)   | **global** — organismo | Shared PG                               |
| **IA**  | cron JSONL + MOS SQLite locali        | **host** — corpo       | Pro ≠ Air (fonti diverse)               |
| **FE**  | `escalations_{pro\|air}.jsonl` locale | **host** — corpo       | Pro ≠ Air                               |

Oggi Air mescola tutte e 4 in 1 row `metabolic_snapshots`. Con due corpi, la mescolanza è perdita di informazione diagnostica. Schema v2 risolve.

---

## 2. Scelte di design

### 2.1 Scelta: Due serie separate + comparatore read-only (deferred)

Respinta l'aggregazione Pro+Air: aggregare TTR-Pro con TTR-Air distruggerebbe segnale diagnostico. Direzione: **due serie separate via `collector_host`**, con comparatore pull-based futuro (CLI read-only, non cron) se servirà.

Lo sprint implementa solo le serie separate. Il comparatore è out-of-scope §6.

### 2.2 Scelta: "C" — metriche `global` vs `host` (insight F5 Codex review)

**TTR + DO sono `metric_scope='global'`** (leggono Fly PG, valore univoco per l'organismo). Misurate da Air (Fly PG tunnel già attivo). Pro **non** replica il tunnel — sarebbe ridondanza, il PG è uno solo.

**IA + FE sono `metric_scope='host'`** (leggono fonti locali, valore per-corpo). Misurate separatamente da ciascuna macchina.

**Schema v2:** colonne nuove `collector_host` (chi ha raccolto: pro/air) + `metric_scope` (global/host). 1 row = 1 fatto semantico coerente.

Row structure possibili:

- `scope='global', collector='air'` → solo TTR+DO popolati (IA+FE NULL)
- `scope='host', collector='air'` → solo IA+FE popolati (TTR+DO NULL)
- `scope='host', collector='pro'` → solo IA+FE popolati (TTR+DO NULL)

Air rollup scrive **2 row/giorno** (1 global + 1 host). Pro rollup scrive **1 row/giorno** (host). Query sempre filtrate per `metric_scope` + `collector_host`.

**Perché 2 colonne e non 1**: `collector_host` risponde "chi ha raccolto?" (operational), `metric_scope` risponde "a quale livello appartiene?" (semantico). Separarle lascia espandibile il modello (es. futuro: Pro collector per global se Air down), senza confondere.

### 2.3 Scelta: scope MINIMO (no nuove metriche)

No `genome_size`, no `cell_pulse_count`, no `intel_scraper_health`. Motivi:

- Legge #7 "Numeri prima" non significa "molti numeri subito". Significa: ogni modifica futura ha numeri. Fissare il baseline delle 4 metriche esistenti è già lavoro completo.
- Definire nuova metrica senza sapere cosa rappresenta richiede federation review. Out of scope.
- Indurire rollup su 2 macchine vale più di rollup "ricco" che crasha random.

### 2.4 Scelta: T0-Pro(bootstrap) oggi, consolidato a T+7 (F3 correction)

**Revisione post-review (Codex + DeepSeek):** un singolo snapshot non è un "baseline" scientificamente difendibile — è un **bootstrap point**. Tre modelli convergono: chiamarlo "T0" senza qualifier espone a claim comparativi prematuri.

Ciclo di vita del T0-Pro, esplicitato:

| Momento          | Label               | Dati               | Uso consentito                                           |
| ---------------- | ------------------- | ------------------ | -------------------------------------------------------- |
| 2026-04-17       | `T0-Pro(bootstrap)` | 1 snapshot manuale | Verificare cron funziona. **NON usare per before/after** |
| 2026-04-24 (T+7) | `T0-Pro(7d-median)` | mediana 7 snapshot | Baseline ufficiale. **Usare per before/after**           |

La transizione da bootstrap a 7d-median è automatizzata dal `claude_task` T+7 con precondizioni semantiche (vedi §3.7). Se al giorno 7 i dati sono incompleti/null, il task rimane pending (non cristallizza dati cattivi).

**Perché fissiamo bootstrap oggi e non aspettiamo 7 giorni per T0-Pro:**

- Verifica immediata che cron + schema + pipeline funzionano end-to-end
- Documenta in SYMBIOSIS la transizione in-flight (evita dimenticanza)
- Bootstrap label è _esplicita_: nessuno lo userà per comparazioni (regola scritta)

### 2.5 Scelta: automazione = task auto-verificanti con precondizioni semantiche (F4)

Né Telegram-alert (si dimentica), né milestone auto-rilevate (richiederebbero regole non verificate). Lavoro concreto in `~/.agent/decisions/claude_tasks/` con formato esistente.

**Correzione post-review (Codex + DeepSeek):** `COUNT(*) >= 7` era insufficiente — può contare row null, duplicate, stantie. Il `test_cmd` T+7 ora include:

- `COUNT(DISTINCT DATE(calculated_at)) >= 7` — 7 giorni distinti (no duplicate)
- `SUM(ia_value IS NOT NULL) >= 7` — IA non-null ≥ 7 volte
- `SUM(fe_value IS NOT NULL) >= 7` — FE non-null ≥ 7 volte
- `WHERE collector_host='pro' AND metric_scope='host'`

Se una precondizione fallisce, task rimane pending → Claude futuro lo diagnostica.

CLAUDE.md §15 è il contract esistente. Sfruttiamo l'infrastruttura, senza crearne di nuova.

---

## 3. Implementazione

### 3.1 Deliverable

1. **`scripts/install_metabolic_rollup_pro.sh`** — installer idempotente
2. **`scripts/launchd/com.cell.metabolic-rollup.pro.plist`** — template plist Pro
3. **`scripts/metabolic_rollup_pro.sh`** — wrapper Pro (venv fallback chain)
4. **`scripts/metabolic_rollup.py`** (modifica) — argparse `--collector-host`, `--metric-scope`, scrive **2 row se scope='both'**
5. **`packages/cell-core/cell_core/metabolic/storage.py`** (modifica) — migration idempotente 2 colonne via `PRAGMA table_info` + lock serializzato
6. **`packages/cell-core/cell_core/metabolic/definitions.py`** (modifica minimale) — convenzione `metadata.error='not_applicable_by_design'` per TTR/DO quando `pg_dsn=None`
7. **`SYMBIOSIS.md §"Dove siamo"`** (modifica) — riga Pilastro 7 con T0-Air + T0-Pro(bootstrap) + regola "bootstrap non per claim"
8. **`~/.agent/decisions/claude_tasks/t0_pro_verify_firstrun_<ts>.json`** — task T+1
9. **`~/.agent/decisions/claude_tasks/t0_pro_consolidate_7days_<ts>.json`** — task T+7 con test_cmd semantico
10. **Test smoke:** `pytest packages/cell-core/tests/metabolic/ -q` + dry-run `metabolic_rollup_pro.sh`
11. **One-shot Air backfill:** espande 3 snapshot esistenti in 6 row (split global + host)

### 3.2 Schema DB — migration idempotente 2 colonne (F1 + F5)

**Design v2:** 2 colonne nuove, migration protetta da `PRAGMA table_info` + lock.

```python
# In MetabolicStore._ensure_schema() — chiamato una sola volta all'apertura

def _ensure_schema(self) -> None:
    conn = self._get_conn()
    with self._write_lock:  # serialize cross-process via SQLite busy timeout + threading.Lock
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Create if missing (idempotent)
            conn.executescript(_SCHEMA)

            # Migration v2: add 2 columns if missing (idempotent)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(metabolic_snapshots)")}
            if "collector_host" not in cols:
                conn.execute("ALTER TABLE metabolic_snapshots ADD COLUMN collector_host TEXT")
            if "metric_scope" not in cols:
                conn.execute("ALTER TABLE metabolic_snapshots ADD COLUMN metric_scope TEXT")

            # Index for filtered queries
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metabolic_collector_scope "
                "ON metabolic_snapshots(collector_host, metric_scope, calculated_at DESC)"
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
```

**Why `BEGIN IMMEDIATE`:** un cron lento + un run manuale potrebbero entrambi aprire il DB. `BEGIN IMMEDIATE` blocca subito il writer lock (non attende il primo write) — il secondo processo attende il `busy_timeout` (5s esistente) e riprova. Nessun rischio di "two writers see column missing".

**Retrocompatibilità:** i 3 snapshot Air esistenti hanno `collector_host=NULL, metric_scope=NULL`. Il backfill script (§4.1) li aggiorna.

**Convenzione NULL (F2):** `metadata.error='not_applicable_by_design'` per TTR/DO quando `pg_dsn=None`; `metadata.error=<real_error>` per fallimenti reali. Già supportato dal dataclass `MetricValue` — solo una convenzione esplicita, 0 nuove colonne.

### 3.3 `MetabolicStore.store()` — firma estesa

```python
def store(
    self,
    snapshot: MetabolicSnapshot,
    collector_host: str,                    # REQUIRED post-v2
    metric_scope: str,                      # 'global' | 'host'
) -> int:
    # ...existing code...
    cursor = conn.execute(
        """INSERT INTO metabolic_snapshots (
            calculated_at,
            ttr_value, ttr_metadata,
            do_value, do_metadata,
            ia_value, ia_metadata,
            fe_value, fe_metadata,
            collector_host, metric_scope
        ) VALUES (?, ?,?, ?,?, ?,?, ?,?, ?,?)""",
        (...existing..., collector_host, metric_scope),
    )
```

Breaking change: `store()` richiede 2 argomenti nuovi. Il vecchio chiamante (`metabolic_rollup.py`) è l'unico call site prod — aggiornato contemporaneamente.

### 3.4 `metabolic_rollup.py` — scrive 1 o 2 row

Nuova logica: argparse `--mode {air,pro,manual}` decide quante row scrivere.

- `--mode=air` (default quando `METABOLIC_PG_DSN` set): scrive 2 row → `scope='global'` (TTR+DO popolati) + `scope='host'` (IA+FE popolati)
- `--mode=pro`: scrive 1 row → `scope='host'` (IA+FE popolati; TTR+DO NULL con `metadata.error='not_applicable_by_design'`)
- `--mode=manual` (dry-run): legge e stampa, non scrive

```python
if args.mode == "air":
    store.store(snap_global, collector_host="air", metric_scope="global")
    store.store(snap_host,   collector_host="air", metric_scope="host")
elif args.mode == "pro":
    store.store(snap_host,   collector_host="pro", metric_scope="host")
```

Lo `snap_global` e `snap_host` sono costruiti dal collector: stessa fonte collect, ma il writer proietta solo i campi rilevanti al scope (altri = `MetricValue(value=None, metadata={'error':'not_applicable_by_design'})`).

### 3.5 Installer idempotente (F1)

```bash
#!/bin/bash
# scripts/install_metabolic_rollup_pro.sh
# Idempotent: safe to run multiple times.

set -euo pipefail

[ "$(whoami)" = "nuzantara" ] || { echo "This script must run on Pro"; exit 1; }

REPO="/Users/nuzantara/Desktop/nuzantara"
PLIST_SRC="$REPO/scripts/launchd/com.cell.metabolic-rollup.pro.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.cell.metabolic-rollup.plist"
LABEL="com.cell.metabolic-rollup"

mkdir -p "$(dirname "$PLIST_DST")"
cp "$PLIST_SRC" "$PLIST_DST"

# Unload-if-loaded + load (scoped al label → non tocca altri agenti)
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl enable "gui/$(id -u)/$LABEL"

launchctl print "gui/$(id -u)/$LABEL" >/dev/null && echo "OK: $LABEL loaded"
```

### 3.6 Plist Pro

Differenze da Air:

- `WorkingDirectory` = `/Users/nuzantara/Desktop/nuzantara`
- `StartCalendarInterval` = **23:45 WITA** (15 min dopo Air — non race condition: DB sono **separati per host** — F7 correction: staggering solo per finestre di log separate durante debug)
- `ProgramArguments[1]` = `$REPO/scripts/metabolic_rollup_pro.sh`
- `StandardOutPath` / `StandardErrorPath` = `/tmp/metabolic-rollup-pro.{stdout,stderr}.log`

### 3.7 Wrapper `metabolic_rollup_pro.sh` — venv fallback chain (F8)

```bash
#!/bin/bash
set -euo pipefail

REPO="/Users/nuzantara/Desktop/nuzantara"
CELLCORE="$REPO/packages/cell-core"
LOG_DIR="$HOME/logs/cron"
mkdir -p "$LOG_DIR"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a; source "$HOME/.nuzantara-secrets.env"; set +a
fi

# Venv fallback chain (F8)
for candidate in \
    "$REPO/apps/backend-rag/.venv/bin/python" \
    "/opt/homebrew/bin/python3.11" \
    "/opt/homebrew/bin/python3" \
    "/usr/bin/python3"
do
    if [ -x "$candidate" ]; then
        PY="$candidate"
        break
    fi
done
[ -z "${PY:-}" ] && { echo "ERR: no python found" >&2; exit 2; }

cd "$REPO"
export PYTHONPATH="$CELLCORE:${PYTHONPATH:-}"
export METABOLIC_DB_PATH="${METABOLIC_DB_PATH:-$HOME/.agent/decisions/organism_metrics.db}"

# No METABOLIC_PG_DSN on Pro → mode=pro → 1 row scope=host
exec "$PY" scripts/metabolic_rollup.py \
    --db-path "$METABOLIC_DB_PATH" \
    --mode pro \
    --notify \
    >> "$LOG_DIR/metabolic-rollup-pro.log" 2>&1
```

### 3.8 Task auto-verificanti con precondizioni semantiche (F4)

**File 1: `t0_pro_verify_firstrun_2026-04-18.json`**

```json
{
  "job": "t0_pro_verify_firstrun",
  "created_at": "2026-04-17T<now>Z",
  "due_after": "2026-04-18T23:45:00Z",
  "priority": "HIGH",
  "subject": "Verify metabolic rollup Pro ran successfully at least once (non-null IA+FE)",
  "pending_condition": "Pro host row with IA+FE non-null exists for 2026-04-18",
  "test_cmd": "sqlite3 ~/.agent/decisions/organism_metrics.db \"SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='pro' AND metric_scope='host' AND DATE(calculated_at)='2026-04-18' AND ia_value IS NOT NULL AND fe_value IS NOT NULL\" | awk '$1>=1 {exit 0} {exit 1}'",
  "action_on_pass": "Delete this task file.",
  "action_on_fail": "Inspect /tmp/metabolic-rollup-pro.stderr.log, launchctl print gui/$(id -u)/com.cell.metabolic-rollup, and re-run scripts/metabolic_rollup_pro.sh manually.",
  "files_implicated": [
    "scripts/metabolic_rollup_pro.sh",
    "~/Library/LaunchAgents/com.cell.metabolic-rollup.plist"
  ]
}
```

**File 2: `t0_pro_consolidate_7days_2026-04-24.json`**

```json
{
  "job": "t0_pro_consolidate_7days",
  "created_at": "2026-04-17T<now>Z",
  "due_after": "2026-04-24T00:00:00Z",
  "priority": "HIGH",
  "subject": "Consolidate T0-Pro(7d-median) in SYMBIOSIS.md, replace bootstrap label",
  "pending_condition": "7 distinct days of Pro host snapshots with IA+FE non-null since 2026-04-17",
  "test_cmd": "sqlite3 ~/.agent/decisions/organism_metrics.db \"SELECT COUNT(DISTINCT DATE(calculated_at)) AS days, SUM(CASE WHEN ia_value IS NOT NULL THEN 1 ELSE 0 END) AS ia_ok, SUM(CASE WHEN fe_value IS NOT NULL THEN 1 ELSE 0 END) AS fe_ok FROM metabolic_snapshots WHERE collector_host='pro' AND metric_scope='host' AND calculated_at>='2026-04-17'\" | awk -F'|' '$1>=7 && $2>=7 && $3>=7 {exit 0} {exit 1}'",
  "action_on_pass": "Compute median of IA/FE last 7 Pro host snapshots. Update SYMBIOSIS.md §'Dove siamo' Pilastro 7: replace 'T0-Pro(bootstrap)' with 'T0-Pro(7d-median)' using real values. Remove 'non usare per claim comparativi' restriction.",
  "action_on_fail": "If precondition fails (days<7 OR IA/FE incomplete), extend due_after by 3 days and inspect cron runs: ls -lt ~/logs/cron/metabolic-rollup-pro.log.",
  "files_implicated": ["SYMBIOSIS.md"]
}
```

### 3.9 Update SYMBIOSIS.md §"Dove siamo"

Riga attuale:

```
| Misura | Implementato v1 (2026-04-16) | T0 baseline: TTR=869, DO=2.21, IA=1.0, FE=0.01 |
```

Diventa:

```
| Misura | v1 live (2026-04-16), parità Pro-Air via schema v2 (2026-04-17) | T0-Sistema (Air-collected, PG Fly): TTR=869, DO=2.21 · T0-Air(body): IA=1.0, FE=0.01 · T0-Pro(bootstrap, 2026-04-17): IA=<val>, FE=<val> **NON usare per claim comparativi — consolidamento 7d-median via claude_task t0_pro_consolidate_7days** |
```

Spiegazione aggiunta per il lettore: la tabella SYMBIOSIS non è più "T0 dell'organismo" ma "T0 delle sue parti", con stati espliciti.

---

## 4. Procedura di esecuzione (oggi)

Ordine cronologico. Idempotenza ovunque.

1. **Branch + spec v2 committed** (questo file)
2. **Edit `definitions.py`** — documentare convenzione `metadata.error='not_applicable_by_design'` (docstring + costante)
3. **Edit `storage.py`** — `_ensure_schema` con 2 colonne + `BEGIN IMMEDIATE` + index
4. **Edit `MetabolicStore.store()`** — signature con `collector_host`, `metric_scope`
5. **Edit `metabolic_rollup.py`** — argparse `--mode {air,pro,manual}` + logica 1 vs 2 row
6. **Create `scripts/launchd/com.cell.metabolic-rollup.pro.plist`**
7. **Create `scripts/metabolic_rollup_pro.sh`** (wrapper con venv fallback chain)
8. **Create `scripts/install_metabolic_rollup_pro.sh`**
9. **Test smoke:** `cd packages/cell-core && pytest tests/metabolic/ -q` — aggiorna test esistenti per nuova signature
10. **Dry-run:** `scripts/metabolic_rollup_pro.sh` con `--mode manual` — verifica snapshot calcolato
11. **First real run:** `scripts/metabolic_rollup_pro.sh` (mode=pro) → primo row Pro host in DB
12. **Query T0-Pro(bootstrap):**
    ```sql
    SELECT ia_value, fe_value FROM metabolic_snapshots
    WHERE collector_host='pro' AND metric_scope='host'
    ORDER BY calculated_at DESC LIMIT 1
    ```
13. **Install cron:** `scripts/install_metabolic_rollup_pro.sh`
14. **Update SYMBIOSIS.md** con valori reali IA/FE letti al passo 12, label `T0-Pro(bootstrap)`
15. **Create 2 claude_tasks** (T+1 verify, T+7 consolidate) con timestamp now
16. **One-shot Air backfill** (§4.1)
17. **Commit + push**

### 4.1 One-shot Air backfill — espande 3 snapshot in 6 row

Script su Air via SSH. I 3 snapshot storici diventano 6 row: ciascuno splittato in global + host con stesso `calculated_at`. Script Python idempotente (controlla prima se backfill già fatto).

```bash
ssh air 'python3 /Users/antonellosiano/Projects/nuzantara/scripts/backfill_air_schema_v2.py'
```

Lo script (da scrivere oggi):

- Legge le row con `collector_host IS NULL`
- Per ogni row storica, UPDATE a `(collector='air', scope='global')` proiettando solo TTR+DO
- INSERT nuova row `(collector='air', scope='host')` con stesso `calculated_at` proiettando solo IA+FE
- Re-eseguibile: se `collector_host IS NOT NULL`, skip

### 4.2 Aggiornamento test esistenti (obbligatorio)

File: `packages/cell-core/tests/metabolic/test_storage.py`

- `_make_snapshot()` e `store.store()` richiedono ora 2 arg nuovi
- Aggiungere test `test_schema_v2_migration_idempotent`: apri store, riapri store → no error, 2 colonne presenti
- Aggiungere test `test_store_scope_filtering`: inserisci 2 row (global+host), query filtrate per scope restituiscono rispettive row

Test breaker esistenti (`test_store_and_latest`, `test_latest_ordering`, ecc.): aggiornare call site con `collector_host='test', metric_scope='host'`.

---

## 5. Sicurezza e vincoli SYMBIOSIS

| Legge                                      | Rispetto                                                                                                                                        |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| #1 CLI-only per LLM                        | ✅ Nessun LLM invocato dal rollup                                                                                                               |
| #2 OSINT blindato                          | ✅ Solo metadati operativi                                                                                                                      |
| #3 Event-driven, no orchestratori centrali | ✅ LaunchAgent locale (pattern esistente), claude_tasks sono file non servizi                                                                   |
| #4 Graceful degradation                    | ✅ PG_DSN vuoto → TTR/DO None con `error='not_applicable_by_design'`; MOS missing → 0 endogenous; escalations missing → FE=0                    |
| #5 Zero ultima istanza                     | ✅ Update SYMBIOSIS.md è git commit, Zero può vetoare; task consolidate_7days è proposto, non auto-applied su SYMBIOSIS prima di Claude session |
| #6 Sovranità locale                        | ✅ Tutto su Pro; zero dati fuori                                                                                                                |
| #7 Numeri prima                            | ✅ Label `bootstrap` esplicita; consolidamento a 7d-median via task con precondizioni semantiche                                                |
| #8 Simbiosi                                | ✅ Zero approva spec; Claude esegue; claude_tasks portano follow-up nel flusso sessioni                                                         |

**Nuovi libri sacri:** nessuno.
**Nuove metriche canoniche:** nessuna (le 4 restano quelle di Pilastro 7).

---

## 6. Cosa NON è in questo sprint (out of scope, volutamente)

- **Comparator CLI Pro-Air read-only** — sprint futuro al primo caso d'uso reale
- **Metriche Pro-specifiche** (genome size, cell pulse count, intel scraper health) — ognuna richiede federation review
- **Fly PG tunnel su Pro** — Air ha monopolio TTR+DO per design §2.2
- **Dashboard visuale / Grafana**
- **HGT activation su 3+ cellule** — prossimo candidato naturale dopo questo sprint
- **Piano canonico aggregazione organismo** (F9 Codex) — legittimamente deferred, entrerà quando il comparator nascerà

---

## 7. Rischi e mitigazioni

| Rischio                                                | Prob  | Impact | Mitigazione                                                                                                    |
| ------------------------------------------------------ | ----- | ------ | -------------------------------------------------------------------------------------------------------------- |
| Primo run Pro fallisce silenzioso                      | media | alto   | Task T+1 `t0_pro_verify_firstrun` con test_cmd semantico                                                       |
| MOS DB path wrong su Pro                               | bassa | medio  | Test dry-run al passo 10                                                                                       |
| Claude session futura ignora claude_tasks              | bassa | alto   | CLAUDE.md §15 esplicito; 10923 task processati provano pattern                                                 |
| ALTER TABLE race (2 processi simultanei)               | bassa | medio  | `BEGIN IMMEDIATE` + threading.Lock + busy_timeout 5s (F1 fix)                                                  |
| Installer rompe cron esistenti                         | bassa | alto   | `launchctl bootout` scoped al label                                                                            |
| Venv `.venv` ricreato → cron fail                      | media | basso  | Fallback chain in wrapper (F8 fix)                                                                             |
| **Air rollup failure = loss of day's TTR/DO** (F6)     | media | medio  | **Rischio pre-esistente accettato.** Future mitigation: Pro fallback tunnel se Air down >24h. Fuori scope oggi |
| Ricaduta in claim comparativi usando T0-Pro(bootstrap) | media | medio  | Regola esplicita in SYMBIOSIS: "bootstrap non usare per before/after". Etichetta label distinta                |

---

## 8. Success criteria

**Sprint complete quando:**

1. ✅ `sqlite3 ... "SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='pro' AND metric_scope='host'"` ≥ 1
2. ✅ `launchctl list | grep com.cell.metabolic-rollup` carica su Pro
3. ✅ `grep T0-Pro SYMBIOSIS.md` trova riga con label `bootstrap` e valori reali
4. ✅ `ls ~/.agent/decisions/claude_tasks/t0_pro_*.json` → 2 file
5. ✅ `pytest packages/cell-core/tests/metabolic/ -q` passa (con nuovi test scope/migration)
6. ✅ Air 3 snapshot storici → 6 row backfilled (`SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='air'` = 6)
7. ✅ Git commit pushed

**Organismo ha fatto un passo vero quando** (T+7):

8. Task `t0_pro_consolidate_7days` eseguito da Claude in sessione automatica
9. SYMBIOSIS riporta `T0-Pro(7d-median)` con valori reali
10. Pronti per prossimo sprint (HGT activation con numeri before/after veri)

---

## 9. Riferimenti

- `SYMBIOSIS.md` — Pilastro 7 (Numeri prima), Leggi #1-#8
- `VADEMECUM.md §1` (Nuova automazione) — checklist soddisfatta
- `INDEX.md` §Cron schedule — aggiungere riga "23:45 WITA metabolic rollup (Pro)"
- `CLAUDE.md §15` — pattern claude_tasks
- `packages/cell-core/cell_core/metabolic/definitions.py` — 4 metriche canoniche invariate
- Spec precedente SUPERSEDED: `docs/superpowers/specs/2026-04-15-libri-sacri-canonici-design.md`
- **Federation review**: Codex GPT-5.4 xhigh (5 findings), Gemini 2.5 Pro (4 findings), DeepSeek R1 (5 findings). 4 correzioni integrate (F1, F3, F4, F5). 3 minori (F6, F7, F8). 3 rigettate motivatamente (F10, F11, F9).

---

## 10. Federation review verdict (conclusa)

**Convergenze valide integrate:**

- F1 (ALTER non idempotente) → `PRAGMA table_info` + `BEGIN IMMEDIATE` + lock
- F3 (T0 da 1 snapshot) → label `bootstrap` → `7d-median` via task
- F4 (test_cmd semantico) → distinct days + null checks
- F5 (Codex insight unico) → schema 2 colonne `collector_host` + `metric_scope`

**Valid minori integrate:**

- F6 (Air SPOF) → nota Risks, accepted
- F7 (staggering motivo) → "separare log windows"
- F8 (venv path) → fallback chain

**Rigettate motivatamente:**

- F9 (Codex: piano aggregazione organismo) → deferred §6 intenzionale
- F10 (DeepSeek: SQLITE_BUSY cross-machine) → lettura errata, DB locali per host
- F11 (Gemini: 4 status columns) → over-engineering, `metadata.error` JSON già copre

**Zero ha ultima parola.**

---

**Fine spec v2.**
