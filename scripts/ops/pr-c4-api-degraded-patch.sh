#!/usr/bin/env bash
# PR-C4 — Patch 4 cron-agent-python scripts on Pro that the 2026-04-29 audit
# flagged as degraded by external API failures or unused/dead LLM calls.
#
# RUN ON PRO ONLY. Idempotent: safe to re-run after success.
#
# IMPORTANT CONTEXT: ~/scripts/cron-agent-python/ on Pro is NOT in git.
# It's "shadow infrastructure" that ought to be promoted into the repo as
# its own future PR. This script applies 4 surgical patches via in-place
# Python rewriting (NOT sed — Python source is too sensitive to regex line
# noise) so the transformation is reproducible without committing the full
# script tree.
#
# Targets:
#   1. imigrasi_monitor.py    — drop _fetch_peraturan() call (peraturan.go.id
#                                returns HTTP 500 for 10+ days; sources
#                                imigrasi.go.id/berita and /produk-hukum
#                                still work and cover the same domain).
#   2. bi_exchange_rate.py    — drop _try_bi_api() tier (bi_api_failed_fallback_html
#                                logged every run since 2026-04-22). HTML
#                                scrape becomes primary, exchangerate-api.com
#                                stays as last-resort fallback.
#   3. compliance_ops.py      — drop get_or_create_session/save_session calls
#                                (claude --print 30s timeout every run, but
#                                session_id is captured and never used for
#                                fork/resume — purely dead code that costs
#                                latency. CLAUDE.md §10 says "no LLM in
#                                compliance — deterministic per fedeltà").
#   4. daily_ops.py           — fix logging false-positive (`error=None if
#                                renewals else "failed"` flagged success
#                                results returning [] as "failed"). The
#                                renewals endpoint actually works, just
#                                returns empty most days.
#
# Backups: each .py saved to ~/.cron-agent-python.backups/<utc-ts>/<file>.py.bak
# Audit log: appended to ~/logs/ops/pr-c4-api-degraded-patch.log
#
# Reference:
#   ~/.claude/plans/RESUME-renaissance-2026-04-29.md (PR-C4 row)
#   research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv

set -euo pipefail

if [[ "$(whoami)" != "nuzantara" ]]; then
  echo "[pr-c4] ERROR: must run on Pro (whoami=nuzantara). got: $(whoami)" >&2
  exit 1
fi

CRON_DIR="$HOME/scripts/cron-agent-python"
BACKUP_ROOT="$HOME/.cron-agent-python.backups"
LOG_DIR="$HOME/logs/ops"
LOG_FILE="$LOG_DIR/pr-c4-api-degraded-patch.log"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$BACKUP_ROOT/$TS_UTC"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG_FILE"
}

# Patch helper: backs up a file then runs an in-place python rewrite via
# `python3 -c "..."`. The python snippet is responsible for being
# idempotent (i.e. tolerate the patch having already been applied).
patch_file() {
  local file="$1"
  local label="$2"
  local pyscript="$3"

  if [[ ! -f "$CRON_DIR/$file" ]]; then
    log "[$label] SKIP: $CRON_DIR/$file does not exist"
    return 0
  fi

  cp "$CRON_DIR/$file" "$BACKUP_DIR/${file}.bak"
  log "[$label] backup -> $BACKUP_DIR/${file}.bak"

  python3 - "$CRON_DIR/$file" <<PY
import sys
from pathlib import Path

target = Path(sys.argv[1])
src = target.read_text()

$pyscript

if new_src == src:
    print(f"[{target.name}] no-op (already patched)", flush=True)
else:
    target.write_text(new_src)
    print(f"[{target.name}] patched ({len(src)} -> {len(new_src)} bytes)", flush=True)
PY

  # Lint the result.
  if ! python3 -m py_compile "$CRON_DIR/$file"; then
    log "[$label] ERROR: py_compile failed on $file. Restoring backup."
    cp "$BACKUP_DIR/${file}.bak" "$CRON_DIR/$file"
    return 2
  fi
  log "[$label] py_compile OK"
}

# ─── Patch 1: imigrasi_monitor.py — drop _fetch_peraturan() ─────────────────
log "=== PATCH 1: imigrasi_monitor.py — drop peraturan.go.id source ==="
patch_file imigrasi_monitor.py imigrasi '
import re

# Drop the peraturan.go.id call block (3 lines: random_delay + fetch_peraturan
# + extend + log_step). Idempotent: if block is gone, this is a no-op.
PATTERN = re.compile(
    r"\n\n        await self\.random_delay\(3\.0, 6\.0\)\n"
    r"\n        # Source 3: peraturan\.go\.id \(imigrasi filter\)\n"
    r"        items_peraturan = await self\._fetch_peraturan\(\)\n"
    r"        all_items\.extend\(items_peraturan\)\n"
    r"        self\.log_step\(\"fetch_peraturan\", outputs=\{\"count\": len\(items_peraturan\)\}\)\n"
)
new_src = PATTERN.sub("\n", src)
'

# ─── Patch 2: bi_exchange_rate.py — drop _try_bi_api() tier ────────────────
log "=== PATCH 2: bi_exchange_rate.py — drop BI API tier ==="
patch_file bi_exchange_rate.py bi-exchange '
import re

# Inside async def run(self), the cascade is:
#   data = await self._try_bi_api()
#   if not data:
#       self.logger.info("bi_api_failed_fallback_html")
#       data = await self._try_html_scrape()
# Replace the BI-API-first cascade with HTML-first.
PATTERN = re.compile(
    r"        # Try JSON API \(much cleaner than HTML scrape\)\n"
    r"        data = await self\._try_bi_api\(\)\n"
    r"        if not data:\n"
    r"            self\.logger\.info\(\"bi_api_failed_fallback_html\"\)\n"
    r"            data = await self\._try_html_scrape\(\)\n"
)
REPLACEMENT = (
    "        # PR-C4 (2026-04-30): BI native API broken since 2026-04-22; HTML primary now.\n"
    "        data = await self._try_html_scrape()\n"
)
new_src = PATTERN.sub(REPLACEMENT, src)
'

# ─── Patch 3: compliance_ops.py — drop session_id dead code ────────────────
log "=== PATCH 3: compliance_ops.py — drop unused session_id (claude --print timeout) ==="
patch_file compliance_ops.py compliance-ops '
import re

# 3a. Drop the import for get_or_create_session / save_session.
PATTERN_IMPORT = re.compile(
    r"from agent_job import AgentJob, RunResult, WITA, main, get_or_create_session, save_session\n"
)
REPLACEMENT_IMPORT = "from agent_job import AgentJob, RunResult, WITA, main\n"
src1 = PATTERN_IMPORT.sub(REPLACEMENT_IMPORT, src)

# 3b. Drop the get_or_create_session block at top of run().
PATTERN_GET = re.compile(
    r"        # ── Session resume \(daily scope\) ─────────────────────────────────\n"
    r"        # Accumulates context from prior runs in the same day\.\n"
    r"        today = datetime\.now\(WITA\)\.strftime\(\"%Y-%m-%d\"\)\n"
    r"        session_id = get_or_create_session\(\"compliance-ops\", scope=f\"daily:\{today\}\"\)\n"
    r"        if session_id:\n"
    r"            self\.logger\.debug\(\"session_resume\", session_id=session_id\)\n"
    r"\n"
)
REPLACEMENT_GET = (
    "        # PR-C4 (2026-04-30): session_id was captured but never used for fork/resume.\n"
    "        # Removed get_or_create_session — it spawns claude --print which times out\n"
    "        # every run (30s) and CLAUDE.md says \"no LLM in compliance — deterministic\".\n"
    "        today = datetime.now(WITA).strftime(\"%Y-%m-%d\")\n"
    "\n"
)
src2 = PATTERN_GET.sub(REPLACEMENT_GET, src1)

# 3c. Drop the save_session block near end of run().
PATTERN_SAVE = re.compile(
    r"\n        # Save session context for next run in same day\n"
    r"        if session_id:\n"
    r"            save_session\(\"compliance-ops\", session_id, scope=f\"daily:\{today\}\"\)\n"
)
REPLACEMENT_SAVE = ""
new_src = PATTERN_SAVE.sub(REPLACEMENT_SAVE, src2)
'

# ─── Patch 4: daily_ops.py — fix log false-positive on empty list ──────────
log "=== PATCH 4: daily_ops.py — log false-positive on empty renewals list ==="
patch_file daily_ops.py daily-ops '
import re

# `error=None if renewals else "failed"` flags `[]` (legitimate empty list)
# as "failed". Use `is None` so only a true None response (httpx error or
# 401/500) triggers the error path.
PATTERN = re.compile(
    r"        renewals = await self\.backend_api\(\"/api/crm/practices/renewals/upcoming\", params=\{\"days_ahead\": 30\}\)\n"
    r"        self\.log_step\(\"fetch_renewals\", outputs=renewals, error=None if renewals else \"failed\"\)\n"
)
REPLACEMENT = (
    "        renewals = await self.backend_api(\"/api/crm/practices/renewals/upcoming\", params={\"days\": 30})\n"
    "        self.log_step(\"fetch_renewals\", outputs=renewals, error=None if renewals is not None else \"failed\")\n"
)
new_src = PATTERN.sub(REPLACEMENT, src)
'

# ─── Final summary ─────────────────────────────────────────────────────────
log "PR-C4 applied. Backups in: $BACKUP_DIR"
log "Rollback: cp $BACKUP_DIR/*.bak $CRON_DIR/<corresponding file>"
log ""
log "Verify next runs:"
log "  bi-exchange-rate (07:00 WITA)        — should NOT log bi_api_failed_fallback_html"
log "  imigrasi-monitor (06:00 WITA)        — should NOT log peraturan_fetch_error"
log "  compliance-ops   (every 6h)          — should NOT log session_error / claude --print timeout"
log "  daily-ops        (08:00 WITA)        — should log fetch_renewals error=None even on []"
