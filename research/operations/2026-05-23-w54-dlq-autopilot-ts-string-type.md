---
date: 2026-05-23
domain: operations
loop: NB-automations-hardening W54
status: shipped (commit 761edf656); empirical live — 9 escalated / 49 checked / 40 healthy (vs pre-W54 10/48/38 with dlq_autopilot crashing)
---

# W54 — `dlq_autopilot.last.json` ts as ISO-8601 string broke sentinel staleness arithmetic

## TL;DR

`dlq_autopilot.py:658` wrote state with `ts: "2026-05-23T11:55:24Z"` (ISO-8601 string) via
`time.strftime()`, while **all 48 sibling state files** use `ts: 1779537900` (float epoch).
Sentinel's `age = now - last_ts` arithmetic in `process_job` crashed with
`TypeError: unsupported operand type(s) for -: 'float' and 'str'` — dlq_autopilot job was
silently skipped from every sentinel cycle (lost monitoring). Fix: dlq_autopilot writes
float epoch (source fix) + sentinel defensively coerces with float()+ISO-8601 fallback
(defense-in-depth).

## Empirical evidence pre-W54

`~/.agent/decisions/state/dlq_autopilot.last.json`:

```json
{"job": "dlq_autopilot", "status": "ok", "detail": "processed=63 fixed=0 escalated=0", "ts": "2026-05-23T11:55:24Z", "_writer": "dlq_autopilot"}
```

48 sibling state files surveyed via:

```python
$ for f in ~/.agent/decisions/state/*.last.json; do
    python3 -c "import json; print(type(json.load(open('$f')).get('ts')).__name__)"
  done | sort | uniq -c
  48 int
   1 str    # ← only dlq_autopilot.last.json
```

Sentinel error log:
```
2026-05-23 19:27:17,755 ERROR Error processing dlq_autopilot: unsupported operand type(s) for -: 'float' and 'str'
2026-05-23 19:52:44,571 ERROR Error processing dlq_autopilot: unsupported operand type(s) for -: 'float' and 'str'
```

Two consecutive sentinel runs crashed at `dlq_autopilot` job — silently skipped (try/except
in main loop catches and logs, then continues). Job count was 48 instead of 49 in those runs.

## Root cause

`scripts/dlq_autopilot.py:653-660` writes its own sentinel state file:

```python
state_file = state_dir / "dlq_autopilot.last.json"
state_file.write_text(json.dumps({
    "job": "dlq_autopilot",
    "status": "ok",
    "detail": f"processed={len(queue)} fixed={fixed} escalated={escalated}",
    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),  # ← BUG: string
    "_writer": "dlq_autopilot",
}))
```

`time.strftime()` returns an ISO-8601 STRING. Other writers in the codebase use `time.time()`
(float epoch). The string was historically tolerable because sentinel didn't crash on it
visibly — it just emitted ERROR + skipped that job. With W53 (TERMINAL gate added), the gate
check fires AFTER the staleness arithmetic, so the crash silently bypassed the new gate too.

Date introduced: unknown (line predates the recent Phase 0-4 sentinel work, likely D1.5
"audit trail" feature). Code review at that PR would have caught the type inconsistency
against sibling state files.

## Fix shipped

### Source fix — `scripts/dlq_autopilot.py:653-672`:

```python
state_file.write_text(json.dumps({
    "job": "dlq_autopilot",
    "status": "ok",
    "detail": f"processed={len(queue)} fixed={fixed} escalated={escalated}",
    "ts": time.time(),  # W54: float epoch seconds (was strftime ISO-8601)
    "_writer": "dlq_autopilot",
}))
```

### Defense-in-depth — `scripts/nuzantara-sentinel.py:528-540` (in `process_job`):

```python
_raw_ts = state.get("ts", 0)
try:
    last_ts = float(_raw_ts) if _raw_ts not in (None, "") else 0.0
except (TypeError, ValueError):
    # ISO-8601 string from pre-W54 dlq_autopilot, etc. Try parse, else 0.
    try:
        import datetime as _dt
        last_ts = _dt.datetime.strptime(str(_raw_ts), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc).timestamp()
    except Exception:
        logger.warning(f"{job_id}: state ts has unparseable type/value {_raw_ts!r}, treating as never-run")
        last_ts = 0.0
```

Three layers of fallback: `float()` → `datetime.strptime("...Z")` → 0 (never-run). Each
emits visible logging on the last fallback so silent data loss is impossible.

## Empirical verification (live)

W54 sentinel manual run at 20:09 WITA:

| Metric | Pre-W54 (19:52) | Post-W54 (20:10) |
|---|---|---|
| `Sentinel done: N checked` | 48 | **49** ✓ |
| `M healthy` | 38 | **40** ✓ |
| `K escalated` | 10 | **9** ✓ |
| `Error processing dlq_autopilot` | YES | **NO** ✓ |

dlq_autopilot is now correctly evaluated by sentinel; its current status is `ok` (its last
successful run was 11:55 WITA + W54 fix not yet executed by dlq_autopilot itself, so the
file still has the stale string — but sentinel's defensive coercion now parses it correctly
via the ISO-8601 fallback path).

The file will be rewritten as float on next dlq_autopilot cron tick (every 30min,
StartInterval=1800).

## Side-discovery: separate W55+ candidate

Same W54 live run surfaced:

```
[ALERT-FAILED] HTTP Error 400: Bad Request
[ALERT-FAILED] HTTP Error 400: Bad Request
[ALERT-FAILED] HTTP Error 400: Bad Request
```

Sentinel's `send_alert()` is hitting Telegram with malformed payload — 400 from Bot API
usually means Markdown parse error or invalid chat_id. Not blocking sentinel runs (alerts
fail soft, sentinel continues), but escalations aren't reaching Telegram. Investigate next:
`sentinel_lib.alerter.send_alert()` retry/format logic.

## Lessons

- **State-file schema consistency matters even when sentinel error-handles**. The `try/except`
  in main loop caught the crash but the job was silently dropped from monitoring for an
  unknown duration. Silent data loss in observability tooling is worst-case.
- **Survey schema across siblings before writing**: a `for f in state/*.json; do python -c "type(...)..."` would have caught the type mismatch at PR time.
- **Defense-in-depth pays off**: source fix alone wouldn't have helped until dlq_autopilot
  ran once post-deploy (every 30min). Sentinel defensive coercion fixes the immediate
  monitoring blackout while waiting for the file rewrite.
- **Sentinel `try/except Exception as e: logger.error(...)` is too permissive**: it catches
  type errors that should be visible alerts. A narrower except clause (or post-loop
  aggregation of error count → alert) would surface this earlier. Deferred to W55+.
- **Family**: state-file schema consistency. Sister to W53 (Phase 0 half-ship of TERMINAL
  state). Both reveal "field added without consumer audit" anti-pattern.

## Reference

- Commit: `761edf656` — `fix(dlq_autopilot,sentinel): ts type consistency + defensive coercion`
- Files: `scripts/dlq_autopilot.py:653-672`, `scripts/nuzantara-sentinel.py:528-540`
- Bad state file (will self-heal at next dlq_autopilot run): `~/.agent/decisions/state/dlq_autopilot.last.json`
- W53 sibling: `research/operations/2026-05-23-w53-sentinel-dlq-terminal-gate.md`
- Pre-W54 error log: `~/logs/sentinel.log` 19:27, 19:52 ERROR lines
