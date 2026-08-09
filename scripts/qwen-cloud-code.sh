#!/usr/bin/env bash
#
# qwen-cloud-code — hardened dispatch wrapper for the qwen-cloud-code council/verify seat.
#
# STATUS: CANDIDATE SEAT — UNARMED. It will refuse to run until the operator
# rotates the seat credential into Keychain (service `qwen-cloud-code-token`).
# Gate decision 2026-08-08 (Fable 5, SHIP-AFTER-FIXES) + council Q2 ruling:
# this seat never self-arms; arming = operator rotation + Claude-lane merge.
#
# Precedent: scripts/claude-glm.sh (deployed as ~/.local/bin symlink, Keychain-
# only credentials, no secrets in argv/env-files/repo). Differences, per the
# 2026-08-08 red-team findings (Legge-5 surface + yolo defaults):
#   - Legge 5 verb scan BEFORE anything runs: no submit/publish*/channel/serve.
#   - No yolo: --approval-mode=yolo (and accept_all) refused; review stays read-only.
#   - Credential gate: Keychain service `qwen-cloud-code-token` ONLY; the old
#     cleartext settings.json path is a P0 scar, never read or recreated here.
#   - Env hygiene: ANTHROPIC_API_KEY never set; PII lane stays Ollama (Law 2).
#
set -euo pipefail

KEYCHAIN_SERVICE="qwen-cloud-code-token"

die() { printf '❌ qwen-cloud-code: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. Legge 5 + yolo scan
for arg in "$@"; do
  case "$arg" in
    submit|publish|publish-assets|channel|serve)
      die "verb '$arg' refused — Legge 5: this wrapper cannot publish or send outward" ;;
    --approval-mode=yolo|--approval-mode=accept_all|--approval-mode=auto_edit)
      die "approval mode '$arg' refused — review lanes run read-only/plan" ;;
  esac
done

# ---------------------------------------------------------------- 2. Credential gate (Keychain only)
if ! TOKEN="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)"; then
  die "Keychain service '$KEYCHAIN_SERVICE' absent — seat UNARMED by gate decision 2026-08-08.
    Cure (operator): rotate the credential, then
      security add-generic-password -s '$KEYCHAIN_SERVICE' -a qwen-cloud-code -w '<new-key>'
    and remove the old cleartext key from ~/.qwen/settings.json."
fi
[ -n "$TOKEN" ] || die "Keychain entry '$KEYCHAIN_SERVICE' is empty"

# ---------------------------------------------------------------- 3. Binary
QWEN_BIN="$(command -v qwen || true)"
[ -x "$QWEN_BIN" ] || QWEN_BIN="$HOME/.local/share/mise/installs/node/22/bin/qwen"
[ -x "$QWEN_BIN" ] || die "qwen binary not found (PATH + mise node 22)"

# ---------------------------------------------------------------- 4. Exec (env hygiene)
export BAILIAN_TOKEN_PLAN_API_KEY="$TOKEN"
unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN 2>/dev/null || true
exec "$QWEN_BIN" "$@"
