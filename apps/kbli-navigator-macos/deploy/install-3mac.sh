#!/bin/zsh
# install-3mac.sh — build KBLI Navigator once, deploy the .app to M5 + Pro + Mini.
# Fixes the ad-hoc-signature Gatekeeper trap (spec §9 F2): an ad-hoc-signed bundle copied to
# another Mac is killed by Gatekeeper ("damaged / cannot be opened") unless we strip the
# quarantine xattr AND re-sign it ON the destination machine.
#
# 2026-07-13 hardening (superscar #2 Esiste≠Armato): deploy is only DONE when the CONTENT
# of the deployed bundle is proven — after rsync+re-sign we shasum the dataset inside the
# installed .app on EVERY machine and compare against the built bundle. rsync exit 0 is a
# proxy; the hash of the file the app will actually read is the work. Also: build.sh's
# dataset auto-refresh used to leave Resources/ dirty forever (uncommitted residue, seen
# live 2026-07-08→13) — now the refresh is committed here, at the deploy checkpoint.
set -euo pipefail

ROOT="${0:A:h:h}"     # repo root (deploy/ is one level down)
cd "$ROOT"

# Fleet targets are the OTHER two machines, derived from the driver host. Only Pro has Xcode, so
# Pro drives (2026-10-08: from Pro `ssh pro` is refused, `ssh m5`/`ssh mini` work; from M5 the
# reverse). KBLI_DRIVER_HOST overrides `hostname -s` (tests); KBLI_REMOTE_TARGETS="m5 mini"
# overrides the derivation but may never list the driver itself.
driver_alias() {  # prints the fleet alias of the driver host, empty if unknown
  case "${(L)${KBLI_DRIVER_HOST:-$(hostname -s)}}" in
    nuzantara) echo pro ;;
    air-m5) echo m5 ;;
    mini-pro2) echo mini ;;
  esac
}

fleet_targets() {  # prints the space-separated remote targets, or returns 2 with a message
  local self; self="$(driver_alias)"
  if [[ -n "${KBLI_REMOTE_TARGETS:-}" ]]; then
    if [[ -n "$self" && " ${KBLI_REMOTE_TARGETS} " == *" $self "* ]]; then
      echo "✗ KBLI_REMOTE_TARGETS lists the driver itself ($self): it is installed locally, not over ssh" >&2
      return 2
    fi
    echo "${KBLI_REMOTE_TARGETS}"
    return 0
  fi
  case "$self" in
    pro) echo "m5 mini" ;;
    m5) echo "pro mini" ;;
    mini) echo "m5 pro" ;;
    *)
      echo "✗ unknown driver host '${KBLI_DRIVER_HOST:-$(hostname -s)}': set KBLI_REMOTE_TARGETS=\"a b\"" >&2
      return 2
      ;;
  esac
}

TARGETS_STR="$(fleet_targets)" || exit 2
if [[ "${1:-}" == "--print-targets" ]]; then
  echo "$TARGETS_STR"
  exit 0
fi

# The 3-Mac fleet always runs the INTERNAL variant (2026-08-09 app split; BKPM is a separate,
# on-demand build zipped to build/ only — see build.sh --variant). NAME CHANGE from the old
# "KBLI Navigator": the fleet's currently-installed copies on M5/Pro/Mini still carry the OLD
# name until the NEXT run of this script, which is a later phase (not executed here).
APP_NAME="KBLI Navigator - INTERNAL"
APP="$ROOT/build/$APP_NAME.app"
DATASET_REL="Contents/Resources/KBLI_2025_FINAL_CLEAN.json"

echo "▸ building on $(hostname)…"
./build.sh --variant internal

# The dataset is copied in by build.sh from the monorepo canonical and is never tracked here (gitignored), so there is nothing to commit.

SRC_HASH="$(shasum -a 256 "$APP/$DATASET_REL" | awk '{print $1}')"
echo "▸ built bundle dataset: ${SRC_HASH:0:12}"

# targets: ssh aliases of the OTHER two machines, from fleet_targets above (the driver is
# installed by a plain local copy, never over ssh to itself).
# App lives on the DESKTOP of all 3 machines (Zero's choice 2026-06-24): a visible, one-click
# icon on M5 + Pro + Mini. The remote home dir resolves to /Users/nuzantara on Pro/Mini.
LOCAL_DEST="$HOME/Desktop"
REMOTE_TARGETS=(${=TARGETS_STR})
FAILED=()

resign() {  # $1 = path to .app on the machine where this runs
  xattr -cr "$1" 2>/dev/null || true
  codesign --force --deep --sign - "$1" 2>/dev/null || true
}

echo "▸ installing locally → $LOCAL_DEST"
mkdir -p "$LOCAL_DEST"
rsync -a --delete "$APP" "$LOCAL_DEST/"
resign "$LOCAL_DEST/$APP_NAME.app"
LOCAL_HASH="$(shasum -a 256 "$LOCAL_DEST/$APP_NAME.app/$DATASET_REL" | awk '{print $1}')"
if [[ "$LOCAL_HASH" == "$SRC_HASH" ]]; then
  echo "  ✓ $(hostname): dataset ${LOCAL_HASH:0:12} matches build"
else
  echo "  ✗ $(hostname): dataset MISMATCH (${LOCAL_HASH:0:12} ≠ ${SRC_HASH:0:12})"
  FAILED+=("local")
fi

for T in "${REMOTE_TARGETS[@]}"; do
  echo "▸ deploying → $T"
  if ! ssh -o ConnectTimeout=8 "$T" 'true' 2>/dev/null; then
    echo "  ⚠︎ $T unreachable — skipped (re-run when it is back; fleet is NOT aligned)"
    FAILED+=("$T:unreachable")
    continue
  fi
  ssh "$T" 'mkdir -p ~/Desktop'
  rsync -a --delete "$APP" "$T":'~/Desktop/'
  # CRITICAL (F2): strip quarantine + re-sign ON the destination, else Gatekeeper blocks it.
  ssh "$T" "xattr -cr ~/Desktop/'$APP_NAME.app' 2>/dev/null; codesign --force --deep --sign - ~/Desktop/'$APP_NAME.app' 2>/dev/null; echo '  re-signed on '$T"
  # PROBE (superscar #2): the deployed CONTENT, not the rsync exit code.
  RHASH="$(ssh "$T" "shasum -a 256 ~/Desktop/'$APP_NAME.app'/$DATASET_REL" 2>/dev/null | awk '{print $1}')"
  if [[ "$RHASH" == "$SRC_HASH" ]]; then
    echo "  ✓ $T: dataset ${RHASH:0:12} matches build"
  else
    echo "  ✗ $T: dataset MISMATCH (${RHASH:0:12} ≠ ${SRC_HASH:0:12})"
    FAILED+=("$T:mismatch")
  fi
done

if (( ${#FAILED[@]} )); then
  echo "⚠︎ deploy INCOMPLETE: ${FAILED[*]} — the fleet does not serve one dataset."
  exit 1
fi
echo "✅ deployed + content-verified on all machines. Launch from the Desktop on each."
