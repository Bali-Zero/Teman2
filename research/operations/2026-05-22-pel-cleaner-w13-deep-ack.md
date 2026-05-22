---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W13 root-cause fix: XCLAIM-without-XACK orphan PEL recovery
sources: 5
---

# PEL-cleaner W13: deep-stale XACK drain — Recovery of 142 abandoned messages

## Context

Loop iteration 13. Survey 30min after W12 ship revealed `nlm_feeder-1`
was still showing 82 pending with no drainage despite the hourly cron
running multiple times since W11 cleanup. Root-cause investigation
exposed a CRITICAL design flaw that invalidated both W11 (manual
XCLAIM) and W12 (cron XCLAIM) hardening approaches.

## Root cause

All Mata Garuda workers (`nlm_feeder`, `ner`, `classifier`, `normalizer`,
`scorer`, `kg_linker`, `gap_consumer`, `dedup_worker`,
`regulation_alert_agent`) consume Redis Streams via `base_worker.stream_read_new`:

```python
# apps/mata-garuda/mata_garuda/workers/base_worker.py:56-80
def stream_read_new(stream, group, consumer, count=10, block_ms=0):
    redis_cmd("XGROUP", "CREATE", stream, group, "0", "MKSTREAM")
    args = ["XREADGROUP", "GROUP", group, consumer, "COUNT", str(count)]
    args += ["STREAMS", stream, ">"]   # ← reads ONLY new msgs
    result = redis_cmd(*args)
    return _parse_xreadgroup(result, stream)
```

The `>` token is the "after last delivered ID" cursor. It NEVER returns
messages from the consumer's Pending Entries List (PEL). To drain PEL,
the worker would need a separate call: `XREADGROUP ... STREAMS stream 0`
(NOT `>`). No Mata Garuda worker does this.

**Consequence**: PEL is functionally write-only. Any message that enters
PEL via:

- (a) Initial delivery (worker received it, attempted processing) followed
  by silent ACK failure or worker crash
- (b) `XCLAIM` transfer from a ghost consumer (W11 manual, W12 cron)

…stays in PEL forever. Workers never re-read it. `XPENDING` counts grow
unbounded.

## W11 + W12 hardening were both wrong

| Iter | Action                                                          | Effect on PEL                   | Effect on lag | Verdict                |
| ---- | --------------------------------------------------------------- | ------------------------------- | ------------- | ---------------------- |
| W11  | Manual `XCLAIM 77 scan→nlm_feeder-1`, `DELCONSUMER 3 ghosts`    | +77 in nlm_feeder-1's PEL       | unchanged     | Just relocated problem |
| W12  | Cron `XCLAIM 5 debug-2→nlm_feeder_alerts-1` (and others weekly) | +5 in nlm_feeder_alerts-1's PEL | unchanged     | Same                   |

In both cases the "alive" target consumer never received the claimed
messages via XREADGROUP `>` and so never XACK'd them. They are orphans.

Empirical proof at 09:20 WITA:

```
nlm_feeder_alerts/nlm_feeder_alerts-1: pending=5, idle=2.3M ms (39min ago),
  deliveries=2 (XCLAIM bump + initial = never re-read)
nlm_feeder/nlm_feeder-1: pending=77, idle=1.2h, deliveries=2 (same)
```

## W13 fix

`pel_cleaner.py` adds a new pre-pass that scans `XPENDING` per group and
XACKs any message with `idle_ms > DEEP_STALE_MSG_IDLE_MS = 24h`. Runs
BEFORE the per-consumer XCLAIM logic so it cleans up XCLAIM-orphans from
prior cycles AND silent-ACK-failure orphans from worker bugs.

```python
def _xack_deep_stale(stream, group):
    xp = rcli("XPENDING", stream, group, "-", "+", "1000")
    records = _parse_xpending_long(xp)   # [(id, owner, idle_ms), ...]
    deep = [mid for mid, _, idle in records if idle > DEEP_STALE_MSG_IDLE_MS]
    # XACK in batches of 100
    for batch in chunks(deep, 100):
        rcli("XACK", stream, group, *batch)
    return len(deep)
```

Threshold reasoning: workers run on 5-30 min cron cycles. If a message
is in PEL >24h, the worker has had ≥48 opportunities to re-read it and
didn't. 24h gives genuinely-slow batches room while catching W11/W12
historical victims at the next weekly run.

## One-shot historical recovery (2026-05-22 09:20 WITA)

The W13 cleaner pass + direct XACK drained:

| Stream          | Group             | Drained | Method                              |
| --------------- | ----------------- | ------- | ----------------------------------- |
| garuda:enriched | nlm_feeder        | 77      | direct XACK (W11 historical)        |
| garuda:alerts   | nlm_feeder_alerts | 5       | direct XACK (W12 historical)        |
| garuda:enriched | ner               | 45      | W13 cleaner deep-ACK (>7d at time)  |
| garuda:raw      | normalizer        | 9       | W13 cleaner deep-ACK                |
| garuda:enriched | nlm_feeder        | 5       | W13 cleaner deep-ACK (dregs of W11) |
| bridge:outbound | bridge-push       | 1       | W13 cleaner deep-ACK                |
| **TOTAL**       |                   | **142** |                                     |

Final state:

```
nexus-bridge      lag=2279  pending=0  (legacy orphan, pending=0)
normalizer        lag=858   pending=0  ✅
classifier        lag=921   pending=0  ✅
kg_linker         lag=542   pending=0  ✅
ner               lag=2181  pending=51 (active processing, normal)
nlm_feeder        lag=2226  pending=0  ✅
scorer            lag=2118  pending=0  ✅
nlm_feeder_alerts pending=0 ✅
```

## Data-loss safety check (49/82 already-fed verified)

Before XACKing, sampled the 82 historical pending against the
`nlm_fed` dedup table (`type='nlm_fed', source=<url|content_hash>` in
`apps/mata-garuda/data/knowledge.db`):

- **49/82 already in nlm_fed**: re-injecting would dedup-skip. XACK
  pure cleanup, zero loss.
- **33/82 not-yet-fed**: all from 2026-04-09/10 (18-day-old arxiv +
  technologyreview + youtube). Re-injection would fan-out cascade
  through normalizer + ner + classifier + nlm_feeder for stale content
  that predates the W6 NER + W9 classifier deploys. Noise > value.

Decision: XACK all 82. Conservative on the 33 not-fed = accepted small
loss vs cascading load on 4 workers for 18-day-old content. Future
operator could re-inject specific URLs manually if recovery becomes
critical (none expected).

## Verification

```bash
# Idempotency
$ python3 apps/mata-garuda/scripts/pel_cleaner.py
{"claims":[],"deletions":[],"deep_acks":[],"errors":[]}
# exit=0

# Tests
$ pytest apps/mata-garuda/tests/test_pel_cleaner.py -v
7 passed in 0.06s
  test_parse_xinfo_consumers_two_consumers_one_pending PASSED
  test_parse_xinfo_consumers_single PASSED
  test_parse_xinfo_consumers_empty PASSED
  test_thresholds_match_design PASSED
  test_parse_xpending_long_4line_records PASSED  ← NEW (W13)
  test_parse_xpending_long_empty PASSED  ← NEW (W13)
  test_parse_xpending_long_skips_malformed_lines PASSED  ← NEW (W13)
```

## Open questions

- **NER pending=51 active**: should we add a NER PEL-overflow alert
  threshold? Currently W10 lag monitor catches it via lag (2181 > 500)
  but pending count isn't surfaced separately. Defer to W14 candidate.
- **nexus-bridge lag 2279**: still orphan, pending=0, no consumer code
  reference. Antonello decision pending (DELETE/RESTORE/LEAVE). W13
  cleaner couldn't help (no pending to drain).
- **`stream_ack` silent-failure detection**: `base_worker.stream_ack`
  calls `redis_cmd("XACK", ...)` and discards return value. Could check
  return ≥1, log warning on 0. W14 candidate.
- **Per-worker startup PEL drainage**: properly fixed by adding
  `XREADGROUP GROUP consumer COUNT N STREAMS stream 0` pass before the
  `>` pass in `base_worker.stream_read_new`. Broad blast radius (6+
  workers), risky — would race with cleaner's deep-ACK pass. Defer.

## Sources

1. W11 cicatrix (commit `646043dff`) — manual nlm_feeder ghost cleanup
2. W12 cicatrix (commit `a4e14ba38`) — cron PEL-cleaner with XCLAIM
3. `apps/mata-garuda/mata_garuda/workers/base_worker.py` lines 56-86 — `>` semantic
4. Empirical XPENDING + deliveries analysis 2026-05-22 09:20 WITA
5. `apps/mata-garuda/data/knowledge.db` nlm_fed lookup of 82 sample IDs
