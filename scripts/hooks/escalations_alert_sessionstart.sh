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
# Escalations file override (tests only): ESCALATIONS_FILE_OVERRIDE=<path>

set -o pipefail

[[ "${ESCALATIONS_RECEPTOR_ENABLED:-true}" == "false" ]] && exit 0

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." && pwd)"

ESC_FILE="${ESCALATIONS_FILE_OVERRIDE:-$REPO_ROOT/shared/escalations_pro.jsonl}"
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
import json, os, re, sys, time

esc_file, tasks_dir, fresh_days = sys.argv[1], sys.argv[2], int(sys.argv[3])
now = time.time()
fresh_cutoff = now - fresh_days * 86400

high = []          # list of (source, job, summary, ts)
normal_pending = 0

# --- cause normalization for grouping (2026-09-09 diet) ---
# The same job can escalate on every tick with an identical CAUSE but a
# different count/timestamp/sha baked into error_summary (measured live:
# healer_pro_tick writing "N dead organs ... none curable" once per tick, 14
# HIGH items that are the SAME finding repeated). Strip the volatile parts
# before grouping so those collapse into one line with a repeat count —
# strip ISO timestamps and hex shas BEFORE digits (a sha is also all-digit-
# capable and would otherwise be partly eaten by the digit pass first).
_ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?")
_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.I)
_NUM_RE = re.compile(r"\d+")


def _normalize_cause(summary: str) -> str:
    s = _ISO_TS_RE.sub("<ts>", summary)
    s = _SHA_RE.sub("<sha>", s)
    s = _NUM_RE.sub("#", s)
    return " ".join(s.split())

# --- 1. live board: shared/escalations_pro.jsonl ---
# D2.3's writer is append-only (sentinel_lib.escalations.mark_resolved): a
# recovered job gets a NEW {"status": "resolved", ...} line appended, the
# original pending line is never rewritten in place. So per-line status
# filtering alone is not enough — a healed job's ORIGINAL pending line still
# reads status=="pending" forever. Net-pending fix (board-honesty, 2026-07-16):
# a pending entry only still counts as OPEN if no resolution for the same job
# was appended at or after it (match job+ts, mirroring how mark_resolved pairs
# them). Recurring jobs (escalate → resolve → escalate again) are handled
# correctly because each pending entry is checked against the LATEST
# resolution timestamp for its job.
if os.path.isfile(esc_file):
    try:
        raw = []
        with open(esc_file) as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    raw.append(json.loads(ln))
                except Exception:
                    continue

        resolved_latest_ts = {}  # job -> latest resolved ts
        for d in raw:
            if str(d.get("status", "pending")).lower() == "resolved":
                job = d.get("job") or "?"
                ts = d.get("resolved_at", d.get("ts", 0)) or 0
                if ts >= resolved_latest_ts.get(job, -1):
                    resolved_latest_ts[job] = ts

        for d in raw:
            if str(d.get("status", "pending")).lower() == "resolved":
                continue  # resolution marker itself is never a board item
            job = d.get("job") or d.get("type") or "?"
            entry_ts = d.get("ts", 0) or 0
            if job in resolved_latest_ts and entry_ts <= resolved_latest_ts[job]:
                continue  # covered by a later resolution — net-resolved, not open
            prio = str(d.get("priority") or d.get("severity") or "NORMAL").upper()
            summ = " ".join((d.get("error_summary") or "").split())[:80]
            if prio == "HIGH":
                high.append(("escalations_pro.jsonl", job, summ, float(entry_ts) if entry_ts else 0.0))
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
            # created_at when parseable, else the mtime pre-filter already read above
            entry_ts = 0.0
            try:
                if isinstance(created, (int, float)):
                    entry_ts = float(created)
            except Exception:
                pass
            if not entry_ts:
                try:
                    entry_ts = os.path.getmtime(path)
                except OSError:
                    entry_ts = 0.0
            high.append(("claude_tasks", job, summ, entry_ts))
    except Exception:
        pass

# Group HIGH by (source, job, normalized cause) — same job/source repeating the
# SAME underlying cause with only a count/timestamp/sha changed (measured live:
# healer_pro_tick's "N dead organs ... none curable" once per tick, 14 HIGH
# items for one standing condition) collapses into one line, "(×N, latest
# <date>)". A genuinely different cause for the same job still gets its own
# group — normalization only strips the volatile tokens, not the job identity.
_groups: dict[tuple[str, str, str], dict] = {}
_group_order: list[tuple[str, str, str]] = []
for source, job, summ, ts in high:
    key = (source, job, _normalize_cause(summ))
    g = _groups.get(key)
    if g is None:
        g = {"source": source, "job": job, "summary": summ, "count": 0, "latest_ts": ts}
        _groups[key] = g
        _group_order.append(key)
    g["count"] += 1
    if ts >= g["latest_ts"]:
        g["latest_ts"] = ts
        g["summary"] = summ  # keep the freshest raw summary as the representative text
groups = [_groups[k] for k in _group_order]
groups.sort(key=lambda g: g["latest_ts"], reverse=True)
total_high = sum(g["count"] for g in groups)

# Nothing worth surfacing => silent (no alert).
if not groups and normal_pending == 0:
    sys.exit(0)

# Output cap (2026-09-04): this receptor injects into EVERY session start on
# every machine — a board with dozens of HIGH items must not itself become
# the noise it exists to cut through. SESSIONSTART_HOOK_MAX_BYTES caps the
# WHOLE stdout payload (the JSON envelope included, since that is what the
# harness actually injects). Priority, most-detail-first: the HIGH count
# line and HIGH items are never dropped; the long explanatory paragraph is
# the first thing to go, then the HIGH item list itself shrinks (still
# naming how many are hidden); the /escalations pointer always survives —
# it is the shortest tail and the one line every stage keeps.
MAX_BYTES = int(os.environ.get("SESSIONSTART_HOOK_MAX_BYTES", "1500"))
SHORT_POINTER = "Run /escalations for the full board."
LONG_EXPLANATION = (
    "Run /escalations for the full board. These are surfaced HIGH-first per "
    "CLAUDE.md §2/§14; the receptor is read-only — it never mutates the board. "
    "claude_tasks shown are HIGH within the last "
    f"{fresh_days}d only (the dir is a 500+ file graveyard; surfacing all would "
    "re-create the noise-blindness — SNAPSHOT, not graveyard)."
)


def _payload(ctx: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    })


def _build(show_n: int, tail_text: str) -> str:
    lines = ["🚨 ESCALATIONS BOARD (injected by SessionStart receptor)"]
    if groups:
        lines.append(
            f"  — {total_high} HIGH-priority open across {len(groups)} group(s) (act first):"
        )
        for g in groups[:show_n]:
            tail = f" — {g['summary']}" if g["summary"] else ""
            date = (
                time.strftime("%Y-%m-%d", time.gmtime(g["latest_ts"]))
                if g["latest_ts"]
                else "unknown"
            )
            count_tail = f" (×{g['count']}, latest {date})" if g["count"] > 1 else f" (latest {date})"
            lines.append(f"    🔴 [{g['source']}] {g['job']}{tail}{count_tail}")
        if len(groups) > show_n:
            lines.append(f"    … +{len(groups) - show_n} more HIGH group(s)")
    else:
        lines.append("  — 0 HIGH-priority open.")
    if normal_pending:
        lines.append(f"  — {normal_pending} NORMAL pending in escalations_pro.jsonl (context).")
    lines.append("")
    lines.append(tail_text)
    return "\n".join(lines)


GROUP_CAP = 6
ctx = _build(GROUP_CAP, LONG_EXPLANATION)
if len(_payload(ctx).encode("utf-8")) > MAX_BYTES:
    ctx = _build(GROUP_CAP, SHORT_POINTER)
show_n = GROUP_CAP
while len(_payload(ctx).encode("utf-8")) > MAX_BYTES and show_n > 1:
    show_n -= 1
    ctx = _build(show_n, SHORT_POINTER)

if len(_payload(ctx).encode("utf-8")) > MAX_BYTES:
    # Defensive last resort (an unbounded `job` field can still overflow at
    # show_n=1): hard-truncate at a line boundary and say so.
    lines = ctx.split("\n")
    kept: list[str] = []
    running = 0
    char_budget = max(MAX_BYTES - 300, 0)  # margin for the JSON envelope + trailer
    for ln in lines:
        running += len(ln) + 1
        if running > char_budget:
            break
        kept.append(ln)
    hidden_lines = len(lines) - len(kept)
    if hidden_lines > 0:
        kept.append(f"… (+{hidden_lines} lines, run /escalations for the full board)")
    ctx = "\n".join(kept) if kept else lines[0]

print(_payload(ctx))
PYEOF

exit 0
