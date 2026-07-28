#!/usr/bin/env bash
# telegram_verdict.sh — decide whether a Telegram sendMessage was actually DELIVERED.
#
# WHY THIS FILE EXISTS (W104, 2026-07-25, recurring on the CI surface 2026-07-28):
# `curl` exits 0 when the server answers, whatever it answers. A revoked or rotated
# bot token makes the Telegram API reply HTTP 401 with a perfectly well-formed JSON
# body — and the shell step goes GREEN. Every alarm in this repo that judged its own
# delivery by curl's exit code was, by construction, unable to report its own silence.
# W104 said it in one line: judge the REPLY, never the exit code.
#
# The judgement lives here, alone and pure, for the same reason
# `queue_rearm_classify.sh` does: a verdict that can only be exercised by making a
# real network call is a verdict nobody tests. This takes (http_code, body) as plain
# strings and prints one token; the corpus in `test_telegram_verdict.sh` drives it
# directly, with no network and no stub server.
#
# Usage:  telegram_verdict.sh <http_code> <body>
# Prints exactly one of:
#   DELIVERED         the API accepted the message ("ok":true on 200)
#   REFUSED-AUTH      token rejected — rotated, revoked, or wrong (401)
#   REFUSED-TARGET    chat unreachable — bad chat_id, bot blocked/kicked (400/403)
#   THROTTLED         rate limited (429) — the message did NOT go out
#   REFUSED           any other explicit rejection from the API
#   CANNOT-VERIFY     no usable answer (curl never ran, timed out, empty body)
# Exit code mirrors the verdict: 0 only for DELIVERED, 1 for every refusal,
# 2 for CANNOT-VERIFY — because "I could not check" is not "it is fine".
set -uo pipefail

code="${1-}"
body="${2-}"

emit() { printf '%s\n' "$1"; }

# CANNOT-VERIFY first and unconditionally. An empty code means curl itself never
# produced one (DNS failure, timeout, killed step). Reading that as anything other
# than "unknown" is the exact fail-open this file exists to prevent: a blind scan is
# not a clean scan.
if [ -z "${code}" ] || [ "${code}" = "000" ]; then
  emit CANNOT-VERIFY
  exit 2
fi

case "${code}" in
200)
  # 200 alone is NOT delivery. Telegram answers 200 with {"ok":false,...} for some
  # rejections, so the body is the authority and the status line is not.
  if printf '%s' "${body}" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true'; then
    emit DELIVERED
    exit 0
  fi
  if [ -z "${body}" ]; then
    # 200 with nothing in it: the transport answered but said nothing we can read.
    emit CANNOT-VERIFY
    exit 2
  fi
  emit REFUSED
  exit 1
  ;;
401) emit REFUSED-AUTH; exit 1 ;;
403) emit REFUSED-TARGET; exit 1 ;;
400)
  # 400 covers both "chat not found" and "can't parse entities" (a malformed
  # parse_mode payload). Both mean the operator was not told; they differ only in
  # which half to fix, and the caller prints the API's own description for that.
  emit REFUSED-TARGET
  exit 1
  ;;
429) emit THROTTLED; exit 1 ;;
*) emit REFUSED; exit 1 ;;
esac
