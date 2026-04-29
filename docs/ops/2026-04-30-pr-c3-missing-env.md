# PR-C3 — Missing-env / missing-secrets fixes (2026-04-30)

Phase C of the Pro automations renaissance. Two cron-driven scripts
were silently broken because they read env vars that the cron context
never set. Fix is canonical: source `~/.nuzantara-secrets.env` at the
top of each script, behind an `if [ -f ]` guard so dev machines
without the file still work.

Audit reference:
`research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`

## Targets

### 1. `run_peraturan_ingestion.sh` (cron `30 21 * * 0`)

**Before:** failed three consecutive Sunday runs (2026-04-12, 04-19,
04-26) with `Google credentials error: GOOGLE_SERVICE_ACCOUNT_JSON env
var missing`. Three lost ingestion windows for `peraturan` regulation
sheet → Qdrant/KG/Drive/NLM NB-6 pipeline.

**After:** sources `~/.nuzantara-secrets.env` so
`GOOGLE_APPLICATION_CREDENTIALS` is set. The script's loader
(`peraturan_ingestion_trigger.py:152`) accepts both
`GOOGLE_SERVICE_ACCOUNT_JSON` (raw JSON, less secure) and
`GOOGLE_APPLICATION_CREDENTIALS` (file path, more secure). We chose
the file-path variant — Pro already has the SA at
`/Users/nuzantara/Desktop/nuzantara/.secrets/service-account.json`
(mode 0444, owner nuzantara) so no JSON has to leak into the env.

### 2. `run_heartbeat_check.sh` (cron `30 */6 * * *` and `0 0 * * *`)

**Before:** every run logged `[ERROR] TELEGRAM_BOT_TOKEN not set —
cannot send alert`. The script computes pipeline freshness
(NEVER_RAN, CRITICAL, DEAD, WARN, OK) but the alert side-effect was
silently disabled. Result: 4 NEVER_RAN + 7 CRITICAL + 1 DEAD pipelines
sat invisible.

**After:** sources `~/.nuzantara-secrets.env` so `TELEGRAM_BOT_TOKEN`
and `TELEGRAM_OWNER_CHAT_ID` reach the curl call at line 42.

## Code change pattern (canonical)

Same shell-source guard used elsewhere in the repo
(`scripts/genome_decay.sh`, `scripts/metabolic_rollup.sh`,
`scripts/wr2-cron-wrapper.sh`):

```bash
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
```

`set -a` auto-exports anything sourced (so child processes see the
vars), `set +a` reverts. The `if [ -f ]` guard means the script still
runs in dev environments / CI where the secrets file doesn't exist
(env vars stay empty, the script's existing fallback path handles it).

## Live operation on Pro

`~/.nuzantara-secrets.env` was missing
`GOOGLE_APPLICATION_CREDENTIALS`. Added on 2026-04-30 ~01:39 WITA
(backup: `~/.nuzantara-secrets.env.bak.20260430-pre-c3`):

```bash
# PR-C3 (2026-04-30): GOOGLE_APPLICATION_CREDENTIALS for run_peraturan_ingestion.sh
export GOOGLE_APPLICATION_CREDENTIALS=/Users/nuzantara/Desktop/nuzantara/.secrets/service-account.json
```

`TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` were already in the
file — just unreachable from the cron context.

File mode preserved at `0600` after edit.

## Out of scope (deliberately deferred)

- **`renewal-alerts` LaunchAgent** (audit row, "No expiries found"
  for 17+ days). The fix is a Python query reconciliation against
  `/api/crm/expiry-alerts` (which `compliance-ops` calls and works).
  That's a backend logic fix, not env-vars — moved to a separate PR.
- **WR2 fact-extractor / fact-checker plist**. Already quarantined in
  `~/Library/LaunchAgents/.disabled/` by sessione 2026-04-29.
  Restoring them needs PR-D2 (WR2 canva race + script restore), not
  config touches.

## Test plan (post-merge)

- [ ] Next Sunday 2026-05-03 21:30 UTC: `run_peraturan_ingestion.sh`
      should log `Google credentials loaded: <SA email>` instead of
      "missing env var". Check `peraturan_ingestion.log`.
- [ ] Next 6h tick (00:30 / 06:30 / 12:30 / 18:30 WITA):
      `run_heartbeat_check.sh --check` should fire a Telegram alert
      to chat `1125336968` if the 7 CRITICAL pipelines are still
      stale. Check `heartbeat_monitor.log` for `telegram_sent` event.
- [ ] If both pipelines silently improve over the next week, the
      audit numbers move: - `peraturan_ingestion`: `NEVER_RAN` → `OK` after the next
      Sunday 21:30 UTC fire - heartbeat: silent → audible (Telegram), so we'll learn whether
      the 7 CRITICAL are real or stale data

## Rollback

Pure git revert — the 2 shell scripts are the only repo change. The
Pro-side `GOOGLE_APPLICATION_CREDENTIALS` line in
`~/.nuzantara-secrets.env` can stay (other consumers may want it) or
be removed via:

```bash
ssh pro 'cp ~/.nuzantara-secrets.env.bak.20260430-pre-c3 ~/.nuzantara-secrets.env && chmod 600 ~/.nuzantara-secrets.env'
```

## Related

- Plan: `~/.claude/plans/RESUME-renaissance-2026-04-29.md` (PR-C3 row)
- Predecessor: PR #367 (PR-C5 dead code uninstall)
- Same pattern: `scripts/genome_decay.sh`, `scripts/metabolic_rollup.sh`
