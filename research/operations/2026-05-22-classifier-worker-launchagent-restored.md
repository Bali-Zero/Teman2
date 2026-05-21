---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W9 classifier worker restored (mirror W6 NER)
sources: 4
---

# Classifier worker LaunchAgent restored — mirror W6 fix

## Context

Loop iteration 9 of NB-automations hardening. After W6+W7 restored the NER
worker, survey of remaining `XINFO GROUPS garuda:enriched` revealed
identical pattern for `classifier` consumer group:

| Metric | Value |
|---|---|
| Consumer name | `classifier-1` |
| Consumer idle | 2760607955 ms ≈ **32 days** |
| Pending | 0 |
| Lag | 1570 (growing — 1003→1408→1570 in 1.5h) |

Same root cause as W6: `classifier_worker.py` library exists (qwen3:8b
with keyword-fallback, see lines 130-147), but:
- no `run_classifier_worker.py` runner in `scripts/`
- no LaunchAgent in `~/Library/LaunchAgents/`
- consumer never re-bootstrapped after some prior cleanup

W4 → W5 → W6 cascade chain extended: classifier is the OTHER consumer
group on garuda:enriched (parallel to NER). Both are needed to keep
the stream from growing unbounded.

## Fix shipped

Mirror of W6 architecture, applied **with W7 lesson baked in from day 1**
(flock semaphore included in initial wrapper, not bolted on after
observing concurrent-cron stacking):

1. **Runner** `apps/mata-garuda/scripts/run_classifier_worker.py` (37
   lines). Drains in batches of 20 (qwen3:8b is faster than 9b NER:
   ~3-8s vs 5-15s/item), cap 10 batches = 200 items per invocation.
2. **Wrapper** `~/scripts/matagaruda-classifier-worker.sh` (50 lines,
   `set -e`, TCC-safe, includes W7 flock semaphore
   `--nonblock --conflict-exit-code 75` for concurrent-cron dedup).
3. **LaunchAgent** `~/Library/LaunchAgents/com.matagaruda.classifier.adaptive.plist`,
   `StartInterval=300` (5min). Bootstrapped via `launchctl bootstrap
   gui/$(id -u)`. State `not running, last exit = (never exited),
   run interval = 300s`.

## Empirical smoke 2026-05-22 07:18 WITA

```
{
  "run": {
    "processed": 200,
    "classified_llm": 25,
    "classified_fallback": 0
  }
}
```

200 items drained — 25 needed LLM classification (new items), 175 hit the
idempotency skip path (`data.get("classified") == "true"`, because NER
worker had already re-published them via its own pipeline). Lag dropped
1570→0 immediately.

Re-run a few seconds later: `processed: 200, llm: 0, fallback: 0` — all
items now show `classified=true`, confirming the idempotency contract
holds across both workers.

## Files installed (HOME, gitignored)

- `~/scripts/matagaruda-classifier-worker.sh` chmod 755
- `~/Library/LaunchAgents/com.matagaruda.classifier.adaptive.plist` chmod 644

Plus the runner script committed to the repo:
- `apps/mata-garuda/scripts/run_classifier_worker.py` chmod 755 (also
  synced to main tree at `~/Desktop/nuzantara/apps/mata-garuda/scripts/`
  so the current cron working-directory finds it before the worktree
  branch merges)

## Verification commands

```bash
# Lag drops to ~0 within 5min cycles
redis-cli XINFO GROUPS garuda:enriched | grep -A6 "^classifier$"

# Worker chain visible — one wrapper + one flock + one python
ps -ef | grep -E "matagaruda-classifier|run_classifier" | grep -v grep

# launchd health
launchctl print "gui/$(id -u)/com.matagaruda.classifier.adaptive" | grep -E "state|last exit|launched"

# Stdout shows JSON heartbeat with processed/classified counts
tail -10 ~/logs/matagaruda-classifier-worker.log
```

## Sources

1. `mata_garuda/workers/classifier_worker.py` — library (qwen3:8b + keyword fallback)
2. `~/scripts/matagaruda-ner-worker.sh` — W6+W7 pattern reference
3. `~/Library/LaunchAgents/com.matagaruda.ner.adaptive.plist` — W6 plist pattern
4. Empirical XINFO CONSUMERS garuda:enriched classifier output 2026-05-22 07:15 WITA
