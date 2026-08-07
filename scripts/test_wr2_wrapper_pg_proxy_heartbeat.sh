#!/usr/bin/env bash
# Proof for the pg-proxy guard's success-path heartbeat in
# scripts/wr2-cron-wrapper.sh.
#
# TRAUMA (ward-round 2026-08-07, id wr2_wrapper_guard_pg_proxy_stale, upheld
# sensor_stale). GUARD_ORGAN_ID's sidecar was write-ONLY-on-failure: both
# guard branches (DATABASE_URL_LOCAL absent, pg-proxy unreachable) called
# `organism_heartbeat "$GUARD_ORGAN_ID" "error" ...`, but nothing ever wrote
# "ok" when the guard passed. A heartbeat that can only ever say "error" can
# never clear itself — one historical trip reads as N days of ongoing outage
# even after the very next run passes clean (superscar #2, W110-adjacent: a
# sidecar that never speaks on the happy path is a guardian aimed at silence).
#
# W107 family-check (done in the prose that shipped alongside this test, not
# repeated here as code): every OTHER wrapper calling organism_heartbeat on
# error (scripts/outbox-prune.sh, scripts/agent_worktree_cleanup_cron.sh)
# already pairs it with an "ok" call on its success path. wr2-cron-wrapper.sh
# was the only sibling missing it — this is a single-site fix, not a class fix.
#
# GUILT      — pg-proxy unreachable still writes "error" (regression guard on
#              the branch the fix sits next to).
# INNOCENCE  — DATABASE_URL_LOCAL absent (the OTHER guard, same organ id)
#              still writes its own "error" and must NOT be clobbered by the
#              new line, because that branch exits before reaching it.
# THE FIX    — pg-proxy reachable writes "ok" with a note, before the module
#              even runs.
# SELF-HEAL  — a prior "error" trip is overwritten by "ok" on the next good
#              run (heartbeat.sh's own contract: atomic overwrite, not append)
#              — this is the actual behavior ward-round asked for: the sidecar
#              must be able to clear itself.
#
# Run: bash scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SRC="$SCRIPT_DIR/wr2-cron-wrapper.sh"
HEARTBEAT_SRC="$SCRIPT_DIR/lib/heartbeat.sh"
PASS=0
FAIL=0
EVIDENCE_FD="${RUNTIME_TRUTH_EVIDENCE_FD:-}"

record_result() {  # record_result <case_id> <passed|failed>
    [[ -n "$EVIDENCE_FD" ]] || return 0
    printf 'runtime-truth-shell-v1\t%s\t%s\n' "$1" "$2" >&"$EVIDENCE_FD"
}

ok() {  # ok <case_id> <label>
    PASS=$((PASS+1))
    record_result "$1" passed
    printf '  ok    %s\n' "$2"
}

bad() {  # bad <case_id> <label> <detail>
    FAIL=$((FAIL+1))
    record_result "$1" failed
    printf '  FAIL  %s\n     -> %s\n' "$2" "${3:-}"
}

# ---------------------------------------------------------------- fake world
# Real heartbeat.sh copied in (not stubbed) — the whole point of this test is
# that the sidecar actually gets written, so a no-op stub would prove nothing.
make_world() {  # make_world <nc_exit>
    local nc_exit="$1"
    W="$(mktemp -d)"
    mkdir -p "$W/scripts/lib" "$W/repo/scripts/lib" \
             "$W/repo/apps/backend-rag/.venv/bin" "$W/bin" "$W/logs" "$W/organism"
    cp "$WRAPPER_SRC" "$W/scripts/wr2-cron-wrapper.sh"
    cp "$HEARTBEAT_SRC" "$W/repo/scripts/lib/heartbeat.sh"

    # Module interpreter: exits 0 (module "succeeds" — irrelevant to what
    # this test checks, which all happens before the module ever runs).
    printf '#!/bin/sh\nexit 0\n' > "$W/repo/apps/backend-rag/.venv/bin/python"
    chmod +x "$W/repo/apps/backend-rag/.venv/bin/python"

    printf '#!/bin/sh\nexit %s\n' "$nc_exit" > "$W/bin/nc"
    chmod +x "$W/bin/nc"

    printf 'DATABASE_URL_LOCAL=postgres://x@127.0.0.1:15432/y\n' > "$W/secrets.env"
}

run_wrapper() {
    env NUZANTARA_REPO_ROOT="$W/repo" \
        NUZANTARA_SECRETS="$W/secrets.env" \
        ORGANISM_LAST_SEEN_DIR="$W/organism" \
        WR2_LOG_DIR="$W/logs" \
        WR2_CRON_ALERT=false \
        PATH="$W/bin:$PATH" \
        HOME="$W" \
        bash "$W/scripts/wr2-cron-wrapper.sh" "$@" >"$W/stdout.txt" 2>"$W/stderr.txt"
    echo $?
}

sidecar_status() {  # sidecar_status <organ_id>
    python3 -c '
import json, sys
try:
    print(json.load(open(sys.argv[1]))["status"])
except Exception:
    print("<missing>")
' "$W/organism/$1.json" 2>/dev/null
}

ORGAN="pro.wr2_wrapper_guard.some.module"

echo
echo "wr2-cron-wrapper pg-proxy guard heartbeat"
echo

# ------------------------------------------------------------------- GUILT
make_world 1   # nc fails: pg-proxy unreachable
rc="$(run_wrapper some.module)"
st="$(sidecar_status "$ORGAN")"
if [[ "$rc" == "74" && "$st" == "error" ]]; then
    ok pg_proxy_unreachable "GUILT: pg-proxy unreachable still writes status=error"
else
    bad pg_proxy_unreachable "GUILT: pg-proxy unreachable" "rc=$rc status=$st"
fi

# --------------------------------------------------------------- INNOCENCE
# The OTHER guard on the same organ id (DATABASE_URL_LOCAL absent) exits
# before ever reaching the new success-path line — must still read "error",
# never silently upgraded to "ok" by a fix that sits three lines below it.
make_world 0
printf '' > "$W/secrets.env"   # DATABASE_URL_LOCAL absent
rc="$(run_wrapper some.module)"
st="$(sidecar_status "$ORGAN")"
if [[ "$rc" == "74" && "$st" == "error" ]]; then
    ok database_url_local_missing \
        "INNOCENCE: DATABASE_URL_LOCAL guard (same organ id) still error, not ok"
else
    bad database_url_local_missing \
        "INNOCENCE: DATABASE_URL_LOCAL guard" "rc=$rc status=$st"
fi

# ------------------------------------------------------------------ THE FIX
make_world 0   # nc succeeds: pg-proxy reachable
rc="$(run_wrapper some.module)"
st="$(sidecar_status "$ORGAN")"
if [[ "$rc" == "0" && "$st" == "ok" ]]; then
    ok pg_proxy_reachable \
        "FIX: pg-proxy reachable writes status=ok — the sidecar now has a voice"
else
    bad pg_proxy_reachable "FIX: pg-proxy reachable" "rc=$rc status=$st"
fi

# --------------------------------------------------------------- SELF-HEAL
# The whole point: a prior error trip must clear on the next good run,
# because heartbeat.sh overwrites atomically rather than appending.
make_world 1
run_wrapper some.module >/dev/null
st1="$(sidecar_status "$ORGAN")"
printf '#!/bin/sh\nexit 0\n' > "$W/bin/nc"; chmod +x "$W/bin/nc"
rc="$(run_wrapper some.module)"
st2="$(sidecar_status "$ORGAN")"
if [[ "$st1" == "error" && "$rc" == "0" && "$st2" == "ok" ]]; then
    ok heartbeat_self_heal \
        "SELF-HEAL: an error sidecar clears to ok on the next good run"
else
    bad heartbeat_self_heal \
        "SELF-HEAL: sidecar did not clear" "st1=$st1 rc=$rc st2=$st2"
fi

echo
echo "  $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
