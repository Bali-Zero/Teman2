#!/usr/bin/env bash
# Offline contract tests for scripts/lib/seat_state.sh and its cascade wiring.
#
# Every fixture report is written by this test into a temp dir; the real
# ~/.claude/seat-quota.json and ~/.organism/arsenal/last.json are NEVER
# touched. Every account/seat name is obviously fake — never a real or
# realistic credential value anywhere in this file.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEAT_STATE="$REPO_ROOT/scripts/lib/seat_state.sh"
CASCADE="$REPO_ROOT/infra/launchagents/wrappers/claude-cascade.sh"
FIXTURE="$(mktemp -d)"
PASS_COUNT=0
FAIL_COUNT=0

cleanup() { rm -rf "$FIXTURE"; }
trap cleanup EXIT

run_case() {
    local name="$1"
    local fn="$2"
    if "$fn"; then
        printf 'PASS %s\n' "$name"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        printf 'FAIL %s\n' "$name"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

now_epoch() { python3 -c 'import time; print(int(time.time()))'; }
now_iso() { python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))'; }

write_quota_fixture() {
    # $1=path $2=account $3=weekly_pct(or "null") $4=session_pct(or "null") $5=epoch(optional, default now)
    local path="$1" account="$2" weekly="$3" session="$4" epoch="${5:-$(now_epoch)}"
    cat > "$path" <<EOF
{"generated_at_epoch": $epoch, "seats": [
  {"account": "$account", "weekly_pct": $weekly, "session_pct": $session}
]}
EOF
}

write_arsenal_fixture() {
    # $1=path $2=seat $3=status $4=ts(optional, default now)
    local path="$1" seat="$2" status="$3" ts="${4:-$(now_iso)}"
    cat > "$path" <<EOF
{"ts": "$ts", "seats": [{"seat": "$seat", "status": "$status"}]}
EOF
}

lookup() {
    # $@ = env assignments (VAR=val ...) followed by "--" then the seat key.
    env "$@"
}

# --- 1: GUILT — exhaustion ---------------------------------------------
case_guilt_exhausted() {
    local quota="$FIXTURE/c1-quota.json" out state rc=0
    write_quota_fixture "$quota" "seat-a@example.invalid" 100.0 10.0
    out="$(env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c1-missing.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-a@example.invalid")" || rc=$?
    [ "$rc" -eq 1 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "EXHAUSTED" ]
}

# --- 2: GUILT — cascade precheck skip -----------------------------------
case_guilt_cascade_skip() {
    local quota="$FIXTURE/c2-quota.json" rc=0
    write_quota_fixture "$quota" "seat-a@example.invalid" 100.0 10.0
    env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c2-missing.json" \
        CLAUDE_SEAT_ACCOUNT_3="seat-a@example.invalid" \
        bash -c ". \"$SEAT_STATE\"; seat_state_precheck_skip claude-token-3-env" || rc=$?
    [ "$rc" -eq 0 ]
}

# --- 3: INNOCENCE — live seat ------------------------------------------
case_innocence_live() {
    local quota="$FIXTURE/c3-quota.json" out state rc=0 skiprc=0
    write_quota_fixture "$quota" "seat-b@example.invalid" 12.0 3.0
    out="$(env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c3-missing.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-b@example.invalid")" || rc=$?
    [ "$rc" -eq 0 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "LIVE" ] || return 1
    env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c3-missing.json" \
        CLAUDE_SEAT_ACCOUNT_2="seat-b@example.invalid" \
        bash -c ". \"$SEAT_STATE\"; seat_state_precheck_skip claude-token-2-env" || skiprc=$?
    [ "$skiprc" -eq 1 ]
}

# --- 4: STALENESS --------------------------------------------------------
case_staleness_unknown() {
    local quota="$FIXTURE/c4-quota.json" out state reason rc=0 skiprc=0
    write_quota_fixture "$quota" "seat-c@example.invalid" 100.0 10.0 "$(( $(now_epoch) - 999999 ))"
    out="$(env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c4-missing.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-c@example.invalid")" || rc=$?
    [ "$rc" -eq 2 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "UNKNOWN" ] || return 1
    reason="${out#*$'\t'}"
    case "$reason" in *stale*) : ;; *) return 1 ;; esac
    env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c4-missing.json" \
        CLAUDE_SEAT_ACCOUNT_5="seat-c@example.invalid" \
        bash -c ". \"$SEAT_STATE\"; seat_state_precheck_skip claude-token-5-env" || skiprc=$?
    [ "$skiprc" -eq 1 ]
}

# --- 5: MISSING REPORT ----------------------------------------------------
case_missing_report_unknown() {
    local rc=0
    env SEAT_STATE_REPORT="$FIXTURE/c5-nope1.json" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c5-nope2.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup ghost@example.invalid >/dev/null" || rc=$?
    [ "$rc" -eq 2 ]
}

# --- 6: UNRESOLVABLE SLOT --------------------------------------------------
case_unresolvable_slot() {
    local rc=0
    unset CLAUDE_SEAT_ACCOUNT_4 2>/dev/null || true
    env SEAT_STATE_REPORT="$FIXTURE/c6-nope.json" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c6-nope2.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_precheck_skip claude-token-4-env" || rc=$?
    [ "$rc" -eq 1 ]
}

# --- 7: UNPARSEABLE LABEL ---------------------------------------------------
case_unparseable_label() {
    local rc=0
    bash -c ". \"$SEAT_STATE\"; seat_state_precheck_skip claude-keychain" || rc=$?
    [ "$rc" -eq 1 ]
}

# --- 8: SINGLE PROBE — exactly once, seat becomes LIVE ----------------------
case_single_probe_refreshes() {
    # The report starts out AT THE SAME PATH the probe will populate — it
    # simply does not exist yet, so the first read is "missing-report"
    # (UNKNOWN) and the probe's job is to bring that exact path to life.
    local counter="$FIXTURE/c8-counter.txt" report="$FIXTURE/c8-quota.json" probe out state rc=0
    : > "$counter"
    [ ! -e "$report" ] || return 1
    probe="$FIXTURE/c8-probe.sh"
    cat > "$probe" <<PROBE
#!/bin/sh
echo ran >> "$counter"
epoch="\$(python3 -c 'import time; print(int(time.time()))')"
cat > "$report" <<JSON
{"generated_at_epoch": \$epoch, "seats": [{"account": "seat-d@example.invalid", "weekly_pct": 5.0, "session_pct": 2.0}]}
JSON
PROBE
    chmod +x "$probe"
    out="$(env SEAT_STATE_REPORT="$report" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c8-missing2.json" \
        SEAT_STATE_PROBE_CMD="$probe" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-d@example.invalid")" || rc=$?
    [ "$rc" -eq 0 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "LIVE" ] || return 1
    [ "$(wc -l < "$counter" | tr -d ' ')" = "1" ] || return 1

    # A SECOND, independent lookup that inherits SEAT_STATE_PROBED=1 (as a
    # freshly-probed process would leave it exported) must NOT fire the
    # probe again even though this seat is absent from the report and
    # resolves UNKNOWN — this is the guarantee a removed/weakened sentinel
    # check would not catch with only a single lookup: "exactly one fresh
    # probe" is a per-PROCESS budget (see the design comment above
    # seat_state_lookup()), and setting the sentinel explicitly here proves
    # the CHECK is honored, independent of same-process persistence timing.
    env SEAT_STATE_REPORT="$report" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c8-missing2.json" \
        SEAT_STATE_PROBE_CMD="$probe" SEAT_STATE_PROBED=1 \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-not-in-report@example.invalid >/dev/null" || true
    [ "$(wc -l < "$counter" | tr -d ' ')" = "1" ]
}

# --- 9: PROBE STILL UNKNOWN --------------------------------------------------
case_probe_still_unknown() {
    local counter="$FIXTURE/c9-counter.txt" probe out state reason rc=0
    : > "$counter"
    probe="$FIXTURE/c9-probe.sh"
    printf '#!/bin/sh\necho ran >> "%s"\n' "$counter" > "$probe"
    chmod +x "$probe"
    out="$(env SEAT_STATE_REPORT="$FIXTURE/c9-nope.json" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c9-nope2.json" \
        SEAT_STATE_PROBE_CMD="$probe" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup ghost9@example.invalid")" || rc=$?
    [ "$rc" -eq 2 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "UNKNOWN" ] || return 1
    reason="${out#*$'\t'}"
    case "$reason" in *after-probe*) : ;; *) return 1 ;; esac
    [ "$(wc -l < "$counter" | tr -d ' ')" = "1" ]
}

# --- 10: ARSENAL EXHAUSTED --------------------------------------------------
case_arsenal_exhausted() {
    local arsenal="$FIXTURE/c10-arsenal.json" out state rc=0
    write_arsenal_fixture "$arsenal" "kimi" "QUOTA_DEAD"
    out="$(env SEAT_STATE_REPORT="$FIXTURE/c10-nope.json" SEAT_STATE_ARSENAL_REPORT="$arsenal" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup kimi")" || rc=$?
    [ "$rc" -eq 1 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "EXHAUSTED" ]
}

# --- 11: ARSENAL LIVE -------------------------------------------------------
case_arsenal_live() {
    local arsenal="$FIXTURE/c11-arsenal.json" out state rc=0
    write_arsenal_fixture "$arsenal" "kimi-live" "LIVE"
    out="$(env SEAT_STATE_REPORT="$FIXTURE/c11-nope.json" SEAT_STATE_ARSENAL_REPORT="$arsenal" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup kimi-live")" || rc=$?
    [ "$rc" -eq 0 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "LIVE" ]
}

# --- 12: NO USAGE FIGURES ---------------------------------------------------
case_no_usage_figures_unknown() {
    local quota="$FIXTURE/c12-quota.json" out state rc=0
    write_quota_fixture "$quota" "seat-e@example.invalid" null null
    out="$(env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c12-missing.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-e@example.invalid")" || rc=$?
    [ "$rc" -eq 2 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "UNKNOWN" ]
}

# --- 13: NO SECRETS IN OUTPUT ------------------------------------------------
case_no_secrets_in_output() {
    local quota="$FIXTURE/c13-quota.json" out
    write_quota_fixture "$quota" "seat-f@example.invalid" 100.0 10.0
    out="$(env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c13-missing.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-f@example.invalid")"
    ! printf '%s' "$out" | grep -Eiq 'sk-ant-|oat01|[A-Za-z0-9+/]{40,}'
}

# --- 14: CASCADE WIRING ------------------------------------------------------
case_cascade_wiring() {
    [ -f "$CASCADE" ] || return 1
    # W108 lesson: assert on EXECUTABLE text, never on the whole file. This guard's
    # first cut grepped the raw file for 'seat_state_precheck_skip' / 'SEAT_STATE_PRECHECK'
    # and PASSED with the hook deleted, because both strings also live in this PR's own
    # explanatory comments and in the fail-open stub. A wiring guard that cannot detect
    # the wiring being removed is theater (family #2). Comments are stripped first.
    local exec_text
    exec_text="$(sed 's/[[:space:]]*#.*$//' "$CASCADE")"

    # The library is actually sourced (a real `.` line, not a mention in prose).
    printf '%s\n' "$exec_text" | grep -Eq '^[[:space:]]*\.[[:space:]]+"\$SEAT_STATE_LIB"' || return 1
    # The kill switch guards a REAL call, and that call is followed by the skip return.
    # POLARITY, not just presence. Inverting the guard to `= "0"` (precheck
    # armed only when the kill switch is ON) left every test green in the first
    # version of this case — the exact "asserts on text while behavior is
    # broken" class this guard's own W108 note claims to avoid.
    printf '%s\n' "$exec_text" \
        | grep -Eq 'SEAT_STATE_PRECHECK:-1\}"[[:space:]]*!=[[:space:]]*"0".*seat_state_precheck_skip[[:space:]]+"\$label"' || return 1
    printf '%s\n' "$exec_text" \
        | grep -A3 -E 'seat_state_precheck_skip[[:space:]]+"\$label"' | grep -Fq 'return 98' || return 1

    # And the call sits INSIDE try_claude(), not merely somewhere in the file:
    # its line number must fall between `try_claude() {` and the first dispatch call.
    local ln_fn ln_call ln_firstcall
    ln_fn="$(grep -n '^try_claude() {' "$CASCADE" | head -1 | cut -d: -f1)"
    ln_call="$(grep -n 'seat_state_precheck_skip[[:space:]]\+"\$label"' "$CASCADE" | head -1 | cut -d: -f1)"
    ln_firstcall="$(grep -n '^[[:space:]]*try_claude "' "$CASCADE" | head -1 | cut -d: -f1)"
    [ -n "$ln_fn" ] && [ -n "$ln_call" ] && [ -n "$ln_firstcall" ] || return 1
    [ "$ln_call" -gt "$ln_fn" ] && [ "$ln_call" -lt "$ln_firstcall" ] || return 1

    # The library must be SOURCED before the first dispatch, or the stub/real function
    # would not exist yet when try_claude first runs.
    local ln_src
    ln_src="$(grep -n '^[[:space:]]*\.[[:space:]]\+"\$SEAT_STATE_LIB"' "$CASCADE" | head -1 | cut -d: -f1)"
    [ -n "$ln_src" ] && [ "$ln_src" -lt "$ln_firstcall" ] || return 1

    local mine origin attempt
    mine="$(grep -n '^for index in 1 2 3 4 5; do' "$CASCADE" || true)"
    [ -n "$mine" ] || return 1
    # This worktree is shared with concurrent sibling squad activity (observed
    # live: SQUAD-LEDGER.md changing underfoot mid-run) — `git show ref:path`
    # can transiently race a sibling's ref/object-db write. Retry a few times
    # before treating an empty read as a real failure, so a git-lock blip
    # never masquerades as "the dispatch loop got touched".
    for attempt in 1 2 3; do
        origin="$(git -C "$REPO_ROOT" show origin/main:infra/launchagents/wrappers/claude-cascade.sh 2>/dev/null \
            | grep -n '^for index in 1 2 3 4 5; do' || true)"
        [ -n "$origin" ] && break
        sleep 0.2
    done
    [ -n "$origin" ] || return 1
    # Only the line NUMBER may legitimately differ (this PR adds lines above
    # it); the line TEXT itself — the dispatch loop's own numbering, which
    # belongs to PR #4644 — must be byte-identical to origin/main.
    [ "${mine#*:}" = "${origin#*:}" ]
}

# --- 15: SYNTAX ---------------------------------------------------------
case_syntax_bash() {
    bash -n "$SEAT_STATE"
}

case_syntax_zsh() {
    if ! command -v zsh >/dev/null 2>&1; then
        printf 'SKIP (no zsh on PATH)\n'
        return 0
    fi
    zsh -n "$CASCADE"
}

run_case "guilt: exhausted quota seat" case_guilt_exhausted
run_case "guilt: cascade precheck skips an exhausted seat" case_guilt_cascade_skip
run_case "innocence: fresh live seat, no skip" case_innocence_live
run_case "staleness: old report is UNKNOWN, never a skip" case_staleness_unknown
run_case "missing report: both sources absent is UNKNOWN" case_missing_report_unknown
run_case "unresolvable slot: unmapped account never skips" case_unresolvable_slot
run_case "unparseable label: non-claude-token label never skips" case_unparseable_label
run_case "single probe: refreshes and resolves LIVE, runs exactly once" case_single_probe_refreshes
run_case "single probe: still UNKNOWN after probe, still exactly once" case_probe_still_unknown
run_case "arsenal report: QUOTA_DEAD resolves EXHAUSTED" case_arsenal_exhausted
run_case "arsenal report: LIVE resolves LIVE" case_arsenal_live
run_case "no usage figures: never LIVE" case_no_usage_figures_unknown
run_case "no secrets ever appear in lookup output" case_no_secrets_in_output
# --- regressions found by the Kimi K3 blind refutation, both CONFIRMED by
# --- measurement before being fixed (a refuter finding is a lead, not a fact).

case_future_timestamp_is_unknown() {
    # GUILT: before the fix, `age > max_age_s` was the ONLY freshness test, so a
    # NEGATIVE age (report dated ahead of now) read as fresh forever. Measured:
    # a report 11.5 days in the future carrying weekly_pct=100 returned
    # EXHAUSTED and SKIPPED the seat. A wrong skip is the dangerous polarity.
    local quota="$FIXTURE/c17-quota.json" out state rc=0 skiprc=0
    write_quota_fixture "$quota" "seat-f@example.invalid" 100.0 1.0 "$(( $(now_epoch) + 1000000 ))"
    out="$(env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c17-missing.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-f@example.invalid")" || rc=$?
    [ "$rc" -eq 2 ] || return 1
    state="${out%%$'\t'*}"
    [ "$state" = "UNKNOWN" ] || return 1
    case "${out#*$'\t'}" in *future*) : ;; *) return 1 ;; esac
    # and it must not skip
    env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c17-missing.json" \
        CLAUDE_SEAT_ACCOUNT_2="seat-f@example.invalid" \
        bash -c ". \"$SEAT_STATE\"; seat_state_precheck_skip claude-token-2-env" || skiprc=$?
    [ "$skiprc" -eq 1 ]
}

case_small_clock_skew_still_tolerated() {
    # INNOCENCE for the fix above: ordinary NTP jitter between two fleet
    # machines must NOT be turned into UNKNOWN, or the feature dies on healthy
    # infrastructure. 60s ahead is still a usable report.
    local quota="$FIXTURE/c18-quota.json" out rc=0
    write_quota_fixture "$quota" "seat-g@example.invalid" 100.0 1.0 "$(( $(now_epoch) + 60 ))"
    out="$(env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c18-missing.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-g@example.invalid")" || rc=$?
    [ "$rc" -eq 1 ] || return 1
    [ "${out%%$'\t'*}" = "EXHAUSTED" ]
}

case_naive_timestamp_is_unknown() {
    # GUILT: a timestamp with no timezone is read by Python in LOCAL time.
    # Measured on Mini (UTC+8): an arsenal report stamped naive-UTC and written
    # THAT SECOND reported "stale age=28800s" — exactly the local offset. West
    # of UTC the same bug yields a negative age, i.e. fresh forever. We cannot
    # know which zone the writer meant, so the answer must be UNKNOWN.
    local arsenal="$FIXTURE/c19-arsenal.json" naive out rc=0
    naive="$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"))')"
    cat > "$arsenal" <<JSON
{"ts": "$naive", "seats": [{"seat": "kimi", "status": "QUOTA_DEAD"}]}
JSON
    out="$(env SEAT_STATE_REPORT="$FIXTURE/c19-missing.json" SEAT_STATE_ARSENAL_REPORT="$arsenal" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup kimi")" || rc=$?
    [ "$rc" -eq 2 ] || return 1
    [ "${out%%$'\t'*}" = "UNKNOWN" ] || return 1
    case "${out#*$'\t'}" in *timezone*) : ;; *) return 1 ;; esac
}

case_real_cascade_labels_match_precheck() {
    # The wiring test proves the CALL exists; this proves the call can ever FIRE.
    # seat_state_precheck_skip only acts on labels shaped claude-token-<N>-...,
    # so if the cascade ever renames its numbered labels the feature goes
    # silently inert — armed-to-nothing, family #2.
    #
    # The cascade passes BOTH kinds of label and both are correct:
    #   numbered  claude-token-{1,2,3,4,5}-...  -> must parse and be able to skip
    #   unnumbered claude-keychain / claude-token-legacy-env
    #                                          -> must NEVER skip (no slot, no map)
    # Asserting "all labels parse" was wrong and failed on the legacy label; the
    # partition below is the real invariant.
    local labels l numbered=0 unnumbered=0 q="$FIXTURE/c20-quota.json" n rc
    # Extract EVERY label the cascade uses, not only ones already shaped
    # claude-token-*. Grepping for the shape we expect is circular: a rename to
    # claude-seat-3-env simply vanishes from the input set, so the shape check
    # below never sees it and the case stays green (measured — that mutant
    # survived two earlier versions of this test). Both `label="..."`
    # assignments and literal try_claude call-site labels are collected.
    labels="$( { grep -oE 'label="[^"]+"' "$CASCADE" | sed -E 's/^label="//; s/"$//'
                 grep -oE 'try_claude "[^"]+" "[^"]+"' "$CASCADE" | sed -E 's/.*" "//; s/"$//'
               } | grep -E '^claude' | sort -u )"
    [ -n "$labels" ] || return 1
    write_quota_fixture "$q" "seat-h@example.invalid" 100.0 1.0
    while IFS= read -r l; do
        [ -n "$l" ] || continue
        n="$(printf '%s' "$l" | sed -nE 's/^claude-token-([0-9]+)(-.*)?$/\1/p')"
        # A label carrying a slot-shaped digit MUST parse. Counting only the
        # labels that already parse is circular: a rename such as
        # claude-token-3-env -> claude-seat-3-env removes a seat from coverage
        # while every REMAINING label still parses, so a floor-count test stays
        # green (measured — that mutant survived the first version of this case).
        # Classify by "does it look like a numbered seat", then demand it parse.
        if [ -z "$n" ] && printf '%s' "$l" | grep -qE -- '-[0-9]+(-|$)'; then
            printf '  label %s looks like a numbered seat but does not parse\n' "$l" >&2
            return 1
        fi
        if [ -n "$n" ]; then
            rc=0
            env SEAT_STATE_REPORT="$q" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c20-missing.json" \
                "CLAUDE_SEAT_ACCOUNT_$n=seat-h@example.invalid" \
                bash -c ". \"$SEAT_STATE\"; seat_state_precheck_skip $l" || rc=$?
            [ "$rc" -eq 0 ] || return 1
            numbered=$((numbered + 1))
        else
            rc=0
            env SEAT_STATE_REPORT="$q" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c20-missing.json" \
                CLAUDE_SEAT_ACCOUNT_1="seat-h@example.invalid" \
                bash -c ". \"$SEAT_STATE\"; seat_state_precheck_skip $l" || rc=$?
            [ "$rc" -eq 1 ] || return 1
            unnumbered=$((unnumbered + 1))
        fi
    done <<< "$labels"
    # A floor alone cannot catch a rename (see above); the per-label shape check
    # does that. The floor stays only as a tripwire against the grep silently
    # matching nothing. It is a FLOOR, not an exact count, so PR #4644 adding a
    # sixth seat does not turn this red.
    [ "$numbered" -ge 5 ] && [ "$unnumbered" -ge 2 ]
}

case_nonstrict_json_is_unknown() {
    # GUILT: Python json accepts Infinity/NaN by default. Measured: a report
    # with weekly_pct Infinity returned EXHAUSTED and SKIPPED the seat — a
    # strictly-invalid report forcing the one decision that costs a live seat.
    local quota="$FIXTURE/c21-quota.json" out rc=0
    cat > "$quota" <<JSON
{"generated_at_epoch": $(now_epoch), "seats": [{"account": "seat-i@example.invalid", "weekly_pct": Infinity, "session_pct": 1.0}]}
JSON
    out="$(env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c21-missing.json" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup seat-i@example.invalid")" || rc=$?
    [ "$rc" -eq 2 ] || return 1
    [ "${out%%$'\t'*}" = "UNKNOWN" ]
}

case_sentinel_not_exported_to_children() {
    # F4: the guarantee is one probe per PROCESS. Exporting made it one probe
    # per process TREE, so every child the cascade spawns inherited the flag and
    # could never refresh.
    #
    # The fixture MUST make the lookup reach the probe branch. The first version
    # used a fresh LIVE report, which resolves immediately and never sets the
    # sentinel at all — so the mutant that re-added `export` survived. A missing
    # report forces UNKNOWN, which is what actually arms the probe path.
    local n
    n="$(env SEAT_STATE_REPORT="$FIXTURE/c22-absent.json" \
        SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c22-absent2.json" \
        SEAT_STATE_PROBE_CMD="/usr/bin/true" \
        bash -c ". \"$SEAT_STATE\"
seat_state_lookup seat-j@example.invalid >/dev/null 2>&1
# proves the branch ran at all: without it this case would pass vacuously
[ \"\${SEAT_STATE_PROBED:-}\" = 1 ] || { echo BRANCH-NOT-REACHED; exit 0; }
env | grep -c '^SEAT_STATE_PROBED=' || true")"
    [ "$n" = "0" ]
}

case_reason_field_is_sanitised() {
    # F5: report values are unvalidated input and land on the field-separated
    # line this bridge prints. A crafted status carrying tabs/newlines must not
    # inject extra fields into that line.
    local arsenal="$FIXTURE/c24-arsenal.json" out
    cat > "$arsenal" <<JSON
{"ts": "$(now_iso)", "seats": [{"seat": "kimi", "status": "WEIRD\tLIVE\t1"}]}
JSON
    out="$(env SEAT_STATE_REPORT="$FIXTURE/c24-missing.json" SEAT_STATE_ARSENAL_REPORT="$arsenal" \
        bash -c ". \"$SEAT_STATE\"; seat_state_lookup kimi" 2>/dev/null || true)"
    # NF alone cannot judge this: an unsanitised tab does not ADD a field, the
    # shell's own field-split TRUNCATES the reason at it (measured: the mutant
    # prints "status=WEIRD" and still shows NF=2). The observable that actually
    # separates them is whether the value survived intact.
    [ "$(printf '%s' "$out" | awk -F'\t' '{print NF}')" = "2" ] || return 1
    [ "${out%%$'\t'*}" = "UNKNOWN" ] || return 1
    case "$out" in *WEIRD*LIVE*1*) : ;; *) return 1 ;; esac
}

case_zsh_sources_and_runs_under_set_u() {
    # T2: invariant 5 said the library must be safe when sourced by zsh under
    # set -u — the cascade's real mode — and nothing tested it. zsh-only
    # regressions (unset refs, local semantics) would ship unseen.
    command -v zsh >/dev/null 2>&1 || { printf '  SKIP zsh not on PATH\n' >&2; return 0; }
    local quota="$FIXTURE/c23-quota.json" rc=0
    write_quota_fixture "$quota" "seat-k@example.invalid" 100.0 1.0
    env SEAT_STATE_REPORT="$quota" SEAT_STATE_ARSENAL_REPORT="$FIXTURE/c23-missing.json" \
        CLAUDE_SEAT_ACCOUNT_2="seat-k@example.invalid" \
        zsh -c 'set -uo pipefail
. '"$SEAT_STATE"'
seat_state_precheck_skip claude-token-2-env' || rc=$?
    # exhausted seat under zsh + set -u must still resolve to a skip (rc 0)
    [ "$rc" -eq 0 ]
}

run_case "regression: non-strict JSON (Infinity) is UNKNOWN" case_nonstrict_json_is_unknown
run_case "regression: probe sentinel does not leak to children" case_sentinel_not_exported_to_children
run_case "regression: reason field is sanitised" case_reason_field_is_sanitised
run_case "zsh: library sources and skips correctly under set -u" case_zsh_sources_and_runs_under_set_u
run_case "regression: future-dated report is UNKNOWN, never a skip" case_future_timestamp_is_unknown
run_case "innocence: small clock skew is still a usable report" case_small_clock_skew_still_tolerated
run_case "regression: timezone-less timestamp is UNKNOWN" case_naive_timestamp_is_unknown
run_case "wiring: every real cascade label parses to a slot" case_real_cascade_labels_match_precheck
run_case "cascade wiring: sourced, called, kill-switched, loop untouched" case_cascade_wiring
run_case "syntax: bash -n on seat_state.sh" case_syntax_bash
run_case "syntax: zsh -n on claude-cascade.sh" case_syntax_zsh

printf 'SUMMARY %d passed, %d failed\n' "$PASS_COUNT" "$FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
