#!/usr/bin/env bash
# Execute every shell fence in the Telegram rotation runbook without touching live state.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
RUNBOOK=${1:-"$ROOT/docs/runbooks/telegram-token-rotation.md"}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAILURES=0

fail() { printf 'FAIL %s\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }
command -v zsh >/dev/null 2>&1 || { fail "zsh is required"; }
ZSH_BIN=$(command -v zsh 2>/dev/null || true)
[ -f "$RUNBOOK" ] || { printf 'missing runbook: %s\n' "$RUNBOOK" >&2; exit 2; }

mkdir -p "$TMP/blocks"
awk -v out="$TMP/blocks" '
  /^[[:space:]]*```(bash|sh)[[:space:]]*$/ {
    inside=1; n++; prefix=$0; sub(/```(bash|sh)[[:space:]]*$/, "", prefix)
    indent=length(prefix); file=sprintf("%s/%03d.sh", out, n); next
  }
  inside && /^[[:space:]]*```[[:space:]]*$/ { close(file); inside=0; next }
  inside { line=$0; for (i=0; i<indent; i++) sub(/^ /, "", line); print line > file }
  END { if (inside) exit 2; print n+0 > (out "/count") }
' "$RUNBOOK"
BLOCK_COUNT=$(cat "$TMP/blocks/count")
[ "$BLOCK_COUNT" -gt 0 ] || { printf 'no shell blocks found\n' >&2; exit 2; }

FAKE_TOKEN=$(printf '%s%s%s%s' '1234' '5678' ':' 'AbCdEfGhIjKlMnOpQrStUvWxYz012345678')
TOKEN_RE='[0-9]{8,10}:[A-Za-z0-9_-]{35}'

setup_case() {
  case_dir=$1
  home_dir="$case_dir/home"
  log_dir="$case_dir/logs"
  mkdir -p "$log_dir" "$case_dir/shims" "$home_dir/Library/LaunchAgents" \
    "$home_dir/.organism/tg_spool" "$home_dir/nuzantara/scripts/ops"
  printf 'TELEGRAM_BOT_TOKEN=\n' > "$home_dir/.nuzantara-secrets.env"
  printf '<string>TELEGRAM_BOT_TOKEN</string>\n' > "$home_dir/Library/LaunchAgents/test.plist"
  printf '{"p0_unsent": true}\n' > "$home_dir/.organism/tg_spool/pending.jsonl"

  cat > "$case_dir/shims/command-shim" <<'SHIM'
#!/bin/bash
name=${0##*/}; n=0
while [ -e "$TEST_LOG_DIR/$name.$n.args" ]; do n=$((n + 1)); done
printf '%s\n' "$@" > "$TEST_LOG_DIR/$name.$n.args"
case "$name:${1-}" in
  fly:*|python3:-) cat > "$TEST_LOG_DIR/$name.$n.stdin" ;;
  gh:*) IFS= read -r value || value=; printf '%s\n' "$value" > "$TEST_LOG_DIR/$name.$n.stdin"; unset value ;;
  *) : > "$TEST_LOG_DIR/$name.$n.stdin" ;;
esac
SHIM
  chmod +x "$case_dir/shims/command-shim"
  for name in fly gh ssh python3; do cp "$case_dir/shims/command-shim" "$case_dir/shims/$name"; done

  repo="$home_dir/nuzantara"
  cat > "$repo/scripts/ops/rotate_telegram_token.sh" <<'SHIM'
#!/bin/bash
n=0
while [ -e "$TEST_LOG_DIR/rotate.$n.args" ]; do n=$((n + 1)); done
printf '%s\n' "$@" > "$TEST_LOG_DIR/rotate.$n.args"
if [ "$#" -eq 0 ]; then IFS= read -r value || value=; printf '%s' "$value" > "$TEST_LOG_DIR/rotate.$n.stdin"; unset value
else : > "$TEST_LOG_DIR/rotate.$n.stdin"; fi
SHIM
  cat > "$repo/scripts/launchd_env_loader.sh" <<'SHIM'
#!/bin/bash
printf '%s\n' "$@" > "$TEST_LOG_DIR/launchd.args"
SHIM
  chmod +x "$repo/scripts/ops/rotate_telegram_token.sh" "$repo/scripts/launchd_env_loader.sh"
}

# Mode "whole": the block is one -c string, parsed before it runs (bracketed paste); a -c string
# honours `#` even with nointeractivecomments. Mode "raw": block, answer and the final probe arrive on
# stdin line by line, as an unbracketed paste does; there zsh -i really reads `#` as a word and a
# `read` that runs before the block is fully parsed swallows the next pasted line.
run_case() {
  block=$1; shell_name=$2; input_name=$3; input_value=$4; mode=$5
  label="block $(basename "$block" .sh) $shell_name $mode $input_name"
  case_dir="$TMP/cases/$(basename "$block" .sh)-$shell_name-$mode-$input_name"
  setup_case "$case_dir"
  payload=$(cat "$block")
  payload="cd \"\$HOME/nuzantara\"
$payload
block_rc=\$?; [ -z \"\${TG+x}\" ] && [ \"\$block_rc\" -eq 0 ]"
  out="$case_dir/stdout"; err="$case_dir/stderr"
  if [ "$shell_name" = zsh ]; then set -- "$ZSH_BIN" -f -o nointeractivecomments -i
  else set -- /bin/bash --noprofile --norc; fi
  if [ "$mode" = raw ]; then
    set -- "$@" -s
    printf '%s\n' "$(sed '$d' <<<"$payload")" "$input_value" "$(tail -n 1 <<<"$payload")" > "$case_dir/stdin"
  else
    set -- "$@" -c "$payload"
    printf '%s\n' "$input_value" > "$case_dir/stdin"
  fi
  if ! cat "$case_dir/stdin" | env -i HOME="$case_dir/home" ZDOTDIR="$case_dir/home" \
    PATH="$case_dir/shims:/usr/bin:/bin:/usr/sbin:/sbin" TEST_LOG_DIR="$case_dir/logs" \
    "$@" >"$out" 2>"$err"; then fail "$label execution"; fi
  for src in "$case_dir"/logs/python3.*.stdin; do
    [ -s "$src" ] || continue
    python3 -c 'import sys; compile(open(sys.argv[1]).read(), "heredoc", "exec")' "$src" 2>/dev/null || fail "$label python heredoc does not compile"
  done
  if grep -Eq "$TOKEN_RE" "$out" "$err" || grep -qF "$FAKE_TOKEN" "$out" "$err"; then fail "$label leaked token to output"; fi
  for args in "$case_dir"/logs/*.args; do
    [ -e "$args" ] || continue
    if grep -qF "$FAKE_TOKEN" "$args" || grep -Eq "$TOKEN_RE" "$args"; then fail "$label put token in argv"; fi
  done
  fly_count=$(find "$case_dir/logs" -name 'fly.*.stdin' | wc -l | tr -d ' ')
  if grep -q 'fly secrets import' "$block"; then
    if [ "$input_name" = token ]; then
      printf 'TELEGRAM_BOT_TOKEN=%s\n' "$FAKE_TOKEN" > "$case_dir/expected"
      [ "$fly_count" -eq 1 ] || fail "$label fly call count=$fly_count"
      fly_stdin=$(find "$case_dir/logs" -name 'fly.*.stdin' | head -1)
      if [ -z "$fly_stdin" ] || ! cmp -s "$case_dir/expected" "$fly_stdin"; then fail "$label fly stdin"; fi
    else
      [ "$fly_count" -eq 0 ] || fail "$label called fly for empty input"
    fi
  else
    [ "$fly_count" -eq 0 ] || fail "$label unexpected fly call"
  fi
}

for block in "$TMP"/blocks/*.sh; do
  if grep -q '#' "$block"; then fail "$(basename "$block") contains #"; fi
  if grep -Eq '(^|[^[:alnum:]_])exit([^[:alnum:]_]|$)' "$block"; then fail "$(basename "$block") contains exit"; fi
  if grep -oE '"[$]TG"[[:space:]]*\|[[:space:]]*[^[:space:]]+' "$block" | grep -Evq '\|[[:space:]]*(fly|gh)$'; then
    fail "$(basename "$block") pipes the token into something other than fly or gh"
  fi
  if grep -oE '(^|[^[:alnum:]_.])read([[:space:]]+-[[:alpha:]]+)*[[:space:]]' "$block" | grep -vq -- '-[[:alpha:]]*s'; then
    fail "$(basename "$block") has a read without -s (the answer would echo)"
  fi
  if [ "$(grep -cve '^[[:space:]]*$' "$block")" -gt 1 ]; then
    first=$(sed -n '/[^[:space:]]/{s/^[[:space:]]*//;p;q;}' "$block")
    last=$(awk 'NF{x=$0} END{sub(/^[[:space:]]*/, "", x); print x}' "$block")
    case "$first" in \{*) ;; *) fail "$(basename "$block") is not one compound command" ;; esac
    case "$last" in *\}) ;; *) fail "$(basename "$block") does not close its compound command" ;; esac
  fi
  if ! /bin/bash -n "$block" >/dev/null 2>&1; then fail "$(basename "$block") bash parse"; fi
  for shell_name in zsh bash; do
    for input_name in token empty; do
      value=$FAKE_TOKEN; [ "$input_name" = token ] || value=
      run_case "$block" "$shell_name" "$input_name" "$value" whole
      whole_logs="$case_dir/logs"
      if [ "$input_name" = token ] && ! grep -qsF "$FAKE_TOKEN" "$whole_logs"/*.stdin; then continue; fi
      run_case "$block" "$shell_name" "$input_name" "$value" raw
      diff -r "$whole_logs" "$case_dir/logs" >/dev/null || fail "block $(basename "$block" .sh) $shell_name $input_name raw paste differs from whole paste"
    done
  done
done

if [ "$FAILURES" -ne 0 ]; then printf '%s failure(s)\n' "$FAILURES" >&2; exit 1; fi
printf 'PASS: %s shell blocks under zsh and bash, whole and raw paste, token and empty input\n' "$BLOCK_COUNT"
