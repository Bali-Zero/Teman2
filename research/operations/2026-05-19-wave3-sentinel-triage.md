# Sentinel Triage — 2026-05-19 ~12:30 WITA

Sentinel reports 67 task / hour, 36 healthy, 29 escalated (24 stale + 5 failed).
Focus: 5 active failed jobs (high-impact subset).

## The 5 failed jobs — root cause diagnosed

### 1. `fly_pg_backup` (cron daily 03:00)

**Last error**: `AWS_ACCESS_KEY_ID not set — set in ~/.zshrc.secrets`
**Last successful**: unknown (every run fails since visible window)
**Root cause**: Script `~/scripts/fly-pg-backup.sh` line 20 sources `~/.zshrc.secrets` (legacy filename) but the secrets file on this machine is `~/.nuzantara-secrets.env`.
**Severity**: P1 — Postgres backup is missing every night, no DR coverage.
**Fix sketch**: Replace source file in `fly-pg-backup.sh` line 20: `~/.zshrc.secrets` → `~/.nuzantara-secrets.env`, OR `set -a; source ~/.nuzantara-secrets.env; set +a`.
**Effort**: 5 min + verify next 03:00 run.
**Risk**: Low.

### 2. `crm_automation` (cron daily 23:00)

**Last error**: `socket.gaierror [Errno 8] nodename nor servname provided, or not known`
**Last run**: 2026-05-18 23:01 failed, 108s before exit
**Root cause**: `cron-wrapper.sh` doesn't override DATABASE_URL to DATABASE_URL_LOCAL like `wr2-script-wrapper.sh` does. Script tries to connect to `nuzantara-postgres.flycast` (Fly internal hostname) → unresolvable from Pro. Same class of bug fixed for WR2 on 2026-05-06 (see scar).
**Severity**: P1 — CRM nightly automation hasn't run for days; team practices pipeline degraded.
**Fix sketch**: Patch `~/Desktop/nuzantara/scripts/cron-wrapper.sh` to add the same DATABASE_URL_LOCAL override block as `wr2-script-wrapper.sh` (lines 60-72 of WR2 wrapper).
**Effort**: 10 min.
**Risk**: Low (mirror of already-tested WR2 pattern).

### 3. `owner_cashout_sync` (cron weekly Mon 01:00)

**Two distinct errors over time**:

- 2026-05-11: `googleapiclient.errors.HttpError 403 caller does not have permission` (Google Sheets API)
- 2026-05-18: `Error: no access token available. Please login with 'flyctl auth login'` (script tries `fly ssh` to nuzantara-rag, token expired)

**Root cause**: Script runs `flyctl ssh console -a nuzantara-rag` and executes Python inside the Fly machine. The local flyctl token has expired. Older 403 was a Google Service Account losing scope.
**Severity**: P1 — owner financial sync weekly missing.
**Fix sketch**: (a) `flyctl auth login` on Pro to refresh token, (b) verify Service Account still has access to the Google Sheet, (c) consider moving to OAuth-refresh-via-secret-file pattern (long-term).
**Effort**: 15 min (auth + verify).
**Risk**: Med (Google Sheet ACL audit may surface deeper issue).

### 4-5. `seo_auto_fixer` + `nightly_code_quality` (ZOMBIE — 54 days)

**Last run**: gio 26 mar 2026 (54 days ago)
**Source**: `openclaw-bridge` (different source than `cron-wrapper` for the other 3)
**Current state**: Sentinel reports `status=failed` because state file `~/.agent/decisions/state/<job>.last.json` is stale from 2026-03-26 — sentinel doesn't know the job hasn't run since.
**Severity**: P2 — pure log noise. Jobs are silently dead, not actively broken.
**Fix options**:

- **Option A**: `dlq clear seo_auto_fixer nightly_code_quality` (sentinel uses dlq registry) — removes from sentinel scope without re-enabling.
- **Option B**: Truncate state file `last_run` to current ts but leave the job dead.
- **Option C**: Investigate WHY they stopped running 54 days ago and re-enable (much more work).
  **Effort**: 5 min for Option A, 30+ min for Option C.
  **Risk**: Low (A/B), High (C).

## Plus: 24 stale tasks

Sentinel reports 24 task with `status=stale, error=""` (no error, just hasn't reported recently). Examples: `zombie_hunter`, `practice_lifecycle_check`, `dlq_autopilot`, `fly_qdrant_backup`, `articles_indexing_daily`, `war_room`, `knowledge_graph_builder`, `quality_orchestrator`, `post_publish_poller`, `prime_tunnel`, `fly_cost_alert`, `gdrive_pg_backup`, `health_check`, `kbli_indexing_daily`, `compliance_autopilot`, `backend_prewarm`, `qdrant_snapshot`, `biz_orchestrator`, `seo_guardian_measure`, `nlm_bridge`, `fly_health_check`, `conversation_trainer`, `gdrive_intel_archive`, `post_publish_webhook`, `weekly_report`.

These are NOT actively failing. Sentinel's stale-detection threshold is too aggressive (probably <6h or <24h since last update). Many of these are weekly/daily jobs that haven't run yet today.

**Severity**: P2.
**Fix**: Relax `STALE_HOURS` threshold per task tier (daily → 36h, weekly → 192h), OR per-task explicit `stale_after_hours` in `organs_registry.yaml`.

## Summary of action items

| #   | Job                  | Action                                   | Risk | Effort |
| --- | -------------------- | ---------------------------------------- | ---- | ------ |
| 1   | fly_pg_backup        | patch script secrets source              | Low  | 5 min  |
| 2   | crm_automation       | patch cron-wrapper.sh DATABASE_URL_LOCAL | Low  | 10 min |
| 3   | owner_cashout_sync   | `flyctl auth login` + ACL audit          | Med  | 15 min |
| 4   | seo_auto_fixer       | `dlq clear` (Option A)                   | Low  | 2 min  |
| 5   | nightly_code_quality | `dlq clear` (Option A)                   | Low  | 2 min  |
| 6   | 24 stale             | tune STALE_HOURS per tier                | Low  | 10 min |

**Total Wave 3 effort: ~45 min** (excluding owner_cashout root-cause-audit).
