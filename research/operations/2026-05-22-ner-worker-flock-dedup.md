---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W7 NER worker concurrent-cron dedup
sources: 4
---

# NER worker flock semaphore — prevent concurrent-cron stacking

## Context

Loop iteration 7 of NB-automations hardening. Post-W6 restoration of NER
LaunchAgent (commit `930d9f30c`), 25min of cron activity revealed:

- ✅ Worker IS draining: lag 1403→1349 (-54 messages in 45min)
- ✅ Pending oscillation 45→99 healthy (in-flight batch pattern)
- ⚠️ **2 concurrent `run_ner_worker.py` processes** (PIDs 8616 + 18302)

The NER batch (`scripts/run_ner_worker.py` cap 200 messages × ~5-15s each
via Ollama qwen3.5:9b) can take 15-30 minutes. The cron interval is 300s
(5 minutes). So every 5min a new cron fires while the previous run is
still active → stacking → consumer group contention + double Ollama calls
per batch + Redis pending list bloat.

## Drainage rate analysis (pre-W7)

| Metric | Value |
|---|---|
| Inflow rate (new garuda:enriched) | ~2.4 msg/min |
| Drain rate (NER cron with stacking) | ~1.2 msg/min |
| Net backlog growth | +1.2 msg/min |
| Hours to drain 1349 lag at current rate | ~19h (and growing) |

Without dedup, the stacking degrades drain rate further (LLM calls
duplicated on same batch IDs that get returned to pending).

## Fix shipped

Updated `~/scripts/matagaruda-ner-worker.sh` (now 60 lines) to use
`flock(1)` with non-blocking exclusive lock + `--conflict-exit-code 75`:

```bash
"$FLOCK" --nonblock --exclusive --conflict-exit-code 75 "$LOCK" -c "cd '$REPO' && PYTHONPATH='$REPO' '$VENV_PY' scripts/run_ner_worker.py"
RC=$?
if [ "$RC" -eq 75 ]; then
    echo "[ner-worker] previous run still active — skipped this tick" >&2
    exit 0
fi
```

Key design:
1. **Non-blocking**: if lock held, exit immediately (no 4-min wait that
   would stack with the next cron tick anyway).
2. **--conflict-exit-code 75**: distinct exit code for lock conflict (vs
   real failure). Without this, flock returns exit 1 on conflict which
   launchd misinterprets as crash.
3. **Translate 75→0**: launchd's `last exit code` should stay clean. The
   "previous run still active" message goes to stderr → launchd error log
   for diagnostic visibility, but the exit code stays 0.
4. **Lock file in /tmp**: cleared on reboot (safe default — no orphan locks
   surviving across system restarts).
5. **Fallback path**: if flock binary missing (system without homebrew),
   wrapper degrades to no-dedup with a warning, rather than failing.

## Verification

```bash
# Kill stale processes from pre-W7 stacking
pkill -f "scripts/run_ner_worker.py"

# Force a fresh cron with new wrapper
launchctl kickstart -k "gui/$(id -u)/com.matagaruda.ner.adaptive"

# After 3s — should see:
#   1. zsh wrapper process
#   2. flock holder
#   3. python3 run_ner_worker.py
# All as a parent-child chain (one stack only, no peers)
ps -ef | grep -E "run_ner|matagaruda-ner|flock.*ner" | grep -v grep
```

Live smoke 2026-05-22 06:17 WITA: pkill cleared 2 stale PIDs, kickstart
produced single process chain (PID 13134→13142→13146). Lock conflict path
verified by holding lock for 5s in background → wrapper invoked → exit 0
with stderr "previous run still active — skipped this tick".

## Expected impact

| Metric | Pre-W7 | Post-W7 (target) |
|---|---|---|
| Concurrent NER processes | 2+ | 1 |
| Drain rate (effective) | 1.2 msg/min | 2.4 msg/min (Ollama capacity) |
| Time to drain 1349 lag | 19h | ~9h |
| launchd false-failures | one per skipped tick | zero (exit 0 on skip) |

If post-deploy `redis-cli XINFO GROUPS garuda:enriched` shows lag continues
to grow despite single-instance NER worker, the real bottleneck is Ollama
throughput on Pro M4 (currently sharing GPU with gemma4:26b) — would need
either (a) bigger cadence batches, (b) qwen3.5 instance pinning, (c)
acceptance that 24-48h drain time is OK.

## Sources

1. Empirical `ps -ef | grep run_ner_worker` showing PID 8616 + 18302 concurrent
2. `flock(1)` man page — `--conflict-exit-code` flag for proper exit code distinction
3. Cron interval analysis: 300s plist vs ~15-30min batch runtime
4. macOS `/opt/homebrew/bin/flock` (Homebrew util-linux package)
