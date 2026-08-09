#!/usr/bin/env bash
#
# qwen-cloud-code — hardened dispatch wrapper for the qwen-cloud-code council/verify seat.
# v2 (2026-08-09): Claude PR review (REQUEST-CHANGES, reviews/claude-pr-review.md)
# live-proved three bypasses in v1 (bare --yolo, space-separated --approval-mode,
# fictional auto_edit spelling) + the missing --comment block Fable's gate required,
# and proved the 0600 mitigation on settings.json is not durable (bare qwen resets it).
#
# v2 design change: stop enumerating dangerous spellings (blocklist) — STRIP the whole
# approval/yolo arg family from argv, refuse Legge-5 verbs and --comment outright, and
# re-assert the 0600 mitigation on EVERY invocation. This build's top-level help exposes
# no approval-mode/yolo/config-override flags (bundled docs are ahead of the binary), so
# nothing legitimate is lost by stripping; if a future build re-adds them, we are defended.
#
# Known residual gap (documented, not faked): this build exposes NO chat-recording
# disable surface (no flag, no settings key found in the installed package). Transcript
# retention remains harness state; revisit when the build exposes a control.
#
set -euo pipefail

KEYCHAIN_SERVICE="qwen-cloud-code-token"
SETTINGS="$HOME/.qwen/settings.json"

die() { printf '❌ qwen-cloud-code: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. Legge 5 verb/flag scan
for arg in "$@"; do
  case "$arg" in
    submit|publish|publish-assets|channel|serve)
      die "verb '$arg' refused — Legge 5: this wrapper cannot publish or send outward" ;;
    --comment|--comment=*)
      die "flag '$arg' refused — posts to a PR (Fable gate 2026-08-08, fix Q2)" ;;
  esac
done

# ---------------------------------------------------------------- 2. Strip the approval/yolo arg family (never enumerate, never forward)
ARGS=()
skip_next=0
for arg in "$@"; do
  if [ "$skip_next" = "1" ]; then skip_next=0; continue; fi
  case "$arg" in
    --yolo|--approval-mode|--approval-mode=*)
      [ "$arg" = "--approval-mode" ] && skip_next=1
      continue ;;
  esac
  ARGS+=("$arg")
done

# ---------------------------------------------------------------- 3. Durable perms re-assertion (bare qwen resets settings.json to 0644)
[ -f "$SETTINGS" ] && chmod 0600 "$SETTINGS" 2>/dev/null || true

# ---------------------------------------------------------------- 4. Credential gate (Keychain only)
if ! TOKEN="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)"; then
  die "Keychain service '$KEYCHAIN_SERVICE' absent — seat UNARMED.
    Operator cure (value-preserving, no rotation needed):
      security add-generic-password -s '$KEYCHAIN_SERVICE' -a qwen-cloud-code -w '<credential>'"
fi
[ -n "$TOKEN" ] || die "Keychain entry '$KEYCHAIN_SERVICE' is empty"

# ---------------------------------------------------------------- 5. Binary
QWEN_BIN="$(command -v qwen || true)"
[ -x "$QWEN_BIN" ] || QWEN_BIN="$HOME/.local/share/mise/installs/node/22/bin/qwen"
[ -x "$QWEN_BIN" ] || die "qwen binary not found (PATH + mise node 22)"

# ---------------------------------------------------------------- 6. Exec (env hygiene)
export BAILIAN_TOKEN_PLAN_API_KEY="$TOKEN"
unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN 2>/dev/null || true
exec "$QWEN_BIN" "${ARGS[@]}"
