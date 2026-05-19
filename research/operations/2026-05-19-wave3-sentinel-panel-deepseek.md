## 1. ROI Ranking

| #   | Action                                      | ROI    |
| --- | ------------------------------------------- | ------ |
| 1   | `fly_pg_backup` – fix secrets source        | High   |
| 2   | `crm_automation` – patch DATABASE_URL_LOCAL | High   |
| 3   | `owner_cashout_sync` – reauth + ACL audit   | Medium |
| 6   | Tune STALE_HOURS per tier                   | Medium |
| 4   | `dlq clear seo_auto_fixer`                  | Low    |
| 5   | `dlq clear nightly_code_quality`            | Low    |

## 2. Patch Code (bash diffs)

### Item 1 – `fly-pg-backup.sh`

```diff
--- a/~/scripts/fly-pg-backup.sh
+++ b/~/scripts/fly-pg-backup.sh
@@ -17,7 +17,7 @@

 # Load secrets
-source ~/.zshrc.secrets
+set -a; source ~/.nuzantara-secrets.env; set +a

 # Backup command
 pg_dump --no-owner --no-acl "$DATABASE_URL" > /tmp/backup.sql
```

### Item 2 – `cron-wrapper.sh`

Add block after `# Override database URL for local runs` (or similar existing comment).  
Assumes `wr2-script-wrapper.sh` lines 60‑72 contain:

```bash
if [ -n "$DATABASE_URL_LOCAL" ]; then
  export DATABASE_URL="$DATABASE_URL_LOCAL"
  echo "Overriding DATABASE_URL with DATABASE_URL_LOCAL"
fi
```

```diff
--- a/~/Desktop/nuzantara/scripts/cron-wrapper.sh
+++ b/~/Desktop/nuzantara/scripts/cron-wrapper.sh
@@ -40,6 +40,12 @@
 # Common setup...

+# Override DATABASE_URL for local cron runs (mirror wr2-script-wrapper.sh)
+if [ -n "$DATABASE_URL_LOCAL" ]; then
+  export DATABASE_URL="$DATABASE_URL_LOCAL"
+  echo "Overriding DATABASE_URL with DATABASE_URL_LOCAL"
+fi
+
 # Run the job
```

## 3. Disagreed Risk

The triage labels `seo_auto_fixer` and `nightly_code_quality` as "ZOMBIE" and recommends `dlq clear` without investigating why they stopped. This is a risk: these jobs may be silently critical for SEO or code health, disabled by a previous failed deployment or config change. Clearing them from monitoring removes visibility, and the underlying problem (e.g., a missing dependency or path change) will never be discovered. The effort to investigate is modest (~30 min) and could prevent a future surprise outage. I’d rate this risk **Medium**, not Low.

## 4. Panel Decision

PANEL_DECISION: Approve Wave 3 actions for items 1,2,3,6; defer items 4/5 pending brief investigation of why they stopped – assign to next sprint with 30 min budget.
