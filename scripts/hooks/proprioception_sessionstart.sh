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

# PROPRIOCEPTION_REPORT_PATH: test-only override (scripts/tests/test_proprioception_receptor_ranking.sh).
# Defaults identical to the always-live path — no production behavior change.
REPORT="${PROPRIOCEPTION_REPORT_PATH:-${HOME}/.nuzantara-proprioception/last.json}"
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

# #44 (2026-07-26): a report's per-item findings are snapshot assertions computed once at
# {report_time}, not live facts — a home_fork_scripts DIVERGED was TRUE at snapshot time and
# was cured 27 minutes later, well inside this receptor's own 48h "fresh" gate, and read as a
# current fact by every session since. The number alone doesn't fix that: 4.6h reads as fresh
# and gets acted on anyway. Every line now names itself as a claim to RE-DERIVE, not trust — a
# reader who re-runs one sha256/git-status pays five seconds and cannot be wrong. That is
# exactly what caught this incident.
report_time = r.get("ts", "")[11:19] or "?"

# a guardian's OWN cadence/self-freshness finding (probe id "guardian_freshness") is context
# for every OTHER finding on this report, not a peer competing for the same print slots — the
# severity-sort + hard [:4] cap could push it off-screen entirely behind enough P1s (W97: a
# truncated list read downstream as complete). Exempt it from both: print first, unconditionally,
# and only when it IS a finding — a fresh guardian emits none, so this stays silent rather than
# becoming furniture nobody reads.
self_finding = next((p for p in div if p.get("id") == "guardian_freshness"), None)
other_div = [p for p in div if p is not self_finding]


def _print_finding(p: dict) -> None:
    # W97 again, one level DOWN from where it was cured. The [:4] probe cap above
    # was fixed on 2026-07-26 so a truncated list of PROBES could not read as
    # complete — but the single line each probe prints still truncated its own
    # FINDINGS to evidence[0], with nothing on the line saying so. Both caps are
    # the same defect at two depths; curing only the outer one is the "curato 1
    # wrapper su 5" shape the outer fix was written against.
    #
    # MEASURED 2026-08-26 on Pro, live: launchagent_canon carried 55 findings and
    # printed one; launchd_liveness 22, printed one; organs_heartbeat 7, printed
    # one; worktree_gate_shim 4, printed one. That last one is not hypothetical
    # damage — the line was read as "one worktree pushes with no gate", so the
    # other three stayed ungated until a hand census found them.
    #
    # The count goes next to the id, not appended after the evidence: the evidence
    # string is truncated to 160 chars upstream (run_wrap), so anything trailing
    # can be the part that falls off.
    n = p.get("n_findings")
    ev = p["evidence"][0] if p.get("evidence") else f"{n if n is not None else '?'} findings"
    more = f" [1 of {n}]" if p.get("evidence") and isinstance(n, int) and n > 1 else ""
    print(f"  !! [{p.get('severity')}] {p.get('id')}{more} (as of {report_time}, {age_h:.1f}h ago — re-verify before acting): {ev}")
    print(f"     fix: {p.get('fix_hint', '')}")


if self_finding is not None:
    _print_finding(self_finding)
ranked = sorted(other_div, key=lambda x: x.get("severity", "P3"))
for p in ranked[:4]:
    _print_finding(p)
hidden = ranked[4:]
if hidden:
    hidden_ids = ", ".join(p.get("id", "?") for p in hidden)
    print(f"  … +{len(hidden)} more ({hidden_ids}) — cat ~/.nuzantara-proprioception/last.md")
PYEOF
)"
RC=$?
if [[ -n "$OUT" ]]; then
  echo "$OUT"
elif [[ $RC -ne 0 ]]; then
  echo "🧭 propriocezione: receptor error (parser exit $RC) — cat ~/.nuzantara-proprioception/last.md"
fi
exit 0
