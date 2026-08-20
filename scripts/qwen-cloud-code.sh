#!/usr/bin/env bash
#
# qwen-cloud-code — hardened dispatch wrapper for the qwen-cloud-code council/verify seat.
# v3 (2026-08-09): Claude focused re-review (REQUEST-CHANGES round 2) proved two defects
# in v2: (NEW-1, P0) `qwen review run` defaults the CHILD to --approval-mode=yolo and the
# v2 strip removed even safe --approval-mode=plan attempts, so every wrapper-mediated
# review ran yolo — a live violation of Fable gate Q2; and the "no recording-disable
# surface" claim was false — `--chat-recording` exists on the review command family
# (verified live by the reviewer, qwen 0.21.7). v2 blind spot: only top-level `qwen --help`
# had been checked.
#
# v3 design:
#   - 0600 re-assertion moved BEFORE every scan (refused paths re-assert too; NEW-3).
#   - Legge-5 verb/flag refusal unchanged (submit/publish*/channel/serve, --comment).
#   - Strip the whole approval/yolo arg family, INCLUDING --yolo=* (NEW-2).
#   - review family: INJECT --approval-mode=plan --chat-recording=false after the strip
#     (the child documents plan as the non-yolo mode; --chat-recording=false satisfies
#     Fable Q5 for the wrapper's primary sanctioned lane).
#   - non-review top-level invocations get no injected flags (the top-level help exposes
#     neither flag; appending would break them). Their transcript retention remains
#     harness state — the one declared residual, now scoped precisely.
#
# v4 (2026-08-21): fleet-arming — Keychain access over non-interactive ssh (Pro/Mini) fails
# with "User interaction is not allowed" (locked, not absent). Credential gate now falls
# back to ~/.qwen/settings.json IFF its mode is exactly 0600 AS FOUND (before step 0's own
# chmod runs — else the fallback's own mode check would be neutered by step 0) and
# env.BAILIAN_TOKEN_PLAN_API_KEY is non-empty; logs which source was accepted (never the
# value — W106 class).
#
set -euo pipefail

KEYCHAIN_SERVICE="qwen-cloud-code-token"
SETTINGS="$HOME/.qwen/settings.json"

die() { printf '❌ qwen-cloud-code: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 0. Durable perms re-assertion (first, so refused paths also re-assert)
# Capture the mode as FOUND before tightening it: step 4's settings.json fallback must
# judge the state a caller actually left it in, not the state we just silently fixed —
# a file discovered 0644 has an untrusted disclosure history (family #4, "secret in the
# clear") even after this chmod hardens it going forward. Fixing before judging would
# make the "only if exactly 0600" gate below vacuous (check≠action, W99/W109 class).
SETTINGS_FOUND_MODE=""
if [ -f "$SETTINGS" ]; then
  SETTINGS_FOUND_MODE="$(stat -f '%Lp' "$SETTINGS" 2>/dev/null || stat -c '%a' "$SETTINGS" 2>/dev/null || true)"
  chmod 0600 "$SETTINGS" 2>/dev/null || true
fi

# ---------------------------------------------------------------- 1. Legge 5 verb/flag scan
for arg in "$@"; do
  case "$arg" in
    submit|publish|publish-assets|channel|serve)
      die "verb '$arg' refused — Legge 5: this wrapper cannot publish or send outward" ;;
    --comment|--comment=*)
      die "flag '$arg' refused — posts to a PR (Fable gate 2026-08-08, fix Q2)" ;;
  esac
done

# ---------------------------------------------------------------- 2. Strip approval/yolo family; detect the review family
ARGS=()
skip_next=0
REVIEW_MODE=0
for arg in "$@"; do
  if [ "$skip_next" = "1" ]; then skip_next=0; continue; fi
  case "$arg" in
    review) REVIEW_MODE=1; ARGS+=("$arg"); continue ;;
    --yolo|--yolo=*|--approval-mode|--approval-mode=*)
      [ "$arg" = "--approval-mode" ] && skip_next=1
      continue ;;
  esac
  ARGS+=("$arg")
done

# ---------------------------------------------------------------- 3. review family: force plan + recording-off
if [ "$REVIEW_MODE" = "1" ]; then
  ARGS+=("--approval-mode=plan" "--chat-recording=false")
fi

# ---------------------------------------------------------------- 4. Credential gate (Keychain, settings.json fallback when Keychain is locked)
# Over ssh (Pro/Mini non-interactive), `security find-generic-password` fails with
# "User interaction is not allowed" — a locked-Keychain state, not an absent-secret
# state. Both must arm the seat if a usable ~/.qwen/settings.json exists. The `if
# TOKEN="$(...)"` form is errexit-safe (condition context is exempt from `set -e`,
# W101 class) — no `|| true` needed here.
TOKEN=""
TOKEN_SOURCE=""
if TOKEN="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)" && [ -n "$TOKEN" ]; then
  TOKEN_SOURCE="keychain"
else
  TOKEN=""
  if [ -f "$SETTINGS" ]; then
    if [ "$SETTINGS_FOUND_MODE" = "600" ]; then
      SETTINGS_TOKEN="$(python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as f:
        d = json.load(f)
    print(d.get("env", {}).get("BAILIAN_TOKEN_PLAN_API_KEY", ""))
except Exception:
    print("")
' "$SETTINGS" 2>/dev/null || true)"
      if [ -n "$SETTINGS_TOKEN" ]; then
        TOKEN="$SETTINGS_TOKEN"
        TOKEN_SOURCE="settings.json"
      fi
    fi
  fi
fi

if [ -z "$TOKEN" ]; then
  die "Keychain service '$KEYCHAIN_SERVICE' absent or locked (e.g. non-interactive ssh) AND
    '$SETTINGS' fallback unavailable (missing / not exactly 0600 / no env.BAILIAN_TOKEN_PLAN_API_KEY) — seat UNARMED.
    Operator cure (value-preserving, no rotation needed):
      security add-generic-password -s '$KEYCHAIN_SERVICE' -a qwen-cloud-code -w '<credential>'
    or ensure '$SETTINGS' is chmod 0600 with env.BAILIAN_TOKEN_PLAN_API_KEY set."
fi
# Log WHICH source was accepted, never the value (W106 class: name the source, not the secret).
printf 'qwen-cloud-code: token source accepted: %s\n' "$TOKEN_SOURCE" >&2

# ---------------------------------------------------------------- 5. Binary
QWEN_BIN="$(command -v qwen || true)"
[ -x "$QWEN_BIN" ] || QWEN_BIN="$HOME/.local/share/mise/installs/node/22/bin/qwen"
[ -x "$QWEN_BIN" ] || die "qwen binary not found (PATH + mise node 22)"

# ---------------------------------------------------------------- 6. Exec (env hygiene)
export BAILIAN_TOKEN_PLAN_API_KEY="$TOKEN"
unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN 2>/dev/null || true
exec "$QWEN_BIN" "${ARGS[@]}"
