#!/usr/bin/env bash
# exclude_cicatrix_from_context.sh — add the heavy cicatrix corpus files to
# claudeMdExcludes in ~/.claude/settings.json, so only the lightweight bridge
# (cicatrix-superscar.md, ~3.5k tokens) enters session context instead of the
# ~25k-token cicatrix-scars.md blob.
#
# The bridge stays IN context (it is NOT excluded); the detail is reachable
# on-demand via the `scar query "<theme>"` CLI (scripts/scar_query.py).
#
# Per-machine: ~/.claude/settings.json is host-local. Run once on each node
# (M5 / Pro / Mini). Idempotent, atomic, backs up first, validates JSON.
#
# NOTE: ~/.claude/ is host_boundary-protected. This is a legitimate control-plane
# edit — invoke with HOST_BOUNDARY_OFF=1 if the host_boundary hook is active
# (the designed valve, NOT a gate bypass).
set -uo pipefail

SETTINGS="$HOME/.claude/settings.json"
[ -f "$SETTINGS" ] || { echo "exclude-cicatrix: $SETTINGS not found" >&2; exit 1; }

python3 - "$SETTINGS" <<'PY'
import json, os, shutil, sys, time

p = sys.argv[1]
with open(p) as f:
    s = json.load(f)  # raises (and aborts) if already corrupt — fail-safe

want = [
    "**/.claude/rules/cicatrix-scars-archive.md",
    "**/.claude/rules/cicatrix-scars.md",
]
ex = s.setdefault("claudeMdExcludes", [])
added = [w for w in want if w not in ex]
if not added:
    print("exclude-cicatrix: already present — no change")
    sys.exit(0)

bak = p + ".bak-pre-superscar-exclude-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(p, bak)
for w in added:
    ex.append(w)

tmp = p + ".tmp"
with open(tmp, "w") as f:
    json.dump(s, f, indent=2, ensure_ascii=False)
    f.write("\n")
# validate the temp before swapping in
with open(tmp) as f:
    json.load(f)
os.replace(tmp, p)
print(f"exclude-cicatrix: backup {bak}")
print(f"exclude-cicatrix: added {added}")
PY
echo "exclude-cicatrix: claudeMdExcludes ->"
HOST_BOUNDARY_OFF=1 python3 -c "import json;print(json.load(open('$SETTINGS'))['claudeMdExcludes'])"
echo "exclude-cicatrix: effective NEXT session (current context keeps the blob until restart)"
