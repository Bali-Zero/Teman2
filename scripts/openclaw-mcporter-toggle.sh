#!/usr/bin/env bash
# openclaw-mcporter-toggle.sh — Sprint 0 Track A3
#
# Inspect / toggle mcporter servers based on empirical usage in OpenClaw
# gateway.log over the last ~50k log lines (best-effort tail; NOT a strict
# 30-day timestamp filter — round-2 reviewer correctly flagged the doc was
# overstated, see "Tail-only audit" caveat below).
#
# Usage:
#   bash scripts/openclaw-mcporter-toggle.sh --list                   # show servers + tail-window invocation counts
#   bash scripts/openclaw-mcporter-toggle.sh --disable-idle [--dry-run|--apply]  # default: dry-run
#   bash scripts/openclaw-mcporter-toggle.sh --enable <server> [--apply]
#
# Source of truth:
#   ~/.config/mcporter/mcp.json  (server registry; NOT OpenClaw's openclaw.json)
#   ~/.openclaw/logs/gateway.log (invocation history; tail of last $TAIL_LINES)
#
# Idle definition: server with 0 lines matching `mcporter call <server>.<tool>`
# in the LAST $TAIL_LINES lines of gateway.log (default 50,000). This is
# tail-only — it does NOT correlate with timestamps. A very-low-frequency
# server with one call older than the tail window will appear idle. Tune
# $MCPORTER_TOGGLE_TAIL_LINES if your gateway.log is unusually high-volume.
#
# Tail-only audit: round-2 review noted the doc claimed "last 30 days" while
# the implementation is a flat tail. The default tail of 50k lines covers
# ~2-3 months of typical Pro gateway.log volume; if log throughput grows,
# bump the env var rather than introducing brittle timestamp parsing of
# ANSI-escape-prefixed log lines.
#
# Missing-log fail-safe: if $GATEWAY_LOG does NOT exist, --disable-idle
# refuses to disable any server (treats every server as "unknown usage")
# — round-2 reviewer flagged the previous implementation that disabled
# all non-allowlisted servers when the log was missing.
#
# Backup: --apply ALWAYS copies mcp.json to mcp.json.pre-mcporter-toggle-<date>
# before writing — applies to BOTH --disable-idle AND --enable now (round-2
# review fixed the gap where --enable skipped the backup).
#
# Reference: brainstorm 2026-05-02 round 2 § "mcporter idle 200MB RAM saving"
# Cicatrix: NEVER edit ~/.openclaw/openclaw.json from this script (separate
# concern; mcporter config lives in ~/.config/mcporter/mcp.json).
# Round-2 cross-LLM review (2026-05-02): fixes (a) arg parsing for
# `--disable-idle --apply` (was silently dry-running), (b) missing-log fail-safe,
# (c) regex injection on server names in count_invocations(), (d) backup
# also for --enable.

set -euo pipefail

CONFIG="${HOME}/.config/mcporter/mcp.json"
GATEWAY_LOG="${HOME}/.openclaw/logs/gateway.log"
TAIL_LINES="${MCPORTER_TOGGLE_TAIL_LINES:-50000}"
KEEP_FORCE=( "nuzantara-mcp" "nuzantara-mcp-advanced" "filesystem" "memory" )

MODE=""
TARGET=""
APPLY=0
DRY=1   # default --dry-run

# ── round-2 fix: arg parsing rewritten as positional consumer ─────────
#
# Old form used `case "${1:-}"` then a separate `while [[ $# -gt 1 ]]` loop
# reading `$2` — this caused `--disable-idle --apply` to silently dry-run
# because after the case-block consumed `$1`, the loop's `[[ $# -gt 1 ]]`
# guard refused to enter when only one arg remained. We now consume each
# token in order, mutating MODE/APPLY/DRY/TARGET as we go. Safe under both
# `--disable-idle --apply` AND `--apply --disable-idle` AND `--enable foo`.

if [[ $# -eq 0 ]]; then
  sed -n '2,30p' "$0"
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)         MODE="list"; shift ;;
    --disable-idle) MODE="disable-idle"; shift ;;
    --enable)
      MODE="enable"
      shift
      TARGET="${1:-}"
      if [[ -z "$TARGET" || "$TARGET" =~ ^-- ]]; then
        echo "ERROR: --enable requires a server name" >&2
        exit 2
      fi
      shift
      ;;
    --apply)    APPLY=1; DRY=0; shift ;;
    --dry-run)  APPLY=0; DRY=1; shift ;;
    --help|-h)  sed -n '2,30p' "$0"; exit 0 ;;
    *)
      echo "ERROR: unknown argument '$1' — see --help" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$MODE" ]]; then
  echo "ERROR: missing mode (one of: --list / --disable-idle / --enable <server>)" >&2
  exit 2
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "ERROR: $CONFIG not found — mcporter not installed on this host?" >&2
  exit 0   # exit 0 so cron/automation doesn't error out on a clean host
fi

GATEWAY_LOG_PRESENT=1
if [[ ! -f "$GATEWAY_LOG" ]]; then
  echo "WARNING: $GATEWAY_LOG not found — usage data unavailable" >&2
  GATEWAY_LOG_PRESENT=0
fi

# require jq for editing
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq not found in PATH — required for safe JSON edits" >&2
  exit 2
fi

list_servers() {
  jq -r '.mcpServers | keys[]' "$CONFIG"
}

# Server-name validation: defensively reject anything that is not a safe
# identifier. mcporter server keys in `mcp.json` should match this regex
# in practice; rejecting an oddly-named server prevents jq/grep injection
# and signals a config issue early.
validate_server_name() {
  local srv="$1"
  if [[ ! "$srv" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "ERROR: server name '$srv' contains unsupported characters" >&2
    return 1
  fi
}

# ── round-2 fix: regex-safe match in grep ─────────────────────────────
# Use grep -F (fixed-string) on the literal prefix, no regex metacharacter
# interpretation. Server names with dots like "my.server" no longer match
# unrelated "myXserver.tool" lines. Round-2 reviewer (Gemini, DeepSeek,
# GPT-5.5) flagged regex injection; this closes the path.
count_invocations() {
  local srv="$1"
  validate_server_name "$srv" || return 1
  if (( GATEWAY_LOG_PRESENT == 0 )); then
    # Fail-safe: if we can't observe the log, we don't claim "0 invocations".
    # Sentinel value 99999 ensures the server is treated as ACTIVE by the
    # idle-disable rule (which only disables zero-count servers).
    echo 99999
    return 0
  fi
  tail -n "$TAIL_LINES" "$GATEWAY_LOG" \
    | grep -cF "mcporter call ${srv}." || true
}

is_keep_force() {
  local srv="$1"
  local k
  for k in "${KEEP_FORCE[@]}"; do
    if [[ "$k" == "$srv" ]]; then
      return 0
    fi
  done
  return 1
}

backup_config() {
  local backup="${CONFIG}.pre-mcporter-toggle-$(date +%F)"
  if [[ ! -f "$backup" ]]; then
    cp "$CONFIG" "$backup"
    echo "[mcporter-toggle] backup: $backup"
  else
    echo "[mcporter-toggle] backup already exists today: $backup"
  fi
}

case "$MODE" in
  list)
    if (( GATEWAY_LOG_PRESENT == 0 )); then
      echo "[mcporter-toggle] WARNING: gateway.log missing — counts will show 99999 (sentinel: unobservable)" >&2
    fi
    printf '%-30s %s\n' SERVER INVOCATIONS_TAIL
    while IFS= read -r srv; do
      n="$(count_invocations "$srv")"
      printf '%-30s %s\n' "$srv" "$n"
    done < <(list_servers)
    ;;
  disable-idle)
    if (( GATEWAY_LOG_PRESENT == 0 )); then
      echo "[mcporter-toggle] REFUSE: gateway.log missing — cannot reliably classify idle servers." >&2
      echo "[mcporter-toggle] Either restore the log or invoke each --enable/--disable manually." >&2
      exit 3
    fi
    DECISIONS=""
    while IFS= read -r srv; do
      n="$(count_invocations "$srv")" || continue
      if (( n > 0 )); then
        DECISIONS+="keep   $srv (invocations=$n)"$'\n'
        continue
      fi
      if is_keep_force "$srv"; then
        DECISIONS+="keep   $srv (KEEP_FORCE allowlist)"$'\n'
        continue
      fi
      DECISIONS+="DISABLE $srv (idle, not in allowlist)"$'\n'
    done < <(list_servers)
    echo "$DECISIONS"
    if (( APPLY == 1 )); then
      backup_config
      # ── round-2 fix: single-pass jq instead of N writes ──────────────
      # Old loop did `mv tmp CONFIG` per disable; race window with the
      # OpenClaw scheduler reading mcp.json. Now we build the full set
      # of disabled servers in one pass and apply with one atomic mv.
      DISABLE_LIST=()
      while IFS= read -r line; do
        if [[ "$line" =~ ^DISABLE\ ([^\ ]+) ]]; then
          DISABLE_LIST+=( "${BASH_REMATCH[1]}" )
        fi
      done <<< "$DECISIONS"

      if (( ${#DISABLE_LIST[@]} == 0 )); then
        echo "[mcporter-toggle] no idle servers — no changes"
      else
        # Build a JSON array of names and let jq do the bulk update.
        names_json=$(printf '%s\n' "${DISABLE_LIST[@]}" | jq -R . | jq -s .)
        tmp="$(mktemp)"
        jq --argjson names "$names_json" '
          reduce $names[] as $n (.; .mcpServers[$n].disabled = true)
        ' "$CONFIG" > "$tmp"
        mv "$tmp" "$CONFIG"
        echo "[mcporter-toggle] disabled ${#DISABLE_LIST[@]} server(s) atomically: ${DISABLE_LIST[*]}"
      fi
      echo "[mcporter-toggle] hot-reload OpenClaw to pick up changes:"
      echo "[mcporter-toggle]   launchctl kickstart -k gui/\$(id -u)/ai.openclaw.gateway"
    else
      echo "[mcporter-toggle] dry-run only. add --apply to write."
    fi
    ;;
  enable)
    validate_server_name "$TARGET" || exit 2
    # Confirm the server actually exists in the config — refuse to create
    # a new entry just by enabling. Round-2 review flagged the gap.
    if ! jq -e --arg srv "$TARGET" '.mcpServers | has($srv)' "$CONFIG" >/dev/null; then
      echo "ERROR: server '$TARGET' is not present in $CONFIG" >&2
      exit 4
    fi
    if (( APPLY == 1 )); then
      backup_config
      tmp="$(mktemp)"
      jq --arg srv "$TARGET" 'del(.mcpServers[$srv].disabled)' "$CONFIG" > "$tmp"
      mv "$tmp" "$CONFIG"
      echo "[mcporter-toggle] enabled: $TARGET"
    else
      echo "[mcporter-toggle] would enable: $TARGET (--apply to commit)"
    fi
    ;;
esac
