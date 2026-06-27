#!/usr/bin/env bash
# runtime-health-gate.sh — pre-advance health gate for the runtime checkout (SPEC split, P0).
#
# THE SCAR IT KILLS: ff-only auto-pull blindly advances the runtime onto origin/main even if
# that commit is broken → all 104 h24 organs crash on next invocation (council red-team). This
# gate runs against a CANDIDATE checkout at the target SHA; the puller advances the live runtime
# ONLY if this exits 0. On non-zero the puller keeps last_good_head untouched (council Q3).
#
# INERT in P0: it's a standalone validator. No puller calls it yet. Run it by hand against any
# checkout to see what it would verdict. Kill switch (for when wired into the puller in P1):
# NUZ_RUNTIME_HEALTH_GATE_DISABLED=1 → gate auto-passes (operator escape).
#
# Usage:  runtime-health-gate.sh <CHECKOUT_DIR>
# Exit:   0 = candidate is safe to become runtime. 1 = a check failed (do NOT advance). 2 = usage.
set -uo pipefail

CHECKOUT="${1:-}"
if [[ -z "$CHECKOUT" ]]; then
  echo "usage: runtime-health-gate.sh <CHECKOUT_DIR>" >&2
  exit 2
fi
if [[ "${NUZ_RUNTIME_HEALTH_GATE_DISABLED:-0}" == "1" ]]; then
  echo "[health-gate] disabled via NUZ_RUNTIME_HEALTH_GATE_DISABLED=1 — auto-pass"
  exit 0
fi
if [[ ! -d "$CHECKOUT" ]]; then
  echo "[health-gate] FAIL: checkout dir does not exist: $CHECKOUT" >&2
  exit 1
fi

export PATH="/opt/homebrew/bin:/usr/bin:/bin:${PATH:-}"
fails=0
check() { local name="$1"; shift; if "$@"; then echo "[health-gate] PASS: $name"; else echo "[health-gate] FAIL: $name" >&2; fails=$((fails+1)); fi; }

REG="$CHECKOUT/apps/organism/organism/organs_registry.yaml"

# Resolve a python that has the repo deps (yaml). Golden Rule #1: prefer the checkout's venv,
# never assume system python carries yaml (it doesn't on a bare M5). Fall back to whatever
# python3 imports yaml; if none does, that's a real FAIL the gate must surface, not mask.
PY="python3"
for cand in "$CHECKOUT/apps/backend-rag/.venv/bin/python3" "$CHECKOUT/.venv/bin/python3" python3; do
  if [[ -x "$cand" ]] && "$cand" -c "import yaml" >/dev/null 2>&1; then PY="$cand"; break; fi
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import yaml" >/dev/null 2>&1; then PY="$cand"; break; fi
done
echo "[health-gate] python: $PY"

# 1. registry parses + checksum valid (the source of truth must be intact)
_reg_valid() {
  [[ -f "$REG" ]] || return 1
  ( cd "$CHECKOUT/apps/organism" && PYTHONPATH=. "$PY" -m organism.tools.validate_organs_registry \
      organism/organs_registry.yaml >/dev/null 2>&1 )
}
check "organs_registry valid + checksum" _reg_valid

# 2. every launchd-owned script the registry references actually EXISTS in this candidate
#    (catches a commit that deletes/moves a script an organ runs — the owner_module-missing class)
_owner_modules_exist() {
  [[ -f "$REG" ]] || return 1
  "$PY" - "$CHECKOUT" "$REG" <<'PY'
import sys, os, yaml
root, reg = sys.argv[1], sys.argv[2]
d = yaml.safe_load(open(reg))
missing = []
for o in d.get("organs", []):
    if not isinstance(o, dict) or o.get("enabled") is False: continue
    om = o.get("owner_module")
    if not om or "/" not in om: continue           # skip dotted module names / non-paths
    if om.startswith("infra/fly") or om.startswith("backend."): continue
    if not os.path.exists(os.path.join(root, om)):
        missing.append((o["id"], om))
# P0 reality: ~42 already-missing owner_modules exist on main TODAY. So this check reports the
# COUNT and only fails if it GROWS past a baseline tolerance (a new commit deleting a live
# script). Baseline overridable via env; default generous so P0 never false-fails.
tol = int(os.environ.get("HEALTH_GATE_OWNER_MISSING_TOL", "60"))
print(f"owner_module missing: {len(missing)} (tolerance {tol})", file=sys.stderr)
sys.exit(0 if len(missing) <= tol else 1)
PY
}
check "owner_module scripts exist (<= tolerance)" _owner_modules_exist

# 3. sentinel + key self-loop python compiles (import-smoke, no execution)
_compiles() {
  "$PY" -m py_compile "$CHECKOUT/scripts/sentinel-aggregate.py" 2>/dev/null
}
check "sentinel-aggregate.py compiles" _compiles

# 4. the A2 starved test passes on the candidate (the self-loop's own guard)
_a2_test() {
  [[ -f "$CHECKOUT/scripts/test_sentinel_starved.py" ]] || return 0   # absent on old commits = skip, not fail
  ( cd "$CHECKOUT" && "$PY" scripts/test_sentinel_starved.py >/dev/null 2>&1 )
}
check "A2 starved test green" _a2_test

if (( fails > 0 )); then
  echo "[health-gate] VERDICT: BLOCK ($fails check(s) failed) — runtime must NOT advance to this commit" >&2
  exit 1
fi
echo "[health-gate] VERDICT: SAFE — candidate may become runtime"
exit 0
