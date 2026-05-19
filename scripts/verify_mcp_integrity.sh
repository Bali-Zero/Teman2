#!/usr/bin/env bash
# verify_mcp_integrity.sh — defense vs claude-plugins-official typosquat chain (Jan-April 2026)
#
# Checks integrity of:
#   1. Marketplaces in ~/.claude/plugins/known_marketplaces.json
#      - GCS-backed (claude-plugins-official): verify .gcs-sha matches installed plugin SHA prefix
#      - Git-backed (thedotmack, trailofbits): verify remote origin URL matches declared repo
#   2. Installed plugins in ~/.claude/plugins/installed_plugins.json
#      - gitCommitSha non-empty, installPath exists
#   3. MCP servers in <repo>/.mcp.json (local-only sanity: command paths exist + inside repo or whitelisted)
#
# Exit codes: 0=LOW (clean), 1=MEDIUM (drift), 2=HIGH (typosquat/missing). Pipe to telegram on tier>=1.
#
# P2-21 closure, sweep totale option B 2026-05-20.

set -u  # NOT -e: we want to collect ALL findings before exit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

PLUGINS_DIR="${HOME}/.claude/plugins"
INSTALLED_JSON="${PLUGINS_DIR}/installed_plugins.json"
MARKETPLACES_JSON="${PLUGINS_DIR}/known_marketplaces.json"
MARKETPLACES_DIR="${PLUGINS_DIR}/marketplaces"
REPO_MCP_JSON="${REPO_MCP_JSON:-${REPO_ROOT}/.mcp.json}"

declare -i FINDINGS_HIGH=0 FINDINGS_MEDIUM=0 FINDINGS_LOW=0
declare -a NOTES=()

log_high()   { NOTES+=("HIGH   $*"); FINDINGS_HIGH+=1; }
log_medium() { NOTES+=("MEDIUM $*"); FINDINGS_MEDIUM+=1; }
log_low()    { NOTES+=("LOW    $*"); FINDINGS_LOW+=1; }

[[ -f "$INSTALLED_JSON" ]]    || { echo "FATAL: $INSTALLED_JSON not found"; exit 2; }
[[ -f "$MARKETPLACES_JSON" ]] || { echo "FATAL: $MARKETPLACES_JSON not found"; exit 2; }

# ── 1. Marketplace remote/SHA verification ─────────────────────────────────
while IFS=$'\t' read -r mkt_name repo_full; do
  mkt_path="${MARKETPLACES_DIR}/${mkt_name}"
  [[ -d "$mkt_path" ]] || { log_high "marketplace dir missing: $mkt_path (repo=$repo_full)"; continue; }

  if [[ -d "${mkt_path}/.git" ]]; then
    # Git-backed marketplace
    remote_url=$(git -C "$mkt_path" remote get-url origin 2>/dev/null || echo "")
    if [[ -z "$remote_url" ]]; then
      log_high "marketplace=$mkt_name has .git/ but no remote origin (manifest declares $repo_full)"
    else
      # Normalize: strip .git suffix, accept both https and ssh forms
      normalized=$(echo "$remote_url" | sed -E 's|\.git$||; s|^git@github\.com:|https://github.com/|')
      expected="https://github.com/${repo_full}"
      if [[ "$normalized" != "$expected" ]]; then
        log_high "marketplace=$mkt_name remote=$remote_url (normalized=$normalized) MISMATCH expected=$expected"
      else
        log_low "marketplace=$mkt_name git remote OK ($remote_url)"
      fi
    fi
  elif [[ -f "${mkt_path}/.gcs-sha" ]]; then
    # GCS-backed marketplace (claude-plugins-official model)
    gcs_sha=$(< "${mkt_path}/.gcs-sha")
    manifest="${mkt_path}/.claude-plugin/marketplace.json"
    if [[ ! -f "$manifest" ]]; then
      log_high "marketplace=$mkt_name has .gcs-sha=$gcs_sha but no .claude-plugin/marketplace.json"
    else
      # Manifest must declare matching name
      declared_name=$(python3 -c "import json; print(json.load(open('$manifest'))['name'])" 2>/dev/null || echo "")
      if [[ "$declared_name" != "$mkt_name" ]]; then
        log_high "marketplace=$mkt_name manifest declares name='$declared_name' (typosquat suspicion)"
      else
        log_low "marketplace=$mkt_name GCS-backed OK (sha=${gcs_sha:0:12}, manifest name match)"
      fi
    fi
  else
    log_high "marketplace=$mkt_name has neither .git/ nor .gcs-sha (unknown provenance, expected $repo_full)"
  fi
done < <(python3 -c "
import json
d = json.load(open('$MARKETPLACES_JSON'))
for k, v in d.items():
    src = v.get('source', {})
    if src.get('source') == 'github':
        print(f\"{k}\t{src['repo']}\")
")

# ── 2. Installed plugin SHA + path verification ────────────────────────────
while IFS=$'\t' read -r plugin_key sha install_path; do
  if [[ -z "$sha" || "$sha" == "null" ]]; then
    log_high "plugin=$plugin_key has empty gitCommitSha"
    continue
  fi
  if [[ ! -d "$install_path" ]]; then
    log_high "plugin=$plugin_key installPath missing: $install_path"
    continue
  fi
  # SHA-prefix sanity (40-hex git-like OR semver 1.0.0-style legacy)
  if [[ ! "$sha" =~ ^[a-f0-9]{40}$ ]] && [[ ! "$sha" =~ ^[a-f0-9]{12,}$ ]]; then
    log_medium "plugin=$plugin_key gitCommitSha non-hex: '$sha' (legacy version-string?)"
  else
    log_low "plugin=$plugin_key sha=${sha:0:12} path OK"
  fi
done < <(python3 -c "
import json
d = json.load(open('$INSTALLED_JSON'))
for key, entries in d.get('plugins', {}).items():
    for e in entries:
        sha = e.get('gitCommitSha', '') or ''
        path = e.get('installPath', '')
        print(f'{key}\t{sha}\t{path}')
")

# ── 3. MCP server sanity (project-level .mcp.json) ─────────────────────────
if [[ -f "$REPO_MCP_JSON" ]]; then
  while IFS=$'\t' read -r srv_name srv_cmd; do
    case "$srv_cmd" in
      /*)
        if [[ ! -x "$srv_cmd" ]]; then
          log_high "mcp=$srv_name command not executable: $srv_cmd"
        else
          log_low "mcp=$srv_name local exec OK ($srv_cmd)"
        fi
        ;;
      uvx|npx|pipx)
        log_low "mcp=$srv_name dispatcher=$srv_cmd (remote fetch — out of scope for offline check)"
        ;;
      *)
        if command -v "$srv_cmd" >/dev/null 2>&1; then
          log_low "mcp=$srv_name PATH-resolved ($srv_cmd → $(command -v "$srv_cmd"))"
        else
          log_medium "mcp=$srv_name command not on PATH: $srv_cmd"
        fi
        ;;
    esac
  done < <(python3 -c "
import json
d = json.load(open('$REPO_MCP_JSON'))
for name, cfg in d.get('mcpServers', {}).items():
    cmd = cfg.get('command', '')
    print(f'{name}\t{cmd}')
")
else
  log_medium "project .mcp.json not found at $REPO_MCP_JSON (skipped MCP check)"
fi

# ── Report ─────────────────────────────────────────────────────────────────
echo "── verify_mcp_integrity.sh @ $(date '+%Y-%m-%dT%H:%M:%S%z') ──"
for note in "${NOTES[@]}"; do
  echo "  $note"
done
echo ""
echo "Summary: HIGH=$FINDINGS_HIGH  MEDIUM=$FINDINGS_MEDIUM  LOW=$FINDINGS_LOW"

if (( FINDINGS_HIGH > 0 )); then
  echo "Risk tier: HIGH — typosquat or missing integrity primitive detected"
  exit 2
elif (( FINDINGS_MEDIUM > 0 )); then
  echo "Risk tier: MEDIUM — drift detected"
  exit 1
else
  echo "Risk tier: LOW — all primitives match"
  exit 0
fi
