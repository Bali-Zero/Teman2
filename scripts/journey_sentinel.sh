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
#     ok        all real journey specs passed AND the self-test correctly
#               failed AND every expected spec file was actually collected
#     degraded  >=1 real journey spec failed or was silently skipped, but the
#               self-test correctly failed too (detection pipeline is proven
#               alive; the failure is real and named — e.g. the known
#               prime-maps credential defect, needs-ruling item 1, stays
#               "degraded" not "error" because it is a KNOWN, already-
#               ledgered, operator[GUI] issue, not a fresh unattributed break)
#     error     the self-test did NOT fail (detection pipeline itself may be
#               broken — cicatrix-superscar #2), OR an expected spec FILE
#               vanished from the report (import failure / accidentally
#               emptied test() body — the exact "esiste ≠ armato" shape
#               refutation round 1 found this suite's own JSON-report
#               parser blind to), OR the JSON report could not be
#               read/parsed/trusted at all, OR this wrapper could not even
#               start the suite (missing npx/node_modules, disallowed
#               baseURL, un-removable stale lock/report)
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
# The lock records its OWNER (pid + acquired-at epoch, see STALE LOCK below)
# so a lock left behind by a killed/crashed run is recoverable within one
# cron cycle instead of blocking this organ forever (found in refutation
# round 2: a bare `mkdir`-only lock with no owner metadata has no way to
# distinguish "a run is genuinely in flight" from "a run died holding it").
#
# Seeded-failure self-test (family #2 — "a sentinel that greens while dead is
# worse than none"): apps/mouth/e2e/production/_selftest.spec.ts contains ONE
# test designed to fail on EVERY invocation. This wrapper looks it up by
# title in the JSON report and treats anything other than "failed" as proof
# the whole detection pipeline (Playwright JSON schema, this script's parser,
# the alert gateway) may be broken — a DIFFERENT, higher-severity condition
# than a real journey defect. This is verified every single run, not once.
#
# Spec-inventory guard (family #2, refutation round 1 CRITICAL): the
# self-test alone does not prove EVERY real spec ran. Measured empirically
# building this fix: emptying prime-maps.spec.ts's `test(...)` body (leaving
# the file importable, zero syntax errors) makes it vanish from the JSON
# report's `suites` array with NO entry in `report.errors` either — the
# self-test still fails exactly as expected, the 3 remaining specs still
# pass, and the OLD verdict logic reported "all real journey specs green,
# self-test correctly failed — healthy" while /prime's real, currently-RED
# defect went completely unwatched. This wrapper now independently globs
# `apps/mouth/e2e/production/*.spec.ts` on disk (the SAME filesystem
# Playwright itself just read, not a hardcoded title list that would drift
# every time a spec is added/renamed) and fails loudly if any of those
# filenames is absent from the report's suites.
#
# Alerting — routed through the ALREADY-WIRED gateway, no new channel:
# scripts/tg_notify.py --tier p0 --source journey-sentinel --dedup-key <key>.
# tg_notify.py owns its own budget + dedup ladder (TG_P0_BUDGET,
# TG_DEDUP_HOURS) — this wrapper never redirects its stdout/stderr to
# /dev/null and always logs the return code (`tg[p0] rc=N`), matching the
# house pattern established in apps/evaluator/nlm_deep_research/scripts/_alert.sh
# (the W108 cure: "an alarm conditioned on the health of its environment
# works exactly in the cases where it isn't needed" — this alarm depends on
# nothing but the gateway script existing). Per-real-failure dedup keys now
# carry a short fingerprint of the actual error text (see FINGERPRINT below),
# not just the (unchanging) spec title.
#
# ---------------------------------------------------------------------------
# ## Known limits (declared, not fixed — see task discussion before "curing"
# any of these; each one was weighed and is either out of this wrapper's
# reach or a real, accepted trade-off)
# ---------------------------------------------------------------------------
#
# 1. The seeded self-test proves DETECTION, not ALERT DELIVERY. On its
#    expected failure this wrapper takes the NORMAL failure path (heartbeat
#    "degraded"/"error" + a real Telegram send attempt for any concurrent
#    real failure) but never calls `alert` FOR the self-test's own expected
#    red — there is nothing to page about, it is supposed to fail. That
#    means the Telegram gateway PATH (network reachability, TELEGRAM
#    credentials, tg_notify.py's own budget/dedup logic) can silently rot —
#    e.g. if `python3` or the gateway script itself breaks — and this
#    wrapper would keep reporting `error`/`degraded` heartbeats correctly
#    while NO human ever gets paged, once prime-maps.spec.ts's known defect
#    is eventually cured and the suite goes fully green. A true
#    delivery-path self-test would need a SEPARATE, deliberately-sent
#    canary alert with its own dedup key, verified end-to-end (e.g. an
#    operator's phone) on some cadence independent of whether any real
#    journey is currently failing — not built here.
#
# 2. magic-link.spec.ts hardcodes `my.balizero.com` as the expected FINAL
#    host (by design — see that file's header for why: it exists
#    specifically to catch the real host silently breaking). A legitimate
#    future migration back onto `balizero.com` directly (undoing the current
#    301) would make that spec fail RED even though nothing is actually
#    broken — this wrapper has no way to distinguish "the redirect target
#    broke" from "the redirect target changed on purpose", because it never
#    reads product/infra decisions, only Playwright's verdict.
#
# 3. `dream.spec.ts` asserts the composer renders and the autosave 401s —
#    it never asserts the FORM'S onChange/onSubmit wiring beyond that one
#    keystroke round-trip. A regression isolated to, say, a SECOND field's
#    change handler would not be caught here.
#
# 4. `install_journey_sentinel.sh` does not verify it is being run ON Mini
#    specifically, while `ORGAN_ID` below is unconditionally
#    "mini.journey_sentinel" — installing this plist on a different machine
#    would fabricate a Mini liveness signal to the organism. (Same class as
#    every other Mini-pinned LaunchAgent in this repo; not unique to this
#    organ, and not fixed here.)
#
# 5. visa-clock.spec.ts's fixed 2.5s wait for hydration before interacting
#    with the form is a TIMING assumption (measured empirically once, not an
#    observable "hydration is done" condition) — a genuine hydration
#    slowdown under load could make this spec flake for reasons unrelated to
#    the #5170 regression it guards.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOUTH_DIR="$REPO_ROOT/apps/mouth"
HEARTBEAT_LIB="$REPO_ROOT/scripts/lib/heartbeat.sh"
TG_NOTIFY="$REPO_ROOT/scripts/tg_notify.py"
LOG="${HOME}/logs/journey-sentinel.log"
LOCKDIR="${HOME}/logs/journey-sentinel.lockdir"
LOCK_OWNER_FILE="$LOCKDIR/owner"
ORGAN_ID="mini.journey_sentinel"
JSON_REPORT="$MOUTH_DIR/output/playwright/production-results.json"
SELFTEST_MARKER="[SEEDED-FAILURE SELF-TEST]"
PRODUCTION_SPEC_DIR="$MOUTH_DIR/e2e/production"

# S5: sane staleness ceiling for the advisory lock. Worst case for one full
# run: 5 tests (4 real + selftest) * Playwright's own 60_000ms per-test
# timeout (playwright.production.config.ts `timeout: 60_000`) = 300s,
# plus ~15s of explicit in-test waits (dream's hydration wait, prime-maps'
# Maps-SDK-settle wait) = ~315s absolute worst case if EVERY test hit its
# own timeout. 1200s (20min) is ~4x that ceiling — long enough that a
# legitimate in-flight run is never mistaken for stale, short enough that a
# truly wedged run (a hung chromium process, a killed wrapper that never
# reached its cleanup trap) self-heals well before the next hourly tick
# (3600s away) would otherwise find the lock still held.
STALE_LOCK_SECONDS=1200

# S7: hosts this suite is written and reasoned about against. Every spec's
# assertions (dream.spec.ts, prime-maps.spec.ts, visa-clock.spec.ts navigate
# relative to this baseURL; magic-link.spec.ts's own expectations were
# measured against my.balizero.com specifically) were verified against
# EXACTLY these hosts — an unrestricted baseURL could point the whole suite
# at an unrelated deployment and this wrapper would alert "production is
# healthy" about something that was never production.
ALLOWED_BASE_URLS="https://balizero.com https://www.balizero.com https://my.balizero.com"

# S9: heartbeat-note budget. scripts/lib/heartbeat.sh silently byte-truncates
# any note at 500 chars (measured: `HOME=<tmp> bash scripts/lib/heartbeat.sh
# id degraded "$(python3 -c 'print("A"*600)')"` publishes exactly 500 'A's,
# with no marker that anything was cut) and its own JSON-safety pass maps
# EVERY non-ASCII byte to a space under `LC_ALL=C tr` (measured: `A — B`
# publishes as `A     B` -- the em dash's 3 UTF-8 bytes each become their own
# space). Both are correct for that library (it must stay provably valid
# JSON in any locale) but neither is a truncation MARKER this wrapper can
# rely on -- so the note is capped here, deliberately, ASCII-only, and the
# cap always says when it fired. 400 leaves >100 chars of margin under
# heartbeat.sh's own 500-char ceiling for whatever else happens downstream.
NOTE_MAX_TOTAL=400
NOTE_MAX_TITLE=150
NOTE_MAX_SUMMARY=120

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
if [ ! -d "$PRODUCTION_SPEC_DIR" ]; then
    echo "[journey-sentinel] FATAL: production spec dir not found under $MOUTH_DIR (REPO_ROOT derived: $REPO_ROOT)" >> "$LOG"
    heartbeat "error" "e2e/production not found under derived REPO_ROOT"
    exit 2
fi
if [ ! -x "$(command -v npx 2>/dev/null)" ]; then
    echo "[journey-sentinel] FATAL: npx not found on PATH" >> "$LOG"
    heartbeat "error" "npx not found on PATH"
    exit 3
fi

# --- S7: baseURL allowlist ---------------------------------------------------
EFFECTIVE_BASE_URL="${JOURNEY_SENTINEL_BASE_URL:-https://balizero.com}"
BASE_URL_ALLOWED=0
for allowed in $ALLOWED_BASE_URLS; do
    if [ "$EFFECTIVE_BASE_URL" = "$allowed" ]; then
        BASE_URL_ALLOWED=1
        break
    fi
done
if [ "$BASE_URL_ALLOWED" -ne 1 ]; then
    echo "[journey-sentinel] FATAL: JOURNEY_SENTINEL_BASE_URL='$EFFECTIVE_BASE_URL' is not an allowlisted production host ($ALLOWED_BASE_URLS) — refusing to run rather than test an unknown deployment" >> "$LOG"
    heartbeat "error" "baseURL '$EFFECTIVE_BASE_URL' not allowlisted — refused to run"
    exit 7
fi

# --- G10 single instance (advisory, portable mkdir lock, S5 staleness) ------
_release_lock() {
    rm -f "$LOCK_OWNER_FILE" 2>/dev/null || true
    rmdir "$LOCKDIR" 2>/dev/null || true
}
_lock_owner_age_seconds() {  # prints age in seconds, or empty if unreadable
    [ -f "$LOCK_OWNER_FILE" ] || { echo ""; return; }
    local owner_pid owner_ts now
    read -r owner_pid owner_ts < "$LOCK_OWNER_FILE" 2>/dev/null || { echo ""; return; }
    [ -n "${owner_ts:-}" ] || { echo ""; return; }
    now=$(date +%s)
    echo $(( now - owner_ts ))
}

LOCK_ACQUIRED=0
if mkdir "$LOCKDIR" 2>/dev/null; then
    LOCK_ACQUIRED=1
else
    # Busy — but is the owner still alive, or did a previous run die holding
    # it? An owner file with no age info at all (pre-S5 lock format, or
    # corrupted) is ALSO treated as stale — we cannot prove it is fresh.
    age="$(_lock_owner_age_seconds)"
    if [ -z "$age" ] || [ "$age" -gt "$STALE_LOCK_SECONDS" ]; then
        stale_owner="$(cat "$LOCK_OWNER_FILE" 2>/dev/null || echo "<no owner file>")"
        echo "[journey-sentinel] STALE LOCK taken over (owner: $stale_owner, age: ${age:-unknown}s > ${STALE_LOCK_SECONDS}s) — a previous run likely died without releasing it" >> "$LOG"
        alert "journey-sentinel:stale-lock-takeover" \
            "journey-sentinel: took over a stale advisory lock on $(hostname -s) (owner: $stale_owner, age ${age:-unknown}s > ${STALE_LOCK_SECONDS}s) — a previous run likely crashed or hung without releasing it."
        _release_lock
        if mkdir "$LOCKDIR" 2>/dev/null; then
            LOCK_ACQUIRED=1
        fi
    fi
fi

if [ "$LOCK_ACQUIRED" -ne 1 ]; then
    echo "[journey-sentinel] overlapping run detected (lockdir busy: $LOCKDIR) — skipping this tick" >> "$LOG"
    heartbeat "warning" "skipped: overlapping run held the advisory lock"
    exit 0
fi

echo "$$ $(date +%s)" > "$LOCK_OWNER_FILE"
# bash's EXIT trap is single-slot — chain the lock cleanup onto the existing
# heartbeat safety-net trap explicitly rather than overwrite it.
trap '_hb_on_exit; _release_lock' EXIT

# --- run the suite -----------------------------------------------------------
echo "[journey-sentinel] running production suite from $MOUTH_DIR (baseURL=$EFFECTIVE_BASE_URL)" >> "$LOG"

# S6 pre-check: the JSON report must be a FRESH artifact of THIS run, never a
# leftover. `rm -f` failing silently (permissions, NFS, a stuck mount) would
# otherwise let a stale-but-valid-JSON old report survive to be read as if
# it were this run's result — a genuinely missing report is a separate,
# already-handled case (the JSON-parse step below raises on FileNotFoundError
# and that already alerts). This catches "still there when it shouldn't be".
RUN_START_EPOCH=$(date +%s)
rm -f "$JSON_REPORT"
if [ -e "$JSON_REPORT" ]; then
    echo "[journey-sentinel] FATAL: could not remove the previous JSON report before starting ($JSON_REPORT still present)" >> "$LOG"
    alert "journey-sentinel:stale-report-not-removable" \
        "journey-sentinel: could not remove the previous Playwright JSON report before starting a new run on $(hostname -s) — refusing to risk reading a stale result. See $LOG."
    heartbeat "error" "stale JSON report could not be removed before run"
    exit 5
fi

(
    cd "$MOUTH_DIR" && \
    PROD_SENTINEL_BASE_URL="$EFFECTIVE_BASE_URL" \
    npx playwright test -c playwright.production.config.ts
) >> "$LOG" 2>&1
PLAYWRIGHT_RC=$?
echo "[journey-sentinel] playwright rc=$PLAYWRIGHT_RC" >> "$LOG"

# S6 post-check: the report that now exists must postdate THIS run's start,
# not merely exist. A crash after `rm -f` but before the JSON reporter's
# flush, racing with something else re-materializing an old copy, would
# otherwise be indistinguishable from a genuine fresh (possibly green)
# result.
if [ -f "$JSON_REPORT" ]; then
    REPORT_MTIME=$(stat -f %m "$JSON_REPORT" 2>/dev/null || stat -c %Y "$JSON_REPORT" 2>/dev/null || echo 0)
    if [ "$REPORT_MTIME" -lt "$RUN_START_EPOCH" ]; then
        echo "[journey-sentinel] FATAL: JSON report predates this run (mtime=$REPORT_MTIME, run started=$RUN_START_EPOCH) — refusing to trust it as this run's verdict" >> "$LOG"
        alert "journey-sentinel:stale-report-predates-run" \
            "journey-sentinel: the Playwright JSON report on $(hostname -s) is OLDER than this run — its (possibly green) contents are being suppressed rather than reported as this run's outcome. See $LOG."
        heartbeat "error" "JSON report predates this run — stale result suppressed"
        exit 6
    fi
fi

# --- verdict, parsed from the JSON report, never from PLAYWRIGHT_RC alone ---
# (PLAYWRIGHT_RC is always non-zero because the self-test always fails — see
# file header. The JSON report is what tells self-test-failure apart from a
# real journey defect.)
VERDICT_JSON=$(python3 - "$JSON_REPORT" "$SELFTEST_MARKER" "$PRODUCTION_SPEC_DIR" <<'PYEOF'
import glob
import hashlib
import json
import os
import re
import sys

report_path, marker, spec_dir = sys.argv[1], sys.argv[2], sys.argv[3]


def walk_specs(suites):
    for suite in suites or []:
        yield from suite.get("specs", []) or []
        yield from walk_specs(suite.get("suites", []) or [])


def walk_files(suites):
    """Top-level suite.file (relative to testDir) for every suite Playwright
    actually collected — including nested ones, though today's layout is
    flat. This is compared against the filesystem, independently, below."""
    for suite in suites or []:
        f = suite.get("file")
        if f:
            yield f
        yield from walk_files(suite.get("suites", []) or [])


def test_bucket(test):
    """Collapse Playwright's per-test `status` into passed/skipped/failed.
    "expected" (clean pass) and "flaky" (failed once, passed on retry —
    playwright.production.config.ts retries:1) both count as passed: a
    single-blip retry recovering is exactly the outcome S8 wants, and
    Playwright itself already distinguishes "flaky" from "expected" in the
    report for anyone auditing the trend later. Anything else ("unexpected"
    = failed on every attempt, or an unrecognized future value) is failed —
    fail-closed on an unknown status, never silently treated as a pass."""
    status = test.get("status")
    if status in ("expected", "flaky"):
        return "passed"
    if status == "skipped":
        return "skipped"
    return "failed"


def spec_status(spec):
    """One spec can carry multiple `tests` entries (one per Playwright
    project — today just chromium-production, but this doesn't assume
    that). failed > skipped > passed in priority; a spec with ZERO test
    entries at all (collected but never executed — no known cause, but not
    provably safe either) is its own "unknown" bucket, fail-closed."""
    tests = spec.get("tests") or []
    if not tests:
        return "unknown"
    buckets = {test_bucket(t) for t in tests}
    if "failed" in buckets:
        return "failed"
    if "skipped" in buckets:
        return "skipped"
    if buckets == {"passed"}:
        return "passed"
    return "unknown"


def spec_error_summary(spec):
    """First line of the first FAILED test's error message, digits replaced
    with '#' (dates/durations/counts are volatility, not identity — same
    normalization philosophy as scripts/tg_notify.py's own
    condition_identity()). Used only to fingerprint the dedup key (S8) —
    never the sole classifier."""
    for t in spec.get("tests") or []:
        if test_bucket(t) != "failed":
            continue
        for r in reversed(t.get("results") or []):
            msg = ((r.get("error") or {}).get("message") or "").strip()
            if not msg:
                continue
            first_line = msg.splitlines()[0]
            return re.sub(r"[0-9]+", "#", first_line)[:200]
    return ""


try:
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
except Exception as exc:  # noqa: BLE001 — any failure here is its own alarm
    print(json.dumps({"parse_error": f"{type(exc).__name__}: {exc}"}))
    sys.exit(0)

# S2a: a top-level Playwright `errors` entry means collection itself failed
# (a broken import, a syntax error) — measured empirically: when this
# happens NO suites are collected AT ALL (not just the broken file), so this
# is checked before anything else.
report_errors = [e.get("message", "<no message>") for e in (report.get("errors") or [])]

specs = list(walk_specs(report.get("suites", [])))
files_in_report = set(walk_files(report.get("suites", [])))

# S2b: spec-inventory guard. Independently glob the filesystem Playwright
# itself just read from — NOT a hardcoded title list (which would drift
# every time a spec is added/renamed) — and diff it against which files
# actually produced a suite in the report. Measured empirically: a spec file
# that imports cleanly but has had its `test(...)` body emptied/commented
# out produces ZERO entries in `report.errors` AND is simply absent from
# `suites` — this is the exact silent-vanish shape refutation round 1 found.
expected_files = {
    os.path.basename(p)
    for p in glob.glob(os.path.join(spec_dir, "*.spec.ts"))
}
missing_files = sorted(expected_files - files_in_report)

# S2b-II: the disk glob above CANNOT see a DELETED spec — measured, by the
# orchestrator, against this very code: moving dream.spec.ts out of the
# directory made both sides of that diff shrink together and produced
# `missing_files: []`, a clean green for a sentinel that no longer exists.
# The round-1 fix was proved with a different mutation (emptying a test BODY,
# which leaves the file on disk) and that mutation cannot distinguish the two
# cases. Deletion is the more dangerous one: it is what removing an
# inconvenient failing sentinel looks like.
#
# So a FLOOR, not a full inventory. A hardcoded complete list would drift on
# every legitimate addition (the objection the glob was chosen to avoid, and it
# is a fair one); a floor of the sentinels that must ALWAYS exist drifts only
# when one is deliberately retired — which is exactly the moment a human should
# have to edit this line and say so.
REQUIRED_SPECS = {
    "_selftest.spec.ts",
    "dream.spec.ts",
    "magic-link.spec.ts",
    "prime-maps.spec.ts",
    "visa-clock.spec.ts",
}
on_disk = {os.path.basename(p) for p in glob.glob(os.path.join(spec_dir, "*.spec.ts"))}
missing_required = sorted(REQUIRED_SPECS - (files_in_report | on_disk))
missing_files = sorted(set(missing_files) | set(missing_required))

selftest_specs = [s for s in specs if marker in s.get("title", "")]
real_specs = [s for s in specs if marker not in s.get("title", "")]

selftest_found = len(selftest_specs) > 0
# S2c: a skipped or passed self-test is EXACTLY as suspect as a missing one
# — spec.ok (Playwright's own field) is TRUE for both "passed cleanly" and
# "skipped" (test.skip() sets expectedStatus="skipped", so a skip matches
# its own expectation and reads "ok"). This wrapper never trusted `ok` for
# this decision even before S2 — spec_status() is the one true source now.
selftest_failed_as_expected = selftest_found and all(
    spec_status(s) == "failed" for s in selftest_specs
)

real_failures = []
for s in real_specs:
    status = spec_status(s)
    if status == "passed":
        continue
    title = s.get("title", "<untitled>")
    if status == "skipped":
        title = f"{title} [SKIPPED — never actually ran]"
    elif status == "unknown":
        title = f"{title} [NO TEST RESULTS COLLECTED]"
    error_summary = spec_error_summary(s)
    fingerprint = (
        hashlib.sha1(error_summary.encode()).hexdigest()[:8]
        if error_summary
        else "nofingerprint"
    )
    real_failures.append(
        {
            "title": title,
            "error_summary": error_summary,
            "fingerprint": fingerprint,
        }
    )

print(json.dumps({
    "spec_count": len(specs),
    "report_errors": report_errors,
    "missing_files": missing_files,
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

# S2a: fatal collection error (import/syntax failure) — Playwright collected
# NOTHING for this run, so nothing else below is meaningful.
REPORT_ERROR_COUNT=$(python3 -c "import json,sys; print(len(json.loads(sys.argv[1])['report_errors']))" "$VERDICT_JSON")
if [ "$REPORT_ERROR_COUNT" -gt 0 ]; then
    REPORT_ERRORS_TEXT=$(python3 -c "
import json, sys
for e in json.loads(sys.argv[1])['report_errors']:
    print(e.splitlines()[0][:300])
" "$VERDICT_JSON")
    echo "[journey-sentinel] FATAL: Playwright reported $REPORT_ERROR_COUNT top-level collection error(s):" >> "$LOG"
    echo "$REPORT_ERRORS_TEXT" >> "$LOG"
    alert "journey-sentinel:collection-failed" \
        "journey-sentinel: Playwright FAILED TO COLLECT the production suite on $(hostname -s) ($REPORT_ERROR_COUNT error(s)) — likely a broken import/syntax error in a spec file. NOTHING was tested this run. First error: $(echo "$REPORT_ERRORS_TEXT" | head -1). See $LOG."
    heartbeat "error" "Playwright collection failed — $REPORT_ERROR_COUNT top-level error(s), nothing tested"
    exit 4
fi

# S2b: a spec file that should have produced a suite silently didn't.
MISSING_FILES_COUNT=$(python3 -c "import json,sys; print(len(json.loads(sys.argv[1])['missing_files']))" "$VERDICT_JSON")
if [ "$MISSING_FILES_COUNT" -gt 0 ]; then
    MISSING_FILES_TEXT=$(python3 -c "
import json, sys
for f in json.loads(sys.argv[1])['missing_files']:
    print(f)
" "$VERDICT_JSON")
    echo "[journey-sentinel] FATAL: $MISSING_FILES_COUNT expected spec file(s) produced NO suite in the report:" >> "$LOG"
    echo "$MISSING_FILES_TEXT" >> "$LOG"
    alert "journey-sentinel:missing-spec-file" \
        "journey-sentinel: $MISSING_FILES_COUNT expected spec file(s) on disk produced NO entry in the Playwright report on $(hostname -s) — a defect on that journey would currently go completely unwatched. File(s): $(echo "$MISSING_FILES_TEXT" | tr '\n' ',' ). See $LOG."
    heartbeat "error" "$MISSING_FILES_COUNT spec file(s) missing from the report — coverage gap, not a clean run"
    exit 8
fi

SELFTEST_OK=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['selftest_failed_as_expected'])" "$VERDICT_JSON")
FAILURE_COUNT=$(python3 -c "import json,sys; print(len(json.loads(sys.argv[1])['real_failures']))" "$VERDICT_JSON")

if [ "$SELFTEST_OK" != "True" ]; then
    echo "[journey-sentinel] CRITICAL: seeded-failure self-test did NOT fail as expected" >> "$LOG"
    alert "journey-sentinel:selftest-malfunction" \
        "journey-sentinel: the SEEDED-FAILURE SELF-TEST did not fail on $(hostname -s) — the detection pipeline may be broken (report a green/missing/skipped self-test as a P0, not a routine journey defect). Log: $LOG"
    heartbeat "error" "self-test did not fail as expected — detection pipeline suspect"
    exit 1
fi

if [ "$FAILURE_COUNT" -gt 0 ]; then
    # S8: dedup key includes a fingerprint of the actual failure text, not
    # just the (unchanging) spec title — so a DIFFERENT root cause on the
    # SAME journey (e.g. prime-maps.spec.ts failing tomorrow on a CSP
    # violation instead of today's ExpiredKeyMapError) gets its own dedup
    # identity instead of being muted by tg_notify.py's repeat-ladder as "the
    # same condition, still ongoing". Declared, not fully closed: this still
    # dedupes on the FIRST LINE of the error only — two distinct defects that
    # happen to share their first line of output would still collide.
    FAILURES_TSV=$(python3 -c "
import json, sys
data = json.loads(sys.argv[1])
for f in data['real_failures']:
    print(f['title'] + '\t' + f['fingerprint'] + '\t' + f['error_summary'])
" "$VERDICT_JSON")
    echo "[journey-sentinel] $FAILURE_COUNT real journey failure(s):" >> "$LOG"
    echo "$FAILURES_TSV" >> "$LOG"
    while IFS=$'\t' read -r title fingerprint error_summary; do
        [ -z "$title" ] && continue
        key="journey-sentinel:$(echo "$title" | tr -cs 'a-zA-Z0-9' '-' | cut -c1-32)-$fingerprint"
        text="journey-sentinel: '$title' FAILED on $(hostname -s) production"
        if [ -n "$error_summary" ]; then
            text="$text ($error_summary)"
        fi
        text="$text. See $LOG for the full error (screenshots in output/playwright/production-artifacts/)."
        alert "$key" "$text"
    done <<< "$FAILURES_TSV"

    # S9: the heartbeat NOTE, built straight from $VERDICT_JSON (never from
    # bash string concatenation over the alert loop's variables) so a title
    # containing ';' can never be confused with our own separator. Two
    # failure modes this closes, both measured on the live note before this
    # fix (`;/prime Google Maps key is valid (currently RED     see file
    # header, needs-ruling item 1)` -- a RED organ publishing a note that
    # reads as its own opposite, with a stray leading ';' from using the
    # join separator as a prefix):
    #   1. every spec TITLE is conventionally phrased as the DESIRED
    #      property ("Google Maps key is valid") -- a bare title list makes
    #      that note ambiguous on its own, with only the sidecar's `status`
    #      field to disambiguate. Every entry is now prefixed "FAILED: " so
    #      the note text itself cannot be misread standalone.
    #   2. the Telegram alert above already carries $error_summary -- the
    #      concrete, useful signal (e.g. "Maps SDK script itself failed",
    #      not just "key is valid" negated) -- and the old note threw it
    #      away. It rides along now, each occurrence capped at
    #      NOTE_MAX_SUMMARY so ONE long summary cannot crowd its siblings
    #      out of the shared budget. When not every failure fits inside
    #      NOTE_MAX_TOTAL, a trailing "+N more (see log)" marker says so --
    #      the reader is told fewer failures are shown, never left to
    #      believe fewer occurred.
    NOTE_TAIL=$(python3 -c "
import json, sys

max_total = int(sys.argv[2])
max_title = int(sys.argv[3])
max_summary = int(sys.argv[4])


def clip(s, limit):
    if len(s) <= limit:
        return s
    if limit <= 3:
        return s[:limit]
    return s[: limit - 3] + '...'


data = json.loads(sys.argv[1])
failures = data['real_failures']
n = len(failures)

entries = []
for f in failures:
    entry = 'FAILED: ' + clip(f.get('title', ''), max_title)
    summary = clip(f.get('error_summary', ''), max_summary)
    if summary:
        entry += ' :: ' + summary
    entries.append(entry)

prefix_len = len(str(n)) + len(' real journey failure(s): ')
budget = max(max_total - prefix_len, 0)


def marker_suffix(k):
    return '+{} more (see log)'.format(k) if k > 0 else ''


# Joined with '; ' as a real SEPARATOR between parts, never glued on as a
# prefix -- a naive `'; '.join(entries[:shown]) + marker(...)` (the first
# draft here) still produced a leading '; +N more (see log)' when shown==0,
# the exact separator-as-prefix mistake this fix exists to remove. Measured
# before this correction: `build_note(..., max_total=50)` on 3 short titles
# printed '; +3 more (see log)'.
tail = None
for shown in range(n, -1, -1):
    parts = list(entries[:shown])
    m = marker_suffix(n - shown)
    if m:
        parts.append(m)
    candidate = '; '.join(parts)
    if len(candidate) <= budget:
        tail = candidate
        break

if tail is None and n > 0:
    # Pathological only: even shown=0 plus its own marker did not fit.
    # Force a hard-clipped signal for the first failure rather than publish
    # nothing for a real one. Declared best-effort -- not expected in
    # practice at NOTE_MAX_TOTAL=400 with realistic Playwright titles.
    m = marker_suffix(n - 1)
    reserve = (len(m) + 2) if m else 0
    parts = [clip(entries[0], max(budget - reserve, 4))]
    if m:
        parts.append(m)
    tail = '; '.join(parts)

print(tail or '')
" "$VERDICT_JSON" "$NOTE_MAX_TOTAL" "$NOTE_MAX_TITLE" "$NOTE_MAX_SUMMARY")

    heartbeat "degraded" "$FAILURE_COUNT real journey failure(s): $NOTE_TAIL"
    exit 1
fi

echo "[journey-sentinel] all real journey specs green, self-test correctly failed — healthy" >> "$LOG"
heartbeat "ok" "all journey specs green, self-test correctly red"
exit 0
