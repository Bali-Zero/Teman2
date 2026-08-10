#!/usr/bin/env bash
# test_mq_sh.sh — proof for scripts/mq.sh (Merge-OS v2 Wave 0 tool).
#
# WHAT IT PINS
#   arm       — records the head sha to the state file, arms bare `--auto`
#               (never `--squash` — that silently arms nothing once the
#               queue governs main, docs/runbooks/merge-queue-discipline.md).
#   guilt     — watch detects a head move away from the armed sha and calls
#               `--disable-auto` (the post-arm watcher IS the "no push after
#               arm" guarantee — arm itself cannot see a future push, spec
#               §3, Codex F13).
#   innocence — watch stays quiet (no disable-auto) across several unmoved
#               polls and exits clean once the PR reaches a terminal state.
#   ordering  — requeue disables BEFORE it re-arms, never the reverse.
#   why-red   — a failing required check is named with its bucket and link;
#               a required check branch protection lists but gh never
#               reported is flagged MISSING, not silently dropped.
#
# No network, no real gh, no real HOME: a fake `gh` on PATH answers from
# per-scenario state files and logs every invocation for order assertions.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
MQSH="$REPO_ROOT/mq.sh"
[ -f "$MQSH" ] || { echo "FAIL: mq.sh not found at $MQSH"; exit 2; }
[ -x "$MQSH" ] || { echo "FAIL: mq.sh not executable at $MQSH"; exit 2; }

failures=0
check() {  # check <name> <0-or-1>
  if [ "$2" = "1" ]; then printf '  ok   %s\n' "$1"
  else printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); fi
}
has() { case "$2" in *"$1"*) return 0 ;; *) return 1 ;; esac; }
yesno() { if "$@"; then echo 1; else echo 0; fi; }

# _json_field <file> <field> — tiny, avoids nested-quote hell in the checks.
_json_field() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' "$1" "$2" 2>/dev/null
}

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/mqsh_test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

SHA_A="$(printf 'a%.0s' $(seq 1 40))"  # 40 lowercase hex chars — the "armed" sha
SHA_B="$(printf 'b%.0s' $(seq 1 40))"  # a DIFFERENT 40-char sha — "moved" head

# One scenario = one fresh world: its own fake-gh state dir, log, state dir,
# and PATH. Nothing here writes to the real $HOME or the real GitHub.
new_world() {
  W="$(mktemp -d "$SANDBOX/w.XXXXXX")"
  mkdir -p "$W/bin" "$W/fgh" "$W/state"
  LOG="$W/log"
  : > "$LOG"

  cat > "$W/bin/gh" <<'FAKEGH'
#!/usr/bin/env bash
# Fake gh — logs every invocation to $FAKE_GH_LOG, answers from
# $FAKE_GH_STATE. An invocation shape this fake does not recognise is a
# HARNESS bug (exit 99), never a silent empty answer.
set -uo pipefail
printf '%s\n' "$*" >> "$FAKE_GH_LOG"

case "${1:-}" in
  api)
    rc=0
    [ -f "$FAKE_GH_STATE/required_names_rc" ] && rc="$(cat "$FAKE_GH_STATE/required_names_rc")"
    [ -f "$FAKE_GH_STATE/required_names" ] && cat "$FAKE_GH_STATE/required_names"
    exit "$rc"
    ;;
  pr)
    case "${2:-}" in
      checks)
        rc=0
        [ -f "$FAKE_GH_STATE/checks_rc" ] && rc="$(cat "$FAKE_GH_STATE/checks_rc")"
        if [ -f "$FAKE_GH_STATE/checks_json" ]; then cat "$FAKE_GH_STATE/checks_json"; else echo '[]'; fi
        exit "$rc"
        ;;
      view)
        # The tested string is wrapped in artificial leading/trailing spaces
        # below, so every `--json <fields>` token is bordered by real spaces
        # regardless of its position in argv — no per-pattern alternates needed.
        case " $* " in
          *" autoMergeRequest,mergeStateStatus,headRefOid "*)
            if [ -f "$FAKE_GH_STATE/confirm_json" ]; then cat "$FAKE_GH_STATE/confirm_json"; else echo '{}'; fi
            exit 0
            ;;
          *" state,mergedAt,headRefOid "*)
            n=$(( $(cat "$FAKE_GH_STATE/watch_call_count" 2>/dev/null || echo 0) + 1 ))
            echo "$n" > "$FAKE_GH_STATE/watch_call_count"
            line="$(sed -n "${n}p" "$FAKE_GH_STATE/watch_responses" 2>/dev/null)"
            [ -z "$line" ] && line="$(tail -1 "$FAKE_GH_STATE/watch_responses" 2>/dev/null)"
            echo "$line"
            exit 0
            ;;
          *" headRefOid "*)
            sha="$(cat "$FAKE_GH_STATE/head_sha" 2>/dev/null || echo '')"
            printf '{"headRefOid":"%s"}\n' "$sha"
            exit 0
            ;;
        esac
        echo '{}'
        exit 0
        ;;
      merge)
        case " $* " in
          *" --disable-auto "*)
            echo "Auto-merge disabled"
            exit 0
            ;;
          *" --auto "*)
            rc=0
            [ -f "$FAKE_GH_STATE/arm_rc" ] && rc="$(cat "$FAKE_GH_STATE/arm_rc")"
            if [ -f "$FAKE_GH_STATE/arm_output" ]; then cat "$FAKE_GH_STATE/arm_output"; else echo "Auto-merge enabled for pull request"; fi
            exit "$rc"
            ;;
        esac
        ;;
    esac
    ;;
esac
echo "FAKE_GH: unhandled invocation: $*" >&2
exit 99
FAKEGH
  chmod +x "$W/bin/gh"
}

# run <verb...> — invokes mq.sh through the fake gh via `env` (a real exec,
# so there is no ambiguity about whether a shell-function env-prefix would
# propagate into the command substitution below — it always does via env).
# Captures combined stdout+stderr in $OUT, exit code in $RC. Reads the
# optional $MQ_WATCH_INTERVAL_S test seam if the caller set it.
#
# No arrays here on purpose: macOS ships bash 3.2 (GPLv3 holdout), where
# `"${arr[@]}"` on an EMPTY array trips `set -u` as "unbound variable" —
# an empty MQ_WATCH_INTERVAL_S is passed as a plain (possibly-empty) env
# var instead, which mq.sh's own `${MQ_WATCH_INTERVAL_S:-60}` treats the
# same as unset.
run() {
  OUT="$(env MQ_REPO="test-owner/test-repo" MQ_STATE_DIR="$W/state" \
             FAKE_GH_LOG="$LOG" FAKE_GH_STATE="$W/fgh" \
             PATH="$W/bin:$PATH" \
             MQ_WATCH_INTERVAL_S="${MQ_WATCH_INTERVAL_S:-}" \
             bash "$MQSH" "$@" 2>&1)"
  RC=$?
}

# poverty check — the fake must actually be the one gh resolves to, or every
# assertion below would be measuring real GitHub instead of the harness
# (W108: a fake world too poor to judge reports its own poverty as a pass).
new_world
resolved="$(PATH="$W/bin:$PATH" command -v gh)"
if [ "$resolved" != "$W/bin/gh" ]; then
  echo "HARNESS TOO POOR TO JUDGE: PATH did not resolve gh to the fake ($resolved)" >&2
  exit 2
fi

echo "arm — records the head sha, arms bare --auto, never --squash:"
new_world
echo "$SHA_A" > "$W/fgh/head_sha"
run arm 42
check "exit 0" "$(yesno test "$RC" = 0)"
check "state file written" "$(yesno test -f "$W/state/armed/42.json")"
check "state file records the armed sha" "$(yesno test "$(_json_field "$W/state/armed/42.json" sha)" = "$SHA_A")"
check "state file records the PR number" "$(yesno test "$(_json_field "$W/state/armed/42.json" pr)" = "42")"
check "merge --auto was called" "$(yesno grep -q -- '--auto' "$LOG")"
check "NEVER --squash anywhere in the log" "$(yesno eval '! grep -q -- "--squash" "$LOG"')"
check "output prints the armed sha" "$(yesno has "$SHA_A" "$OUT")"

echo "guilt — watch sees a head move away from the armed sha and dequeues:"
new_world
mkdir -p "$W/state/armed"
python3 -c 'import json,sys; json.dump({"pr":77,"sha":sys.argv[1],"armed_at":"2026-08-10T00:00:00Z"}, open(sys.argv[2],"w"))' \
  "$SHA_A" "$W/state/armed/77.json"
printf '{"state":"OPEN","mergedAt":null,"headRefOid":"%s"}\n' "$SHA_B" > "$W/fgh/watch_responses"
MQ_WATCH_INTERVAL_S=0 run watch 77 --timeout-mins 5
check "exit 3 (head moved)" "$(yesno test "$RC" = 3)"
check "alert names the moved head" "$(yesno has "HEAD MOVED" "$OUT")"
check "disable-auto WAS called" "$(yesno grep -q -- '--disable-auto' "$LOG")"

echo "innocence — watch stays quiet on an unmoved head, exits clean on MERGED:"
new_world
mkdir -p "$W/state/armed"
python3 -c 'import json,sys; json.dump({"pr":88,"sha":sys.argv[1],"armed_at":"2026-08-10T00:00:00Z"}, open(sys.argv[2],"w"))' \
  "$SHA_A" "$W/state/armed/88.json"
{
  printf '{"state":"OPEN","mergedAt":null,"headRefOid":"%s"}\n' "$SHA_A"
  printf '{"state":"OPEN","mergedAt":null,"headRefOid":"%s"}\n' "$SHA_A"
  printf '{"state":"MERGED","mergedAt":"2026-08-10T01:00:00Z","headRefOid":"%s"}\n' "$SHA_A"
} > "$W/fgh/watch_responses"
MQ_WATCH_INTERVAL_S=0 run watch 88 --timeout-mins 5
check "exit 0 (MERGED)" "$(yesno test "$RC" = 0)"
check "disable-auto NEVER called across the unmoved polls" "$(yesno eval '! grep -q -- "--disable-auto" "$LOG"')"
check "at least 3 view polls happened before the terminal state" \
  "$(yesno test "$(cat "$W/fgh/watch_call_count")" -ge 3)"

echo "ordering — requeue disables BEFORE it re-arms, never the reverse:"
new_world
echo "$SHA_A" > "$W/fgh/head_sha"
run requeue 99
check "exit 0" "$(yesno test "$RC" = 0)"
disable_line="$(grep -n -- '--disable-auto' "$LOG" | head -1 | cut -d: -f1)"
auto_line="$(grep -n -- '--auto' "$LOG" | grep -v -- '--disable-auto' | head -1 | cut -d: -f1)"
check "both calls happened" "$(yesno test -n "${disable_line:-}" -a -n "${auto_line:-}")"
check "disable-auto precedes the re-arm --auto" "$(yesno test "${disable_line:-99}" -lt "${auto_line:-0}")"
check "requeue re-armed with a fresh state file" "$(yesno test -f "$W/state/armed/99.json")"

echo "why-red — names a failing required check, and one required-but-unreported:"
new_world
printf 'Backend Tests (Python)\nDetect Secrets\nGhost Check (never runs)\n' > "$W/fgh/required_names"
cat > "$W/fgh/checks_json" <<'JSON'
[
  {"name":"Backend Tests (Python)","bucket":"fail","link":"https://example.test/run/1","description":"","workflow":"Tests & Coverage"},
  {"name":"Detect Secrets","bucket":"pass","link":"https://example.test/run/2","description":"","workflow":"Security Scanning"}
]
JSON
run why-red 42
check "exit 0" "$(yesno test "$RC" = 0)"
check "failing check named with its bucket" "$(yesno has "[FAIL" "$OUT")"
check "failing check's name is present" "$(yesno has "Backend Tests (Python)" "$OUT")"
check "failing check's link is present" "$(yesno has "https://example.test/run/1" "$OUT")"
check "a required check gh never reported is flagged MISSING" "$(yesno has "[MISSING" "$OUT")"
check "the missing check is named" "$(yesno has "Ghost Check (never runs)" "$OUT")"
check "a passing required check is NOT listed as trouble" "$(yesno eval '! has "Detect Secrets" "$OUT"')"

echo "why-red — innocence: an all-clean set says so, once:"
new_world
printf 'Detect Secrets\n' > "$W/fgh/required_names"
printf '[{"name":"Detect Secrets","bucket":"pass","link":"","description":"","workflow":"Security Scanning"}]' > "$W/fgh/checks_json"
run why-red 7
check "exit 0" "$(yesno test "$RC" = 0)"
check "reports clean" "$(yesno has "clean" "$OUT")"
check "does not fabricate a FAIL/MISSING line on a clean set" "$(yesno eval '! has "[FAIL" "$OUT" && ! has "[MISSING" "$OUT"')"

echo "dequeue — disables and removes the local armed-state file:"
new_world
mkdir -p "$W/state/armed"
python3 -c 'import json,sys; json.dump({"pr":55,"sha":sys.argv[1],"armed_at":"2026-08-10T00:00:00Z"}, open(sys.argv[2],"w"))' \
  "$SHA_A" "$W/state/armed/55.json"
run dequeue 55
check "exit 0" "$(yesno test "$RC" = 0)"
check "disable-auto was called" "$(yesno grep -q -- '--disable-auto' "$LOG")"
check "state file removed" "$(yesno eval '[ ! -f "$W/state/armed/55.json" ]')"

echo
if [ "$failures" -eq 0 ]; then echo "PASS (all checks)"; exit 0; fi
echo "FAIL ($failures check(s))"; exit 1
