---
date: 2026-06-03
domain: operations
client_case: false
sources:
  - "Empirical observation 2026-06-03 (operator session): Cell red ~5 days; health_status = worst-of-13-sensors dragged red by backup/cron secondary sensor (fly_pg_backup failed 113h); alarm illegible (generic 'red' + 'potential transient issue that needs verification' ×959)."
  - "Empirical: olympus_rules superseded_by always NULL (0 rules ever superseded across 13 rules / ~740 applications)."
  - "Empirical: reasoner 'Reasoner produced unparseable output:' ×25 — DeepSeek/LLM judgment returns '' or non-parsable (same class as evoskill judge '' → 0.0)."
  - "Empirical: alert_human max_per_day=20 reached 20/20 + cooldown 300s suppress TRUE alarms with no alternate escalation channel (anti-storm cicatrix W61)."
  - "apps/cell/cell/core/pulse.py (lines 331-367 worst-of aggregation; 374-380 log line; sensor_metadata dict built 266-364)."
  - "apps/cell/cell/sensors/backup_sensor.py, cron_sensor.py (status classification + metadata that already carries age_hours / failed_jobs / stale_jobs)."
  - "apps/cell/cell/slow/reasoner.py (lines 115-165 _parse_response → 'unparseable output' fallback; 167-186 _call_ollama)."
  - "apps/backend-rag/backend/llm/deepseek_client.py (lines 86-276: response_format json_object documented 115-117; raises DeepSeekError on empty content 208-210)."
  - "apps/backend-rag/backend/services/olympus/rules_engine.py (load_rules WHERE superseded_by IS NULL line 32; lower_confidence 76-95; NO supersede writer); models.py OlympusRule.superseded_by line 109."
  - "apps/cell/cell/effectors/allowlist.py (alert_human max_per_day=20 cooldown 300s line 22; alert_silent max_per_day=1000 → cell_alerts line 23)."
  - "apps/cell/cell/core/db.py log_alert() lines 126-143 (writes cell_alerts — the un-throttled sink)."
  - "apps/organism/organism/rules/base.yaml (13 base rules); supervisor/consiglio_gate.py (multi-LLM gate, DeepSeek panelist)."
---

# The Fourth Verb — Specification: the Organism that Reviews Itself

> Status: **SPEC ONLY. No production changes. Do not touch evoskill / agent-library (concurrent session).**
> Scope: `apps/cell`, `apps/backend-rag/backend/services/olympus`, `apps/backend-rag/backend/llm`. Surgical, reversible, testable.

---

## 0. The principle (read this first)

The organism already conjugates three verbs:

| Verb | Where it lives | Empirical proof of life |
|---|---|---|
| **SENTE** (senses) | `cell/core/pulse.py` pulse loop, 13 sensors; `olympus_heartbeats` | pulse #5788, ~1326 heartbeats/mo, health 99.1 |
| **GIUDICA** (judges) | `cell/slow/reasoner.py`; `olympus_rules` (13 rules) + DeepSeek | 740 rule applications |
| **AGISCE** (acts) | `cell` effectors + `organism` actuators; supervisor MAPE-K | 20,504 real actions (vacuum/cleanup/refresh/kickstart) |

It does **not** conjugate the fourth: **RIVEDERE SÉ STESSO** — *to review itself*. The operator's phrase — *"l'agente è figlio dell'Esperienza"* — names exactly what is missing. Experience is not the accumulation of pulses, rules and actions; experience is the faculty of **turning a critical eye on your own instruments and your own output** and *correcting* them. Remembering + judging + acting are present. The reflexive loop that audits those three is not.

Tonight's incident is the proof, and it is **one** failure wearing four masks:

- The organism **sensed** a real red (backup stuck 113h) but **could not say what it sensed** → mask A (legibility).
- The organism **learned 13 rules** but has **never revised one** (`superseded_by` perpetually NULL) → mask B (rule self-revision).
- The organism's **judge returned empty** ('' → "unparseable output" ×25) and **nobody audited the judge** → mask C (judgment robustness).
- The organism's **safety brakes muted a true alarm** (20/20 + cooldown) with **no second channel to say "this one is real"** → mask D (escalation past the brakes).

Each mask is the *same* defect: **the organism trusts its own instruments and its own output uncritically.** A is "it can't read its own sensor truthfully to a human." B is "it can't read its own rule as possibly-stale." C is "it can't read its own LLM output as possibly-junk." D is "it can't read its own suppressed alarm as possibly-true." The fourth verb is the single faculty of **distrusting-then-correcting the self** — applied to four surfaces (the human-facing readout, the rule store, the LLM channel, the alarm budget). That is why this is **one conceptual intervention, not four disconnected patches**: ship them as a family ("Tema: l'organismo che si rivede"), reviewable as a whole.

The scalpel rule: each pillar is a **small, reversible, independently-testable** change to existing files. No new daemon, no re-architecture, no Consiglio panel. We are adding a *reflexive mirror*, not a second brain.

---

## 1. Order-by-leverage (validated, with one correction to the operator's hypothesis)

The operator hypothesised: **A (legibility) and C (reasoner robustness) highest, because both are cross-cutting.** I **partially confirm and partially refute**:

| Rank | Pillar | Leverage rationale | Effort | Risk |
|---|---|---|---|---|
| **1** | **C — Robust LLM judgment** | **Highest, and higher than A.** The empty-reasoner bug is *upstream of everything that judges*: Cell's reasoner, evoskill scorer, Consiglio panelist, any future DeepSeek caller. When the judge returns '', A produces a *legible report of a broken judgment*, B *cannot evaluate confidence to supersede*, D *escalates noise*. Fixing C makes A/B/D trustworthy. It is also the lowest-risk (a wrapper, pure-additive). **This is the correction: C strictly dominates A** — a legible readout of a hallucinated/empty judgment is worse than an illegible readout of a sound one, because it *looks* authoritative. | S | Very low |
| **2** | **A — Alarm legibility** | Highest *operator-facing* value and the direct cause of "read as false positive for 5 days." But it is **downstream of C** in trust: the synthesis is only as honest as the judgment feeding it. Strictly mechanical (the data already exists in `sensor_metadata`), so very low risk. | S | Low |
| **3** | **D — Escalation past the brakes** | High value (a true alarm that is invisible is the worst failure mode), but **depends on A** (you can only escalate a legible "this sensor, this long" line) **and C** (you must not escalate noise). Therefore third, not first. Pure-additive (a digest reader over the already-un-throttled `cell_alerts` sink). | S–M | Low |
| **4** | **B — Rule self-revision (`superseded_by`)** | Genuinely transformative ("accumulate" → "refine"), but **lowest immediate leverage and highest blast-radius**: it *mutates the live rule store* that drives 20,504 actions. It also *needs* C (confidence comparison must be trustworthy) and benefits from A (legible supersede audit). Ship it last, behind a shadow-mode flag, after C has hardened the confidence signal it depends on. | M | Medium (mutates live rules) |

**Verdict on the hypothesis:** the operator was right that **A and C are the two cross-cutting ones** and belong at the top. The refinement is the *ordering between them*: **C before A**, because a legible readout built on an empty/garbage judgment is actively dangerous (false authority), whereas C makes every other pillar's output trustworthy. D and B are real but *derived* — they consume what C and A produce, and B additionally carries mutation risk, so it goes last.

Build order: **C → A → D → B.**

---

## 2. Pillar C — Robust LLM judgment (rank 1)

### Problem (empirical)
- Cell reasoner logs `"Reasoner produced unparseable output:"` ×25 (`cell/slow/reasoner.py:122`). When the model returns no JSON, `_parse_response` degrades to `action="alert_human", confidence=0.5` — i.e. a *guess dressed as a decision*.
- Same class as the evoskill saga ("judge sees '' → 0.0"). The defect is **trans-organ**: any path that asks an LLM for a verdict and gets `''` or junk has no robust retry/fallback.
- `deepseek_client.py` already does the *right thing on its side* — it `raise DeepSeekError` on empty content (lines 208-210) — but **callers don't uniformly catch it, retry, or fall back**, and the Ollama path in the reasoner has *no* retry at all (one shot per tier, `_call_ollama` lines 167-186).
- Verified constraint: DeepSeek accepts `response_format={"type": "json_object"}` **only** (documented `deepseek_client.py:115-117`); it does **not** support `json_schema`. The prompt must contain the word "JSON" for json_object mode to engage.

### Fix proposed — a `robust_judge` wrapper (pure-additive, not a panel)
Add one small helper module: `apps/cell/cell/slow/robust_parse.py` (Cell side) and reuse the same contract in backend via a thin function in `backend/llm/deepseek_client.py`. The wrapper does **four** things, in order, and is the *single* entry point for "ask an LLM for a structured verdict":

1. **Force JSON mode** where supported: when calling DeepSeek, always pass `response_format={"type":"json_object"}` and guarantee the literal token `JSON` is in the prompt (assert at call site). Never `json_schema`.
2. **Retry with backoff on empty/unparsable**: up to `N=2` retries (total 3 attempts) with jittered backoff (0.5s, 1.5s). "Empty/unparsable" = empty string, no `{`…`}` span, or `json.loads` raises. Each retry appends a one-line *parser-feedback* nudge to the prompt ("Your previous reply was not valid JSON. Reply with exactly one JSON object.") — mirrors the existing `genai_client.generate_structured` retry pattern documented in backend CLAUDE.md.
3. **Fallback to a typed heuristic** when all attempts fail: return a `JudgeResult(ok=False, fallback=True, raw=<first_raw>, value=<caller_default>)`. The caller decides the safe default — Cell's reasoner falls back to `action="none"` when health is GREEN/YELLOW (not `alert_human`), and to a *legible* `alert_silent` ("reasoner unavailable after 3 attempts; raw head: …") when RED, so the failure is *recorded*, not *acted on as a real decision*.
4. **Always log the raw**: the discarded raw output is written (truncated to 500 chars) to the existing observability sink (`record_llm_call` already captures `error_class`; add `raw_head` to the JSONL row) so the empty-reasoner pattern becomes *queryable* instead of buried in a warning.

Crucially, the wrapper **changes the meaning of "unparseable" from "guess + alert_human@0.5" to "fall back to the safe action + record honestly"**. That single change removes the *false authority* that masks A/B/D.

### Files / tables touched
- NEW `apps/cell/cell/slow/robust_parse.py` (the wrapper + `JudgeResult` dataclass).
- EDIT `apps/cell/cell/slow/reasoner.py`: replace the bodies of `_parse_response` (lines 115-165) and the per-tier `_call_ollama` call sites in `think()` (lines 276-319) to route through `robust_parse`. Remove the `alert_human@0.5` "unparseable" path (lines 122-128, 159-165).
- EDIT `apps/backend-rag/backend/llm/deepseek_client.py`: add a `complete_json_async()` convenience that wraps `complete_async` with forced `response_format={"type":"json_object"}`, prompt-token assertion, and the same retry-then-raise contract. (Does **not** change the existing `complete_async` signature — additive.)
- No schema change. (`record_llm_call` JSONL gains an optional `raw_head` field — backward-compatible.)

### How it is tested (TDD)
- `apps/cell/tests/test_robust_parse.py` (new):
  - empty string → 3 attempts → `fallback=True`, value=caller default, raw logged.
  - junk-then-valid (mock returns '' on attempt 1, valid JSON on attempt 2) → `ok=True` on retry.
  - valid first try → 1 attempt, no retry (assert call count == 1).
  - confidence clamp preserved (0..1).
- `apps/cell/tests/test_reasoner_red.py` (extend existing): when reasoner is fed an empty model reply and health=RED, assert action is `alert_silent` with a legible message **not** `alert_human@0.5`.
- Backend: `apps/backend-rag/tests/.../test_deepseek_json.py` (new): assert `complete_json_async` raises if prompt lacks "JSON"; asserts `response_format` is json_object; asserts retry count on empty content.

### Risk / rollback
- Risk: **very low** — pure-additive wrapper; existing call paths keep working until repointed. The only behavior change is the *unparseable* branch, which today is already a degraded guess.
- Rollback: revert the two call-site edits in `reasoner.py`; the wrapper module is inert if unused. No data migration to undo.
- Kill switch: env `CELL_REASONER_ROBUST=false` short-circuits `robust_parse` back to single-shot legacy behavior.

---

## 3. Pillar A — Alarm legibility (rank 2)

### Problem (empirical)
- `pulse.py:331-367`: `worst = max(sensor_statuses, key=severity)`. One secondary sensor (`backup`/`cron`, root cause `fly_pg_backup` failed 113h) makes the *whole organism* red.
- The human-facing signal was a generic `"red"` plus `"potential transient issue that needs verification"` repeated **959×**. The operator (and the first-pass analysis) read the **true** alarm as a false positive **for five days**.
- The data to do better **already exists**: `sensor_metadata` is built per-pulse (`pulse.py:266-364`) and carries, e.g., `backup.age_hours`, `cron.failed_jobs`, `cron.stale_jobs` (`backup_sensor.py:108-113`, `cron_sensor.py:146-150`). What is missing is the **synthesis** ("which sensor + why + how long") and the **routing** of that synthesis to a place a human reads.

### Fix proposed — `summarize_red()` + a legible error_message + driver-sensor field
Add a pure function `summarize_pulse(status, sensor_statuses, sensor_metadata) -> RedSummary` in a new `apps/cell/cell/fast/red_summary.py`:

- Identifies the **driver sensor(s)**: the sensor(s) whose status == `worst`. (When several tie, list all, worst-first.)
- Renders a **one-line human sentence** per driver from a small, per-sensor template registry keyed by sensor name, e.g.:
  - `backup` → `"DB backup stale {age_hours:.0f}h (job fly_pg_backup {last_job_status})"`
  - `cron` → `"cron job(s) {failed_jobs|stale_jobs} not fresh (worst {age_hours:.0f}h)"`
  - `db`/`qdrant`/`error_rate`/`ollama`/`vercel`/`outbox` → their own one-liners from existing metadata fields.
  - default → `"{sensor}={status} ({metadata})"` (never silently drop an unknown sensor).
- Returns `RedSummary(driver_sensors=[...], headline="DB backup stale 113h …", details={...})`.

Wire it at three points:
1. **DB persist** (`pulse.py:768-778`): set `error_message = summary.headline` (when not GREEN) **instead of** the current `action_reason` blob. The dashboard `cell_pulse_log.error_message` becomes a *sentence*, not a generic phrase.
2. **Log line** (`pulse.py:374-380`): append `driver=<sensor> because <headline>` so the *grep-able* log says which sensor, not just `health=red`.
3. **Observatory emit** (`pulse.py:1016-1044`): add `driver_sensors` + `headline` to the `pulse_result` payload so downstream consumers (and Pillar D's digest) get the legible field for free.

This is **only** a readout synthesis — it does **not** change the `worst` aggregation (that is correct: a stuck backup *is* a real degradation). It changes what the organism *says about* the red.

### Files / tables touched
- NEW `apps/cell/cell/fast/red_summary.py` (`summarize_pulse` + `RedSummary` + per-sensor template registry).
- EDIT `apps/cell/cell/core/pulse.py`: 3 wiring points above (error_message line ~777, log line ~374, observatory payload ~1028). ~15 lines net.
- No new sensor, no schema change (`cell_pulse_log.error_message` already exists and is free-text).

### How it is tested (TDD)
- `apps/cell/tests/test_red_summary.py` (new):
  - backup-driven red → headline contains "backup" and the age in hours; `driver_sensors == ["backup"]`.
  - tie (backup red + cron red) → both listed, deterministic order.
  - unknown sensor red → falls through to default template, never empty.
  - all-green → `headline == ""`, `driver_sensors == []`.
- `apps/cell/tests/test_pulse_*.py` (extend): assert `log_pulse` receives the headline as `error_message` on a synthesized red reading.

### Risk / rollback
- Risk: **low** — read-only synthesis of data already collected; no decision logic touched.
- Rollback: revert the 3 wiring lines; `red_summary.py` becomes inert.
- Edge: templates must `.get()` metadata defensively (a sensor may omit a field) — the default template guarantees no `KeyError` aborts a pulse.

---

## 4. Pillar D — Escalation past the brakes (rank 3)

### Problem (empirical)
- `alert_human` is capped at `max_per_day=20` + `cooldown_seconds=300` (`allowlist.py:22`). Tonight it hit **20/20**; subsequent true alarms were silently dropped. This brake is **correct** (cicatrix W61 retry-storm) — but it is **blind**: a real, sustained alarm that has exhausted budget becomes *invisible*, indistinguishable from "all clear."
- There is **already an un-throttled sink**: `alert_silent` → `cell_alerts` (`max_per_day=1000`, `db.py:log_alert` lines 126-143). Every suppressed-but-real condition can be *recorded* there cheaply; what is missing is a **periodic digest** that says *"these alarms are suppressed by the brakes but have been true for N hours."* A digest, **not** more real-time spam.

### Fix proposed — suppression-aware digest over `cell_alerts`
1. **Mark suppression at the source**: when the reasoner *would* `alert_human` but the daily-limit/cooldown gate blocks it, write an `alert_silent` row to `cell_alerts` with `action="alert_suppressed"` and `message = <Pillar-A headline>` (so the suppressed alarm carries the legible reason). This reuses the existing un-throttled path — no new table.
2. **Digest job** (`apps/cell/cell/slow/suppression_digest.py`, new): a small async function, invoked **once per hour** from the existing pulse loop (gate on `pulse_number % 60 == 0`, same cadence as the LTM refresh at `pulse.py:542`), that:
   - queries `cell_alerts` for rows with `action IN ('alert_suppressed','alert_human')` in the last 24h that are **still active** (the same driver sensor is still red on the latest pulse),
   - groups by driver/headline, computes "true for N hours" from the earliest matching row,
   - if any group exceeds a threshold (default: suppressed **and** sustained ≥ 2h), emits **one** consolidated message through whatever escalation channel is live (Telegram via `alerter` when enabled, else the Organism `cell_incident` outbox channel — the autonomic path already used at `pulse.py:733-752`).
   - The digest itself is rate-limited to **1 per `digest_cooldown` (default 6h)** so the escalation-of-suppressions cannot itself become a storm (W61 discipline applied recursively to the fix).

This gives the organism a *second, quieter voice*: "I have been shouting and you muted me; here is the one thing that is actually still wrong, and how long."

### Files / tables touched
- EDIT `apps/cell/cell/core/pulse.py`: at the `alert_human` branch (lines 733-752), when the action is blocked by limit/cooldown, also `log_alert(action="alert_suppressed", message=headline)`. (~6 lines.)
- NEW `apps/cell/cell/slow/suppression_digest.py` (the query + grouping + single-emit + digest cooldown).
- EDIT `apps/cell/cell/core/pulse.py`: hourly invocation hook (`pulse_number % 60 == 0`), fire-and-forget like the observatory emit. (~5 lines.)
- No schema change (`cell_alerts` already has `level/action/message/health_status/pulse_number`).

### How it is tested (TDD)
- `apps/cell/tests/test_suppression_digest.py` (new), against a test PG pool or a fake:
  - 25 suppressed rows over 3h for the same driver → digest emits exactly **one** message, text contains "≥3h"/"3h" and the headline.
  - suppression that resolved (driver now green) → digest emits **nothing**.
  - two distinct drivers suppressed → one message listing both groups.
  - digest cooldown: two invocations 1h apart → second is a no-op.
- Extend `test_pulse_*`: blocked `alert_human` writes an `alert_suppressed` row.

### Risk / rollback
- Risk: **low** — reuses the un-throttled `alert_silent`/`cell_alerts` path and adds a *rate-limited* read-side digest; cannot increase real-time alert volume (digest cooldown ≥ 6h).
- Rollback: remove the hourly hook + the `alert_suppressed` write; `suppression_digest.py` goes inert.
- Kill switch: env `CELL_SUPPRESSION_DIGEST_ENABLED=false`.
- Edge: digest must dedupe against its own prior emits (store last-digest timestamp in `cell_alerts` with `action="digest_emitted"`), or it re-escalates the same group every hour — that *would* be a storm.

---

## 5. Pillar B — Rule self-revision via `superseded_by` (rank 4)

### Problem (empirical)
- `olympus_rules.superseded_by` exists in schema and in the model (`models.py:109`); `load_rules` already filters `WHERE superseded_by IS NULL` (`rules_engine.py:32`) — **the read side is built and waiting.** But across 13 rules / ~740 applications, `superseded_by` is **always NULL**: the organism has **never** retired or replaced a rule. `lower_confidence` (lines 76-95) can *erode* a rule's confidence to 0 but never *supersedes* it — a confidence-0 rule lingers, still loaded, still matchable.
- Result: the organism **accumulates** rules but never **refines** them. New learning cannot correct old learning. This is the rule-store face of "the organism doesn't review its own output."

### Fix proposed — a supersede writer with a shadow-mode gate
Add `RulesEngine.supersede(old_rule_name, new_rule_id, reason)` and a periodic `propose_supersessions()` that the existing weekly Reflexion/dream synthesis can call. Logic (conservative, confidence-driven):

- A candidate supersession exists when **two active rules in the same `category` target the same `config` key/threshold with contradictory values**, OR an existing rule's confidence has decayed below a floor (default 0.2) **and** a newer rule (`source` learned, higher `confidence`, more recent) covers the same category.
- The writer sets `old.superseded_by = new.id`, stamps `updated_at`, and records an `olympus_actions` row (`action_type="rule_superseded"`, `outcome="success"`, `detail={old, new, reason, old_conf, new_conf}`) so the audit is first-class and Pillar A can render it legibly.
- **Shadow mode first** (default `OLYMPUS_RULE_SUPERSEDE_MODE=shadow`): `propose_supersessions()` writes a *proposal* row to `olympus_insights` (`insight_type="recommendation"`, the table already exists per `models.py:122` `InsightRecord`) instead of mutating `olympus_rules`. The operator (or a later promotion job) flips to `enforce` after reviewing proposals. This keeps the *live rule store that drives 20,504 actions* untouched until the heuristic is proven.
- Guard: never supersede a `source="base"` (hand-authored) rule automatically; base rules are constitutional. Only `source` in {`learned`,`reflexion`,`dream`} are eligible to be superseded by another learned rule.

This is the one pillar that **depends on Pillar C**: the confidence comparison that decides a supersession is only trustworthy once the judge that produces those confidences is robust (no '' → 0.0 artifacts). Hence rank 4, after C.

### Files / tables touched
- EDIT `apps/backend-rag/backend/services/olympus/rules_engine.py`: add `supersede()` (UPDATE writer + `olympus_actions` audit) and `propose_supersessions()` (read candidates → shadow proposal or enforce). Reuse existing pool pattern.
- EDIT `apps/backend-rag/backend/services/olympus/models.py`: no new field needed (`superseded_by` already present); optionally a `SupersessionProposal` view-model over `InsightRecord`.
- Reuses existing tables: `olympus_rules` (UPDATE `superseded_by`), `olympus_actions` (audit), `olympus_insights` (shadow proposals). **No migration.**
- Caller: the existing weekly Reflexion/synthesis entry point (where `dream`/rule-extraction already runs) invokes `propose_supersessions()`.

### How it is tested (TDD)
- `apps/backend-rag/tests/services/olympus/test_rules_engine.py` (extend):
  - two contradictory same-category rules → `propose_supersessions(mode=enforce)` sets the older/lower-confidence one's `superseded_by` to the newer id; an `olympus_actions` audit row is written; `load_rules` no longer returns the superseded rule.
  - shadow mode → writes an `olympus_insights` recommendation, **does not** mutate `olympus_rules`.
  - base rule never auto-superseded (assert UPDATE skipped for `source="base"`).
  - confidence-decay path: rule at conf 0.1 + newer covering rule → proposal generated.
- Regression: existing `load_rules`/`record_applied`/`lower_confidence` tests stay green.

### Risk / rollback
- Risk: **medium** — the only pillar that mutates the live rule store. Mitigated by (a) shadow mode default, (b) base-rule immunity, (c) full `olympus_actions` audit, (d) `superseded_by` is itself the rollback handle.
- Rollback: `UPDATE olympus_rules SET superseded_by = NULL WHERE superseded_by IS NOT NULL` restores every superseded rule instantly (the read filter immediately re-includes them). No data lost — supersession is non-destructive by construction.
- Kill switch: `OLYMPUS_RULE_SUPERSEDE_MODE=off` disables both proposal and enforcement.

---

## 6. Why this is one verb, not four features (restated for the reviewer)

If you ship only A you get a clearer voice that may still be lying (C unfixed). If you ship only C you get sound judgments nobody can read (A unfixed). If you ship only D you escalate whatever the (possibly broken) judge produced. If you ship only B you mutate live rules on the strength of a confidence signal that can be a parser artifact. They interlock because they are the **same faculty pointed at four surfaces**:

```
                 ┌─────────────────────────────────────────────┐
                 │  FOURTH VERB: distrust-then-correct the self │
                 └─────────────────────────────────────────────┘
   C (judge output) ─┬─► A (sensor readout) ─┬─► D (suppressed alarm) 
                     │                        │
                     └────────► B (own rules) ┘
   "is my LLM         "is my red honest      "is my silence       "is my old rule
    answer real?"      and legible?"          hiding a truth?"     still right?"
```

C is the root because every other surface consumes a judgment. A makes the self legible. D makes the self's *silence* legible. B makes the self's *history* correctable. Together they are the organism acquiring **Experience** in the operator's sense — not more pulses, but the capacity to *audit and amend its own three verbs*.

---

## 7. Delivery checklist (scalpel discipline)

- [ ] **C** — `robust_parse.py` + reasoner repoint + `complete_json_async`; tests green; `CELL_REASONER_ROBUST` kill switch. *(ship first, hardest dependency)*
- [ ] **A** — `red_summary.py` + 3 wiring points; tests green. *(ship second, operator-visible win)*
- [ ] **D** — `suppression_digest.py` + suppressed-write + hourly hook + digest cooldown; tests green; `CELL_SUPPRESSION_DIGEST_ENABLED` kill switch. *(ship third)*
- [ ] **B** — `supersede()` + `propose_supersessions()` shadow-mode; tests green; `OLYMPUS_RULE_SUPERSEDE_MODE` gate; base-rule immunity. *(ship last, behind shadow flag)*
- [ ] Family commit message theme: `feat(organism): fourth verb — distrust-then-correct the self (A/B/C/D)`.
- [ ] **Re-verify the live counters** (13 rules / 0 superseded / 740 applications / 20,504 actions / pulse #5788) against the object store before quoting them in the PR body — tonight's Postgres MCP read failed (`-32603`) in this worktree, so those figures are operator-stated, not re-derived here (anti-hallucination discipline).

---

## 8. Explicit non-goals / boundaries

- **No** evoskill / agent-library edits (concurrent session owns that surface). Pillar C's empty-judgment fix is *parallel* to the evoskill scorer bug — same disease, separate patient; do not cross-edit.
- **No** Anthropic SDK / `ANTHROPIC_API_KEY` anywhere (project hard rule). LLM judgment uses DeepSeek V4 Pro API (`json_object`, never `json_schema`) and local Ollama only.
- **No** new daemon or LaunchAgent — every pillar rides the existing pulse loop or the existing Reflexion/weekly hook (avoids the W62/W61/P0-3 orphan-automation family).
- **No** change to the `worst`-of-sensors aggregation (Pillar A is readout-only) and **no** loosening of the `alert_human` brakes (Pillar D adds a second channel, it does not raise the cap).
- Every pillar reversible via a single env flag or a single SQL `UPDATE … = NULL`; no destructive migration.
