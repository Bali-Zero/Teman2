#!/usr/bin/env bash
# Corpus for telegram_verdict.sh — GUILT and INNOCENCE, per superscar #3's antidote:
# a guard merged with only guilt cases is half a guard, and the half it is missing is
# the one that blocks legitimate work.
#
# Every guilt fixture below is a real Telegram API response shape, not a paraphrase.
# W104's own lesson was that the FIRST antibody written for it was a check on the exit
# code — decorative by construction — and the reason nobody noticed is that the fixture
# beside it had been typed from memory instead of copied off the wire.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VERDICT="${HERE}/telegram_verdict.sh"
pass=0; fail=0

check() { # check <expected-verdict> <expected-exit> <label> <http_code> <body>
  local want="$1" want_rc="$2" label="$3" code="$4" body="$5"
  local got rc
  got="$("${VERDICT}" "${code}" "${body}")"; rc=$?
  if [ "${got}" = "${want}" ] && [ "${rc}" -eq "${want_rc}" ]; then
    pass=$((pass+1))
  else
    fail=$((fail+1))
    printf '  FAIL  %s\n        want=%s/rc%s  got=%s/rc%s\n' "${label}" "${want}" "${want_rc}" "${got}" "${rc}"
  fi
}

echo "== INNOCENCE: a real delivery must not be reported as a failure =="
check DELIVERED 0 "the ordinary success body" 200 \
  '{"ok":true,"result":{"message_id":4211,"chat":{"id":8847435604,"type":"private"},"date":1785000000,"text":"x"}}'
check DELIVERED 0 "success with whitespace around the colon" 200 \
  '{"ok" : true,"result":{"message_id":1}}'

echo "== GUILT: the shapes that used to go green =="
# THE case this whole file exists for: token rotated, curl exits 0, step was green.
check REFUSED-AUTH 1 "rotated/revoked bot token" 401 \
  '{"ok":false,"error_code":401,"description":"Unauthorized"}'
check REFUSED-TARGET 1 "chat id wrong or never started the bot" 400 \
  '{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}'
check REFUSED-TARGET 1 "malformed HTML in parse_mode — message silently never sent" 400 \
  '{"ok":false,"error_code":400,"description":"Bad Request: can'"'"'t parse entities: Unsupported start tag \"b\" at byte offset 12"}'
check REFUSED-TARGET 1 "bot was blocked or kicked" 403 \
  '{"ok":false,"error_code":403,"description":"Forbidden: bot was blocked by the user"}'
check THROTTLED 1 "rate limited — the message did NOT go out" 429 \
  '{"ok":false,"error_code":429,"description":"Too Many Requests: retry after 31","parameters":{"retry_after":31}}'
check REFUSED 1 "HTTP 200 but ok:false — status line lies, body is the authority" 200 \
  '{"ok":false,"error_code":400,"description":"Bad Request: message text is empty"}'
check REFUSED 1 "server error" 502 '<html>502 Bad Gateway</html>'

echo "== FAIL-CLOSED: no answer is not a good answer =="
check CANNOT-VERIFY 2 "curl never produced a status (DNS down, timeout, step killed)" "" ""
check CANNOT-VERIFY 2 "curl's own no-connection sentinel" "000" ""
check CANNOT-VERIFY 2 "200 with an empty body — transport answered, said nothing" 200 ""

echo "== ANTI-SUBSTRING: the word 'true' elsewhere is not a delivery =="
# Superscar #3: the verdict must match the FIELD, not the presence of a token that
# happens to read like success. A description quoting the word would flip a naive grep.
check REFUSED 1 "the literal word true inside a description" 200 \
  '{"ok":false,"description":"Bad Request: field must be true"}'
check REFUSED 1 "ok:false while a nested field is true" 200 \
  '{"ok":false,"result":{"is_bot":true}}'

echo "== THE WRAPPER: the verdict is worthless if the caller drops it =="
# Written after the wrapper was caught doing exactly that: it captured
# telegram_verdict.sh's stdout and discarded its EXIT CODE, so CANNOT-VERIFY
# (2) came out as a plain refusal (1). Both are "fail", so nothing was red and
# nothing looked wrong — the distinction between "the token is dead, fetch a
# human" and "I could not tell, this may be a flake" had simply evaporated.
# A judge nobody's caller listens to is the same organ as no judge.
NOTIFY="${HERE}/telegram_notify.sh"
PORTFILE="$(mktemp)"; SRVLOG="$(mktemp)"
python3 - "${PORTFILE}" > "${SRVLOG}" 2>&1 <<'PY' &
import http.server, json, sys, threading
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.dumps({"ok": False, "error_code": 401,
                           "description": "Unauthorized"}).encode()
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H)          # port 0: never collide
open(sys.argv[1], "w").write(str(srv.server_address[1]))
srv.serve_forever()
PY
SRV_PID=$!
disown "${SRV_PID}" 2>/dev/null || true   # keep the shell's reaper quiet on kill
trap 'kill "${SRV_PID}" 2>/dev/null' EXIT

PORT=""
for _ in $(seq 1 60); do
  PORT="$(cat "${PORTFILE}" 2>/dev/null || true)"
  [ -n "${PORT}" ] && break
  sleep 0.1
done

wrap() { # wrap <expected-rc> <label> <api-base> [notify-args...]
  local want="$1" label="$2"; shift 2
  local rc
  TELEGRAM_BOT_TOKEN=fake TELEGRAM_OWNER_CHAT_ID=123 \
  TELEGRAM_API_BASE="$1" "${NOTIFY}" "${@:2}" >/dev/null 2>&1
  rc=$?
  if [ "${rc}" -eq "${want}" ]; then
    pass=$((pass+1))
  else
    fail=$((fail+1)); printf '  FAIL  %s\n        want rc%s got rc%s\n' "${label}" "${want}" "${rc}"
  fi
}

if [ -z "${PORT}" ]; then
  fail=$((fail+1)); printf '  FAIL  fake API never came up — cannot test the wrapper\n'
  printf '        (a corpus that silently skips its own subject is the defect it tests for)\n'
  cat "${SRVLOG}" || true
else
  wrap 1 "401 from the API → refusal, rc 1" "http://127.0.0.1:${PORT}" --text probe
  wrap 0 "--soft downgrades a refusal to a warning" "http://127.0.0.1:${PORT}" --soft --text probe
  # Port 9 (discard) refuses instantly: curl yields no status at all.
  wrap 2 "no answer at all → CANNOT-VERIFY, rc 2 (NOT 1)" "http://127.0.0.1:9" --text probe
  # A delivery must still be a delivery: without this, "always fail" would pass.
  wrap 1 "empty text is refused before any network call" "http://127.0.0.1:${PORT}" --text ""
fi

kill "${SRV_PID}" 2>/dev/null; trap - EXIT
rm -f "${PORTFILE}" "${SRVLOG}"

printf '\n  passed=%d failed=%d\n' "${pass}" "${fail}"
[ "${fail}" -eq 0 ] || exit 1
echo "  telegram_verdict corpus: OK"
