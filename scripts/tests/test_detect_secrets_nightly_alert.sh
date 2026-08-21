#!/usr/bin/env bash
# test_detect_secrets_nightly_alert.sh — guilt+innocence for
# scripts/ci/detect_secrets_nightly_alert.sh (audit lever L3, 2026-08-21).
#
# No network, no real Telegram gateway: TELEGRAM_NOTIFY_BIN points at a fake
# gateway (same pattern as scripts/tests/test_tg_sender_migration.sh) that
# only records the text it was asked to send and exits with a scripted code,
# so this corpus proves the MESSAGE-BUILDING and EXIT-CODE-PROPAGATION
# contract without ever touching curl.
#
# Assertions:
#   1. GUILT: a captured findings summary is quoted verbatim in the message.
#   2. INNOCENCE: no summary file (or an empty one) never fabricates a
#      "secret found" claim — it states plainly that nothing was captured
#      (W114/W106 — a message may not inventory a state it cannot prove).
#   3. The event name and run URL both land in the message.
#   4. The gateway's exit code is propagated, not swallowed, in both
#      directions (delivered vs refused) — this script is a message
#      composer, not a second verdict judge; telegram_notify.sh/
#      telegram_verdict.sh already own that judgment (W104), and this test
#      only proves the composer does not eat their answer.
#
# Run: bash scripts/tests/test_detect_secrets_nightly_alert.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALERT_SCRIPT="${REPO_ROOT}/scripts/ci/detect_secrets_nightly_alert.sh"

PASS=0
FAIL=0
ok()  { PASS=$((PASS + 1)); printf '  \xe2\x9c\x93 %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  \xe2\x9c\x97 %s\n' "$1"; }

if [ ! -f "${ALERT_SCRIPT}" ]; then
  bad "missing ${ALERT_SCRIPT}"
  echo "Results: ${PASS} passed, ${FAIL} failed"
  exit 1
fi

WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "${WORKDIR}"; }
trap cleanup EXIT

# Fake gateway: writes its --text argument verbatim to CAPTURED_TEXT_FILE and
# exits with whatever FAKE_GATEWAY_EXIT says (default 0 = "delivered").
cat > "${WORKDIR}/fake_telegram_notify.sh" <<'FAKE'
#!/usr/bin/env bash
set -uo pipefail
TEXT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --text) TEXT="${2-}"; shift 2 ;;
    *) shift ;;
  esac
done
printf '%s' "${TEXT}" > "${CAPTURED_TEXT_FILE}"
exit "${FAKE_GATEWAY_EXIT:-0}"
FAKE
chmod +x "${WORKDIR}/fake_telegram_notify.sh"

echo "── GUILT: a captured findings summary is quoted verbatim"
printf '%s\n' "unaudited findings (of 3 total): apps/x.py:12 AWSKeyDetector" > "${WORKDIR}/summary.txt"
CAPTURED_TEXT_FILE="${WORKDIR}/captured1.txt" \
FAKE_GATEWAY_EXIT=0 \
TELEGRAM_NOTIFY_BIN="${WORKDIR}/fake_telegram_notify.sh" \
EVENT_NAME=schedule \
RUN_URL="https://github.com/Bali-Zero/Teman2/actions/runs/12345" \
SUMMARY_FILE="${WORKDIR}/summary.txt" \
  bash "${ALERT_SCRIPT}"
RC1=$?

if [ "${RC1}" -eq 0 ] && grep -q "AWSKeyDetector" "${WORKDIR}/captured1.txt" 2>/dev/null; then
  ok "summary content reaches the composed message"
else
  bad "summary content missing from composed message (rc=${RC1})"
fi
if grep -q "schedule" "${WORKDIR}/captured1.txt" 2>/dev/null; then
  ok "event name lands in the message"
else
  bad "event name missing from message"
fi
if grep -q "actions/runs/12345" "${WORKDIR}/captured1.txt" 2>/dev/null; then
  ok "run URL lands in the message"
else
  bad "run URL missing from message"
fi

echo "── INNOCENCE: no summary file never fabricates a finding"
CAPTURED_TEXT_FILE="${WORKDIR}/captured2.txt" \
FAKE_GATEWAY_EXIT=0 \
TELEGRAM_NOTIFY_BIN="${WORKDIR}/fake_telegram_notify.sh" \
EVENT_NAME=workflow_dispatch \
RUN_URL="https://example/run/2" \
SUMMARY_FILE="${WORKDIR}/does-not-exist.txt" \
  bash "${ALERT_SCRIPT}" >/dev/null
if grep -qi "no findings summary captured" "${WORKDIR}/captured2.txt" 2>/dev/null; then
  ok "missing summary is stated honestly, not fabricated"
else
  bad "missing-summary case did not produce the honest fallback text"
fi
if grep -qi "AKIA\|AWSKeyDetector" "${WORKDIR}/captured2.txt" 2>/dev/null; then
  bad "innocence violated: a finding-shaped string appeared with no summary file"
else
  ok "no finding-shaped content fabricated when nothing was captured"
fi

echo "── INNOCENCE: an EMPTY summary file is treated the same as absent"
: > "${WORKDIR}/empty-summary.txt"
CAPTURED_TEXT_FILE="${WORKDIR}/captured3.txt" \
FAKE_GATEWAY_EXIT=0 \
TELEGRAM_NOTIFY_BIN="${WORKDIR}/fake_telegram_notify.sh" \
EVENT_NAME=schedule \
RUN_URL="https://example/run/3" \
SUMMARY_FILE="${WORKDIR}/empty-summary.txt" \
  bash "${ALERT_SCRIPT}" >/dev/null
if grep -qi "no findings summary captured" "${WORKDIR}/captured3.txt" 2>/dev/null; then
  ok "empty summary file falls back to the honest message, same as absent"
else
  bad "empty summary file was not treated as 'no summary captured'"
fi

echo "── exit-code propagation: gateway REFUSAL is not swallowed"
CAPTURED_TEXT_FILE="${WORKDIR}/captured4.txt" \
FAKE_GATEWAY_EXIT=1 \
TELEGRAM_NOTIFY_BIN="${WORKDIR}/fake_telegram_notify.sh" \
EVENT_NAME=schedule \
RUN_URL="https://example/run/4" \
SUMMARY_FILE="${WORKDIR}/summary.txt" \
  bash "${ALERT_SCRIPT}" >/dev/null
RC4=$?
if [ "${RC4}" -eq 1 ]; then
  ok "gateway refusal (exit 1) propagates through the composer"
else
  bad "gateway refusal was swallowed: composer exited ${RC4}, expected 1"
fi

CAPTURED_TEXT_FILE="${WORKDIR}/captured5.txt" \
FAKE_GATEWAY_EXIT=2 \
TELEGRAM_NOTIFY_BIN="${WORKDIR}/fake_telegram_notify.sh" \
EVENT_NAME=schedule \
RUN_URL="https://example/run/5" \
SUMMARY_FILE="${WORKDIR}/summary.txt" \
  bash "${ALERT_SCRIPT}" >/dev/null
RC5=$?
if [ "${RC5}" -eq 2 ]; then
  ok "gateway CANNOT-VERIFY (exit 2) propagates through the composer"
else
  bad "gateway CANNOT-VERIFY was not propagated: composer exited ${RC5}, expected 2"
fi

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
if [ "${FAIL}" -gt 0 ]; then
  exit 1
fi
exit 0
