# PR-D1 — Gap scanner Layer B resilience (2026-04-30)

Phase D (self-learning chains) of the Pro automations renaissance.
First PR of the D-series — sblocca self-learning chain #1
(Layer A → Layer B → Remediate).

## Audit reformulation

The 2026-04-29 audit said:

> BROKEN. Cron-runner.sh now exports correct PATH (fixed 2026-04-19
> 21:40 per file mtime), so future runs MAY work. But Sunday 04-26
> produced no log file at all — chain did not close last week. Layer
> B last successfully classified 2026-04-19 (and it claimed every
> topic was 100% gap because nlm CLI was not in PATH).

**Live verification on 2026-04-30 02:30 WITA contradicts that:**

A manual `--layer-b` run kicked off at 02:30 WITA showed:

```
02:30:45 [GapScanner] Starting --layer-b
02:30:45 [GapScanner] Layer B — coverage matrix for immigration (8 topics)
02:36:12 [GapScanner] Query timeout for notebook cff93ab0-...
02:39:21 [GapScanner]   immigration: 62% fresh, 12% gap
02:39:21 [GapScanner] Layer B — coverage matrix for company (8 topics)
02:48:09 [GapScanner]   company: 100% fresh, 0% gap
02:48:09 [GapScanner] Layer B — coverage matrix for tax (8 topics)
02:56:05 [GapScanner] Query timeout for notebook d4b2eedb-...
02:57:06 [GapScanner]   tax: 75% fresh, 12% gap
03:03:31 [GapScanner]   property: 75% fresh, 0% gap
03:13:19 [GapScanner]   operations: 38% fresh, 25% gap
...
```

So the actual root causes are **different**:

1. **NLM bridge is slow under load.** Query timeouts (~90s) fire on the
   largest notebooks. 8 queries × 7 domains × ~30s avg = ~28 min for the
   full Layer B run, but the slowest notebooks push individual queries past
   the 90s ceiling.
2. **Per-topic logging is missing.** The current code only logs once
   per domain (`X% fresh, Y% gap`). If the cron run gets killed mid-domain
   (sleep, system crash, OOM, etc.), the log shows nothing about what was
   in flight — making post-mortem impossible.
3. **Crontab comment lies about timezone.** The cron line
   `0 19 * * 0 ...layer-b` uses a comment that says "Sun 19:00 UTC =
   Mon 03:00 WITA", but cron uses the system local timezone (WITA), so
   `0 19 * * 0` actually fires at **19:00 WITA Sunday = 11:00 UTC Sunday**.
   This is purely cosmetic but caused confusion when reading the audit.
4. **`run_gap_scanner.sh` only sources `~/.zshrc.secrets`** (legacy path),
   not `~/.nuzantara-secrets.env` (canonical, introduced in PR-C3). So
   Telegram alerts depend on the legacy file being present and current.

## Fixes

### 1. Per-query timeout 90s → 180s (`gap_scanner.py:46-47`)

```python
NLM_QUERY_TIMEOUT = 120
LAYER_B_QUERY_TIMEOUT = 180  # PR-D1: NLM bridge slow under load — was 90s
```

The `--layer-b` flow now uses `LAYER_B_QUERY_TIMEOUT` instead of the
hardcoded `90`. Larger notebooks (immigration, tax, operations,
editorial) routinely hit 90s+ on freshness queries; 180s gives 2× safety
margin without making individual failures take much longer.

### 2. Per-topic progress logging (`gap_scanner.py:450-470`)

```python
for topic_idx, topic in enumerate(topics, 1):
    ...
    logger.info(
        "  [%s %d/%d] %s — %s",
        domain, topic_idx, len(topics), topic[:60], classification,
    )
```

Promoted from `logger.debug` to `logger.info` and added topic position
(`3/8`) + truncated topic title + classification. A killed run now leaves
a breadcrumb at the exact topic where it died.

### 3. Source canonical secrets (`run_gap_scanner.sh:33-42`)

Added a second secrets-source block that reads
`~/.nuzantara-secrets.env` (canonical, PR-C3 baseline) on top of the
existing legacy `.zshrc.secrets`. Both are guarded with `if [ -f ]` so
dev environments without either file still work. Also makes the cron
firing `_send_telegram` succeed even if `.zshrc.secrets` is removed
later.

## Out of scope (deliberately deferred)

- **Crontab comment fix** (cosmetic). The comment says "Sun 19:00 UTC"
  but cron uses WITA. Fixable on Pro via `crontab -e`, but not in
  repo. Tracked as TODO.
- **Sunday 26/04 missing run forensic.** The 26/04 log file has only
  Layer A; Layer B/Remediate left no trace. Possible causes: cron
  daemon sleep, PID lock orphan, stdout silently lost. Not actionable
  without more data.
- **Remediate bug** (`No such file or directory: 'nlm'`). The audit
  observed this on 2026-04-19 but the fix to cron-runner.sh on the same
  day's 21:40 should have fixed it. Will re-validate next Sunday after
  Layer B completes — if Remediate still errors, it's a separate bug
  (possibly a different subprocess shell context).
- **Eliminate timeouts via batching** (proper architectural fix). The
  bottleneck is one NLM query per topic. A batched API would cut the
  full run from ~30 min to ~3 min. Out of scope here — needs an
  upstream NLM bridge change.

## Verification

Live `--layer-b` test launched 2026-04-30 02:30 WITA — runs ~25-30 min,
Telegram digest expected at end. Per-topic logging will show in the
next firing (Sunday 19:00 WITA = next 2026-05-04, or via manual
`run_gap_scanner.sh --layer-b`).

## Test plan

- [x] py_compile gap_scanner.py
- [x] bash -n run_gap_scanner.sh
- [x] Live `--layer-b` running (started 02:30 WITA on 2026-04-30) —
      confirms the audit's "100% gap because nlm not in PATH" narrative
      is **stale** — Layer B is producing real classifications
- [ ] (Post-merge, next Sunday firing) Logs in `~/logs/cron-tmp/gap-scanner.log`
      should show `[domain X/8] topic — CLASSIFICATION` lines per query
- [ ] (Post-merge, next Sunday firing) Telegram digest delivered at
      end of `--layer-b` (already happens via `_send_telegram` line 520
      — this PR ensures it works regardless of `.zshrc.secrets`
      presence)

## Related

- Plan: `~/.claude/plans/RESUME-renaissance-2026-04-29.md` (PR-D1 row)
- Audit SSOT: `research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`
- Predecessors: PR #367 (C5), #368 (C3), #369 (C4), #371 (E1)
- Same secrets pattern: `scripts/genome_decay.sh`,
  `apps/evaluator/nlm_deep_research/scripts/run_heartbeat_check.sh` (PR-C3)
