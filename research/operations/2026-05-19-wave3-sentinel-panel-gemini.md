### 1. ROI Ranking Table

| Rank | Job                    | Action                          | ROI      | Rationale                                                              |
| ---- | ---------------------- | ------------------------------- | -------- | ---------------------------------------------------------------------- |
| 1    | `fly_pg_backup`        | Patch script secrets source     | **High** | Critical DR capability restored in 5 mins.                             |
| 2    | `crm_automation`       | Patch `cron-wrapper.sh` DB URL  | **High** | Unblocks core business pipeline; known verified fix.                   |
| 3    | 24 stale tasks         | Tune `STALE_HOURS` per tier     | **High** | Eliminates 70% of Sentinel noise (24/34 alerts) in 10 mins.            |
| 4    | `seo_auto_fixer`       | `dlq clear`                     | **Med**  | Quick fix, but only resolves dashboard noise, no lost functionality.   |
| 5    | `nightly_code_quality` | `dlq clear`                     | **Med**  | Same as above.                                                         |
| 6    | `owner_cashout_sync`   | `flyctl auth login` + ACL audit | **Low**  | Requires interactive human auth and potentially debugging Google ACLs. |

### 2. Specific Patch Code (Bash Diffs)

**Item 1: `fly-pg-backup.sh`**

```diff
--- ~/scripts/fly-pg-backup.sh
+++ ~/scripts/fly-pg-backup.sh
@@ -19,2 +19,4 @@
-source ~/.zshrc.secrets
+set -a
+source ~/.nuzantara-secrets.env
+set +a
```

**Item 2: `cron-wrapper.sh`**

```diff
--- ~/Desktop/nuzantara/scripts/cron-wrapper.sh
+++ ~/Desktop/nuzantara/scripts/cron-wrapper.sh
@@ -45,2 +45,7 @@
 # Setup environment
+if [ -n "$DATABASE_URL_LOCAL" ]; then
+  echo "Overriding DATABASE_URL with DATABASE_URL_LOCAL"
+  export DATABASE_URL="$DATABASE_URL_LOCAL"
+fi
```

### 3. Risk Disagreement

We disagree with the assessment that patching `fly_pg_backup` carries "Low" risk. Modifying global environment sourcing (`set -a; source...`) inside a critical backup script introduces a **Moderate** risk. If `~/.nuzantara-secrets.env` contains parsing errors, syntax changes, or unintended exported variables that clash with AWS CLI expectations, the script will crash or silently fail to upload to S3. Because this job has already been failing silently, applying this patch without an immediate manual dry-run (`./fly-pg-backup.sh` in the terminal) risks extending the DR vulnerability while providing a false sense of security that the cron will succeed at 03:00.

### 4. Panel Decision

**PANEL_DECISION:** APPROVED. Execute items 1 and 2 immediately with manual dry-runs. Execute item 6 to clear dashboard noise. Defer item 3 for manual interactive auth. Clear items 4 and 5 via DLQ.
