#!/usr/bin/env bash
# Hermetic test for rotate_telegram_token.sh: temp secrets file, FAKE tokens assembled at run time
# (no token-shaped literal in this source: the repo secret guards scan it). Exit 0 = all pass.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SUT="$HERE/rotate_telegram_token.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export TG_SECRETS_FILE="$T/secrets.env"
fails=0
ok()  { echo "ok   $1"; }
bad() { echo "FAIL $1"; fails=$((fails + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

rep() { local c="$1" n="$2" s=""; while [ "${#s}" -lt "$n" ]; do s="$s$c"; done; printf '%s' "$s"; }
mk() { printf '%s%s%s%s' "$1" ":" "$2" "$(rep "$3" 34)"; }
OLD=$(mk 1111111111 A b)
NEW=$(mk 2222222222 B c)
SHORT=$(mk 333 C d)
BADCH="$(mk 4444444444 D e)!"

seed() {
  printf '# secrets\nexport DATABASE_URL=keepme\nexport TELEGRAM_BOT_TOKEN=%s\nOTHER=1\n' "$OLD" > "$TG_SECRETS_FILE"
  chmod 600 "$TG_SECRETS_FILE"; rm -f "$TG_SECRETS_FILE".bak-*
}
run() { printf '%s\n' "$1" | bash "$SUT" > "$T/out" 2> "$T/err"; echo $? > "$T/rc"; }
rc() { cat "$T/rc"; }
leak() { ! grep -qF -e "$OLD" -e "$NEW" -e "$SHORT" -e "$BADCH" "$T/out" "$T/err"; }
fmode() { stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1"; }
inode() { stat -c %i "$1" 2>/dev/null || stat -f %i "$1"; }

seed
before_inode=$(inode "$TG_SECRETS_FILE")
run "$SHORT"
check "short token rejected" '[ "$(rc)" -ne 0 ]'
check "rejection leaves file byte-identical" 'grep -qF -e "$OLD" "$TG_SECRETS_FILE" && ! ls "$TG_SECRETS_FILE".bak-* >/dev/null 2>&1'
run "$BADCH"
check "bad-charset token rejected" '[ "$(rc)" -ne 0 ]'
run ""
check "empty input rejected" '[ "$(rc)" -ne 0 ]'

run "$NEW"
check "valid token accepted (rc 0)" '[ "$(rc)" -eq 0 ]'
after_inode=$(inode "$TG_SECRETS_FILE")
check "atomic rename replaced the inode" '[ "$before_inode" != "$after_inode" ]'
check "line replaced, export form kept" 'grep -qxF "export TELEGRAM_BOT_TOKEN=$NEW" "$TG_SECRETS_FILE"'
check "other lines untouched" 'grep -qx "export DATABASE_URL=keepme" "$TG_SECRETS_FILE" && grep -qx "OTHER=1" "$TG_SECRETS_FILE" && [ "$(wc -l < "$TG_SECRETS_FILE")" -eq 4 ]'
check "file mode preserved (600)" '[ "$(fmode "$TG_SECRETS_FILE")" = 600 ]'
bak=$(ls "$TG_SECRETS_FILE".bak-* 2>/dev/null | head -1)
check "backup exists, mode 600, holds the old token" '[ -n "$bak" ] && [ "$(fmode "$bak")" = 600 ] && grep -qF -e "$OLD" "$bak"'
check "no token value in stdout/stderr" leak
check "no temp file left behind" '[ -z "$(ls -A "$T" | grep "\.tmp\.")" ]'

run "$NEW"
check "second run is an idempotent no-op (rc 0)" '[ "$(rc)" -eq 0 ] && grep -q "nothing to do" "$T/out"'
check "second run keeps the same inode" '[ "$(inode "$TG_SECRETS_FILE")" = "$after_inode" ]'
check "second run made no second backup" '[ "$(ls "$TG_SECRETS_FILE".bak-* | wc -l)" -eq 1 ]'
check "second run leaks nothing" leak

bash "$SUT" --check > "$T/out" 2> "$T/err" < /dev/null; echo $? > "$T/rc"
check "--check reports SET, shape ok, no value" '[ "$(rc)" -eq 0 ] && grep -qx "TELEGRAM_BOT_TOKEN: SET" "$T/out" && grep -qx "shape: ok" "$T/out" && leak'

seed
bash "$SUT" --dry-run > "$T/out" 2> "$T/err" < /dev/null; echo $? > "$T/rc"
check "--dry-run names file+line, writes nothing, no value" '[ "$(rc)" -eq 0 ] && grep -q "line 3 of" "$T/out" && grep -qF "$OLD" "$TG_SECRETS_FILE" && ! ls "$TG_SECRETS_FILE".bak-* >/dev/null 2>&1 && leak'

printf 'A=1\n' > "$TG_SECRETS_FILE"
bash "$SUT" --check > "$T/out" 2> "$T/err" < /dev/null; echo $? > "$T/rc"
check "no token line: --check says UNSET, non-zero" '[ "$(rc)" -ne 0 ] && grep -q "UNSET" "$T/out"'
run "$NEW"
check "no token line: apply refuses" '[ "$(rc)" -ne 0 ] && ! grep -qF "$NEW" "$TG_SECRETS_FILE"'

printf 'TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_BOT_TOKEN=%s\n' "$OLD" "$OLD" > "$TG_SECRETS_FILE"
run "$NEW"
check "duplicate token lines: apply refuses" '[ "$(rc)" -ne 0 ] && ! grep -qF "$NEW" "$TG_SECRETS_FILE"'

printf 'TELEGRAM_BOT_TOKEN="%s"\n' "$OLD" > "$TG_SECRETS_FILE"; chmod 600 "$TG_SECRETS_FILE"
run "$NEW"
check "plain+quoted form replaced, no export added" '[ "$(rc)" -eq 0 ] && grep -qxF "TELEGRAM_BOT_TOKEN=$NEW" "$TG_SECRETS_FILE"'

rm -f "$TG_SECRETS_FILE"; printf 'TELEGRAM_BOT_TOKEN=%s\n' "$OLD" > "$T/real"; ln -s "$T/real" "$TG_SECRETS_FILE"
run "$NEW"
check "symlinked secrets file refused" '[ "$(rc)" -ne 0 ]'

rm -f "$TG_SECRETS_FILE"
printf 'TELEGRAM_BOT_TOKEN="%s\n' "$NEW" > "$TG_SECRETS_FILE"; chmod 600 "$TG_SECRETS_FILE"; rm -f "$TG_SECRETS_FILE".bak-*
run "$NEW"
check "unpaired quote is not mistaken for the same value" '[ "$(rc)" -eq 0 ] && ! grep -q "nothing to do" "$T/out" && grep -qxF "TELEGRAM_BOT_TOKEN=$NEW" "$TG_SECRETS_FILE"'

printf 'A=1\r\nTELEGRAM_BOT_TOKEN=%s\r\n' "$OLD" > "$TG_SECRETS_FILE"; rm -f "$TG_SECRETS_FILE".bak-*
run "$NEW"
check "CRLF line keeps its CR" '[ "$(rc)" -eq 0 ] && [ "$(grep -c "$(printf "\r")$" "$TG_SECRETS_FILE")" -eq 2 ] && grep -qF "=$NEW" "$TG_SECRETS_FILE"'

printf 'TELEGRAM_BOT_TOKEN=%s\n' "$OLD" > "$TG_SECRETS_FILE"; chmod 644 "$TG_SECRETS_FILE"
run "$NEW"
check "mode other than 600 refused" '[ "$(rc)" -ne 0 ] && grep -qF "$OLD" "$TG_SECRETS_FILE"'

chmod 600 "$TG_SECRETS_FILE"
printf '%s\n' "$NEW" | bash -x "$SUT" > "$T/out" 2> "$T/err"
check "bash -x does not trace the token" 'leak'

echo "---"; [ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails FAILED"
exit "$fails"
