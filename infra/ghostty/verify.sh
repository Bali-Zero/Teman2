#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  Prove the installed Ghostty profile is real, current, and doing its job.
#
#    bash infra/ghostty/verify.sh
#
#  Exit codes are a bit field, so several problems report at once:
#      1  config invalid or absent
#      2  installed copy has DRIFTED from the repo source
#      4  a declared capability is not actually working
#  0 means every check below passed.
#
#  This script reports; it never repairs. Each check states what it measured,
#  and a check that cannot run says so rather than passing quietly.
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${GHOSTTY_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/ghostty}"
# Every ghostty invocation below is pinned to the directory we are verifying
# (see the note in install.sh) so a check does not silently read some other XDG
# location. It is NOT total isolation: the macOS Application Support path is
# searched ahead of XDG regardless, which is why check 6b exists.
XDG_PARENT="$(dirname "$DEST_DIR")"
GHOSTTY_BIN="${GHOSTTY_BIN:-/Applications/Ghostty.app/Contents/MacOS/ghostty}"
RC=0
ok()   { echo "  ok    $*"; }
bad()  { echo "  FAIL  $*"; }
warn() { echo "  warn  $*"; }
note() { echo "        $*"; }

echo "Ghostty profile verification — $(hostname -s), macOS $(sw_vers -productVersion 2>/dev/null)"
echo

# ── 1. The binary ──────────────────────────────────────────────────────────
if [ ! -x "$GHOSTTY_BIN" ]; then
  bad "Ghostty not installed at $GHOSTTY_BIN"; exit 1
fi
ok "binary $("$GHOSTTY_BIN" --version 2>/dev/null | head -1)"

# ── 2. The config loads ────────────────────────────────────────────────────
VOUT="$(XDG_CONFIG_HOME="$XDG_PARENT" "$GHOSTTY_BIN" +validate-config 2>&1)"; VRC=$?
if [ $VRC -eq 0 ]; then ok "config validates (rc=0)"
else bad "config rejected (rc=$VRC): $VOUT"; RC=$((RC|1)); fi

# ── 3. The stale-filename trap ─────────────────────────────────────────────
# Ghostty reads `config` AND `config.ghostty` and merges them. Measured order:
# top-level config, top-level config.ghostty, config's includes, then
# config.ghostty's includes. So a leftover config.ghostty does not override this
# profile wholesale — it loses every key our included files set and wins every
# key they do not. Partial, silent, and position-dependent: retire it.
if [ -f "$DEST_DIR/config.ghostty" ]; then
  bad "$DEST_DIR/config.ghostty exists — it merges with 'config' and wins on every key this profile does not set"
  RC=$((RC|1))
else
  ok "no shadowing config.ghostty"
fi

# ── 4. Drift: installed copy vs repo source ────────────────────────────────
# Compared against the repo working tree. On a machine whose checkout is behind
# origin/main this can read as drift when the live copy is simply newer — the
# fleet-wide authority is scripts/lint_home_fork.py, which compares against
# origin/main. This check is the local, fast one.
drift=0
for pair in "config|config" "fleet.ghostty|fleet.ghostty" "keys.ghostty|keys.ghostty"; do
  s="$SRC_DIR/${pair%%|*}"; d="$DEST_DIR/${pair##*|}"
  if [ ! -f "$d" ]; then bad "missing installed file: $d"; RC=$((RC|2)); drift=1
  elif ! cmp -s "$s" "$d"; then bad "drift: $d differs from $s"; RC=$((RC|2)); drift=1
  fi
done
# machine.ghostty is installed under a fixed name from a per-host source, so it
# must be compared against the profile THIS host should have. Matching against
# "any profile in machines/" was the earlier version and it passed happily with
# M5's profile installed on Pro — including a working-directory that does not
# exist on this machine. Same hostname mapping as install.sh.
expected_machine() {
  local h; h="$(hostname -s 2>/dev/null || hostname)"
  case "$h" in
    Nuzantara|nuzantara) echo pro  ;;
    Air-M5|air-m5)       echo m5   ;;
    Mini-Pro2|mini-pro2) echo mini ;;
    *) return 1 ;;
  esac
}
EXPECT="${GHOSTTY_EXPECT_MACHINE:-$(expected_machine || true)}"
if [ -z "$EXPECT" ]; then
  warn "unrecognised host '$(hostname -s)' — cannot tell which profile belongs here (check skipped, not passed)"
  RC=$((RC|4))
elif [ ! -f "$DEST_DIR/machine.ghostty" ]; then
  bad "missing installed file: $DEST_DIR/machine.ghostty"; RC=$((RC|2)); drift=1
elif cmp -s "$SRC_DIR/machines/$EXPECT.ghostty" "$DEST_DIR/machine.ghostty"; then
  ok "machine profile installed: $EXPECT (matches this host)"
else
  actual="none"
  for m in "$SRC_DIR"/machines/*.ghostty; do
    cmp -s "$m" "$DEST_DIR/machine.ghostty" && actual="$(basename "$m" .ghostty)"
  done
  bad "wrong machine profile: this host is '$EXPECT' but machine.ghostty is '$actual'"
  RC=$((RC|2)); drift=1
fi

# The configured working directory has to exist, or every new window opens
# somewhere unintended. This is what catches a foreign profile in practice.
WD="$(XDG_CONFIG_HOME="$XDG_PARENT" "$GHOSTTY_BIN" +show-config --default=false 2>/dev/null | sed -n 's/^working-directory = //p' | head -1)"
if [ -n "$WD" ] && [ ! -d "$WD" ]; then
  bad "working-directory does not exist on this machine: $WD"; RC=$((RC|2))
fi
[ $drift -eq 0 ] && ok "installed copies match the repo source"

# ── 5. The font actually resolves ──────────────────────────────────────────
# An unresolvable family does NOT error — it silently falls back to a face with
# no Nerd glyphs, so this must be measured, not assumed. Probed with an isolated
# XDG_CONFIG_HOME so the configured family cannot answer for the tested one.
FAM="$(grep -m1 '^font-family = ' "$SRC_DIR/fleet.ghostty" | sed 's/^font-family = //')"
if [ -n "$FAM" ]; then
  FOUT="$(XDG_CONFIG_HOME=/nonexistent-xdg "$GHOSTTY_BIN" +show-face --font-family="$FAM" --string=A 2>&1)"
  if printf '%s' "$FOUT" | grep -qF "$FAM"; then
    ok "font resolves: $FAM"
  else
    warn "font '$FAM' does NOT resolve here — falling back to: $FOUT"
    note "install it: brew install --cask font-jetbrains-mono-nerd-font"
    RC=$((RC|4))
  fi
else
  warn "could not read font-family from fleet.ghostty (check skipped, not passed)"
  RC=$((RC|4))
fi

# ── 6. SSH terminfo — the fleet's daily defect ─────────────────────────────
# xterm-ghostty is unknown on a fresh remote host; the shell integration
# installs it on first ssh and caches the host. Empty cache with reachable
# peers means the wrapper has never actually run.
CACHE="$(XDG_CONFIG_HOME="$XDG_PARENT" "$GHOSTTY_BIN" +ssh-cache 2>&1)"; CRC=$?
if [ $CRC -ne 0 ]; then
  bad "+ssh-cache failed (rc=$CRC): $CACHE"
  RC=$((RC|4))
else
  if printf '%s' "$CACHE" | grep -qi "no hosts"; then
    warn "ssh terminfo cache is EMPTY — no remote host has xterm-ghostty yet"
    note "it fills on your first interactive ssh from a Ghostty window"
    note "(the wrapper is a shell function; it does not exist in non-interactive shells)"
  else
    ok "ssh terminfo cache: $(printf '%s' "$CACHE" | tr '\n' ' ')"
  fi
fi

# ── 6b. The location that outranks everything ──────────────────────────────
# macOS searches $HOME/Library/Application Support/com.mitchellh.ghostty/
# config.ghostty BEFORE any XDG location. Nothing this profile installs can
# override a file sitting there, so its presence is a finding, not a detail.
# Judged by CONTENT, not by existence: Ghostty.app creates this file empty on
# its own (observed 2026-08-18 — the CLI does not, the running app does), so a
# presence test would fail forever on every machine and train you to ignore this
# script. An empty or comment-only file changes nothing; a file with settings
# in it silently outranks the whole profile.
APPSUP="$HOME/Library/Application Support/com.mitchellh.ghostty/config.ghostty"
if [ -f "$APPSUP" ]; then
  # `grep -c` prints its count on stdout AND exits 1 when that count is zero, so
  # a `|| echo 0` fallback appends a SECOND zero: the variable becomes "0\n0" and
  # the numeric test below dies with "integer expression expected" — which is
  # what it did on all three machines. grep already emits the number; take it and
  # only substitute when the capture is empty (file unreadable).
  APPSUP_SETTINGS="$(grep -cvE '^[[:space:]]*(#.*)?$' "$APPSUP" 2>/dev/null)"
  case "$APPSUP_SETTINGS" in
    ''|*[!0-9]*) bad "cannot count settings in $APPSUP — treating as a finding, not as empty"
                 RC=$((RC|4)); APPSUP_SETTINGS=0 ;;
  esac
  if [ "$APPSUP_SETTINGS" -gt 0 ]; then
    bad "$APPSUP holds $APPSUP_SETTINGS setting(s) and takes PRECEDENCE over everything installed here"
    RC=$((RC|1))
  else
    ok "Application Support config present but empty (no effect)"
  fi
else
  ok "no higher-priority config in Application Support"
fi

# ── 7. Effective values worth eyeballing ───────────────────────────────────
echo
echo "  effective (non-default) values:"
XDG_CONFIG_HOME="$XDG_PARENT" "$GHOSTTY_BIN" +show-config --default=false 2>/dev/null \
  | grep -E '^(theme|font-family|font-size|scrollback-limit|background-opacity|background-blur|cursor-color|working-directory|shell-integration-features|notify-on-command-finish|macos-option-as-alt|macos-icon) =' \
  | sed 's/^/        /'

echo
if [ $RC -eq 0 ]; then echo "ALL CHECKS PASSED (rc=0)"; else echo "PROBLEMS FOUND (rc=$RC)"; fi
exit $RC
