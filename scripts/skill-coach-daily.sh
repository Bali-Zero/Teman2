#!/bin/zsh
# Repo-canonical (W50 promotion from ~/.openclaw/bin/, 2026-06-21).
# Plist MUST exec THIS copy; paths derive from repo root (no dead worktree).
set -euo pipefail

export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
WT="$(cd "$(dirname "${0:A}")/.." && pwd)"  # repo root (W50: derive; was dead worktree)
APP="$WT/apps/backend-rag"
VENV="$APP/.venv"
OPENCLAW_NODE="/opt/homebrew/opt/node/bin/node"
OPENCLAW_CLI="/opt/homebrew/lib/node_modules/openclaw/dist/index.js"
LOG_DIR="$HOME/.openclaw/cron/runs"
RUN_ID="skill-coach-launchd-$(date -u +%Y%m%dT%H%M%SZ)"
RUN_LOG="$LOG_DIR/${RUN_ID}.jsonl"
LATEST="$LOG_DIR/skill-coach-daily.latest.json"
TMP_OUTPUT="${TMPDIR:-/tmp}/skill-coach-runner.$$.$RANDOM.out"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$LOG_DIR"
cd "$APP"

if [[ ! -x "$VENV/bin/python" ]]; then
  printf '{"status":"error","error_type":"MissingVenv","message":"backend venv python not executable"}\n' > "$TMP_OUTPUT"
  RC=1
else
  set +e
  PYTHONPATH=. "$VENV/bin/python" -m backend.scripts.skill_coach_openclaw_runner --window-days 15 > "$TMP_OUTPUT" 2>&1
  RC=$?
  set -e
fi

"$VENV/bin/python" - "$TMP_OUTPUT" "$RC" "$RUN_ID" "$STARTED_AT" "$LATEST" "$RUN_LOG" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

output_path = Path(sys.argv[1])
rc = int(sys.argv[2])
run_id = sys.argv[3]
started_at = sys.argv[4]
latest_path = Path(sys.argv[5])
run_log_path = Path(sys.argv[6])
ended_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
summary = None
for line in output_path.read_text(encoding="utf-8", errors="replace").splitlines():
    stripped = line.strip()
    if not stripped.startswith("{"):
        continue
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        continue
    if isinstance(parsed, dict):
        summary = parsed
if summary is None:
    summary = {
        "status": "error" if rc else "unknown",
        "error_type": "NoJsonSummary",
        "message": "runner produced no machine-readable summary",
    }
record = {
    "run_id": run_id,
    "started_at": started_at,
    "ended_at": ended_at,
    "rc": rc,
    "status": "ok" if rc == 0 and summary.get("status") == "ok" else "error",
    "summary": summary,
}
latest_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
with run_log_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, sort_keys=True) + "\n")
print(json.dumps(record, sort_keys=True))
PY

EVENT_TEXT=$("$VENV/bin/python" - "$LATEST" <<'PY'
import json, sys
record = json.load(open(sys.argv[1], encoding='utf-8'))
summary = record.get('summary') or {}
print(
    "Skill Coach daily finished: "
    f"status={record.get('status')} rc={record.get('rc')} "
    f"proposals={summary.get('proposals_written')} "
    f"evidence={summary.get('evidence_written')} "
    f"evidence_by_status={summary.get('evidence_by_status')} "
    f"latest={sys.argv[1]}"
)
PY
)
"$OPENCLAW_NODE" "$OPENCLAW_CLI" system event \
  --json \
  --mode next-heartbeat \
  --session-key agent:ops:skill-coach-daily \
  --text "$EVENT_TEXT" >/dev/null 2>&1 || true

rm -f "$TMP_OUTPUT"
exit "$RC"
