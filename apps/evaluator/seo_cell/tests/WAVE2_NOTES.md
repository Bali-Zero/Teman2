# SEO Cell — Wave 2 Fix Notes (A1 sensor name drift)

Scope minimale: chiudere la sola anomalia A1 prima del wiring Sprint 3
del Bayesian calibrator. A2 e A3 restano aperte (out of scope).

---

## Option chosen: B — update `SENSOR_NAMES` to long names

Rinominati nella tuple `SENSOR_NAMES` di `bayesian_calibrator.py`:
`"war_room"` → `"war_room_event"`, `"competitor"` → `"competitor_serp"`.
I sensor instance `.name` sono rimasti immutati.

**Perché Option B:**

1. `.name` è la public API dei sensor: pinned in 3 suite test
   (`test_sensors_stub.py::test_six_distinct_sensor_names`,
   `test_cell_factory.py`,
   `test_integration_wave1.py::EXPECTED_SENSOR_NAMES`). Toccarlo
   avrebbe obbligato a modificare anche contract test wave 1 appena
   merged (scope creep).
2. Naming semantico: `war_room_event` distingue eventi da canali di
   altro genere; `competitor_serp` distingue SERP da altre fonti.
   `"war_room"` / `"competitor"` erano alias più vaghi.
3. Nessun dato persisted: un `find . -name '*.db'` nel worktree ha
   restituito zero genome row con `seo_scoring_weights` pattern; nessun
   Brief in DB. Zero migration risk.
4. Raccomandazione esplicita in `NOTES.md` Wave 1 §A1 "Fix direction".

## File modificati (3 file, 14 inserts / 12 deletes, 1 file nuovo da 149 righe)

- `apps/evaluator/seo_cell/bayesian_calibrator.py` — 2 righe dentro la
  tuple `SENSOR_NAMES` (righe 50-51).
- `apps/evaluator/seo_cell/tests/test_bayesian_calibrator.py` — 3
  fixture dicts + 1 assertion pinata aggiornati (righe 68-69, 90-96,
  188-189, 211-212). Cambio solo delle chiavi; valori numerici e shape
  invariati.
- `apps/evaluator/seo_cell/tests/test_sensor_name_contract.py` — NUOVO,
  4 test tripwire (vedi sotto).

Totale diff misurato con `git diff --stat main -- apps/evaluator/seo_cell/`:
14 inserts, 12 deletes su 2 file tracked + 1 file nuovo = 163 righe
modificate totali, ben sotto il budget di 200.

## Test scritti (4 tripwire, tutti passing dopo fix)

`test_sensor_name_contract.py`:

1. `test_sensor_names_match_live_sensor_instances` — costruisce le 6
   istanze sensor come fa `sensors/__init__.py`, compara
   `{.name for ...}` con `set(SENSOR_NAMES)`. Guardia simmetrica
   contro drift futuro in qualsiasi direzione.
2. `test_default_weights_keys_match_live_sensor_instances` — pin sulla
   derivazione `DEFAULT_WEIGHTS` dalle live instance. Protegge il read
   path del thinker anche se qualcuno in futuro unpins
   `DEFAULT_WEIGHTS` da `SENSOR_NAMES`.
3. `test_calibrator_fit_reads_nonzero_scores_for_every_sensor` — costruisce un `Brief` keyed dalle live `.name`, proietta come fa
   `_fit` e verifica che nessuna colonna X collassi a 0.0. Questo è
   l'assertion che riproduce direttamente la 33% signal loss di A1.
4. `test_calibrator_mutates_when_briefs_keyed_by_live_sensor_names` —
   end-to-end: 40 brief sintetici, `calibrate()`, verifica che nessun
   weight collassi a 0.0. Regression test che lega drift →
   osservabilità nei pesi finali.

**Failure evidence senza fix** (verificata rimettendo temporaneamente
SENSOR_NAMES = ('war_room', 'competitor', ...) e rieseguendo la suite):

```
AssertionError: A1 regression: these sensors collapsed to zero weight
(likely key drift SENSOR_NAMES ↔ sensor.name): ['war_room', 'competitor'];
full weights={'gsc': 0.20, 'ga4': 0.29, 'kg': 0.30,
              'war_room': 0.0, 'competitor': 0.0,
              'cannibalization': 0.21}
```

Le 2 colonne col bug vanno letteralmente a 0, esattamente come
predetto dalla cross-LLM review 4/4.

## Run finale

```
$ PYTHONPATH=. apps/backend-rag/.venv/bin/pytest apps/evaluator/seo_cell/tests/ -x -v
...
apps/evaluator/seo_cell/tests/test_sensor_name_contract.py::test_sensor_names_match_live_sensor_instances PASSED
apps/evaluator/seo_cell/tests/test_sensor_name_contract.py::test_default_weights_keys_match_live_sensor_instances PASSED
apps/evaluator/seo_cell/tests/test_sensor_name_contract.py::test_calibrator_fit_reads_nonzero_scores_for_every_sensor PASSED
apps/evaluator/seo_cell/tests/test_sensor_name_contract.py::test_calibrator_mutates_when_briefs_keyed_by_live_sensor_names PASSED
...
114 passed in 0.46s
```

114 test totali, zero regressioni sugli esistenti (i 18 di
`test_bayesian_calibrator.py` + i 14 di `test_integration_wave1.py`
sono entrambi green).

## Out-of-scope found (non toccato per policy wave 2 minimale)

- **A2 observed (not fixed)**: `data/seo_cell/` viene creato nel
  worktree come side-effect dell'import di
  `apps/evaluator/seo_cell/config.py` (che chiama
  `DATA_DIR.mkdir(parents=True, exist_ok=True)` a import time).
  Osservato dopo la run pytest di questa sessione. NON rimosso dal
  working tree: rimuoverlo qui nasconderebbe il sintomo e il fix vero
  (lazy mkdir) è scope A2 ≠ wave 2. Lasciato untracked; la cleanup
  manuale o la .gitignore entry sono decisioni del PR di A2.
- **A3 still present**: `thinker.current_phase` continua a hardcoded
  `lead_count = 0`. Nessun lead sensor ancora in Sprint 2.

Nessun bug nuovo scoperto oltre a quelli già tracked.

## Cosa NON è stato fatto (dichiarazione onestà, per brief)

Tutto quello che il prompt chiedeva è stato fatto:

- [x] grep downstream prima di decidere
- [x] Option A/B decision con giustificazione
- [x] fix 1-riga + consumer update
- [x] 2-4 test tripwire che falliscono SENZA e passano CON fix
- [x] `pytest apps/evaluator/seo_cell/tests/ -x -v` verde
- [x] nessun file in root del repo (tutto sotto
      `apps/evaluator/seo_cell/tests/`)
- [x] nessuna modifica ad A2/A3

Non è stato fatto:

- commit e push da qui — il prompt dice "no PR", commit + push
  branch sono la last step.
