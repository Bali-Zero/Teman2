#!/usr/bin/env bash
# telegram_notify.sh — send one Telegram message and PROVE whether it arrived.
#
# Replaces the `curl -s https://api.telegram.org/... ` one-liners scattered across the
# workflows, every one of which took curl's exit code as evidence of delivery. See the
# header of `telegram_verdict.sh` for why that is worthless (W104).
#
# Secrets come from the ENVIRONMENT, never from argv: an argument list is visible to
# `ps` and to anything reading /proc, which is superscar #4. The token is also never
# echoed — the URL that contains it is built inline and the failure path prints only
# the API's own `description` field.
#
#   env:  TELEGRAM_BOT_TOKEN        (required)
#         TELEGRAM_OWNER_CHAT_ID    (required unless --chat given)
#         TELEGRAM_API_BASE         (optional, default https://api.telegram.org)
#
#   telegram_notify.sh --text "..." [--parse-mode HTML] [--chat <id>] [--soft]
#   telegram_notify.sh --stdin      [--parse-mode HTML]        # body on stdin
#
# --soft: still LOG the refusal loudly (GitHub ::error:: annotation), but exit 0.
#   Use it ONLY where a failed notification must not invert the meaning of the run —
#   e.g. a success notification on a deploy that genuinely succeeded. Never use it on
#   an alarm whose whole purpose is to be the thing that speaks.
set -uo pipefail

TEXT=""
PARSE_MODE=""
CHAT="${TELEGRAM_OWNER_CHAT_ID:-}"
SOFT=0
API_BASE="${TELEGRAM_API_BASE:-https://api.telegram.org}"

while [ $# -gt 0 ]; do
  case "$1" in
    --text) TEXT="${2-}"; shift 2 ;;
    --stdin) TEXT="$(cat)"; shift ;;
    --parse-mode) PARSE_MODE="${2-}"; shift 2 ;;
    --chat) CHAT="${2-}"; shift 2 ;;
    --soft) SOFT=1; shift ;;
    *) printf '::error::telegram_notify: unknown argument %s\n' "$1" >&2; exit 64 ;;
  esac
done

fail() { # fail <verdict> <detail> [exit-code, default 1]
  # A refusal is LOGGED, always — the one thing the old call sites could not do.
  printf '::error::Telegram NOT delivered (%s): %s\n' "$1" "$2" >&2
  [ "${SOFT}" -eq 1 ] && exit 0
  exit "${3:-1}"
}

[ -n "${TELEGRAM_BOT_TOKEN:-}" ] || fail MISSING-TOKEN "TELEGRAM_BOT_TOKEN is empty in this context (a fork PR, or the secret is unset)"
[ -n "${CHAT}" ] || fail MISSING-CHAT "no chat id: pass --chat or set TELEGRAM_OWNER_CHAT_ID"
[ -n "${TEXT}" ] || fail EMPTY-TEXT "refusing to send an empty message"

args=(--data-urlencode "chat_id=${CHAT}" --data-urlencode "text=${TEXT}")
[ -n "${PARSE_MODE}" ] && args+=(--data-urlencode "parse_mode=${PARSE_MODE}")

# `-w` appends the status on its own final line. `-sS` keeps curl quiet but lets real
# transport errors reach stderr. No `--fail`: we WANT the body of a rejection, because
# the body is where Telegram explains itself.
resp="$(curl -sS -m 20 -X POST "${API_BASE}/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        "${args[@]}" -w $'\n%{http_code}' 2>/dev/null)" || resp=""

code="${resp##*$'\n'}"
body="${resp%$'\n'*}"
[ "${code}" = "${resp}" ] && { body=""; code=""; }   # curl produced nothing at all

# Take the verdict's EXIT CODE too, not just its word. `2` means CANNOT-VERIFY —
# "I could not tell" — and collapsing that onto `1` ("refused") would erase the one
# distinction this whole file is about: a rotated token needs a human, a dead socket
# may just need a retry. The `|| rc=$?` form is errexit-immune on purpose (W101: a
# bare assignment from a failing command substitution dies before the check that was
# written to handle it, the day someone adds `set -e` above).
verdict_rc=0
verdict="$("$(dirname "$0")/telegram_verdict.sh" "${code}" "${body}")" || verdict_rc=$?

if [ -z "${verdict}" ]; then
  # The judge itself did not answer (missing, unreadable, non-executable). That is
  # not a delivery and not a refusal — it is the blind-scan case, and it must never
  # read as either.
  fail CANNOT-VERIFY "telegram_verdict.sh produced no verdict (rc=${verdict_rc})" 2
fi

if [ "${verdict}" = "DELIVERED" ]; then
  printf 'Telegram delivered (chat %s).\n' "${CHAT}"
  exit 0
fi

# Print the API's own words, which name the half that is broken (a rotated token vs a
# chat that blocked the bot are one HTTP code apart and a world apart to fix).
desc="$(printf '%s' "${body}" | sed -n 's/.*"description"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
fail "${verdict}" "http=${code:-none} ${desc:-${body:-no body}}" "${verdict_rc}"
