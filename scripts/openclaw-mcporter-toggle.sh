#!/usr/bin/env bash
# openclaw-mcporter-toggle.sh — Sprint 0 Track A3
#
# Inspect / toggle mcporter servers based on empirical usage in OpenClaw
# gateway.log over the last 30 days.
#
# Usage:
#   bash scripts/openclaw-mcporter-toggle.sh --list                   # show servers + last-30d invocation counts
#   bash scripts/openclaw-mcporter-toggle.sh --disable-idle --dry-run # default; print what disable would do
#   bash scripts/openclaw-mcporter-toggle.sh --disable-idle --apply   # actually toggle in mcp.json
#   bash scripts/openclaw-mcporter-toggle.sh --enable <server>        # re-enable a single server
#
# Source of truth:
#   ~/.config/mcporter/mcp.json  (server registry; NOT OpenClaw's openclaw.json)
#   ~/.openclaw/logs/gateway.log (invocation history; tailing 50_000 lines)
#
# Idle definition: server with 0 lines matching `mcporter call <server>.<tool>`
# in the last 50_000 lines of gateway.log. The threshold is intentionally
# empirical — re-running in a few weeks adapts to changed usage.
#
# Backup: --apply always copies mcp.json to mcp.json.pre-mcporter-toggle-<date>
# before writing.
#
# Reference: brainstorm 2026-05-02 round 2 § "mcporter idle 200MB RAM saving"
# Cicatrix: NEVER edit ~/.openclaw/openclaw.json from this script (separate
# concern; mcporter config lives in ~/.config/mcporter/mcp.json).

set -euo pipefail

CONFIG="${HOME}/.config/mcporter/mcp.json"
GATEWAY_LOG="${HOME}/.openclaw/logs/gateway.log"
TAIL_LINES="${MCPORTER_TOGGLE_TAIL_LINES:-50000}"
KEEP_FORCE=( "nuzantara-mcp" "nuzantara-mcp-advanced" "filesystem" "memory" )

MODE=""
TARGET=""
APPLY=0
DRY=1   # default --dry-run
case "${1:-}" in
  --list)         MODE="list" ;;
  --disable-idle) MODE="disable-idle" ;;
  --enable)       MODE="enable"; TARGET="${2:-}"; shift ;;
  ""|--help|-h)
    sed -n '2,30p' "$0"
    exit 0
    ;;
  *)
    echo "ERROR: unknown command '$1' — see --help" >&2
    exit 2
    ;;
esac

while [[ $# -gt 1 ]]; do
  case "${2:-}" in
    --apply)    APPLY=1; DRY=0 ;;
    --dry-run)  APPLY=0; DRY=1 ;;
    "")         break ;;
  esac
  shift
done

if [[ ! -f "$CONFIG" ]]; then
  echo "ERROR: $CONFIG not found — mcporter not installed on this host?" >&2
  exit 0   # exit 0 so cron/automation doesn't error out on a clean host
fi
if [[ ! -f "$GATEWAY_LOG" ]]; then
  echo "WARNING: $GATEWAY_LOG not found — usage data unavailable, --disable-idle will fail safe (no-op)" >&2
fi

# require jq for editing
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq not found in PATH — required for safe JSON edits" >&2
  exit 2
fi

list_servers() {
  jq -r '.mcpServers | keys[]' "$CONFIG"
}

count_invocations() {
  local srv="$1"
  if [[ ! -f "$GATEWAY_LOG" ]]; then
    echo 0
    return
  fi
  tail -n "$TAIL_LINES" "$GATEWAY_LOG" \
    | grep -cE "mcporter call ${srv}\." || true
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

case "$MODE" in
  list)
    printf '%-30s %s\n' SERVER INVOCATIONS_30D
    while IFS= read -r srv; do
      n="$(count_invocations "$srv")"
      printf '%-30s %s\n' "$srv" "$n"
    done < <(list_servers)
    ;;
  disable-idle)
    BACKUP="${CONFIG}.pre-mcporter-toggle-$(date +%F)"
    DECISIONS=""
    while IFS= read -r srv; do
      n="$(count_invocations "$srv")"
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
      cp "$CONFIG" "$BACKUP"
      echo "[mcporter-toggle] backup: $BACKUP"
      while IFS= read -r line; do
        if [[ "$line" =~ ^DISABLE\ ([^\ ]+) ]]; then
          srv="${BASH_REMATCH[1]}"
          tmp="$(mktemp)"
          jq --arg srv "$srv" '.mcpServers[$srv].disabled = true' "$CONFIG" > "$tmp"
          mv "$tmp" "$CONFIG"
          echo "[mcporter-toggle] disabled: $srv"
        fi
      done <<< "$DECISIONS"
      echo "[mcporter-toggle] done. restart OpenClaw to re-snapshot:"
      echo "[mcporter-toggle]   launchctl kickstart -k gui/\$(id -u)/ai.openclaw.gateway"
    else
      echo "[mcporter-toggle] dry-run only. add --apply to write."
    fi
    ;;
  enable)
    if [[ -z "$TARGET" ]]; then
      echo "ERROR: --enable requires a server name" >&2
      exit 2
    fi
    if (( APPLY == 1 )); then
      tmp="$(mktemp)"
      jq --arg srv "$TARGET" 'del(.mcpServers[$srv].disabled)' "$CONFIG" > "$tmp"
      mv "$tmp" "$CONFIG"
      echo "[mcporter-toggle] enabled: $TARGET"
    else
      echo "[mcporter-toggle] would enable: $TARGET (--apply to commit)"
    fi
    ;;
esac
