# SEO Cell — Integration Testing Notes

Wave 1 covers schema + tier + cross-sensor graceful. Anomalies annotated
here; none fixed in this session (per brief: no scope creep).

---

## Anomalies found (annotated, NOT fixed)

### A1. Sensor name drift between sensors and BayesianCalibrator

**Where:**
* `sensors/__init__.py` wires sensor instances whose `.name` attributes
  are `war_room_event` and `competitor_serp`.
* `bayesian_calibrator.SENSOR_NAMES` lists `"war_room"` and
  `"competitor"`.

**Impact:** The thinker calls `bayesian_calibrator.current_weights()`
and destructures weights keyed by `SENSOR_NAMES`. If the calibrator
ever ingests real Brief rows keyed by sensor *instance* names, the
keys will not match — the fit is silently fed zeros for two of six
sensors.

Today this does not manifest because:
* Wave 1 is sprint-1 stub territory (thinker returns no-op).
* The reconciliation layer (Brief generator in Sprint 3) does not
  exist yet.

**Fix direction:** align both to a single source. Preferred fix is to
update `SENSOR_NAMES` in `bayesian_calibrator.py` to the longer names
(`war_room_event`, `competitor_serp`), because the sensor `.name`
attributes are the user-facing API and already referenced by
`test_sensors_stub.test_six_distinct_sensor_names`. Would also require
updating `DEFAULT_WEIGHTS` consumers — trivial, same file.

**Recommended location:** wave 2, before the first calibration call
lands. Until then, the test at
`test_integration_wave1::test_sensor_names_match_expected_set` pins
the sensor-side names so they cannot drift further.

### A2. `data/seo_cell/` created on import

`apps/evaluator/seo_cell/config.py` does `DATA_DIR.mkdir(parents=True,
exist_ok=True)` at *import* time. Just importing the module creates
`data/seo_cell/` relative to `PROJECT_ROOT` — that pollutes the
workspace every time a tool or test touches the module.

Observed: running `test_integration_wave1.py` created `data/seo_cell/`
in the nuzantara-seo worktree (not committed, not in `.gitignore`).

**Fix direction:** move the `mkdir` into a lazy helper
(`_ensure_data_dir()`) called by `cell_birth_date()` and
`create_seo_cell()`. Import-time side effects on the filesystem are a
smell.

**Recommended location:** wave 2, same PR as the first live pulse test.

### A3. `thinker.current_phase` reads lead_count=0 unconditionally

The comment says "lead_count comes from CRM via a future sensor" but
the pessimistic default permanently locks pre_natal even if the real
gate (80 GSC queries × 3 leads × 28 days) is otherwise met. Until the
lead_attribution_sensor ships, the cell cannot graduate — even in
integration-test fixtures (which is why Wave 1's
`test_thinker_aggregates_mixed_status_readings_into_noop` pins
birth_date *after* the min_age_days cutoff and still expects no-op).

**Fix direction:** Sprint 2 lead_attribution_sensor, or a
`memory_context["lead_count"]` hook that the actor writes and the
thinker reads.

---

## Wave 2 TODOs

(Not written in Wave 1 by brief instruction. Listed here for the next
agent.)

### W2-T1. Bayesian calibrator sensitivity battery

Goals:
* `measure_lift` bounds: verify output is monotone in `after` for
  fixed `before`, rejects disallowed window_days.
* `BayesianCalibrator.calibrate()`:
  - <30 briefs → `mutated=False`, reason surfaces sample count
  - exactly 30 briefs → first mutation path exercised
  - degenerate input (all sensors score = 0, all lift = 0) → falls
    back to `DEFAULT_WEIGHTS`, not NaN.
  - ridge regularisation actually damps high-variance sensors
    (parametrize with known X, y).
* Simplex projection invariants: output `sum(weights)==1` and
  all `weights >= 0` on adversarial input (negative lift, one-hot
  sensor).
* Genome persistence round-trip: calibrate → read back via
  `thinker.current_weights` → exact dict match (within float
  tolerance).

Estimate: 15-20 tests.

### W2-T2. PulseLoop end-to-end on a temp SQLite

Goals:
* `create_seo_cell()` + `.single_pulse()` on a disposable DB path —
  verify pulse_number=1, halted=False, action_taken="no_action".
* Assert the pulse does not touch the live `GOOGLE_CREDENTIALS_PATH`
  or `DATABASE_URL` when both are monkeypatched to missing.
* Assert SqliteMemoryStack captures the reading for each of the 6
  sensors (episodic + stm).
* Assert on_pulse callback fires exactly once per `.single_pulse()`.

Estimate: 6-8 tests.

### W2-T3. Actor refusal bookkeeping

Goals:
* After N pre_natal pulses with non-none proposals, actor
  `_refused_intents` grows by N and preserves `{action, reason,
  phase}` shape.
* A post-graduation pulse with a not-whitelisted action returns
  `refused_not_implemented`, not `refused_pre_natal`.

Estimate: 3-5 tests.

### W2-T4. Align SENSOR_NAMES (blocks W2-T1)

See A1 above. Required before the calibrator tests can be written
against the real sensor name contract.

---

## Out of scope (both waves)

* Live GSC/GA4/Qdrant calls — stays mocked.
* Council-4LLM regression — eliminated by v2.1 memo, no tests needed.
* cannibalization clustering — will move to thinker layer per stub
  header comment.
