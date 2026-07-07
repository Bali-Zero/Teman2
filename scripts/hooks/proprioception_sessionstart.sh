#!/usr/bin/env bash
# proprioception_sessionstart.sh — the RECEPTOR for the boundary-reconciliation organ.
#
# Sibling of escalations_alert_sessionstart.sh. Reads ~/.nuzantara-proprioception/last.json
# (written by scripts/proprioception.py) and surfaces boundary divergences at session boot.
#
# ANTI-CALM-LIAR CONTRACT (Codex red-team 2026-07-02): this receptor is NEVER silent.
#   - report fresh + 0 diverged  -> one-line heartbeat (proves the receptor itself ran)
#   - report fresh + diverged    -> compact block, top items with copy-pasteable fix
#   - report missing or >48h old -> LOUD stale alarm with the exact command to run
#   - receptor error             -> one visible error line (fail-open, never blocks boot)
# Silence therefore means exactly one thing: the hook is not registered/armed.
#
# Budget: hard ≤4s. Kill switch: PROPRIOCEPTION_RECEPTOR_ENABLED=false. Always exit 0.

set -o pipefail
[[ "${PROPRIOCEPTION_RECEPTOR_ENABLED:-true}" == "false" ]] && exit 0

REPORT="${HOME}/.nuzantara-proprioception/last.json"
MAX_AGE_H="${PROPRIOCEPTION_MAX_AGE_H:-48}"

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." 2>/dev/null && pwd)"

if [[ ! -f "$REPORT" ]]; then
  echo "🧭 PROPRIOCEZIONE: never run on this machine — run: python3 scripts/proprioception.py"
  exit 0
fi

# NOTE: no `timeout` wrapper — GNU timeout doesn't exist on stock macOS (exit 127, found by
# this hook's own first test run). The parse below is a local-file json read (<100ms); the
# 4s budget is enforced by the parser's own SIGALRM.
OUT="$(python3 - "$REPORT" "$MAX_AGE_H" "$REPO_ROOT" <<'PYEOF' 2>/dev/null
import json, os, signal, subprocess, sys, time
signal.alarm(4)  # hard budget: never block session boot
report_path, max_age_h, repo_root = sys.argv[1], float(sys.argv[2]), sys.argv[3]
try:
    with open(report_path) as fh:
        r = json.load(fh)
except Exception as e:
    print(f"🧭 propriocezione: receptor error — report unreadable ({type(e).__name__})")
    sys.exit(0)
age_h = (time.time() - os.path.getmtime(report_path)) / 3600
if age_h > max_age_h:
    print(f"🧭 PROPRIOCEZIONE STALE ({age_h:.0f}h > {max_age_h:.0f}h) — rerun: python3 scripts/proprioception.py")
    sys.exit(0)
probes = r.get("probes", [])
div = [p for p in probes if p.get("status") == "DIVERGED"]
unp = [p for p in probes if p.get("status") == "UNPROBEABLE"]
head_note = ""
try:
    cur = subprocess.run(["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, timeout=2).stdout.strip()
    if cur and r.get("repo_head") not in ("", "unknown", None) and cur != r["repo_head"]:
        head_note = f" (report from {r['repo_head']}, checkout now {cur})"
except Exception:
    pass
if not div:
    n = len(probes)
    if unp and len(unp) == n:
        # all-unprobeable is NOT calm — the organ could not see anything (spalla #3)
        print(f"🧭 PROPRIOCEZIONE: report fresh but ALL {n} probes UNPROBEABLE — the organ is blind, read ~/.nuzantara-proprioception/last.md")
    elif unp:
        print(f"🧭 propriocezione: fresh ({age_h:.1f}h), {n - len(unp)} reconciled, {len(unp)} unprobeable{head_note}")
    else:
        print(f"🧭 propriocezione: fresh ({age_h:.1f}h), all {n} probes reconciled{head_note}")
    sys.exit(0)
print(f"🧭 PROPRIOCEZIONE: {len(div)} boundary divergence(s) ({len(unp)} unprobeable), report {age_h:.1f}h old{head_note}")
for p in sorted(div, key=lambda x: x.get("severity", "P3"))[:4]:
    ev = p["evidence"][0] if p.get("evidence") else f"{p.get('n_findings', '?')} findings"
    print(f"  !! [{p.get('severity')}] {p.get('id')}: {ev}")
    print(f"     fix: {p.get('fix_hint', '')}")
more = len(div) - 4
if more > 0:
    print(f"  … +{more} more — cat ~/.nuzantara-proprioception/last.md")
PYEOF
)"
RC=$?
if [[ -n "$OUT" ]]; then
  echo "$OUT"
elif [[ $RC -ne 0 ]]; then
  echo "🧭 propriocezione: receptor error (parser exit $RC) — cat ~/.nuzantara-proprioception/last.md"
fi
exit 0
