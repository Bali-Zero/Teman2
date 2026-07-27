#!/usr/bin/env bash
# Guilt + innocence corpus for scripts/ci/queue_rearm_classify.sh
# (superscar #3 antidote: "nessuna guardia mergiata senza un test di innocenza
#  E di colpevolezza"). The guard here decides whether a pull request may be
#  put BACK into the merge queue, so a false "yes" turns the queue into a
#  machine that retries until it passes — a disarmed gate that still looks
#  armed (superscar #2).
#
# GUILT     — an infrastructural failure IS classified re-armable.
# INNOCENCE — a code failure is NOT, and neither is a mixed set, and neither
#             is a snapshot that has not finished.
# SCAR-PINS — the three real mistakes this tool exists to not repeat:
#             * an EMPTY conclusion read as "no failure"  (#3326, 2026-07-27)
#             * a `cancelled` treated as non-terminal     (2026-07-26)
#             * an EMPTY input read as a clean verdict    (empty-set lesson)
#
# No network, no `gh`, no fixtures on disk. Runs in any POSIX-ish bash.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNDER_TEST="$SCRIPT_DIR/queue_rearm_classify.sh"
FAILURES=0

fail() { echo "  ✗ $*"; FAILURES=$((FAILURES + 1)); }
pass() { echo "  ✓ $*"; }

if [[ ! -x "$UNDER_TEST" ]]; then
  echo "FATAL: $UNDER_TEST missing or not executable"
  exit 1
fi

# expect <label> <want_verdict> <want_rc> <<< rows
expect() {
  local label="$1" want="$2" want_rc="$3" out rc
  out="$("$UNDER_TEST")"
  rc=$?
  if [[ "$out" != "$want" ]]; then
    fail "$label — verdict want=$want got=$out"
    return
  fi
  if [[ "$rc" != "$want_rc" ]]; then
    fail "$label — exit code want=$want_rc got=$rc (verdict was right; the rc contract is not)"
    return
  fi
  pass "$label ($out, rc=$rc)"
}

T=$'\t'
INFRA=1
CLEAN=0

echo "── GUILT: an infra failure is re-armable ──"

expect "single docker-pull failure -> INFRA" INFRA 0 <<EOF
30261173862${T}completed${T}failure${T}${INFRA}${T}Tests & Coverage
EOF

expect "infra failure alongside green siblings -> INFRA" INFRA 0 <<EOF
1${T}completed${T}success${T}${CLEAN}${T}Security Scanning
2${T}completed${T}failure${T}${INFRA}${T}Tests & Coverage
3${T}completed${T}success${T}${CLEAN}${T}actionlint
EOF

echo "── INNOCENCE: a code failure is never retried ──"

expect "single code failure -> CODE" CODE 1 <<EOF
1${T}completed${T}failure${T}${CLEAN}${T}Tests & Coverage
EOF

# THE load-bearing case: unanimity. Nine infra reds do not buy one code red a
# retry. Without this test, an implementation using "any infra hit" instead of
# "all failures are infra" would look green.
expect "MIXED infra+code -> CODE (unanimity)" CODE 1 <<EOF
1${T}completed${T}failure${T}${INFRA}${T}Tests & Coverage
2${T}completed${T}failure${T}${CLEAN}${T}Backend Tests (Python)
EOF

expect "all-green terminal set -> UNKNOWN (not our business)" UNKNOWN 3 <<EOF
1${T}completed${T}success${T}${CLEAN}${T}Security Scanning
2${T}completed${T}success${T}${CLEAN}${T}Tests & Coverage
EOF

echo "── SCAR-PIN 1: an EMPTY conclusion is 'not yet known', not 'no failure' ──"
# 2026-07-27, #3326: read while in_progress with conclusion=∅ and filed as
# "ejected with ZERO failures". At terminal state it was `failure`.
expect "in_progress + empty conclusion -> UNKNOWN" UNKNOWN 3 <<EOF
1${T}completed${T}success${T}${CLEAN}${T}Security Scanning
2${T}in_progress${T}${T}${CLEAN}${T}Tests & Coverage
EOF

# The converse half: once a failure IS known, a sibling still running cannot
# un-know it. Without this, the pending-guard would swallow decided reds.
expect "in_progress + a KNOWN code failure -> CODE" CODE 1 <<EOF
1${T}in_progress${T}${T}${CLEAN}${T}Security Scanning
2${T}completed${T}failure${T}${CLEAN}${T}Backend Tests (Python)
EOF

expect "in_progress + a KNOWN infra failure -> INFRA" INFRA 0 <<EOF
1${T}in_progress${T}${T}${CLEAN}${T}Security Scanning
2${T}completed${T}failure${T}${INFRA}${T}Tests & Coverage
EOF

# THE case that makes the pending-guard non-decorative, found by MUTATION:
# deleting the guard entirely left every other test green, because they all
# fall through to UNKNOWN by another route. Only here does the guard change
# the answer — without it, a set with a cancelled row and something STILL
# RUNNING reads CANCELLED, i.e. re-armable, which is acting on a snapshot: the
# in-flight check may yet fail, and this tool would already have re-queued it.
# (W104's gotcha, in a corpus rather than in a cure: the first antibody you
# write for a defect is the one most likely to be decorative by construction.)
expect "cancelled + something STILL RUNNING -> UNKNOWN, not CANCELLED" UNKNOWN 3 <<EOF
1${T}completed${T}cancelled${T}${CLEAN}${T}Security Scanning
2${T}in_progress${T}${T}${CLEAN}${T}Tests & Coverage
EOF

echo "── SCAR-PIN 2: a cancelled conclusion IS terminal ──"
# 2026-07-26: a cancelled required check is terminal AND invisible.
expect "cancelled with no failure -> CANCELLED" CANCELLED 2 <<EOF
1${T}completed${T}success${T}${CLEAN}${T}Security Scanning
2${T}completed${T}cancelled${T}${CLEAN}${T}Tests & Coverage
EOF

expect "cancelled DOES NOT rescue a code failure" CODE 1 <<EOF
1${T}completed${T}cancelled${T}${CLEAN}${T}Security Scanning
2${T}completed${T}failure${T}${CLEAN}${T}Backend Tests (Python)
EOF

echo "── SCAR-PIN 3: an EMPTY input decides nothing ──"
# An empty set otherwise impersonates both everything and nothing.
expect "zero rows -> UNKNOWN" UNKNOWN 3 </dev/null

expect "blank lines only -> UNKNOWN" UNKNOWN 3 <<EOF


EOF

echo "── EDGE: unreadable evidence is not clean evidence ──"
expect "a row missing fields, nothing else -> UNKNOWN" UNKNOWN 3 <<EOF
1
EOF

# timed_out is a failure shape too — a required check that never answered is
# not a pass. Left as CODE unless the caller proved it infrastructural.
expect "timed_out with no infra proof -> CODE" CODE 1 <<EOF
1${T}completed${T}timed_out${T}${CLEAN}${T}Tests & Coverage
EOF

expect "timed_out proven infra -> INFRA" INFRA 0 <<EOF
1${T}completed${T}timed_out${T}${INFRA}${T}Tests & Coverage
EOF

echo
# ---------------------------------------------------------------------------
# INFRA_RE corpus. The classifier above is handed `infra_hit` already computed;
# the thing that COMPUTES it is the regex in queue_rearm.sh, and a matcher that
# decides "infrastructural or the diff's fault" is a guard like any other — it
# does not ship without proof it fires on the guilty AND spares the innocent
# (superscar #3). Read out of the real file rather than restated here, so the
# corpus cannot pass against a copy while the live pattern drifts.
# ---------------------------------------------------------------------------
INFRA_RE=$(grep "^INFRA_RE=" "$SCRIPT_DIR/queue_rearm.sh" | sed "s/^INFRA_RE='//;s/'$//")
if [[ -z "$INFRA_RE" ]]; then
  echo "FAILED: could not read INFRA_RE out of queue_rearm.sh"
  exit 1
fi

infra_case() { # <expect: yes|no> <name> <line>
  local want="$1" name="$2" line="$3" got=no
  printf '%s' "$line" | grep -qE "$INFRA_RE" && got=yes
  if [[ "$got" == "$want" ]]; then
    printf '  ✅ %s\n' "$name"
  else
    printf '  ❌ %s (want %s, got %s)\n' "$name" "$want" "$got"
    FAILURES=$((FAILURES + 1))
  fi
}

echo "INFRA_RE — guilt:"
# The line from #3372, 2026-07-28: the queue destroyed its temporary branch on
# ejection and a still-running CodeQL then failed uploading to it.
#
# The 40-char SHA is DELIBERATELY a short placeholder rather than the real one.
# The first draft pasted the actual commit hash "verbatim" and `Detect Secrets`
# — a required check — flagged it as a Hex/Base64 High Entropy String and went
# red. Nothing here needs the true hash: what the matcher keys on is the PATH
# SHAPE (`refs/heads/gh-readonly-queue/<base>/pr-<n>-<sha>`), so fidelity to the
# shape is the fidelity that matters, and a realistic-looking 40-hex string buys
# nothing but a secret-scanner false positive on every future run.
infra_case yes "post-ejection ref vanished (#3372)" \
  "##[error]ref 'refs/heads/gh-readonly-queue/main/pr-3372-abc1234' not found in the repository"
infra_case yes "docker.io container-init timeout (the original cause)" \
  "Error response from daemon: registry-1.docker.io: context deadline exceeded"

echo "INFRA_RE — innocence:"
# The one that matters most: a MISSING REF is only infrastructural when it is
# the queue's own temporary branch. Any other vanished ref is a real problem.
infra_case no "an ordinary missing ref is NOT infra" \
  "ref 'refs/heads/feature/my-branch' not found in the repository"
infra_case no "a genuine test failure" "AssertionError: expected 3 items, got 4"
infra_case no "a syntax error" "SyntaxError: invalid syntax at line 42"
infra_case no "a lint rejection" "RH005: test function has no assertion"

echo
if (( FAILURES > 0 )); then
  echo "FAILED: $FAILURES case(s)"
  exit 1
fi
echo "OK: every case passed"
