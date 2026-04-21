# SEO Cell — Wave 3 Fix Notes (A2 + A3)

Scope minimale: chiudere le ultime due anomalie rimaste dopo che wave 1
ha risolto A1 (sensor name drift). Nessun altro refactor.

Branch: `session/seo-a2-a3-fix` · Base: `main @ d4fa14115` (post wave 1+2
merges).

---

## A2 — `DATA_DIR` creato al module import

### Option chosen: lazy helper `ensure_data_dir()`

`apps/evaluator/seo_cell/config.py` non fa più `mkdir` al top level.
La directory viene materializzata solo dai due siti che scrivono
davvero dentro:

1. `config.cell_birth_date()` — prima di `_BIRTH_DATE_MARKER.write_text(...)`.
   Il marker è il trigger della PRIMA scrittura in assoluto; senza
   `ensure_data_dir()` a monte il write fallirebbe con `FileNotFoundError`
   al primo avvio del cell.
2. `cell.create_seo_cell()` — prima di `SqliteMemoryStack(cell_config.db_path)`.
   `SqliteMemoryStack` apre `DB_PATH` immediatamente e non tollera una
   parent dir mancante.

Il terzo consumatore, `CompetitorSERPSensor`, è **reader-only** e già
protetto da un guard `if not self._cache_db.exists(): return yellow(...)`
al primo read. Non crea nulla quindi non chiama il helper: resterebbe
in stato yellow `cache_not_populated` fino a che lo scraper cron
(`scripts/scrape_competitor_serp.py`, sprint 2f) popolerà il file.

### Perché Option A (lazy helper) e non Option B (mkdir dentro `get_db_path`)

- Nessuna delle path-costanti esportate (`DB_PATH`, `COMPETITOR_CACHE_DB`,
  `_BIRTH_DATE_MARKER`) ha bisogno del helper per essere **letta** — solo
  per essere **scritta**. Mettere mkdir in un getter penalizzerebbe anche
  il sensore reader, che per contratto non deve avere side effect su
  disco.
- Due chiamate esplicite a `ensure_data_dir()` rendono visibile nel grep
  chi è il writer — una virtù di debug che un getter implicito nasconde.
- Il cambio è additivo: `DATA_DIR` resta identico come `Path`, nessun
  import esterno rotto. Il sensore, i test wave 1 e le dipendenze
  `from apps.evaluator.seo_cell.config import ...` continuano a vedere le
  stesse costanti.

### File modificati

- `apps/evaluator/seo_cell/config.py` — rimossa la riga
  `DATA_DIR.mkdir(...)` top-level (era riga 10), aggiunta funzione
  `ensure_data_dir() -> Path` + commento esplicativo sopra `DATA_DIR`
  per i Claude futuri. `cell_birth_date()` ora chiama
  `ensure_data_dir()` prima del primo `write_text`.
- `apps/evaluator/seo_cell/cell.py` — aggiunta chiamata
  `config.ensure_data_dir()` in cima a `create_seo_cell()`, prima che
  `CellConfig`/`SqliteMemoryStack` tocchino disco.
- `apps/evaluator/seo_cell/tests/test_config_lazy_data_dir.py` — NUOVO,
  2 test (vedi sotto).

### Test aggiunti (2, entrambi verdi, tripwire armato)

`test_config_lazy_data_dir.py`:

1. `test_import_config_does_not_create_data_dir` — **static AST check**:
   parsa `config.py` e fallisce se un `.mkdir(...)` riappare a scope
   modulo. Scelto statico e non runtime perché a pytest-collection-time
   il modulo è già in `sys.modules` e altri test della suite (es.
   `test_cell_factory`) possono aver già creato `DATA_DIR` via factory
   call — un probe runtime sarebbe flaky sul campo.
2. `test_ensure_data_dir_creates_when_called` — usa `monkeypatch.setattr`
   per puntare `DATA_DIR` a `tmp_path / "seo_cell_under_test"`
   (inesistente), chiama `ensure_data_dir()`, verifica che la directory
   venga creata, il return sia il path stesso, e che una seconda
   chiamata sia idempotente (exist_ok contract).

**Reality check tripwire armato**: ho re-introdotto
`DATA_DIR.mkdir(parents=True, exist_ok=True)` a scope modulo in locale,
il test #1 ha fallito riportando `Offending lines: [17]`. Rimosso il bait,
tutti i 116 test della suite verdi in 0.17s. Il tripwire effettivamente
cattura la regressione.

---

## A3 — `lead_count = 0` hardcoded nel thinker

### Option chosen: **A** — docstring allineata alla realtà

Il commento pre-wave-3 (`thinker.py:118-121`) diceva:
> memory context carries a rolling count written by the actor on every pulse

**Non è vero.** `rg "rolling_lead_count" apps/` restituisce 0 match;
`rg "website_organic_lead"` fuori dai test mostra solo la firma di
`phase.is_pre_natal(...)` e l'attuale call site nel thinker. L'attore
non scrive il counter perché non esiste ancora un sensore che lo
produca (sprint 2 non ha shippato `lead_attribution_sensor`).

Il nuovo commento spiega **il comportamento attuale** (0 hardcoded),
**perché è il default sicuro** (una lettura da `memory_context` popolato
da nessuno graduerebbe in silenzio il cell), e **chi deve svincolarlo**
(lo sprint 2 `lead_attribution_sensor`). Nessuna modifica di logica:
il thinker continua a emettere `Proposal(action="none")` e `pre_natal`
resta locked finché il sensore non arriverà.

### Perché NON Option B (lettura da memory_context)

Opzione B avrebbe letto `memory_context.get("rolling_lead_count", 0)`.
Sembrava elegante ma:

1. **Nessuno scrive la chiave.** `rg` sopra lo conferma. Il valore
   sarebbe 0 all'infinito — stessa semantica dell'hardcode ma con più
   superficie di bug futuri.
2. **Rischio di falso positivo.** Se un futuro cambio (fuori scope wave
   3) inserisse un default non-zero in `memory_context` per un motivo
   ortogonale — es. telemetry o seeding — il thinker graduerebbe il
   cell basandosi su un valore che non è attribution reale. La
   graduation deve arrivare solo dal sensore dedicato, mai da un
   counter ambient.
3. **Sprint 2 non ha consegnato**, quindi B è prematuro. Il momento
   giusto per leggere da memory_context è quando lo scrive un writer
   affidabile; ora writer affidabile = il sensore che deve arrivare.

### File modificati

- `apps/evaluator/seo_cell/thinker.py` — 5 righe di commento riscritte,
  più 4 righe aggiunte per esplicitare il reasoning. Zero cambi di
  logica: `lead_count = 0` resta, `is_pre_natal(...)` chiamata
  invariata. Diff isolato.

### Test aggiunti

**Zero nuovi test per A3**: la behavior (`pre_natal=True` quando
`lead_count < PRE_NATAL_MIN_WEBSITE_ORGANIC_LEADS`) è già pinnata da
`test_phase.py` e `test_thinker_and_actor.py` (5 test passing). Un
test del commento sarebbe paranoia — il tripwire è il fatto che la
suite continua a passare con la realtà documentata.

---

## Reality check finale

| metric | value |
| --- | --- |
| N test aggiunti | **2** (target 2-4, A2 tripwire + A2 behavior) |
| A3 Option chosen | **A** (honest comment); Sprint 2 non ha shippato |
| Test suite seo_cell | **116 passed, 0.17s** |
| File nuovi fuori pkg | **0** (WAVE3_NOTES sotto `tests/`, come wave 2) |
| Refactor fuori scope | **0** — nessun touch a bayesian_calibrator, nessun sensor |

### Out-of-scope osservato (annotate only, non fixed)

- **Bayesian sensitivity analysis**. Wave 2 ha chiuso il name drift ma
  non ha scritto un test di sensitività dei pesi (es. "se un sensore
  resta 0 per N pulse il suo peso decade di ≤X"). Va eseguito in wave 4
  quando arriveranno Brief row reali, non prima.
- **`CompetitorSERPSensor.__init__` default `cache_db=COMPETITOR_CACHE_DB`**.
  `COMPETITOR_CACHE_DB = DATA_DIR / "competitor_serp_cache.db"` viene
  valutato a import-time, quindi "congelato" al path reale del
  worktree. Se un test patcha `DATA_DIR` a tmp, le istanze successive
  del sensore NON leggono il nuovo path — guarderebbero sempre il path
  originale. In pratica nessun test corrente lo fa (il sensore è
  reader-only e graceful), ma è un punto di attenzione se wave 4
  introdurrà fixture che manipolano DATA_DIR via monkeypatch.
- **`lead_attribution_sensor` propriamente detto**. Blocker sprint 2.
  Fuori scope wave 3 per design. Quando arriverà, il commento scritto
  in A3 è la lista della spesa: deve scrivere `rolling_lead_count` (o
  nome equivalente) in un canale ben definito — sensor value o genome
  pattern, NON memory_context generico — e il thinker leggerà da lì
  invece che hardcodare 0.

### Wave 4 TODO (backlog, non blocker oggi)

1. Bayesian sensitivity test (vedi sopra).
2. Migrazione di `COMPETITOR_CACHE_DB` / `DB_PATH` a funzioni lazy se
   wave 4 introduce test fixture che patchano `DATA_DIR`. Oggi non
   necessario.
3. `lead_attribution_sensor` + rimozione dello hardcode A3 quando
   il sensore landa.
