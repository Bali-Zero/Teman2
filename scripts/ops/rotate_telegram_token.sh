#!/usr/bin/env bash
# rotate_telegram_token.sh — replace TELEGRAM_BOT_TOKEN in this host's secrets file.
#
#   rotate_telegram_token.sh             prompt (no echo) for the new token, replace atomically
#   rotate_telegram_token.sh --dry-run   say WHICH file/line would change; no prompt, no write
#   rotate_telegram_token.sh --check     report presence + shape of the current value; no value
#
# The token is never printed, never an argument, never in the process list. File:
# ${TG_SECRETS_FILE:-~/.nuzantara-secrets.env} (the same override tg_notify.py honours).
# Exit 0 = done/idempotent no-op; any doubt (no/multiple lines, symlink, bad shape) = non-zero.
set -euo pipefail
set +o xtrace   # never trace: expansions below can hold the token

F="${TG_SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
KEY=TELEGRAM_BOT_TOKEN
LINE_RE='^[[:space:]]*(export[[:space:]]+)?'"$KEY"'='
SHAPE_RE='^[0-9]{8,10}:[A-Za-z0-9_-]{35}$'
die() { echo "rotate_telegram_token: $*" >&2; exit "${2:-2}"; }
fmode() { stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1"; }

mode="apply"
case "${1:-}" in
  "") ;;
  --dry-run) mode="dry" ;;
  --check) mode="check" ;;
  -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
  *) die "unknown argument (see --help)" 64 ;;
esac
[ "$#" -le 1 ] || die "too many arguments" 64

[ -f "$F" ] || die "secrets file not found: $F"
[ ! -L "$F" ] || die "secrets file is a symlink, refusing: $F"
[ -O "$F" ] || die "secrets file is not owned by $(id -un), refusing: $F"
[ "$(fmode "$F")" = 600 ] || die "secrets file mode must already be 600: $F"
n=$(grep -cE "$LINE_RE" "$F" || true)
lineno=$(grep -nE "$LINE_RE" "$F" | cut -d: -f1 | tr '\n' ' ' || true)

# The candidate reaches awk on fd 3 (never argv, never the environment). Modes: same | shape | write.
filter() {
  SHAPE="$SHAPE_RE" awk -v mode="$1" -v key="$KEY" '
    BEGIN { if ((getline VAL < "/dev/fd/3") <= 0) VAL = "" }
    $0 ~ "^[[:space:]]*(export[[:space:]]+)?" key "=" {
      v = $0; sub(/^[^=]*=/, "", v); cr = (v ~ /\r$/) ? "\r" : ""; sub(/\r$/, "", v)
      if (v ~ /^".*"[ \t]*$/ || v ~ /^\047.*\047[ \t]*$/) { sub(/^./, "", v); sub(/["\047][ \t]*$/, "", v) }
      if (mode == "same")  { found = (v == VAL) }
      if (mode == "shape") { found = (v ~ ENVIRON["SHAPE"]) }
      if (mode == "write") { pre = ($0 ~ /^[[:space:]]*export[[:space:]]/) ? "export " : ""
                             print pre key "=" VAL cr; next }
    }
    mode == "write" { print }
    END { if (mode != "write") exit(found ? 0 : 1) }' "$F"
}

case "$mode" in
  check)
    if [ "$n" -eq 0 ]; then echo "$KEY: UNSET (no line in $F)"; exit 1; fi
    echo "$KEY: SET"
    echo "file: $F (line ${lineno% }, mode $(fmode "$F"))"
    if [ "$n" -eq 1 ] && filter shape; then echo "shape: ok"; else echo "shape: BAD or ambiguous" >&2; exit 1; fi
    echo "process env $KEY: ${TELEGRAM_BOT_TOKEN:+SET}"
    exit 0 ;;
  dry)
    [ "$n" -eq 1 ] || die "expected exactly 1 $KEY line in $F, found $n"
    form=plain
    if grep -E "$LINE_RE" "$F" | grep -q '^[[:space:]]*export'; then form=export; fi
    echo "would replace line ${lineno% } of $F ($form form)"
    echo "would back up to $F.bak-<UTC> (mode 600), then temp file + mv (mode $(fmode "$F") kept)"
    exit 0 ;;
esac

[ "$n" -eq 1 ] || die "expected exactly 1 $KEY line in $F, found $n"
IFS= read -rs -p "New $KEY (input hidden): " tok || die "no input"
if [ -t 0 ]; then echo >&2; fi
[[ "$tok" =~ $SHAPE_RE ]] || die "input does not match <8-10 digits>:<35 chars> (value not shown)"

if filter same 3<<<"$tok"; then
  echo "$KEY already holds this value in $F: nothing to do"
  exit 0
fi

umask 077
tmp=$(mktemp "$(dirname "$F")/.$(basename "$F").tmp.XXXXXX")
bak="$F.bak-$(date -u +%Y%m%dT%H%M%SZ)"
trap 'rm -f "$tmp"' EXIT
sum0=$(cksum < "$F")
filter write 3<<<"$tok" > "$tmp"
[ "$(grep -cE "$LINE_RE" "$tmp")" -eq 1 ] || die "post-write check failed (token line count), original untouched"
[ "$(wc -l < "$tmp")" -eq "$(wc -l < "$F")" ] || die "post-write check failed (line count differs), original untouched"
( set -C; : > "$bak" ) 2>/dev/null || die "backup path exists, refusing to overwrite: $bak"
cat "$F" > "$bak"
chmod 600 "$tmp"
[ "$(cksum < "$F")" = "$sum0" ] || die "secrets file changed while rotating, original untouched (backup: $bak)"
mv "$tmp" "$F"
trap - EXIT
echo "$KEY replaced in $F (backup: $bak, mode 600). Next: docs/runbooks/telegram-token-rotation.md"
