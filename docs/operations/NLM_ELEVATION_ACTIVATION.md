# NLM Elevation — Production Activation Runbook

**Date:** 2026-04-25
**Owner:** Antonello (solo-dev)
**Scope:** rollout the 6 PR shipped in Sprint 0/1/2 to production with measurable gates and rollback at every stage

> **Read first:** the design behind these PR is in `research/nlm-elevation/07-synthesis-plan-v2.md`. The diagnosis behind T16/S0.5 is in `research/nlm-elevation/08-s02-dispatcher-diagnosis.md`. **Do not** activate components in a different order — each stage relies on signals produced by the previous one.

## Overview

Six PR are pending merge:

| PR | Subject | Risk | Activation gate |
| --- | --- | --- | --- |
| #243 | Sprint 0 core fix (claim_extractor + bridge timeout + docs Fed A2A + research artifacts) | Low | Merge → next NB-2 cron run produces a real log |
| #244 | truth_dashboard + S0.2 diagnosis + doc hygiene | Low | Merge → run `--truth` daily |
| #245 | T16 sentinel ARCH-9 preference + 7 wrapper record + S1.2 verify_ingestion canary | Medium | Merge → next sentinel tick reads ARCH-9 |
| #246 | S1.3 oracle stale gate (resolve_notebook) | Off-by-default | Merge with flag OFF — no behavior change |
| #247 | Sprint 2 Shadow Graphing (collection + chunk schema + extractor) | Off-by-default | Merge — extractor only runs when invoked |
| (next) | Wire-up retrieval `nlm_shadow_hybrid` (this branch) | Off-by-default | Merge with `NLM_SHADOW_RETRIEVAL_ENABLED` unset |

All activation flags default to **OFF**. Every flag flip is a separate intentional action with its own rollback.

---

## Stage 1 — Baseline (immediately after merge)

**Goal:** prove that no behavior changed.

### Actions
1. Merge PR #243, #244, #245, #246, #247 in any order.
2. After CI green, deploy backend-rag without setting any new env var.
3. Run on Pro Mac:
   ```bash
   PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --truth
   ```
   Confirm output now classifies pipelines (some `GATEWAY_LIES`, some `OK`) and the table prints correctly.
4. Verify the next NB-2 cron at 02:10 WITA produces a real log in `apps/evaluator/nlm_deep_research/logs/nb2_pipeline_YYYYMMDD.log` and a fresh `heartbeat_nb2_pipeline.json` in `~/.agent/decisions/state/`.

### Success
- `heartbeat_monitor --truth` runs in <2s and produces 18 rows.
- NB-2 log file exists and shows `[DONE]` line.
- `pytest backend/tests/services/oracle/test_nlm_orchestrator.py -q` → 30/30 PASS (no regression).

### Rollback
Revert merge of any PR; everything is feature-flag gated so no production traffic is at risk.

---

## Stage 2 — Heartbeat truth (after 24h baseline observation)

**Goal:** the sentinel starts trusting ARCH-9 over the gateway projection so monitoring stops lying.

### Pre-requisite
Stage 1 stable for 24h: `heartbeat_monitor --truth` shows ≥1 NB pipeline with `verdict=OK` (not just GATEWAY_LIES).

### Actions
1. The T16 fix in PR #245 is automatic on merge — no flag flip needed.
2. After 24h, verify on Pro Mac:
   ```bash
   python3 -c "
   import importlib.util, sys, json
   p = '/Users/nuzantara/Desktop/nuzantara/scripts/nuzantara-sentinel.py'
   spec = importlib.util.spec_from_file_location('s', p)
   m = importlib.util.module_from_spec(spec); sys.modules['s'] = m
   spec.loader.exec_module(m)
   reg = {'nlm_nb2_pipeline': {'type': 'openclaw'}}
   states = m.collect_state_files(registry=reg)
   for jid, s in states.items():
       print(jid, s.get('_source'), s.get('ts'))
   "
   ```
   Expect to see `_source=arch9_heartbeat` for at least the pipelines that have run successfully.

### Success
- At least 5/9 NB pipelines emit `_source=arch9_heartbeat` within 48h.
- Telegram daily digest from `heartbeat_monitor --digest` reflects real success/fail (no more all-green-because-mtime).

### Rollback
The fix is in scope of `collect_state_files()` — revert PR #245 only and the gateway projection becomes the source of truth again.

---

## Stage 3 — Canary verification (after Stage 2 stable 48h)

**Goal:** establish a daily ground truth on every NB by running ingestion canaries.

### Pre-requisite
Stage 2 stable 48h. NB-2..NB-10 producing real heartbeats.

### Actions
1. Add to user crontab on Pro:
   ```cron
   # Sprint 1 S1.2 — daily ingestion canary on each NB-2..NB-8 + NB-10
   30 4 * * 1-6 /bin/bash /Users/nuzantara/scripts/cron-runner.sh /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/scripts/run_canary_all.sh >> /tmp/cron-canary.log 2>&1
   ```
   The wrapper `run_canary_all.sh` does NOT exist yet — create it as part of activation:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   cd "$HOME/Desktop/nuzantara"
   source apps/backend-rag/.venv/bin/activate
   for NB_ID in cff93ab0-813a-42f2-a8de-36987e724271 \
                933509f9-1561-403d-bd44-4a7a67a36df2 \
                d4b2eedb-9863-4a1a-81ff-a11b0b45d853 \
                d9438180-5e63-4e2a-a473-6061101f6a8d \
                85207af3-352f-4554-8d2a-18f42cc541ba ; do
       PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.freshness_monitor \
           --verify-ingestion "$NB_ID" || true
       sleep 30
   done
   ```
2. Wait for the cron to run for 24h. Inspect:
   ```bash
   python3 -c "
   import json
   d = json.load(open('apps/evaluator/nlm_deep_research/freshness_monitor_state.json'))
   for nb, e in d.get('ingestion_verifications', {}).items():
       last = e['last']
       print(nb[:8], last['status'], last.get('age_seconds'), last.get('error') or '')
   "
   ```
   Expect 5/5 NB with status=ok.

### Success
- 5/5 NB report `status=ok` for 3 consecutive cron runs.
- `freshness_monitor_state.json` grows the rolling history.

### Rollback
- Comment out the cron line.
- The state file remains; nothing else depends on it yet.

---

## Stage 4 — Oracle stale gate (after Stage 3 stable 7 days)

**Goal:** the production RAG starts refusing queries on stale notebooks. Cliente UX becomes self-healing.

### Pre-requisite
Stage 3 stable 7 days. ALL 5 NB have ≥7 consecutive `status=ok` canaries.

### Actions
1. **First in staging if available**, else directly on prod with low traffic window (Sun 02:00 WITA):
   ```bash
   # Mount the freshness state file into the Fly container
   fly secrets set NLM_FRESHNESS_STATE_FILE=/path/inside/container -a nuzantara-rag
   # The file must be accessible to the container — easiest: bind via Tigris
   #   bucket sync, or copy into the container at deploy time.

   # Enable the gate
   fly secrets set NLM_ENFORCE_FRESHNESS=1 -a nuzantara-rag
   ```
2. Watch backend logs for 1h:
   ```bash
   fly logs -a nuzantara-rag | grep "NLM oracle gate"
   ```
   Expect: zero "refusing" lines (everything fresh) OR explicit refusals on NB that are actually stale.
3. Run a manual query that should hit NB-2:
   ```bash
   curl -s "https://nuzantara-rag.fly.dev/api/rag/query?q=KITAS+E23+duration"
   ```
   Verify a sensible answer is returned with NLM citations (or fallback to Qdrant pure if NB stale).

### Success
- 0 unintended fallback-to-Qdrant in 24h.
- Hit rate from CEP (Stage 5) improves OR remains stable when the gate is enabled.

### Rollback
```bash
fly secrets unset NLM_ENFORCE_FRESHNESS -a nuzantara-rag
fly deploy -a nuzantara-rag --strategy rolling
```
Behavior reverts to legacy (no gate).

---

## Stage 5 — CEP baseline (parallel with Stage 4)

**Goal:** measure RAG quality before activating Shadow Graphing, so we can detect drift later.

### Actions
1. Add cron on Pro:
   ```cron
   # Sprint 2 CEP — daily evaluation 06:00 WITA
   0 6 * * * /bin/bash /Users/nuzantara/scripts/cron-runner.sh /Users/nuzantara/Desktop/nuzantara/apps/evaluator/cep/run_cep_daily.sh >> /tmp/cron-cep.log 2>&1
   ```
   Wrapper `run_cep_daily.sh` (create):
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   cd "$HOME/Desktop/nuzantara"
   source apps/backend-rag/.venv/bin/activate
   # Pre-collect answers from production RAG endpoint
   python apps/evaluator/cep/collect_answers.py \
       --golden apps/evaluator/cep/golden_v20260425.json \
       --endpoint "https://nuzantara-rag.fly.dev" \
       --out /tmp/cep-answers-$(date +%F).json
   # Run grader
   PYTHONPATH=. python -m apps.evaluator.cep.run_cep \
       --answers-file /tmp/cep-answers-$(date +%F).json \
       --report /tmp/cep-report-$(date +%F).csv
   ```
2. After 7 days, compute baseline hit rate (target ≥ 80%).

### Success
- Baseline hit rate ≥80% measured for 7 consecutive days.
- Per-domain hit rate ≥75% on each domain (immigration, company, tax, property, operations).

### Rollback
- Cron job removal only — nothing in production depends on CEP output yet (it observes, does not act).

---

## Stage 6 — Shadow Graphing extraction (after Stage 5 baseline established)

**Goal:** populate `nlm_shadow_hybrid` Qdrant collection. Still nobody reads from it.

### Actions
1. Set required env vars:
   ```bash
   # On Pro (where the cron runs)
   export DEEPSEEK_API_KEY="..."  # already in ~/.ai_keys.env
   export OPENAI_API_KEY="..."    # already in ~/.nuzantara-secrets.env
   export QDRANT_URL="https://nuzantara-qdrant.fly.dev"
   export QDRANT_API_KEY="..."    # if cloud Qdrant
   ```
2. First manual run on one domain:
   ```bash
   PYTHONPATH=. python scripts/nlm_shadow_extractor.py --notebook tax --limit 10
   ```
   Verify Qdrant collection `nlm_shadow_hybrid` was created with ≥1 valid claim.
3. Schedule cron:
   ```cron
   # Sprint 2 Shadow Graphing — nightly 03:30 WITA after NB pipelines complete
   30 3 * * 1-6 /bin/bash /Users/nuzantara/scripts/cron-runner.sh /Users/nuzantara/Desktop/nuzantara/scripts/nlm_shadow_run_all.sh >> /tmp/cron-shadow-extractor.log 2>&1
   ```
   Wrapper `nlm_shadow_run_all.sh`:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   cd "$HOME/Desktop/nuzantara"
   source apps/backend-rag/.venv/bin/activate
   PYTHONPATH=. python scripts/nlm_shadow_extractor.py --all-domains --limit 25
   ```
4. After 7 days, verify Qdrant collection has 100-500 claims with `deepseek_validated=true` and varied `nb_label`.

### Success
- ≥500 valid claims in `nlm_shadow_hybrid` after 7 days.
- DeepSeek cost <$30 in those 7 days (50 claims × 5 NB × $0.01 × 7 = ~$17 expected).

### Rollback
- Comment out cron.
- Optional: `qdrant-cli delete nlm_shadow_hybrid` (no consumer reads from it before Stage 7).

---

## Stage 7 — Shadow retrieval activation (gradual)

**Goal:** the agentic orchestrator starts reading shadow claims as cheap context.

### Pre-requisite
- Stage 6 produced ≥500 claims for 7 days.
- Stage 5 CEP hit rate ≥85% (so we have a baseline to detect regressions).

### Actions
1. **Canary**: enable for 5% of traffic via feature flag (if your platform supports it). If not, stage on Air (lower-traffic mirror) first.
2. Set env on backend:
   ```bash
   fly secrets set NLM_SHADOW_RETRIEVAL_ENABLED=1 -a nuzantara-rag
   fly deploy -a nuzantara-rag --strategy rolling
   ```
3. Monitor for 24h:
   - CEP hit rate must not drop more than 2 percentage points.
   - Backend p95 latency must not regress (shadow retrieval adds <50ms).
   - Logs grep for `nlm_shadow search failed` — Qdrant errors flag here.

### Success
- 24h post-activation: CEP hit rate ≥ baseline − 2pp.
- p95 latency stable.
- ≥10% of queries now include at least one shadow claim in their context.

### Rollback
```bash
fly secrets unset NLM_SHADOW_RETRIEVAL_ENABLED -a nuzantara-rag
fly deploy -a nuzantara-rag --strategy rolling
```
The orchestrator immediately stops reading from `nlm_shadow_hybrid`. The collection itself remains; no data loss.

---

## Failure modes & runbook responses

### Symptom: `truth_dashboard` shows GATEWAY_LIES on a pipeline that actually ran today
- Cause: the wrapper for that NB doesn't call `heartbeat_monitor --record nbN_pipeline`.
- Fix: confirm the wrapper has the call (PR #245 added it for nb3..nb10; nb2 already had it). If still missing, patch the wrapper.

### Symptom: `verify_ingestion` reports `error: source add failed` for one NB
- Cause: the NB UUID in the cron wrapper is wrong, or the user's NLM session expired.
- Fix: `nlm notebook list` to confirm UUID, `nlm login` to refresh.

### Symptom: oracle gate refusing all NB-2 queries while users complain
- Cause: the canary cron failed but the env var is still on.
- Immediate: `fly secrets unset NLM_ENFORCE_FRESHNESS -a nuzantara-rag`.
- Diagnose: check `freshness_monitor_state.json` — `last.status` of NB-2 should be `ok`. If `error` or `stale`, fix the canary first, then re-enable.

### Symptom: Shadow extractor produces 0 valid claims on every run
- Cause: NLM extraction returns empty list (notebook has no source for the prompt subject) or DeepSeek rejects all.
- Fix: lower `--limit`, check `_parse_json_list` output by running with `--limit 5` manually, inspect DeepSeek `notes` field in payloads via Qdrant inspector.

### Symptom: CEP hit rate drops >5pp post Shadow retrieval activation
- Cause: shadow claims are misleading retrieval (low precision content polluting context).
- Immediate: `fly secrets unset NLM_SHADOW_RETRIEVAL_ENABLED -a nuzantara-rag`.
- Diagnose: increase `min_confidence` from 0.6 → 0.75 in the orchestrator caller; or filter `nb_label` strictly.

---

## Decisions register

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-25 | All activation gates default OFF | The 6 PR are merged together so no rollback is needed if a single one is unfit; activation is a separate intentional act. |
| 2026-04-25 | Canary cron daily, not bi-daily | Daily gives 7 data points/week which is enough for a credible Stage 4 gate; bi-daily would 2x the cost without enabling earlier rollout. |
| 2026-04-25 | CEP hit rate baseline 80% | Below this, the RAG is not reliable enough to gate user queries on freshness — fallback Qdrant might be better. Once baseline proven, raise to 85% before enabling shadow retrieval. |
| 2026-04-25 | Stage 7 not staged on real prod first | We have no Air mirror with prod traffic; Pro is dev. Either accept a 5% canary on prod or accept a 24h risk window. |

## Stage 0 / pre-activation checklist

- [ ] PR #243 merged
- [ ] PR #244 merged
- [ ] PR #245 merged
- [ ] PR #246 merged
- [ ] PR #247 merged
- [ ] Wire-up retrieval PR merged
- [ ] All 56 regression tests still PASS in main
- [ ] `heartbeat_monitor --truth` works on Pro Mac

Once all checked, start at Stage 1.
