# PR-C4 — API degraded fixes (2026-04-30)

Phase C of the Pro automations renaissance. Four `cron-agent-python`
scripts that the 2026-04-29 audit flagged as degraded by external API
failures or by dead/unused LLM calls. Applied via reproducible script
`scripts/ops/pr-c4-api-degraded-patch.sh` (idempotent, per-file backup,
in-place Python rewrite, `py_compile` validation).

Audit reference:
`research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`

## ⚠️ Architectural note

`/Users/nuzantara/scripts/cron-agent-python/` on Pro is **NOT in
git**. It is "shadow infrastructure" — 31 Python files, ~10k lines,
running production cron jobs since at least 2026-04-14, never
versioned. PR-C4 does not solve this; it documents the patches so
they can be re-applied if Pro is rebuilt, and so the next maintainer
can audit what was changed.

A proper fix is a separate future PR: promote
`cron-agent-python/` into the repo under `scripts/cron-agent-python/`,
with a CI guardrail that fails when Pro's working tree drifts from
HEAD. Out of scope here.

## Targets

### 1. `imigrasi_monitor.py` — drop `peraturan.go.id` source

**Before:** Source 3 (`peraturan.go.id/search?q=imigrasi`) returned
HTTP 500 every run for 10+ days. Sources 1
(`imigrasi.go.id/berita`) and 2
(`imigrasi.go.id/produk-hukum/peraturan-pemerintah`) cover the same
domain (immigration regulations) and work fine.

**Patch:** Remove the 7-line block that calls `_fetch_peraturan` and
the `random_delay` before it. The method definition stays in the file
(harmless dead code; can be deleted in a future cleanup), only the
call site is removed.

**Net:** one less hung HTTP roundtrip per daily run, no functional
loss.

### 2. `bi_exchange_rate.py` — drop BI native API tier

**Before:** 3-tier cascade: `_try_bi_api` (BI's `wskursbi.asmx`
JSON endpoint) → `_try_html_scrape` (HTML table parse) →
`_try_fallback_api` (`exchangerate-api.com`). The BI native API has
been broken since 2026-04-22 (every run logs
`bi_api_failed_fallback_html`). The HTML scrape via Playwright works
reliably.

**Patch:** Remove the BI-API-first cascade. HTML scrape is now
primary; `exchangerate-api.com` stays as last-resort fallback.

**Net:** ~10s saved per run (BI API timeout) + cleaner logs.

### 3. `compliance_ops.py` — drop unused `session_id`

**Before:** `get_or_create_session("compliance-ops", scope="daily")`
spawns `claude --print "Session start for compliance-ops daily ..."`
with `timeout=30` to obtain a session ID. The session ID is then
captured and saved via `save_session(...)` at end of run, but **never
used** anywhere in the code path — no `fork_from_session`, no
`claude --resume`. Pure dead code that costs ~30s per run.

CLAUDE.md §10 explicitly says _"compliance-ops: no LLM in main path
(deterministic per fedeltà) — touches money/clients/legal, sensitive
zone."_ So even the _intent_ of session-resume here is questionable.

**Patch:** Remove the `get_or_create_session` import, the
`session_id = get_or_create_session(...)` block at top of `run()`,
and the `save_session(...)` block at end of `run()`. Keep
`today = datetime.now(WITA).strftime("%Y-%m-%d")` because it's still
used for log scoping.

**Live verification (2026-04-30 02:01 WITA):** Manual `run.sh
compliance-ops` finished in ~2s (vs 30+s before patch). Telegram
delivery succeeded (`side_effect=compliance_summary`). No
`session_error` warning in log.

### 4. `daily_ops.py` — fix log false-positive

**Before:** `error=None if renewals else "failed"` flagged a legit
empty list `[]` as `error="failed"`. The endpoint
`/api/crm/practices/renewals/upcoming` actually works (HTTP 200 +
`X-API-Key` auth verified), it just returns `[]` most days.

**Patch:** Change to `error=None if renewals is not None else
"failed"`. Only an actual httpx error or non-200 response
(`backend_api` returns `None`) triggers the error path now.

Also: change `params={"days_ahead": 30}` → `params={"days": 30}`
to match the endpoint's actual query-param name (router signature is
`days: int = Query(...)`). FastAPI silently ignored the wrong name
before; this just makes the call honest.

**Net:** clean logs, correct param name, no behavior change (the
endpoint accepted both names due to FastAPI tolerating extra params).

## Live operation on Pro (2026-04-29 18:01 UTC = 2026-04-30 02:01 WITA)

```
[2026-04-29T18:01:26Z] === PATCH 1: imigrasi_monitor.py — drop peraturan.go.id source ===
[imigrasi_monitor.py] patched (11717 -> 11439 bytes)
py_compile OK
[2026-04-29T18:01:26Z] === PATCH 2: bi_exchange_rate.py — drop BI API tier ===
[bi_exchange_rate.py] patched (9871 -> 9778 bytes)
py_compile OK
[2026-04-29T18:01:26Z] === PATCH 3: compliance_ops.py — drop unused session_id ===
[compliance_ops.py] patched (10250 -> 9990 bytes)
py_compile OK
[2026-04-29T18:01:26Z] === PATCH 4: daily_ops.py — log false-positive ===
[daily_ops.py] patched (7262 -> 7268 bytes)
py_compile OK
```

Re-run: all 4 files reported `no-op (already patched)`.

Backups: `/Users/nuzantara/.cron-agent-python.backups/20260429T180126Z/`

## Rollback

```bash
ssh pro 'cp ~/.cron-agent-python.backups/20260429T180126Z/imigrasi_monitor.py.bak ~/scripts/cron-agent-python/imigrasi_monitor.py'
ssh pro 'cp ~/.cron-agent-python.backups/20260429T180126Z/bi_exchange_rate.py.bak ~/scripts/cron-agent-python/bi_exchange_rate.py'
ssh pro 'cp ~/.cron-agent-python.backups/20260429T180126Z/compliance_ops.py.bak ~/scripts/cron-agent-python/compliance_ops.py'
ssh pro 'cp ~/.cron-agent-python.backups/20260429T180126Z/daily_ops.py.bak ~/scripts/cron-agent-python/daily_ops.py'
```

Backups persist indefinitely (no shared state between patched files
and other crons).

## Test plan

- [x] Pre-flight: dry-run on local copies of all 4 files
- [x] py_compile all 4 patched files
- [x] Live apply on Pro
- [x] Verify idempotence (re-run = 4× no-op)
- [x] Live runtime test: `compliance-ops` finished in ~2s (vs 30s)
      with no session_error
- [ ] (Post-merge, next 24h) Watch logs: - `bi-exchange-rate.log` 07:00 WITA → no
      `bi_api_failed_fallback_html` - `imigrasi-monitor.log` 06:00 WITA → no `peraturan_fetch_error` - `compliance-ops.cron.log` 00:00/06:00/12:00/18:00 WITA → no
      session_error - `daily-ops.cron.log` 08:00 WITA → `fetch_renewals error=None`
      even when result is `[]`

## Related

- Plan: `~/.claude/plans/RESUME-renaissance-2026-04-29.md` (PR-C4 row)
- Audit SSOT:
  `research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`
- Predecessors: PR #367 (PR-C5), PR #368 (PR-C3)
- Future: promote `~/scripts/cron-agent-python/` to repo (separate PR)
