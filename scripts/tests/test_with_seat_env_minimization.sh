#!/usr/bin/env bash
# Plain-bash verification for with_seat.  The guilt check matters: if an
# unwrapped child cannot see the planted name, the isolation check proves nothing.

set -u

if [ "${1:-}" = "--dry-run" ]; then
  shift
fi

ROOT="$(cd -P "$(dirname "$0")/../.." && pwd)"
BROKER="$ROOT/scripts/with_seat.sh"
REAL_REGISTRY="$ROOT/infra/llm-credentials/seat-env.json"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/with-seat-test.XXXXXX")"
trap 'rm -rf "$TEMP_DIR"' EXIT HUP INT TERM

TOTAL=0
FAILED=0

# On failure, surface the broker's own stderr from the most recent invocation.
#
# Without this a red CI run says only WHICH check failed, never why: the broker writes
# diagnostics to a captured file, so the job log shows a bare "FAIL" and the next move
# is a guess. Measured cost of not having it: a full CI cycle unable to distinguish a
# missing interpreter from a refused seat. A corpus that can go red without saying why
# spends its reader's time instead of its own.
LAST_STDERR=""
check() {
  local label="$1"
  shift
  TOTAL=$((TOTAL + 1))
  if "$@"; then
    printf 'PASS %s\n' "$label"
  else
    printf 'FAIL %s\n' "$label"
    if [ -n "$LAST_STDERR" ] && [ -s "$LAST_STDERR" ]; then
      printf '     broker stderr: %s\n' "$(head -c 500 "$LAST_STDERR" | tr '\n' '|')"
    fi
    FAILED=$((FAILED + 1))
  fi
}

capture="$TEMP_DIR/env-capture"
exit_seven="$TEMP_DIR/exit-seven"
self_term="$TEMP_DIR/self-term"
registry="$TEMP_DIR/seat-env.json"
output="$TEMP_DIR/environment-names"
stderr_file="$TEMP_DIR/stderr"

cat >"$capture" <<'EOF'
#!/usr/bin/perl
use strict;
use warnings;

open(my $output_handle, '>', $ARGV[0]) or die "cannot write output\n";
print {$output_handle} "$_\n" for sort keys %ENV;
close($output_handle) or die "cannot close output\n";
EOF
cat >"$exit_seven" <<'EOF'
#!/usr/bin/perl
exit 7
EOF
cat >"$self_term" <<'EOF'
#!/usr/bin/perl
kill 'TERM', $$;
EOF
slow="$TEMP_DIR/slow-child"
cat >"$slow" <<'EOF'
#!/usr/bin/perl
sleep 5;
EOF
chmod 700 "$capture" "$exit_seven" "$self_term" "$slow"

cat >"$registry" <<'EOF'
{
  "seats": {
    "test-seat": {
      "env": ["HOME", "PATH", "TERM", "LANG", "LC_ALL", "TMPDIR"],
      "exec_allowlist": ["env-capture", "exit-seven", "self-term", "slow-child"],
      "exec_search_path": ["__TEMP_DIR__"],
      "note": "Test-only local executables."
    }
  }
}
EOF
sed -i.bak "s#__TEMP_DIR__#$TEMP_DIR#" "$registry" && rm -f "$registry.bak"
chmod 600 "$registry"

export HOME PATH
export TERM="${TERM:-dumb}"
export LANG="${LANG:-C}"
export LC_ALL="${LC_ALL:-C}"
export TMPDIR="${TMPDIR:-/tmp}"
FAKE_PLANTED_TOKEN_FOR_TEST=""
export FAKE_PLANTED_TOKEN_FOR_TEST

"$capture" "$output"
check "guilt fixture exposes planted inherited name" grep -qx 'FAKE_PLANTED_TOKEN_FOR_TEST' "$output"

LAST_STDERR="$stderr_file"
WITH_SEAT_REGISTRY="$registry" "$BROKER" test-seat env-capture "$output" >"$TEMP_DIR/stdout" 2>"$stderr_file"
check "innocence planted name absent" bash -c '! grep -qx FAKE_PLANTED_TOKEN_FOR_TEST "$1"' _ "$output"
printf '%s\n' HOME PATH TERM LANG LC_ALL TMPDIR | LC_ALL=C sort >"$TEMP_DIR/expected"
check "innocence exact declared intersection" cmp -s "$TEMP_DIR/expected" "$output"

WITH_SEAT_REGISTRY="$registry" "$BROKER" unknown-seat env-capture "$output" >"$TEMP_DIR/stdout" 2>"$stderr_file"
unknown_status=$?
check "unknown seat refuses clearly" bash -c '[ "$1" -ne 0 ] && grep -q "unknown seat" "$2"' _ "$unknown_status" "$stderr_file"

cat >"$registry" <<'EOF'
{"seats":{"bad":{"env":["BAD-NAME"],"exec_allowlist":["env-capture"]}}}
EOF
WITH_SEAT_REGISTRY="$registry" "$BROKER" bad env-capture "$output" >"$TEMP_DIR/stdout" 2>"$stderr_file"
malformed_status=$?
check "malformed env name refuses" test "$malformed_status" -ne 0

cat >"$registry" <<'EOF'
{"seats":{"bad":{"env":["HOME","HOME"],"exec_allowlist":["env-capture"]}}}
EOF
WITH_SEAT_REGISTRY="$registry" "$BROKER" bad env-capture "$output" >"$TEMP_DIR/stdout" 2>"$stderr_file"
duplicate_status=$?
check "duplicate env name refuses" test "$duplicate_status" -ne 0

cat >"$registry" <<'EOF'
{"seats":{"test-seat":{"env":["HOME","PATH","TERM","LANG","LC_ALL","TMPDIR"],"exec_allowlist":["env-capture","exit-seven","self-term","slow-child"],"exec_search_path":["__TEMP_DIR__"]}}}
EOF
sed -i.bak "s#__TEMP_DIR__#$TEMP_DIR#" "$registry" && rm -f "$registry.bak"
WITH_SEAT_REGISTRY="$registry" "$BROKER" test-seat >"$TEMP_DIR/stdout" 2>"$stderr_file"
empty_status=$?
check "empty command refuses" test "$empty_status" -ne 0

WITH_SEAT_REGISTRY="$registry" "$BROKER" test-seat /bin/true >"$TEMP_DIR/stdout" 2>"$stderr_file"
allowlist_status=$?
check "non-allowlisted basename refuses" test "$allowlist_status" -ne 0

chmod 666 "$registry"
WITH_SEAT_REGISTRY="$registry" "$BROKER" test-seat env-capture "$output" >"$TEMP_DIR/stdout" 2>"$stderr_file"
writable_status=$?
check "group/world-writable registry refuses" test "$writable_status" -ne 0
chmod 600 "$registry"

LAST_STDERR="$stderr_file"
WITH_SEAT_REGISTRY="$registry" "$BROKER" test-seat exit-seven >"$TEMP_DIR/stdout" 2>"$stderr_file"
exit_seven_status=$?
check "child exit status preserved" test "$exit_seven_status" -eq 7

LAST_STDERR="$stderr_file"
WITH_SEAT_REGISTRY="$registry" "$BROKER" test-seat self-term >"$TEMP_DIR/stdout" 2>"$stderr_file"
self_term_status=$?
check "child TERM signal preserved" test "$self_term_status" -eq 143

# The exec allowlist must be an ALLOWLIST, not a naming convention.
#
# Measured on the first build: `with_seat.sh codex /tmp/evil/codex` executed the
# attacker's binary and the broker reported a clean exit, because the allowlist
# was checked against the BASENAME of a caller-supplied path. Anyone who can
# write a file anywhere and name it `codex` satisfied it.
# A bare name is now the only accepted form, and WHERE it resolves comes from the
# registry -- which the broker already refuses to read if it is group- or
# world-writable.
attack_dir="$TEMP_DIR/evil"
mkdir -p "$attack_dir"
cat >"$attack_dir/env-capture" <<'ATTACK'
#!/usr/bin/perl
open(my $h, '>', "$ENV{ATTACK_MARKER_PATH}") or exit 0;
print {$h} "attacker code ran\n";
close($h);
ATTACK
chmod 700 "$attack_dir/env-capture"
attack_marker="$TEMP_DIR/attack-marker"
rm -f "$attack_marker"
ATTACK_MARKER_PATH="$attack_marker" WITH_SEAT_REGISTRY="$registry" \
  "$BROKER" test-seat "$attack_dir/env-capture" >"$TEMP_DIR/stdout" 2>"$stderr_file"
attack_status=$?
check "a caller-supplied path with an allowlisted basename cannot execute" \
  bash -c '[ "$1" -ne 0 ] && [ ! -e "$2" ]' _ "$attack_status" "$attack_marker"

# A TERM sent to the BROKER must kill the broker, not be swallowed.
#
# Measured on bash 3.2: `trap 'rm -f x' TERM` runs the handler and lets the
# script CONTINUE, exiting 0. A broker that survives the TERM its supervisor
# sent — and then reports success — tells the caller a dispatch was cancelled
# when it was not. Found by blind cross-family refutation (Kimi K3).
# 143 = 128 + SIGTERM.
# A SLOW child makes this deterministic: the broker is guaranteed still alive
# when the signal lands, so 143 is the only correct answer and 0 is exactly the
# pre-fix bug rather than a race we would have to tolerate.
term_broker_out="$TEMP_DIR/term-broker.out"
WITH_SEAT_REGISTRY="$registry" "$BROKER" test-seat slow-child >"$term_broker_out" 2>&1 &
broker_pid=$!
sleep 1
kill -TERM "$broker_pid" 2>/dev/null
wait "$broker_pid"
broker_term_status=$?
LAST_STDERR="$term_broker_out"
check "a TERM to the broker is not swallowed" test "$broker_term_status" -eq 143

# THE REAL REGISTRY, not a synthetic seat.
#
# Every check above uses a fabricated test-seat, and that is how the shipped
# registry came to declare four seats of which TWO could not resolve their own
# binary at all: agy lives in ~/.local/bin and kimi in ~/.kimi-code/bin, neither
# on the broker's fixed system search path. `with_seat.sh agy agy` answered
# "cannot resolve command" — a broker that exists and is armed for one seat in
# two. A corpus that only ever exercises its own fixture cannot see that.
#
# Structural half (bites on EVERY machine, including a CI runner where none of
# these binaries exist): every seat declares a non-empty exec_allowlist, and
# every exec_search_path entry is absolute or "~/"-prefixed — never bare-relative,
# which would resolve against the caller's cwd.
# Structural half. Written as a reusable validator so the SAME rules can be run
# against a guilt fixture below -- a check that only ever sees the real, correct
# registry cannot show that it would reject a wrong one.
#
# It is deliberately structural rather than a grep for secret-shaped strings. The
# first version of this check was such a grep, and it MISSED both realistic
# pastes, measured: the registry is arrays of strings, so a token dropped into an
# `env` array is not a `key: "value"` pair and never matched; and a 64-char hex
# token is itself a syntactically valid env NAME, so even a pattern that saw it
# would have to argue about entropy. Bounding the SHAPE of every field closes
# both without guessing what a secret looks like.
registry_validator="$TEMP_DIR/validate_registry.py"
cat >"$registry_validator" <<'REGPY'
import json, re, sys
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
BASENAME = re.compile(r"^[A-Za-z0-9._-]+$")
bad = []
raw = open(sys.argv[1]).read()
registry = json.loads(raw)
seats = registry["seats"]

# Secret-shape scan over the WHOLE file, prose included.
#
# An earlier version exempted `note` because notes are prose. Measured, that let
# this through untouched:
#     "note": "OPENAI_API_KEY: sk-proj-0123456789abcdefghijklmnopqrstuv"
# -- the key name is only 14 chars before the colon breaks the run, and the token
# itself is not adjacent to a quote, so a key/value grep never considered it.
# Found by blind cross-family refutation (Codex GPT-5.6 sol).
#
# 32 is measured, not guessed: the longest legitimate token anywhere in this
# registry's prose is 23 chars (CLAUDE_CODE_OAUTH_TOKEN, FLEET_BURST_SEAT_BROKER),
# and real credentials are far longer. Prose does not need 32-character words; if
# a future note genuinely does, shorten the word rather than raising this.
for token in re.findall(r"[A-Za-z0-9+/=_-]{32,}", raw):
    bad.append("value-shaped token (%d chars) in the registry — this file declares NAMES only: %r..."
               % (len(token), token[:8]))
for name, seat in seats.items():
    env = seat.get("env") or []
    if not env:
        bad.append("%s: empty or missing env" % name)
    for item in env:
        if not isinstance(item, str) or not NAME.match(item):
            bad.append("%s: env entry is not a valid variable name: %r" % (name, item[:24]))
        elif len(item) > 48:
            # A real variable name is short: the longest this fleet uses is
            # GOOGLE_APPLICATION_CREDENTIALS at 30. 48 leaves generous headroom
            # while sitting BELOW 64, which is the length of a sha256 hex token —
            # the common secret shape, and a syntactically valid identifier. A
            # cap of 64 would have let exactly that through (measured: it did).
            bad.append("%s: env entry is %d chars — too long to be a name" % (name, len(item)))
    allow = seat.get("exec_allowlist") or []
    if not allow:
        bad.append("%s: empty or missing exec_allowlist" % name)
    for item in allow:
        if not isinstance(item, str) or not BASENAME.match(item) or len(item) > 64:
            bad.append("%s: exec_allowlist entry is not a plain basename: %r" % (name, str(item)[:24]))
    for item in seat.get("exec_search_path", []):
        if not isinstance(item, str) or not (item.startswith("/") or item.startswith("~/")):
            bad.append("%s: bare-relative exec_search_path entry %r" % (name, str(item)[:24]))
    # A seat's allowlist must plausibly serve the seat it belongs to. Without
    # this, `"exec_allowlist": ["codxe"]` is structurally perfect and the
    # resolution check below cannot see it on a machine where codex is not
    # installed -- which is every CI runner. Found by blind cross-family
    # refutation (Codex GPT-5.6 sol).
    expected = name[:-5] if name.endswith("-seat") else name
    if expected not in allow:
        bad.append("%s: exec_allowlist %r does not contain %r, the executable this seat is named for"
                   % (name, allow, expected))
if bad:
    sys.stderr.write("\n".join(bad) + "\n")
    sys.exit(1)
REGPY

python3 "$registry_validator" "$REAL_REGISTRY" 2>"$TEMP_DIR/reg.err"
check "the real registry passes the structural rules" test $? -eq 0

# Guilt for the validator itself: the two pastes a real person would actually
# make. Both were MISSED by the grep this replaced.
secret_in_array="$TEMP_DIR/secret-in-array.json"
cat >"$secret_in_array" <<'EOF'
{"seats":{"codex":{"env":["HOME","sk-ant-oat01-FAKEFAKEFAKEFAKEFAKE"],"exec_allowlist":["codex"]}}}
EOF
python3 "$registry_validator" "$secret_in_array" >/dev/null 2>&1
check "a token pasted into an env array is rejected" test $? -ne 0

hex_as_name="$TEMP_DIR/hex-as-name.json"
cat >"$hex_as_name" <<'EOF'
{"seats":{"codex":{"env":["HOME","a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"],"exec_allowlist":["codex"]}}}
EOF
python3 "$registry_validator" "$hex_as_name" >/dev/null 2>&1
check "a hex token wearing a valid name's syntax is rejected on length" test $? -ne 0

# Guilt for the two gaps a blind cross-family refuter (Codex GPT-5.6 sol) found in
# the first version of these rules. Both are edits a real person could plausibly
# make, and both passed everything before this.
prose_secret="$TEMP_DIR/prose-secret.json"
python3 - "$REAL_REGISTRY" "$prose_secret" <<'MKPROSE'
import json, sys
d = json.load(open(sys.argv[1]))
d["seats"]["codex"]["note"] = "OPENAI_API_KEY: sk-proj-0123456789abcdefghijklmnopqrstuv"
json.dump(d, open(sys.argv[2], "w"))
MKPROSE
python3 "$registry_validator" "$prose_secret" >/dev/null 2>&1
check "a secret wrapped in prose inside a note is rejected" test $? -ne 0

typo_allowlist="$TEMP_DIR/typo-allowlist.json"
python3 - "$REAL_REGISTRY" "$typo_allowlist" <<'MKTYPO'
import json, sys
d = json.load(open(sys.argv[1]))
d["seats"]["codex"]["exec_allowlist"] = ["codxe"]
json.dump(d, open(sys.argv[2], "w"))
MKTYPO
python3 "$registry_validator" "$typo_allowlist" >/dev/null 2>&1
check "an allowlist that does not name its own seat's executable is rejected" test $? -ne 0

# Resolution half: for each real seat, if its executable exists ANYWHERE the
# operator's own PATH can see it, the broker must resolve it too. A seat whose
# binary is simply not installed on this machine is skipped BY NAME and counted,
# so the printed line distinguishes "checked" from "not present here" instead of
# reporting a silent green.
resolvable_failures=0
resolvable_checked=0
resolvable_skipped=""
for seat_pair in "codex:codex" "agy:agy" "kimi:kimi" "claude-seat:claude"; do
  seat_name="${seat_pair%%:*}"
  seat_bin="${seat_pair##*:}"
  if ! command -v "$seat_bin" >/dev/null 2>&1; then
    resolvable_skipped="$resolvable_skipped $seat_name"
    continue
  fi
  resolvable_checked=$((resolvable_checked + 1))
  if ! "$BROKER" --dry-run "$seat_name" "$seat_bin" >/dev/null 2>&1; then
    resolvable_failures=$((resolvable_failures + 1))
    printf '  seat %s cannot resolve %s through its declared search path\n' "$seat_name" "$seat_bin" >&2
  fi
done
printf '  (real-seat resolution: %s checked, not installed here:%s)\n' \
  "$resolvable_checked" "${resolvable_skipped:- none}"
check "every installed real seat resolves its own executable" test "$resolvable_failures" -eq 0

check "bash syntax passes" bash -n "$BROKER"
check "real registry JSON parses" bash -c 'python3 -m json.tool "$1" >/dev/null' _ "$REAL_REGISTRY"

printf 'TOTAL %s FAILED %s\n' "$TOTAL" "$FAILED"
[ "$FAILED" -eq 0 ]
