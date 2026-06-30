#!/usr/bin/env bash
# escalations_alert_sessionstart.sh — the ESCALATIONS RECEPTOR (SessionStart hook).
#
# Sibling of organism_alert_sessionstart.sh. Closes the SAME blindness class for
# the escalations board: CLAUDE.md §2/§14 tells the brain to "check
# shared/escalations_pro.jsonl + ~/.agent/decisions/claude_tasks/ at session
# start, HIGH first" — but a prose instruction is not a receptor. Until this
# hook, nothing inside a session read that board. Documentation is not a
# receptor; a hook is (CLAUDE.md §7).
#
# On every session start it surfaces, HIGH-first:
#   - HIGH-priority pending entries in shared/escalations_pro.jsonl (the LIVE board)
#   - HIGH-priority claude_tasks created within the freshness window (default 14d)
#     — the window is deliberate: ~/.agent/decisions/claude_tasks/ is a 500+ file
#     graveyard; surfacing ancient HIGH items every session would re-create the
#     noise-blindness this receptor exists to cure (SNAPSHOT, not graveyard).
#   - a one-line count of NORMAL-pending items (context, not noise).
#
# Design constraints (identical to the organism receptor, so the receptor itself
# never becomes the blindness):
#   - FAST: hard 4s budget; never blocks session start.
#   - FAIL-OPEN: any error => no alert, exit 0 (degrades to pre-existing silence).
#   - SNAPSHOT: only currently-open / fresh-HIGH items; resolved ones vanish.
#   - PATH-AWARE: works on M5 (balizero) and Pro/Mini (nuzantara).
#   - READ-ONLY: never mutates the board (that stays the /escalations command's job).
#
# Kill-switch: ESCALATIONS_RECEPTOR_ENABLED=false
# Freshness window override: ESCALATIONS_FRESH_DAYS=<n>

set -o pipefail

[[ "${ESCALATIONS_RECEPTOR_ENABLED:-true}" == "false" ]] && exit 0

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." && pwd)"

ESC_FILE="$REPO_ROOT/shared/escalations_pro.jsonl"
TASKS_DIR="${CLAUDE_TASKS_DIR:-$HOME/.agent/decisions/claude_tasks}"
FRESH_DAYS="${ESCALATIONS_FRESH_DAYS:-14}"

# Nothing to read => silent.
[[ -f "$ESC_FILE" || -d "$TASKS_DIR" ]] || exit 0

PY=""
for cand in \
    "$REPO_ROOT/apps/backend-rag/.venv/bin/python" \
    "$(command -v python3 2>/dev/null)"; do
    [[ -x "$cand" ]] && { PY="$cand"; break; }
done
[[ -n "$PY" ]] || exit 0

_TIMEOUT=()
if command -v timeout >/dev/null 2>&1; then _TIMEOUT=(timeout 4)
elif command -v gtimeout >/dev/null 2>&1; then _TIMEOUT=(gtimeout 4); fi

"${_TIMEOUT[@]}" "$PY" - "$ESC_FILE" "$TASKS_DIR" "$FRESH_DAYS" <<'PYEOF' 2>/dev/null || exit 0
import json, os, sys, time

esc_file, tasks_dir, fresh_days = sys.argv[1], sys.argv[2], int(sys.argv[3])
now = time.time()
fresh_cutoff = now - fresh_days * 86400

high = []          # list of (source, job, summary)
normal_pending = 0

# --- 1. live board: shared/escalations_pro.jsonl ---
if os.path.isfile(esc_file):
    try:
        with open(esc_file) as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if str(d.get("status", "pending")).lower() == "resolved":
                    continue
                prio = str(d.get("priority") or d.get("severity") or "NORMAL").upper()
                job = d.get("job") or d.get("type") or "?"
                summ = " ".join((d.get("error_summary") or "").split())[:80]
                if prio == "HIGH":
                    high.append(("escalations_pro.jsonl", job, summ))
                else:
                    normal_pending += 1
    except Exception:
        pass

# --- 2. claude_tasks graveyard: only HIGH within freshness window ---
if os.path.isdir(tasks_dir):
    try:
        for name in os.listdir(tasks_dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(tasks_dir, name)
            try:
                # cheap freshness pre-filter on mtime before parsing
                if os.path.getmtime(path) < fresh_cutoff:
                    continue
                with open(path) as fh:
                    d = json.load(fh)
            except Exception:
                continue
            prio = str(d.get("priority") or d.get("severity") or "NORMAL").upper()
            if prio != "HIGH":
                continue
            created = d.get("created_at")
            # if created_at is an epoch/parseable, enforce window; else trust mtime
            try:
                if isinstance(created, (int, float)) and float(created) < fresh_cutoff:
                    continue
            except Exception:
                pass
            job = d.get("job") or "?"
            summ = " ".join((d.get("error_summary") or d.get("fix_instruction") or "").split())[:80]
            high.append(("claude_tasks", job, summ))
    except Exception:
        pass

# Dedupe HIGH by (source, job, summary) — the graveyard has repeats.
_seen = set()
_dedup = []
for item in high:
    if item in _seen:
        continue
    _seen.add(item)
    _dedup.append(item)
high = _dedup

# Nothing worth surfacing => silent (no alert).
if not high and normal_pending == 0:
    sys.exit(0)

lines = ["🚨 ESCALATIONS BOARD (injected by SessionStart receptor)"]
if high:
    lines.append(f"  — {len(high)} HIGH-priority open (act first):")
    for src, job, summ in high[:12]:
        tail = f" — {summ}" if summ else ""
        lines.append(f"    🔴 [{src}] {job}{tail}")
    if len(high) > 12:
        lines.append(f"    … +{len(high) - 12} more HIGH")
else:
    lines.append("  — 0 HIGH-priority open.")
if normal_pending:
    lines.append(f"  — {normal_pending} NORMAL pending in escalations_pro.jsonl (context).")
lines.append("")
lines.append(
    "Run /escalations for the full board. These are surfaced HIGH-first per "
    "CLAUDE.md §2/§14; the receptor is read-only — it never mutates the board. "
    "claude_tasks shown are HIGH within the last "
    f"{fresh_days}d only (the dir is a 500+ file graveyard; surfacing all would "
    "re-create the noise-blindness — SNAPSHOT, not graveyard)."
)
ctx = "\n".join(lines)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }
}))
PYEOF

exit 0
