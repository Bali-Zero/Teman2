#!/bin/bash
# journey_sentinel.sh — cron wrapper for the L11 production journey sentinels
# (apps/mouth/e2e/production/*.spec.ts, run via
# apps/mouth/playwright.production.config.ts against REAL production).
#
# LaunchAgent: com.nuzantara.journey-sentinel (StartInterval, see plist — an
# hourly cadence, not the VOA probe's 15min: this drives a real chromium
# launch + 5 network-bound page loads against a live host, which is far more
# expensive per tick than a fetch-based journey; none of the four defect
# classes it guards need sub-hour detection latency).
#
# ---------------------------------------------------------------------------
# ORGANISM GENES (infra/organ-conformance/genes.json — this organ is
# mini.journey_sentinel in apps/organism/organism/organs_registry.yaml)
# ---------------------------------------------------------------------------
#
# G2_heartbeat — every run reports liveness to the ORGANISM
#   (scripts/lib/heartbeat.sh -> ~/.organism/last_seen/mini.journey_sentinel.json).
#   Status mapping, decided from the Playwright JSON report, never from this
#   script's own exit code alone (the exit code below is deliberately
#   "honest-nonzero" — see the tail of this file):
#     ok        all real journey specs passed AND the self-test correctly failed
#     degraded  >=1 real journey spec failed, but the self-test correctly
#               failed too (detection pipeline is proven alive; the failure
#               is real and named — e.g. the known prime-maps credential
#               defect, needs-ruling item 1, stays "degraded" not "error"
#               because it is a KNOWN, already-ledgered, operator[GUI] issue,
#               not a fresh unattributed break)
#     error     the self-test did NOT fail (detection pipeline itself may be
#               broken — cicatrix-superscar #2), OR the JSON report could not
#               be read/parsed at all, OR this wrapper could not even start
#               the suite (missing npx/node_modules)
#
# G5_kill_switch — JOURNEY_SENTINEL_ENABLED (default true) is the RUNTIME
#   switch: an operator can silence a tick without touching launchd. Distinct
#   from any install-time toggle (there is none here — this organ has no
#   install-time equivalent of VOA_PROBE_CRON_ENABLED because the plist is
#   rendered by install_journey_sentinel.sh unconditionally; add one there if
#   a future need arises). When disabled: heartbeat "disabled", exit 0,
#   never launches chromium.
#
# G9_fail_visible — `set -uo pipefail`, never a bare pipeline whose exit code
#   is inferred (W101/W108: under errexit a naked pipeline aborts ON the
#   pipeline itself and any capture written after it is dead code on the one
#   path it exists for — this script does not use `set -e` at all, and every
#   command whose exit code matters is captured explicitly with `|| RC=$?`).
#
# G10_single_instance — a portable bash lock via `mkdir` (atomic on every
# POSIX filesystem, no dependency on GNU flock — macOS ships none by
# default, same reasoning as voa-probe-wrapper.sh's zsh-native choice, ported
# to bash). Non-blocking: a busy lock means a SKIPPED tick (status=warning),
# never a failure — losing one tick of a UX-quality sentinel is harmless.
#
# Seeded-failure self-test (family #2 — "a sentinel that greens while dead is
# worse than none"): apps/mouth/e2e/production/_selftest.spec.ts contains ONE
# test designed to fail on EVERY invocation. This wrapper looks it up by
# title in the JSON report and treats anything other than "failed" as proof
# the whole detection pipeline (Playwright JSON schema, this script's parser,
# the alert gateway) may be broken — a DIFFERENT, higher-severity condition
# than a real journey defect. This is verified every single run, not once.
#
# Alerting — routed through the ALREADY-WIRED gateway, no new channel:
# scripts/tg_notify.py --tier p0 --source journey-sentinel --dedup-key <key>.
# tg_notify.py owns its own budget + dedup ladder (TG_P0_BUDGET,
# TG_DEDUP_HOURS) — this wrapper never redirects its stdout/stderr to
# /dev/null and always logs the return code (`tg[p0] rc=N`), matching the
# house pattern established in apps/evaluator/nlm_deep_research/scripts/_alert.sh
# (the W108 cure: "an alarm conditioned on the health of its environment
# works exactly in the cases where it isn't needed" — this alarm depends on
# nothing but the gateway script existing).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOUTH_DIR="$REPO_ROOT/apps/mouth"
HEARTBEAT_LIB="$REPO_ROOT/scripts/lib/heartbeat.sh"
TG_NOTIFY="$REPO_ROOT/scripts/tg_notify.py"
LOG="${HOME}/logs/journey-sentinel.log"
LOCKDIR="${HOME}/logs/journey-sentinel.lockdir"
ORGAN_ID="mini.journey_sentinel"
JSON_REPORT="$MOUTH_DIR/output/playwright/production-results.json"
SELFTEST_MARKER="[SEEDED-FAILURE SELF-TEST]"

mkdir -p "$(dirname "$LOG")"
echo "" >> "$LOG"
echo "=== Journey Sentinel — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

# --- G2 heartbeat plumbing (same exit-trap safety net as voa-probe-wrapper.sh) ---
HB_EMITTED=0
heartbeat() {  # heartbeat <status> [note]
    HB_EMITTED=1
    [ -f "$HEARTBEAT_LIB" ] || return 0
    bash "$HEARTBEAT_LIB" "$ORGAN_ID" "$1" "${2:-}" || true
}
_hb_on_exit() {
    local rc=$?
    if [ "$HB_EMITTED" -eq 0 ]; then
        heartbeat error "aborted before verdict (rc=$rc)"
    fi
    return 0
}
trap _hb_on_exit EXIT

# --- alert helper: log rc, never /dev/null (W108 house pattern) ------------
alert() {  # alert <dedup-key> <text>
    local dedup_key="$1"
    shift
    if [ ! -f "$TG_NOTIFY" ]; then
        echo "[journey-sentinel] ALERT NOT SENT — gateway missing at $TG_NOTIFY: $*" >> "$LOG"
        return 1
    fi
    local out rc
    if out=$(python3 "$TG_NOTIFY" --tier p0 --source journey-sentinel --dedup-key "$dedup_key" -- "$*" 2>&1); then
        rc=0
    else
        rc=$?
    fi
    echo "[journey-sentinel] tg[p0 key=$dedup_key] rc=$rc ${out:-<no output>}" >> "$LOG"
    return $rc
}

# --- G5 kill switch (RUNTIME) -----------------------------------------------
if [ "${JOURNEY_SENTINEL_ENABLED:-true}" = "false" ]; then
    echo "[journey-sentinel] JOURNEY_SENTINEL_ENABLED=false — skipping this tick" >> "$LOG"
    heartbeat "disabled" "kill switch JOURNEY_SENTINEL_ENABLED=false"
    exit 0
fi

# Signature guard (W105 class): the derived REPO_ROOT must actually contain
# what this wrapper is about to invoke.
if [ ! -d "$MOUTH_DIR/e2e/production" ]; then
    echo "[journey-sentinel] FATAL: production spec dir not found under $MOUTH_DIR (REPO_ROOT derived: $REPO_ROOT)" >> "$LOG"
    heartbeat "error" "e2e/production not found under derived REPO_ROOT"
    exit 2
fi
if [ ! -x "$(command -v npx 2>/dev/null)" ]; then
    echo "[journey-sentinel] FATAL: npx not found on PATH" >> "$LOG"
    heartbeat "error" "npx not found on PATH"
    exit 3
fi

# --- G10 single instance (advisory, portable mkdir lock) --------------------
LOCK_ACQUIRED=0
if mkdir "$LOCKDIR" 2>/dev/null; then
    LOCK_ACQUIRED=1
    # bash's EXIT trap is single-slot — chain the lock cleanup onto the
    # existing heartbeat safety-net trap explicitly rather than overwrite it.
    trap '_hb_on_exit; rmdir "$LOCKDIR" 2>/dev/null || true' EXIT
else
    echo "[journey-sentinel] overlapping run detected (lockdir busy: $LOCKDIR) — skipping this tick" >> "$LOG"
    heartbeat "warning" "skipped: overlapping run held the advisory lock"
    exit 0
fi

# --- run the suite -----------------------------------------------------------
echo "[journey-sentinel] running production suite from $MOUTH_DIR" >> "$LOG"
rm -f "$JSON_REPORT"
(
    cd "$MOUTH_DIR" && \
    PROD_SENTINEL_BASE_URL="${JOURNEY_SENTINEL_BASE_URL:-https://balizero.com}" \
    npx playwright test -c playwright.production.config.ts
) >> "$LOG" 2>&1
PLAYWRIGHT_RC=$?
echo "[journey-sentinel] playwright rc=$PLAYWRIGHT_RC" >> "$LOG"

# --- verdict, parsed from the JSON report, never from PLAYWRIGHT_RC alone ---
# (PLAYWRIGHT_RC is always non-zero because the self-test always fails — see
# file header. The JSON report is what tells self-test-failure apart from a
# real journey defect.)
VERDICT_JSON=$(python3 - "$JSON_REPORT" "$SELFTEST_MARKER" <<'PYEOF'
import json
import sys

report_path, marker = sys.argv[1], sys.argv[2]


def walk_specs(suites):
    for suite in suites or []:
        yield from suite.get("specs", []) or []
        yield from walk_specs(suite.get("suites", []) or [])


try:
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
except Exception as exc:  # noqa: BLE001 — any failure here is its own alarm
    print(json.dumps({"parse_error": f"{type(exc).__name__}: {exc}"}))
    sys.exit(0)

specs = list(walk_specs(report.get("suites", [])))
selftest_specs = [s for s in specs if marker in s.get("title", "")]
real_specs = [s for s in specs if marker not in s.get("title", "")]

selftest_found = len(selftest_specs) > 0
selftest_failed_as_expected = selftest_found and not any(s.get("ok", True) for s in selftest_specs)

real_failures = [s.get("title", "<untitled>") for s in real_specs if not s.get("ok", True)]

print(json.dumps({
    "spec_count": len(specs),
    "selftest_found": selftest_found,
    "selftest_failed_as_expected": selftest_failed_as_expected,
    "real_failures": real_failures,
}))
PYEOF
)
echo "[journey-sentinel] verdict=$VERDICT_JSON" >> "$LOG"

PARSE_ERROR=$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('parse_error',''))" "$VERDICT_JSON" 2>/dev/null || echo "unparseable-verdict-json")
if [ -n "$PARSE_ERROR" ]; then
    echo "[journey-sentinel] FATAL: could not parse Playwright JSON report ($PARSE_ERROR)" >> "$LOG"
    alert "journey-sentinel:report-unreadable" \
        "journey-sentinel: could not read/parse the Playwright JSON report ($PARSE_ERROR) on $(hostname -s). The detection pipeline itself may be broken — see $LOG."
    heartbeat "error" "JSON report unreadable: $PARSE_ERROR"
    exit 1
fi

SELFTEST_OK=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['selftest_failed_as_expected'])" "$VERDICT_JSON")
FAILURE_COUNT=$(python3 -c "import json,sys; print(len(json.loads(sys.argv[1])['real_failures']))" "$VERDICT_JSON")

if [ "$SELFTEST_OK" != "True" ]; then
    echo "[journey-sentinel] CRITICAL: seeded-failure self-test did NOT fail as expected" >> "$LOG"
    alert "journey-sentinel:selftest-malfunction" \
        "journey-sentinel: the SEEDED-FAILURE SELF-TEST did not fail on $(hostname -s) — the detection pipeline may be broken (report a green/missing self-test as a P0, not a routine journey defect). Log: $LOG"
    heartbeat "error" "self-test did not fail as expected — detection pipeline suspect"
    exit 1
fi

if [ "$FAILURE_COUNT" -gt 0 ]; then
    FAILING_TITLES=$(python3 -c "
import json, sys
data = json.loads(sys.argv[1])
for t in data['real_failures']:
    print(t)
" "$VERDICT_JSON")
    echo "[journey-sentinel] $FAILURE_COUNT real journey failure(s):" >> "$LOG"
    echo "$FAILING_TITLES" >> "$LOG"
    while IFS= read -r title; do
        [ -z "$title" ] && continue
        key="journey-sentinel:$(echo "$title" | tr -cs 'a-zA-Z0-9' '-' | cut -c1-40)"
        alert "$key" "journey-sentinel: '$title' FAILED on $(hostname -s) production. See $LOG for the full error (screenshots in output/playwright/production-artifacts/)."
    done <<< "$FAILING_TITLES"
    heartbeat "degraded" "$FAILURE_COUNT real journey failure(s): $(echo "$FAILING_TITLES" | tr '\n' ';')"
    exit 1
fi

echo "[journey-sentinel] all real journey specs green, self-test correctly failed — healthy" >> "$LOG"
heartbeat "ok" "all journey specs green, self-test correctly red"
exit 0
