#!/usr/bin/env bash
# install_scar_cli.sh — install the `scar` lexical-search CLI into ~/.claude/scripts/scar
#
# The wrapper delegates to <repo>/scripts/scar_query.py (the repo source of truth).
# It searches the main checkout AND any .worktrees/* for the script, so it works
# before this PR is merged into the main checkout.
#
# Idempotent. Backs up any existing wrapper. Run on each node (M5/Pro/Mini).
#
# NOTE: ~/.claude/ is a host_boundary-protected control-plane dir. Installing here
# is a legitimate control-plane edit — invoke with HOST_BOUNDARY_OFF=1 if the
# host_boundary hook is active (the designed valve, NOT a bypass of a gate).
set -uo pipefail

DEST="$HOME/.claude/scripts/scar"
mkdir -p "$HOME/.claude/scripts"

if [ -f "$DEST" ]; then
  ts="$(date +%Y%m%d-%H%M%S)"
  cp "$DEST" "$DEST.bak-pre-scarcli-$ts"
  echo "[scar-cli] backed up existing wrapper → $DEST.bak-pre-scarcli-$ts"
fi

# Quoted heredoc — the wrapper body must reach disk VERBATIM (no $repo / $@
# interpolation at write time; that corruption is the quoting trap this installer exists to avoid).
cat > "$DEST" <<'WRAPPER'
#!/usr/bin/env bash
# scar — cicatrix scar lexical search CLI (wrapper → scripts/scar_query.py)
# Installed by scripts/install_scar_cli.sh. Repo source of truth:
#   <repo>/scripts/scar_query.py
# Usage: scar query "<theme>" | scar query --list | scar query --family N
set -uo pipefail
SUB="${1:-}"
if [ "$SUB" = "query" ]; then shift; fi
for repo in "$HOME/nuzantara" "$HOME/nuzantara/.worktrees"/*; do
  if [ -f "$repo/scripts/scar_query.py" ]; then
    exec python3 "$repo/scripts/scar_query.py" "$@"
  fi
done
echo "scar: scar_query.py not found under ~/nuzantara (or its .worktrees)" >&2
exit 2
WRAPPER

chmod 755 "$DEST"
echo "[scar-cli] installed → $DEST"
echo "[scar-cli] smoke:"
"$DEST" query --list >/dev/null 2>&1 && echo "  ✅ scar query --list OK" || echo "  ⚠️  scar query --list failed (is the repo checkout present?)"
