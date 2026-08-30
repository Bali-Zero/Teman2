#!/usr/bin/env bash
# Run an approved external CLI with an allowlist-defined environment only.
#
# --dry-run output is machine-readable: key=value records for the plan followed
# by TSV records of the form "env<TAB>NAME<TAB>present|absent".  It reports
# names only; secret values never leave the process environment.
# WITH_SEAT_REGISTRY may override the registry solely to support isolated tests.

set -euo pipefail

# Resolved from THIS SCRIPT's location, not the caller's cwd. A relative default
# made the broker work only when invoked from the repo root -- measured: from any
# other directory it died with "registry not found". It fails closed, which is the
# right direction, but a security wrapper that cannot be called from where its
# callers live is a wrapper that gets bypassed.
SCRIPT_DIR="$(cd -P "$(dirname "$0")" && pwd)"
readonly SCRIPT_DIR
readonly DEFAULT_REGISTRY="${SCRIPT_DIR}/../infra/llm-credentials/seat-env.json"
readonly FIXED_COMMAND_PATHS="/opt/homebrew/bin /usr/local/bin /usr/bin /bin"

usage() {
  cat <<'EOF'
Usage: with_seat.sh [--dry-run] <seat> <command> [args...]

Runs an allowlisted command with exactly the environment names declared for the
seat.  WITH_SEAT_REGISTRY is a test-only override for the registry path.
EOF
}

fail() {
  printf '%s\n' "with_seat: error: $*" >&2
  exit 1
}

# Mode via python3, NOT stat.
#
# `stat` is the one tool here whose FLAGS differ by platform: BSD/macOS wants
# `stat -f '%Lp'`, GNU/ubuntu wants `stat -c '%a'`, and on GNU `-f` is not an
# unknown flag at all -- it means --file-system. A probe of the form
# "try the BSD form, fall back to the GNU form if it fails" therefore rests on
# GNU stat FAILING for the right reason, which is a guess about another
# platform's error handling, and the consequence of guessing wrong is that this
# function returns garbage and the group/world-writable refusal below silently
# stops refusing. python3 is already a hard dependency of this script (the
# registry parser and the exec runner are both python), so it costs nothing and
# it means the same thing on every machine.
file_mode() {
  /usr/bin/python3 -c 'import os,sys; print("%o" % (os.stat(sys.argv[1]).st_mode & 0o777))' "$1"
}

is_group_or_world_writable() {
  local mode="$1"
  local group_part
  local group_digit
  local other_digit

  mode="${mode#0}"
  while [ "${#mode}" -lt 3 ]; do
    mode="0${mode}"
  done
  group_part="${mode%?}"
  group_digit="${group_part#?}"
  other_digit="${mode#??}"
  case "$group_digit$other_digit" in
    *2*|*3*|*6*|*7*) return 0 ;;
    *) return 1 ;;
  esac
}

# A caller may name only a BARE COMMAND, never a path.
#
# This is the difference between an allowlist and a naming convention. The first
# version accepted any argument containing "/" as a literal path and then checked
# only its BASENAME against the seat's allowlist -- so
# `with_seat.sh codex /tmp/evil/codex` executed the attacker's binary, measured,
# with the broker reporting a clean exit. An exec allowlist that a caller can
# satisfy by choosing a filename is not an allowlist.
#
# Resolution therefore happens ONLY through a search path the REGISTRY supplies:
# the seat's optional `exec_search_path`, else the fixed list above. The registry
# is the right source because it is already the trusted input here -- the wrapper
# refuses to run at all if it is group- or world-writable -- whereas argv and the
# environment are attacker-reachable by construction.
resolve_command() {
  local requested="$1"
  shift
  local candidate
  local directory

  # No path separators: a caller names WHAT to run, never WHERE it lives.
  case "$requested" in
    */*) return 2 ;;
  esac

  for directory in "$@"; do
    candidate="$directory/$requested"
    if [ -x "$candidate" ] && [ ! -d "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

emit_declared_environment() {
  local index
  local env_name
  local env_value

  for ((index = 0; index < ${#DECLARED_NAMES[@]}; index++)); do
    env_name="${DECLARED_NAMES[$index]}"
    if [[ -n "${!env_name+x}" ]]; then
      env_value="${!env_name}"
      # NUL framing keeps values off argv, diagnostics, and temporary files.
      printf '%s\0%s\0' "$env_name" "$env_value"
    fi
  done
}

if [ "$#" -eq 0 ]; then
  usage >&2
  exit 1
fi

if [ "$1" = "--help" ]; then
  usage
  exit 0
fi

dry_run=0
if [ "$1" = "--dry-run" ]; then
  dry_run=1
  shift
fi

[ "$#" -ge 1 ] || fail "missing seat"
seat="$1"
shift
[ "$#" -ge 1 ] || fail "empty command"
requested_command="$1"
shift
[ -n "$requested_command" ] || fail "empty command"

script_path="$(cd -P "$(dirname "$0")" && pwd)/$(basename "$0")"
script_mode="$(file_mode "$script_path")" || fail "cannot inspect wrapper mode"
if is_group_or_world_writable "$script_mode"; then
  # A writable wrapper is risky, but we cannot safely infer the operator's intent.
  printf '%s\n' "with_seat: warning: wrapper is group- or world-writable" >&2
fi

registry="${WITH_SEAT_REGISTRY:-$DEFAULT_REGISTRY}"
[ -f "$registry" ] || fail "registry not found"
registry_mode="$(file_mode "$registry")" || fail "cannot inspect registry mode"
if is_group_or_world_writable "$registry_mode"; then
  fail "registry is group- or world-writable"
fi

metadata_file="$(mktemp "${TMPDIR:-/tmp}/with-seat-metadata.XXXXXX")"
# A signal trap that only cleans up does NOT stop the script: measured on bash
# 3.2, `trap 'rm -f x' TERM` + `kill -TERM $$` prints the line after it and exits
# 0. A broker that survives the TERM its supervisor sent, and then reports
# success, is a broker whose caller believes a dispatch was cancelled when it was
# not. Clean up, restore the default handler, and re-raise so the exit status
# carries the signal.
cleanup_and_reraise() {
  local signal="$1"
  rm -f "$metadata_file"
  trap - "$signal"
  kill -s "$signal" $$
}
trap 'rm -f "$metadata_file"' EXIT
for _sig in HUP INT TERM; do
  # shellcheck disable=SC2064  # expand $_sig now: each trap must name its own signal
  trap "cleanup_and_reraise $_sig" "$_sig"
done

# Python is used only for JSON validation/parsing; values are neither read nor emitted here.
if ! /usr/bin/python3 - "$registry" "$seat" >"$metadata_file" <<'PY'
import hashlib
import json
import os
import re
import sys

registry_path, requested_seat = sys.argv[1:]
try:
    with open(registry_path, "r") as registry_file:
        registry = json.load(registry_file)
except (OSError, ValueError) as exc:
    sys.stderr.write("with_seat: error: invalid registry: %s\n" % exc)
    sys.exit(1)

seats = registry.get("seats") if isinstance(registry, dict) else None
if not isinstance(seats, dict) or requested_seat not in seats:
    sys.stderr.write("with_seat: error: unknown seat %s\n" % requested_seat)
    sys.exit(1)

seat = seats[requested_seat]
if not isinstance(seat, dict):
    sys.stderr.write("with_seat: error: seat %s is not an object\n" % requested_seat)
    sys.exit(1)
names = seat.get("env")
if not isinstance(names, list) or not names:
    sys.stderr.write("with_seat: error: seat %s env declaration is empty or not a list\n" % requested_seat)
    sys.exit(1)
for name in names:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        sys.stderr.write("with_seat: error: malformed env name in seat %s\n" % requested_seat)
        sys.exit(1)
if len(set(names)) != len(names):
    sys.stderr.write("with_seat: error: duplicate env name in seat %s\n" % requested_seat)
    sys.exit(1)

allowlist = seat.get("exec_allowlist")
# `not allowlist` rejects the EMPTY list explicitly: all() is vacuously true on
# it, so an empty allowlist would have passed validation and then blown up
# downstream on an unbound array under set -u. "Permits nothing" must be an
# error the registry author sees, not a crash a caller sees.
if not isinstance(allowlist, list) or not allowlist or not all(
    isinstance(item, str) and item and os.path.basename(item) == item for item in allowlist
):
    sys.stderr.write("with_seat: error: invalid or empty exec_allowlist in seat %s\n" % requested_seat)
    sys.exit(1)

# Optional per-seat search path. Absolute, or "~/"-prefixed and expanded against
# the BROKER's own HOME -- never a bare relative entry, which would resolve
# against the CALLER's cwd and hand back exactly the caller-controlled
# resolution this field exists to remove.
#
# "~/" is not a convenience: agy lives in ~/.local/bin and kimi in
# ~/.kimi-code/bin, and this fleet's three machines do not share a home
# (/Users/nuzantara on Pro and Mini, /Users/balizero on M5). An absolute-only
# rule would force a machine-specific registry, and a registry that is wrong on
# one machine is a broker that gets bypassed there.
search_path = seat.get("exec_search_path", [])
if not isinstance(search_path, list) or not all(
    isinstance(item, str) and (item.startswith("/") or item.startswith("~/"))
    for item in search_path
):
    sys.stderr.write("with_seat: error: invalid exec_search_path in seat %s\n" % requested_seat)
    sys.exit(1)
home = os.environ.get("HOME", "")
expanded_search_path = []
for item in search_path:
    if item.startswith("~/"):
        if not home:
            sys.stderr.write("with_seat: error: exec_search_path uses ~/ but HOME is unset\n")
            sys.exit(1)
        expanded_search_path.append(os.path.join(home, item[2:]))
    else:
        expanded_search_path.append(item)
search_path = expanded_search_path

sorted_names = sorted(names)
# The newline delimiter makes the ordered input to the documented digest unambiguous.
fingerprint = hashlib.sha256("\n".join(sorted_names).encode("utf-8")).hexdigest()[:16]
print("fingerprint\t%s" % fingerprint)
for name in sorted_names:
    print("env\t%s" % name)
for executable in allowlist:
    print("allow\t%s" % executable)
for directory in search_path:
    print("searchpath\t%s" % directory)
PY
then
  exit 1
fi

fingerprint=""
# `=()` is load-bearing, not style. `declare -a X` alone leaves X with the array
# ATTRIBUTE but no value, so on bash 5 `${#X[@]}` under `set -u` is an "unbound
# variable" error the first time through the loop below; bash 3.2 tolerates it.
# This machine has only bash 3.2, so the corpus was green here and the job died on
# every ubuntu runner at the first env name — the whole dispatch path, invisible
# locally. Assigning an empty array makes them SET on both.
declare -a DECLARED_NAMES=()
declare -a ALLOWED_EXECUTABLES=()
declare -a SEARCH_PATH=()
while IFS=$'\t' read -r kind value; do
  case "$kind" in
    fingerprint) fingerprint="$value" ;;
    env) DECLARED_NAMES[${#DECLARED_NAMES[@]}]="$value" ;;
    allow) ALLOWED_EXECUTABLES[${#ALLOWED_EXECUTABLES[@]}]="$value" ;;
    searchpath) SEARCH_PATH[${#SEARCH_PATH[@]}]="$value" ;;
    *) fail "invalid registry parser output" ;;
  esac
done <"$metadata_file"

# The seat may narrow WHERE its executables are found; absent that, the fixed
# system list. Either way the caller never contributes a directory.
if [ "${#SEARCH_PATH[@]}" -eq 0 ]; then
  for _fixed_dir in $FIXED_COMMAND_PATHS; do
    SEARCH_PATH[${#SEARCH_PATH[@]}]="$_fixed_dir"
  done
fi

[ -n "$fingerprint" ] || fail "registry parser did not return a fingerprint"
# The python validator refuses a seat with an empty `env` list, so an empty array
# here means the parse loop never ran — a silently skipped read rather than an
# empty declaration. Fail rather than dispatch a child with NO environment, which
# would look like perfect isolation and be a broken probe.
[ "${#DECLARED_NAMES[@]}" -gt 0 ] || fail "registry parser returned no environment names"
resolve_status=0
resolved_command="$(resolve_command "$requested_command" "${SEARCH_PATH[@]}")" || resolve_status=$?
if [ "$resolve_status" -eq 2 ]; then
  fail "command must be a bare name, not a path: '$requested_command' (the seat's registry entry decides where its executables live)"
elif [ "$resolve_status" -ne 0 ]; then
  fail "cannot resolve command '$requested_command' on this seat's search path"
fi
command_basename="$(basename "$resolved_command")"
allowed=0
for executable in "${ALLOWED_EXECUTABLES[@]}"; do
  if [ "$command_basename" = "$executable" ]; then
    allowed=1
    break
  fi
done
[ "$allowed" -eq 1 ] || fail "command basename is not permitted for seat $seat"

if [ "$dry_run" -eq 1 ]; then
  printf 'seat=%s\n' "$seat"
  printf 'fingerprint=%s\n' "$fingerprint"
  printf 'command=%s\n' "$resolved_command"
  for env_name in "${DECLARED_NAMES[@]}"; do
    if [[ -n "${!env_name+x}" ]]; then
      printf 'env\t%s\tpresent\n' "$env_name"
    else
      printf 'env\t%s\tabsent\n' "$env_name"
    fi
  done
  exit 0
fi

# The runner starts under env -i.  It receives NUL-framed values over stdin and
# uses execve with a new dictionary, so bash/macOS helper variables cannot leak.
# `set +e` alone is not enough: it disables errexit but leaves PIPEFAIL on, so a
# SIGPIPE or failure in the LEFT side of this pipeline would be reported as the
# child's exit status. The child's status is the one thing this wrapper promises
# to preserve faithfully, so pipefail is disabled for exactly this pipeline.
set +e
set +o pipefail
emit_declared_environment | env -i /usr/bin/python3 -c '
import os
import sys

data = sys.stdin.buffer.read()
parts = data.split(b"\0")
if parts and parts[-1] == b"":
    parts.pop()
if len(parts) % 2:
    sys.stderr.write("with_seat: error: invalid internal environment stream\n")
    sys.exit(1)
child_environment = {}
for index in range(0, len(parts), 2):
    child_environment[parts[index]] = parts[index + 1]
os.execve(sys.argv[1], sys.argv[1:], child_environment)
' "$resolved_command" "$@"
child_status=$?
set -o pipefail
set -e

printf 'with_seat: seat=%s fingerprint=%s exit_status=%s\n' "$seat" "$fingerprint" "$child_status" >&2
exit "$child_status"
