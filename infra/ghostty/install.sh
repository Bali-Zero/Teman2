#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  Install the Nuzantara Ghostty profile onto THIS machine.
#
#    bash infra/ghostty/install.sh              # install (backs up first)
#    bash infra/ghostty/install.sh --dry-run    # show what would change
#    bash infra/ghostty/install.sh --machine m5 # force a profile
#
#  Safe by construction: it backs up whatever is already there, installs, then
#  VALIDATES — and if validation fails it restores the backup and exits non-zero.
#  A machine is never left with a config Ghostty cannot load.
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${GHOSTTY_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/ghostty}"
# Ghostty discovers its config as <XDG_CONFIG_HOME>/ghostty/config, so to make
# any check act on the directory we are actually writing to — not on whatever
# the invoking shell happens to point at — we validate with XDG_CONFIG_HOME set
# to this directory's parent. With the default destination that is exactly the
# normal lookup; with an overridden one it is the difference between proving
# this install and proving an unrelated file.
XDG_PARENT="$(dirname "$DEST_DIR")"
GHOSTTY_BIN="${GHOSTTY_BIN:-/Applications/Ghostty.app/Contents/MacOS/ghostty}"
DRY_RUN=0
FORCE_MACHINE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --machine) FORCE_MACHINE="${2:-}"; shift ;;
    -h|--help) sed -n '2,14p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

die() { echo "FAIL: $*" >&2; exit 1; }
say() { echo "  $*"; }

# ── Which machine is this? ─────────────────────────────────────────────────
# By hostname, because the username is not unique across the fleet (Pro and
# Mini are both `nuzantara`) and the hostname is.
detect_machine() {
  local h; h="$(hostname -s 2>/dev/null || hostname)"
  case "$h" in
    Nuzantara|nuzantara)     echo pro  ;;
    Air-M5|air-m5)           echo m5   ;;
    Mini-Pro2|mini-pro2)     echo mini ;;
    *) return 1 ;;
  esac
}

MACHINE="${FORCE_MACHINE:-$(detect_machine || true)}"
[ -n "$MACHINE" ] || die "unrecognised host '$(hostname -s)'. Pass --machine pro|m5|mini."
[ -f "$SRC_DIR/machines/$MACHINE.ghostty" ] || die "no profile for machine '$MACHINE'"

echo "Ghostty profile install"
say "machine : $MACHINE  ($(hostname -s), $(sw_vers -productVersion 2>/dev/null))"
say "source  : $SRC_DIR"
say "dest    : $DEST_DIR"

[ "$(basename "$DEST_DIR")" = "ghostty" ] || die "destination must be a directory named 'ghostty' (got $DEST_DIR) — Ghostty only looks for <config-home>/ghostty/config"
[ -x "$GHOSTTY_BIN" ] || die "Ghostty binary not found at $GHOSTTY_BIN"
say "ghostty : $("$GHOSTTY_BIN" --version 2>/dev/null | head -1)"

# ── What we are about to place ─────────────────────────────────────────────
# machine.ghostty is a COPY of machines/<machine>.ghostty under a fixed name,
# so ~/.config/ghostty/config can include one stable filename on every host.
declare -a PLAN=(
  "$SRC_DIR/config|$DEST_DIR/config"
  "$SRC_DIR/fleet.ghostty|$DEST_DIR/fleet.ghostty"
  "$SRC_DIR/keys.ghostty|$DEST_DIR/keys.ghostty"
  "$SRC_DIR/machines/$MACHINE.ghostty|$DEST_DIR/machine.ghostty"
)

if [ "$DRY_RUN" -eq 1 ]; then
  echo
  echo "DRY RUN — nothing will be written."
  for p in "${PLAN[@]}"; do
    src="${p%%|*}"; dst="${p##*|}"
    if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
      say "same     $dst"
    elif [ -f "$dst" ]; then
      say "REPLACE  $dst"
    else
      say "create   $dst"
    fi
  done
  # The stale-name trap: `config.ghostty` is read TOO and merged in, winning on
  # every key this profile does not set. Leaving it produces a patchwork config.
  [ -f "$DEST_DIR/config.ghostty" ] && say "RETIRE   $DEST_DIR/config.ghostty  (merges in and wins on keys this profile leaves unset)"
  exit 0
fi

# ── Back up ────────────────────────────────────────────────────────────────
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$DEST_DIR/.backup-$STAMP"
mkdir -p "$DEST_DIR" || die "cannot create $DEST_DIR"
if compgen -G "$DEST_DIR/*" >/dev/null 2>&1; then
  mkdir -p "$BACKUP" || die "cannot create backup dir"
  for f in "$DEST_DIR"/*; do
    [ -f "$f" ] || continue
    cp -p "$f" "$BACKUP/" || die "backup of $f failed"
  done
  say "backup  : $BACKUP  ($(find "$BACKUP" -type f | wc -l | tr -d ' ') file/s)"
else
  say "backup  : nothing to back up (fresh install)"
  BACKUP=""
fi

restore() {
  [ -n "$BACKUP" ] || return 0
  echo "  rolling back from $BACKUP" >&2
  rm -f "$DEST_DIR"/config "$DEST_DIR"/fleet.ghostty "$DEST_DIR"/keys.ghostty "$DEST_DIR"/machine.ghostty
  for f in "$BACKUP"/*; do [ -f "$f" ] && cp -p "$f" "$DEST_DIR/"; done
}

# ── Install ────────────────────────────────────────────────────────────────
for p in "${PLAN[@]}"; do
  src="${p%%|*}"; dst="${p##*|}"
  cp "$src" "$dst" || { restore; die "copy failed: $src -> $dst"; }
  say "wrote   : $dst"
done

# Retire the stale filename rather than deleting it: it must not remain (it
# merges in and wins on any key this profile leaves unset), but the previous
# content is kept on disk under a dated name in case something in it is wanted.
if [ -f "$DEST_DIR/config.ghostty" ]; then
  mv "$DEST_DIR/config.ghostty" "$DEST_DIR/config.ghostty.retired-$STAMP" \
    || { restore; die "could not retire config.ghostty"; }
  say "retired : config.ghostty -> config.ghostty.retired-$STAMP"
fi

# ── Prove it loads ─────────────────────────────────────────────────────────
# rc captured on its own line: a pipe would hide it (this is the W97 lesson).
VOUT="$(XDG_CONFIG_HOME="$XDG_PARENT" "$GHOSTTY_BIN" +validate-config 2>&1)"; VRC=$?
if [ $VRC -ne 0 ]; then
  echo "  validation FAILED (rc=$VRC):" >&2
  echo "$VOUT" >&2
  restore
  die "config rejected by Ghostty — previous config restored, nothing lost."
fi
say "validate: OK (rc=0)"

echo
echo "Installed. Reload a running Ghostty with cmd+shift+comma."
echo "Opacity, blur and the Dock icon need a full quit and relaunch."
echo "Verify with: bash $SRC_DIR/verify.sh"
