#!/usr/bin/env bash
# Guilt + innocence corpus for scripts/ci/apt_install.sh.
#
# WHY THIS EXISTS, in the words of the failure it pins:
# `apt-get` has no timeout of its own. On 2026-08-18 the unbounded
# `Require zsh` step in organ-conformance.yml ran 10m15s against a
# `timeout-minutes: 10` job budget, twice. GitHub reports a budget kill as
# `cancelled`, NOT `failure` — so a REQUIRED context went not-green with no
# failing check anywhere to point at, and the merge queue ejected the entry.
# That is why the bound, and the SIZE of the bound, are both properties worth
# testing: the FIRST attempt at this cure retried 3x180s inside the same
# 10-minute budget, which does not avoid budget exhaustion — it guarantees it.
# test_the_total_bound_fits_well_inside_a_ten_minute_job pins that arithmetic
# so the next author cannot re-derive the same mistake from a green suite.
#
# The stubs make `timeout`/`sudo`/`apt-get` observable, which also lets this
# corpus run on a machine that has no `timeout` at all (macOS) — and the
# missing-timeout case is itself asserted, because "the tool is absent" must
# never read as green.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUT="$HERE/apt_install.sh"
PASS=0
FAIL=0

fail() { echo "  FAIL: $*"; FAIL=$((FAIL + 1)); }
ok() { echo "  ok: $*"; PASS=$((PASS + 1)); }

# Builds a sandbox: $BIN holds the stubs, $LOG_* capture what was invoked.
# APT_UPDATE_RC / APT_INSTALL_RC steer the fake apt; APT_CREATES names a
# binary the fake install "produces" (empty = install succeeds but delivers
# nothing, the fail-open trap).
setup() {
  SANDBOX="$(mktemp -d)"
  BIN="$SANDBOX/bin"
  mkdir -p "$BIN"
  LOG_TIMEOUT="$SANDBOX/timeout.log"
  LOG_APT="$SANDBOX/apt.log"
  LOG_SOURCE="$SANDBOX/fallback.sources"
  LOG_SOURCE_ORIGIN="$SANDBOX/fallback.origin"
  : >"$LOG_TIMEOUT"
  : >"$LOG_APT"
  : >"$LOG_SOURCE"
  : >"$LOG_SOURCE_ORIGIN"

  cat >"$BIN/timeout" <<EOF
#!/usr/bin/env bash
echo "\$@" >>"$LOG_TIMEOUT"
shift    # drop the duration; run the rest for real (against the stubs below)
exec "\$@"
EOF

  cat >"$BIN/sudo" <<'EOF'
#!/usr/bin/env bash
exec "$@"
EOF

  cat >"$BIN/apt-get" <<EOF
#!/usr/bin/env bash
echo "\$@" >>"$LOG_APT"
ARGS=("\$@")
SOURCE_LIST=""
SOURCE_PARTS=""
for ((i = 0; i < \${#ARGS[@]}; i++)); do
  if [ "\${ARGS[i]}" = "-o" ]; then
    i=\$((i + 1))
    case "\${ARGS[i]}" in
      Dir::Etc::SourceList=*) SOURCE_LIST="\${ARGS[i]#Dir::Etc::SourceList=}" ;;
      Dir::Etc::SourceParts=*) SOURCE_PARTS="\${ARGS[i]#Dir::Etc::SourceParts=}" ;;
    esac
  fi
done
# apt's own rule, as measured on ubuntu:24.04: SourceList is one-line format
# only; a deb822 stanza there is a parse error before any network I/O.
if [ -n "\$SOURCE_LIST" ] && grep -Eq '^[[:space:]]*(Types|URIs|Suites|Components):' "\$SOURCE_LIST"; then
  echo "E: Type 'Types:' is not known on line 1 in source list \$SOURCE_LIST" >&2
  echo "E: The list of sources could not be read." >&2
  exit 100
fi
IS_UPDATE=0
for a in "\${ARGS[@]}"; do [ "\$a" = "update" ] && IS_UPDATE=1; done
if [ "\${APT_REQUIRE_FALLBACK:-}" = "1" ]; then
  if [ -z "\$SOURCE_LIST" ]; then exit 100; fi
  if [ -n "\$SOURCE_PARTS" ] && ls "\$SOURCE_PARTS"/*.sources >/dev/null 2>&1; then
    cat "\$SOURCE_PARTS"/*.sources >"$LOG_SOURCE"
    echo "parts" >"$LOG_SOURCE_ORIGIN"
  else
    cat "\$SOURCE_LIST" >"$LOG_SOURCE"
    echo "list" >"$LOG_SOURCE_ORIGIN"
  fi
  [ "\$IS_UPDATE" = "1" ] && exit "\${APT_FALLBACK_UPDATE_RC:-0}"
  if [ -n "\${APT_CREATES:-}" ]; then
    printf '#!/bin/sh\nexit 0\n' >"$BIN/\$APT_CREATES"
    chmod +x "$BIN/\$APT_CREATES"
  fi
  exit "\${APT_FALLBACK_RC:-0}"
fi
for a in "\${ARGS[@]}"; do
  if [ "\$a" = "update" ]; then exit \${APT_UPDATE_RC:-0}; fi
done
if [ -n "\${APT_CREATES:-}" ]; then
  printf '#!/bin/sh\nexit 0\n' >"$BIN/\$APT_CREATES"
  chmod +x "$BIN/\$APT_CREATES"
fi
exit \${APT_INSTALL_RC:-0}
EOF

  chmod +x "$BIN"/*
}

teardown() { rm -rf "$SANDBOX"; }

# Runs the subject with ONLY the stub dir on PATH (plus the system dirs the
# script's own `set`/`command` need). Captures rc without tripping errexit.
run_sut() {
  ( PATH="$BIN:/usr/bin:/bin" "$@" bash "$SUT" "${SUT_ARGS[@]}" ) >"$SANDBOX/out" 2>&1
  echo $?
}

echo "== apt_install.sh corpus =="

# ---------------------------------------------------------------- innocence
setup
printf '#!/bin/sh\nexit 0\n' >"$BIN/nzfakebin"; chmod +x "$BIN/nzfakebin"
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env)
[ "$RC" = "0" ] || fail "already-present: rc=$RC (want 0)"
[ "$RC" = "0" ] && ok "a binary already on PATH exits 0"
if [ -s "$LOG_APT" ]; then fail "already-present: apt was invoked anyway"; else ok "...and never calls apt"; fi
teardown

# -------------------------------------------------------------------- guilt
# The cure itself: nothing may reach apt un-bounded.
setup
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env APT_CREATES=nzfakebin)
[ "$RC" = "0" ] || fail "bounded-install: rc=$RC (want 0)"
APT_CALLS=$(wc -l <"$LOG_APT" | tr -d ' ')
TIMEOUT_CALLS=$(wc -l <"$LOG_TIMEOUT" | tr -d ' ')
if [ "$APT_CALLS" = "$TIMEOUT_CALLS" ] && [ "$APT_CALLS" -ge 2 ]; then
  ok "every apt invocation ($APT_CALLS) went through timeout"
else
  fail "unbounded apt: $APT_CALLS apt calls vs $TIMEOUT_CALLS timeout wrappers"
fi
if grep -qE '^[0-9]+ ' "$LOG_TIMEOUT"; then
  ok "timeout was given a numeric bound"
else
  fail "timeout invoked without a leading numeric duration: $(cat "$LOG_TIMEOUT")"
fi
# The arithmetic that the FIRST cure got wrong (3x180s inside a 10-min budget).
TOTAL=$(awk '{s += $1} END {print s+0}' "$LOG_TIMEOUT")
if [ "$TOTAL" -le 240 ]; then
  ok "total bound ${TOTAL}s fits well inside a ten-minute job budget"
else
  fail "total bound ${TOTAL}s is too close to (or over) the job budget"
fi
teardown

# The primary mirror can stall while another mirror is healthy. The fallback
# must use an isolated sources file, never rewrite /etc/apt.
setup
SOURCES="$SANDBOX/ubuntu.sources"
printf 'Types: deb\nURIs: http://azure.archive.ubuntu.com/ubuntu\nSuites: noble\n' >"$SOURCES"
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env APT_REQUIRE_FALLBACK=1 APT_INSTALL_SOURCES_FILE="$SOURCES" APT_CREATES=nzfakebin)
[ "$RC" = "0" ] && ok "fallback mirror delivers after primary stalls" || fail "fallback mirror rc=$RC (want 0)"
grep -q 'delivered by fallback mirror archive.ubuntu.com' "$SANDBOX/out" && ok "...and names the fallback mirror" || fail "fallback delivery was not reported"
grep -q 'archive.ubuntu.com' "$LOG_SOURCE" && ! grep -q 'azure.archive.ubuntu.com' "$LOG_SOURCE" && ok "...and rewrites only the temporary sources file" || fail "fallback sources were not rewritten"
[ "$(cat "$LOG_SOURCE_ORIGIN")" = "parts" ] && ok "...deb822 stanzas reach apt as a SourceParts *.sources file" || fail "deb822 sources were handed to apt as SourceList (origin=$(cat "$LOG_SOURCE_ORIGIN"))"
if grep -q "Type 'Types:' is not known" "$SANDBOX/out"; then fail "apt rejected the fallback sources as deb822-in-SourceList"; else ok "...and apt never sees a deb822 body through SourceList"; fi
grep -q '::warning::apt_install: primary mirror azure.archive.ubuntu.com did not deliver' "$SANDBOX/out" && ok "...and warns that the primary stalled" || fail "no ::warning:: for the stalled primary"
if grep -q '/etc/apt' "$LOG_APT"; then fail "fallback wrote /etc/apt"; else ok "...and never writes /etc/apt"; fi
teardown

# The same fallback from a one-line sources.list (pre-24.04 images) goes
# through SourceList, rewritten, and still never touches /etc/apt.
setup
SOURCES="$SANDBOX/sources.list"
printf 'deb http://azure.archive.ubuntu.com/ubuntu noble main\n' >"$SOURCES"
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env APT_REQUIRE_FALLBACK=1 APT_INSTALL_SOURCES_FILE="$SOURCES" APT_CREATES=nzfakebin)
[ "$RC" = "0" ] && ok "one-line sources.list: fallback mirror delivers" || fail "one-line fallback rc=$RC (want 0)"
[ "$(cat "$LOG_SOURCE_ORIGIN")" = "list" ] && grep -q 'deb http://archive.ubuntu.com/ubuntu noble main' "$LOG_SOURCE" && ok "...through SourceList, host rewritten" || fail "one-line sources not rewritten through SourceList"
grep -q 'trying archive.ubuntu.com (one-line sources)' "$SANDBOX/out" && ok "...and names the format it used" || fail "format not named in the warning"
teardown

# A second stalled mirror still fails closed and names the unavailable package.
setup
SOURCES="$SANDBOX/ubuntu.sources"
printf 'URIs: http://azure.archive.ubuntu.com/ubuntu\n' >"$SOURCES"
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env APT_REQUIRE_FALLBACK=1 APT_FALLBACK_RC=100 APT_INSTALL_SOURCES_FILE="$SOURCES")
[ "$RC" != "0" ] && ok "two stalled mirrors fail closed" || fail "two stalled mirrors rc=0"
grep -q "package 'nzfakebin' is still unavailable" "$SANDBOX/out" && ok "...and names the package" || fail "missing package failure message"
TOTAL=$(awk '{s += $1} END {print s+0}' "$LOG_TIMEOUT")
[ "$TOTAL" -le 240 ] && ok "...within the 240s timeout ceiling" || fail "timeout ceiling ${TOTAL}s exceeds 240s"
teardown

# Without a readable active sources file, fallback is explicitly skipped.
setup
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env APT_INSTALL_RC=100 APT_INSTALL_SOURCES_FILE="$SANDBOX/no-sources")
[ "$RC" != "0" ] && ok "no sources file fails closed" || fail "no sources file rc=0"
grep -q 'no active apt sources file; fallback skipped' "$SANDBOX/out" && ok "...and reports fallback skipped" || fail "missing no-sources message"
[ "$(grep -c 'apt_install:' "$SANDBOX/out")" = "1" ] && ok "...with one stderr diagnostic" || fail "no-sources emitted extra diagnostics"
teardown

# The fail-open I wrote once and must not write again: apt exits 0, the
# binary is still absent, and the step must NOT report green.
setup
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env)   # APT_CREATES unset: install "succeeds", delivers nothing
if [ "$RC" != "0" ]; then ok "install that delivers nothing fails closed (rc=$RC)"; else fail "fail-open: rc=0 with the binary absent"; fi
teardown

# A hard apt failure must also fail closed, not warn-and-continue.
setup
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env APT_INSTALL_RC=100)
if [ "$RC" != "0" ]; then ok "apt install rc=100 fails closed (rc=$RC)"; else fail "fail-open: rc=0 after apt exit 100"; fi
teardown

# `timeout` itself absent (macOS, or a stripped image): still never green.
setup
rm -f "$BIN/timeout"
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env)
if [ "$RC" != "0" ]; then ok "no timeout binary at all still fails closed (rc=$RC)"; else fail "fail-open: rc=0 with timeout missing"; fi
teardown

# ----------------------------------------------------------------- resilience
# A stalled/failed `apt-get update` must NOT abort the install: the runner
# image usually already has the package indexed, and aborting here would turn
# a mirror hiccup into a red required check.
setup
SUT_ARGS=(nzfakebin nzfakebin)
RC=$(run_sut env APT_UPDATE_RC=1 APT_CREATES=nzfakebin)
[ "$RC" = "0" ] && ok "a failed 'apt-get update' still lets the install run" || fail "update failure aborted the install (rc=$RC)"
grep -q "install" "$LOG_APT" && ok "...and apt-get install was actually reached" || fail "apt-get install never ran"
teardown

# ------------------------------------------------------------- the '-' door
# `locales` has no binary of its own — the caller asserts with `locale -a`.
# The sentinel must skip verification WITHOUT skipping the install.
setup
SUT_ARGS=(- locales)
RC=$(run_sut env)
[ "$RC" = "0" ] && ok "'-' sentinel exits 0 with no binary to verify" || fail "'-' sentinel rc=$RC (want 0)"
grep -q "locales" "$LOG_APT" && ok "...and still installed the package" || fail "'-' sentinel skipped the install too"
teardown

# ------------------------------------------------------------------- misuse
setup
SUT_ARGS=(zsh)
RC=$(run_sut env)
[ "$RC" = "2" ] && ok "no package named exits 2 (usage, not a silent no-op)" || fail "missing package: rc=$RC (want 2)"
teardown

echo "== $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]
