---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W14 stream_ack silent-failure detection (W13 open question follow-up)
sources: 3
---

# stream_ack v2: surface XACK silent failures to operator logs

## Context

Loop iteration 14. W13 cicatrix (commit `e08aa4b74`) flagged as open
question: "`stream_ack` silent-failure detection — base_worker.stream_ack
calls redis_cmd('XACK', ...) and discards return value. Could check
return ≥1, log warning on 0. W14 candidate."

W13 investigation found 60 PEL-stuck messages across 4 groups from
silent `stream_ack` failures at unknown past points. Workers called
ack on every code branch — but Redis XACK can return 0 if the message
is no longer in PEL (already drained by cleaner, race, wrong id) —
and the original `stream_ack` ignored the return value, so operators
had no log signal when ACK silently no-op'd.

## Survey

W14 iter started by checking the lag dashboard + recent error logs
across all NB-cron sources. Findings:

| Source                                                | Status                                                           | W14?              |
| ----------------------------------------------------- | ---------------------------------------------------------------- | ----------------- |
| W11 nlm_feeder cron (drainage check)                  | pending=0 ✅ after W13 deep-ACK                                  | no                |
| Lag dashboard 6 groups                                | only ner=46 pending (active), others clean                       | no                |
| sentinel.hourly exit=1 (launchctl)                    | health=red → exit 1 by design (no_items condition)               | no — not a bug    |
| wr2-canva-renderer ERROR PG flycast                   | 749 gaierror/24h — known scar from 2026-05-19, resurrected plist | wr2-scope, not NB |
| matagaruda-sentinel.error.log timeouts                | 10 days old (May 12), stale                                      | no                |
| NB-INTEL-AIResearch source-add silent fail            | NB at 600 sources, Google rejects in 3s — separate finding       | defer to W15      |
| **W13 open: `stream_ack` swallowing silent failures** | confirmed in code                                                | **YES**           |

W14 candidate selected: **`base_worker.stream_ack` return-value
hardening** — directly addresses W13 cicatrix open question with
small surface area + high diagnostic value.

## Fix

**Before** (`base_worker.py:83-85`):

```python
def stream_ack(stream: str, group: str, msg_id: str) -> None:
    """Acknowledge a message in a consumer group."""
    redis_cmd("XACK", stream, group, msg_id)
```

**After** (W14):

```python
def stream_ack(stream: str, group: str, msg_id: str) -> bool:
    result = redis_cmd("XACK", stream, group, msg_id)
    if result.startswith("[ERROR]"):
        logger.warning("[stream_ack] redis-cli error acking %s/%s/%s: %s",
                       stream, group, msg_id, result)
        return False
    try:
        acked = int(result.strip())
    except ValueError:
        logger.warning("[stream_ack] unparseable XACK reply for %s/%s/%s: %r",
                       stream, group, msg_id, result)
        return False
    if acked == 0:
        logger.warning("[stream_ack] XACK returned 0 for %s/%s/%s — "
                       "msg not in PEL (already drained, wrong id, or race)",
                       stream, group, msg_id)
        return False
    return True
```

Three failure paths now produce WARNING logs (grep-able):

- `[stream_ack] redis-cli error` — connection / timeout / unknown
- `[stream_ack] unparseable XACK reply` — Redis protocol drift
- `[stream_ack] XACK returned 0` — silent no-op (most common in practice)

## Backward compatibility

All 10 existing callers use statement form (ignore return value):

```python
# normalizer.py, nlm_feeder.py, regulation_alert_agent.py, etc.
stream_ack(stream, consumer_group, msg_id)   # value discarded
```

Statement-form invocation works identically with `-> bool`. New
`test_stream_ack_callers_remain_backward_compatible` test locks
this property.

Wrapper-form callers (3 found: `contradiction_worker`, `dedup_worker`,
`embedder_worker`) wrap in lambda: `lambda s,g,m: stream_ack(s,g,m)`.
Lambda returns the wrapped function's value but the call site ignores
it — also backward-compat.

## Tests

`apps/mata-garuda/tests/test_base_worker_stream_ack.py` (5 tests):

| Test                                                     | Mock XACK reply                           | Expected        |
| -------------------------------------------------------- | ----------------------------------------- | --------------- |
| `test_stream_ack_success_returns_true`                   | `"1"`                                     | True, no log    |
| `test_stream_ack_silent_failure_returns_false_and_warns` | `"0"`                                     | False + WARNING |
| `test_stream_ack_redis_error_returns_false_and_warns`    | `"[ERROR] redis-cli: connection refused"` | False + WARNING |
| `test_stream_ack_unparseable_returns_false_and_warns`    | `"OK"`                                    | False + WARNING |
| `test_stream_ack_callers_remain_backward_compatible`     | both `"1"` and `"0"` in statement form    | no exception    |

**5/5 PASS** in 0.79s.

Full mata-garuda suite: 942 passed, 21 skipped, 2 failed where:

- `test_compat_shim.py::test_legacy_dict_byte_identical_to_pre_pr_snapshot` —
  known pre-existing NB UUID drift (referenced in W12 + W13 cicatrices)
- `test_kg_query.py::test_t11_concurrent_reads` — confirmed flaky/timing
  under load (PASSED in isolation). Not W14-caused.

Both unrelated to W14.

## Cross-tree gotcha (W9 lesson recurrence)

While editing, I used the absolute path `apps/mata-garuda/...` to Edit
the base_worker.py file — but the absolute path resolved to the MAIN
tree (not the worktree where tests run). Result: tests initially failed
4/5 with `None` returns because the worktree still had the `-> None`
version. Fixed by `cp` from main tree to worktree.

Lesson reinforced: when Edit'ing files in a worktree, always pass the
worktree-prefixed absolute path. Tools resolve relative + abs paths
the same way, and worktree vs main tree is invisible in the file path.

## Operator runbook impact

Future PEL stuck-orphan investigations:

```bash
# OLD: had to dive XPENDING across all groups to find what failed
$ for g in nlm_feeder ner classifier normalizer scorer kg_linker; do
    redis-cli XPENDING garuda:enriched $g - + 10
done

# NEW: grep the worker logs directly
$ grep "stream_ack" ~/logs/matagaruda-*.log
2026-05-22 10:15:32 WARNING [stream_ack] XACK returned 0 for garuda:enriched/nlm_feeder/1779413843-0 — msg not in PEL (already drained, wrong id, or race)
2026-05-22 10:16:01 WARNING [stream_ack] redis-cli error acking garuda:raw/normalizer/1779414001-0: [ERROR] redis-cli timeout after 10s
```

This catches the failure point in real-time, not via a post-mortem
audit. Race-with-cleaner cases ("already drained") are expected and
benign — the log message says so to set operator expectations.

## Open questions (deferred)

- **Per-worker startup PEL drainage** (W13 deferred): adding
  `XREADGROUP GROUP consumer COUNT N STREAMS stream 0` before the `>`
  pass in `base_worker.stream_read_new` would let workers recover their
  own PEL on restart. Broad blast radius (9 workers), races with
  cleaner's deep-ACK. Defer.
- **NLM-INTEL-AIResearch source cap**: 600/1000 cap reached, every
  `nlm source add` to that NB returns "Could not add url source" in 3s.
  Worker (`_nlm_add_url`) catches non-zero but logs `case_not_resolved`
  with no actionable context. W15 candidate: surface stderr in log +
  add per-NB source-count gate.
- **wr2-canva-renderer plist resurrection**: 749 gaierror/24h from
  another plist (`canva-renderer` + `canva-apply`), resurrected
  2026-05-21 23:38. Out of NB scope but pollutes Pro log directory.
  Defer to wr2-team or Antonello decision.
- **nexus-bridge legacy decision** (W11 deferred): unchanged.

## Sources

1. W13 cicatrix (commit `e08aa4b74`) — open question §4 of "Open questions"
2. `apps/mata-garuda/mata_garuda/workers/base_worker.py` lines 83-130 (W14 edit)
3. Empirical XACK behavior: Redis docs + experimental confirmation that
   XACK on already-drained msg returns 0 (not error)
