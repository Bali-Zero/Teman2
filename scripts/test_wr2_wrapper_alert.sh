#!/usr/bin/env bash
# Proof for the failure voice in scripts/wr2-cron-wrapper.sh.
#
# TRAUMA (2026-08-06). W107 cured cron-runner.sh and named a sixth wrapper —
# wr2-cron-wrapper.sh, 14 launchd jobs — as NOT cured but excused: "by design it
# relies on the missed_runs_alerter". Measured this turn instead of assumed:
#
#   * `war_room_missed_runs` holds 0 rows on the live DB and always has
#     (max(created_at) IS NULL);
#   * `record_missed_run`, its only writer, has zero callers outside its own
#     definition — the table is never written by anything;
#   * the alerter is HEALTHY: every 6h inside com.balizero.wr2.hardening,
#     exit 0, `pending_count: 0` since April. It reads an empty population.
#   * meanwhile com.balizero.wr2.dossier-compiler sat at LastExitStatus=512
#     (exit 2) with nobody informed.
#
# A guardian aimed at an empty table is not coverage. And the wrapper could not
# have spoken even if asked to: it ended in `exec`, a one-way door with no
# "after" in which to read an exit code.
#
#   GUILT ×4    — ALL the exits must speak, not the one that bit us (W107 is
#                 exactly that mistake): module failure, the DATABASE_URL_LOCAL
#                 guard, the pg-proxy guard, and the no-argument usage exit,
#                 which is the most invisible of all.
#   INNOCENCE ×2 — success must NOT alert, and neither must the kill switch.
#                 An alarm that fires on a deliberate stop gets turned off.
#   FAIL-OPEN ×2 — a missing gateway and an exploding gateway must both leave
#                 the job's exit code untouched. The exit code is the contract
#                 this wrapper exists to preserve.
#   W108        — the alert must survive a POISONED interpreter on PATH and in
#                 the venv. This is the one line that is not a copy of
#                 cron-runner.sh: this wrapper activates a venv before running
#                 the module, so a bare `python3` in the alarm would run on the
#                 interpreter whose breakage is a leading cause of the failure
#                 being reported. A bare-python3 implementation fails this test.
#   KEY STABLE  — two failures of the same module with different exit codes must
#                 produce the SAME dedup key. A key that moves with a
#                 measurement beats every window (#3677, discovery 2026-08-06).
#
# Run: bash scripts/test_wr2_wrapper_alert.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SRC="$SCRIPT_DIR/wr2-cron-wrapper.sh"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n     -> %s\n' "$1" "${2:-}"; }

# ---------------------------------------------------------------- fake world
# A wrapper copied into tmp, with a fake gateway beside it, a fake venv python,
# a fake `nc`, and a secrets file. Poor fake worlds measure their own poverty
# (W108 GOTCHA-2: a first harness reported 17/20 because nearly every script
# died at its own "no virtualenv found" before reaching the code under test),
# so every knob the wrapper actually consults is provided and each case asserts
# it got as far as it meant to.
make_world() {  # make_world <venv_exit> [--no-gateway|--boom-gateway]
    local venv_exit="$1"; shift || true
    local mode="${1:-normal}"
    W="$(mktemp -d)"
    mkdir -p "$W/scripts" "$W/repo/apps/backend-rag/.venv/bin" "$W/bin" "$W/logs"
    cp "$WRAPPER_SRC" "$W/scripts/wr2-cron-wrapper.sh"

    if [[ "$mode" != "--no-gateway" ]]; then
        if [[ "$mode" == "--boom-gateway" ]]; then
            cat > "$W/scripts/tg_notify.py" <<'PYX'
import sys
sys.stderr.write("gateway exploded\n")
raise SystemExit(9)
PYX
        else
            cat > "$W/scripts/tg_notify.py" <<'PYX'
import json, os, sys
with open(os.environ["FAKE_TG_CALLS"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
PYX
        fi
    fi

    # The venv interpreter the wrapper will run the module with.
    printf '#!/bin/sh\nexit %s\n' "$venv_exit" > "$W/repo/apps/backend-rag/.venv/bin/python"
    chmod +x "$W/repo/apps/backend-rag/.venv/bin/python"

    # pg-proxy reachability probe: succeed unless a case overrides it.
    printf '#!/bin/sh\nexit 0\n' > "$W/bin/nc"; chmod +x "$W/bin/nc"

    printf 'DATABASE_URL_LOCAL=postgres://x@127.0.0.1:15432/y\n' > "$W/secrets.env"
    : > "$W/calls.jsonl"
}

run_wrapper() {  # run_wrapper [extra env assignments...] -- <args>
    env FAKE_TG_CALLS="$W/calls.jsonl" \
        NUZANTARA_REPO_ROOT="$W/repo" \
        NUZANTARA_SECRETS="$W/secrets.env" \
        WR2_LOG_DIR="$W/logs" \
        PATH="$W/bin:$PATH" \
        HOME="$W" \
        "$@" >"$W/stdout.txt" 2>"$W/stderr.txt"
    echo $?
}

calls()      { cat "$W/calls.jsonl" 2>/dev/null; }
# `grep -c` PRINTS 0 and EXITS 1 on no match, so the obvious
# `grep -c . f || echo 0` emits TWO zeros and every comparison against "0"
# fails. The probe that measures a disease can have it (W107) — this cost
# two false reds on the innocence cases before it was caught.
call_count() { awk 'NF{n++} END{print n+0}' "$W/calls.jsonl" 2>/dev/null || echo 0; }
dedup_key()  { python3 -c '
import json,sys
for line in open(sys.argv[1]):
    a=json.loads(line)
    print(a[a.index("--dedup-key")+1]) if "--dedup-key" in a else None
' "$W/calls.jsonl" 2>/dev/null; }

echo
echo "wr2-cron-wrapper failure voice"
echo

# ------------------------------------------------------------------- GUILT 1
make_world 3
rc="$(run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module)"
if [[ "$rc" == "3" && "$(call_count)" == "1" ]] && calls | grep -q '"cron-fail:wr2.module.module"'; then
    ok "GUILT: a module that exits 3 alerts, and the wrapper still exits 3"
else
    bad "GUILT: module failure" "rc=$rc calls=$(call_count) $(calls)"
fi

# ------------------------------------------------------------------- GUILT 2
make_world 0
printf '' > "$W/secrets.env"   # DATABASE_URL_LOCAL absent
rc="$(run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module)"
if [[ "$rc" == "74" && "$(call_count)" == "1" ]] && calls | grep -q '"cron-fail:wr2.module.guard"'; then
    ok "GUILT: the DATABASE_URL_LOCAL guard speaks (was stderr + sidecar only)"
else
    bad "GUILT: DATABASE_URL_LOCAL guard" "rc=$rc calls=$(call_count) $(calls)"
fi

# ------------------------------------------------------------------- GUILT 3
make_world 0
printf '#!/bin/sh\nexit 1\n' > "$W/bin/nc"; chmod +x "$W/bin/nc"
rc="$(run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module)"
if [[ "$rc" == "74" && "$(call_count)" == "1" ]]; then
    ok "GUILT: the pg-proxy guard speaks"
else
    bad "GUILT: pg-proxy guard" "rc=$rc calls=$(call_count) $(calls)"
fi

# ------------------------------------------------------------------- GUILT 4
make_world 0
rc="$(run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh")"
if [[ "$rc" == "64" && "$(call_count)" == "1" ]] && calls | grep -q 'startup'; then
    ok "GUILT: invoked with no module at all — the most invisible exit"
else
    bad "GUILT: usage exit" "rc=$rc calls=$(call_count) $(calls)"
fi

# --------------------------------------------------------------- INNOCENCE 1
make_world 0
rc="$(run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module)"
if [[ "$rc" == "0" && "$(call_count)" == "0" ]]; then
    ok "INNOCENCE: a succeeding module does not alert"
else
    bad "INNOCENCE: success" "rc=$rc calls=$(call_count) $(calls)"
fi

# --------------------------------------------------------------- INNOCENCE 2
make_world 3
rc="$(run_wrapper WR2_CRON_ENABLED=false bash "$W/scripts/wr2-cron-wrapper.sh" some.module)"
if [[ "$rc" == "0" && "$(call_count)" == "0" ]]; then
    ok "INNOCENCE: the kill switch is a deliberate stop, not a death"
else
    bad "INNOCENCE: kill switch" "rc=$rc calls=$(call_count) $(calls)"
fi

# ---------------------------------------------------------------- FAIL-OPEN 1
make_world 5 --no-gateway
rc="$(run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module)"
if [[ "$rc" == "5" ]]; then
    ok "FAIL-OPEN: no gateway on disk — the job's exit code survives untouched"
else
    bad "FAIL-OPEN: missing gateway" "rc=$rc (expected 5)"
fi

# ---------------------------------------------------------------- FAIL-OPEN 2
make_world 5 --boom-gateway
rc="$(run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module)"
if [[ "$rc" == "5" ]]; then
    ok "FAIL-OPEN: a gateway that raises does not rewrite the exit code"
else
    bad "FAIL-OPEN: exploding gateway" "rc=$rc (expected 5)"
fi

# --------------------------------------------------------------------- W108
# Poison BOTH interpreters a naive implementation would reach for: the venv's
# (which is also the failing module's) and a `python3` earlier on PATH. Only an
# absolute system interpreter still delivers. A bare-`python3` alarm scores 0
# calls here — which is precisely how run_nb5_t4_monitor.sh stayed mute.
make_world 4
printf '#!/bin/sh\nexit 127\n' > "$W/bin/python3"; chmod +x "$W/bin/python3"
cp "$W/bin/python3" "$W/repo/apps/backend-rag/.venv/bin/python3" 2>/dev/null || true
rc="$(run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module)"
if [[ "$rc" == "4" && "$(call_count)" == "1" ]]; then
    ok "W108: the alarm survives a poisoned python3 on PATH and in the venv"
else
    bad "W108: poisoned interpreter" "rc=$rc calls=$(call_count) — a PATH-resolved python3 would score 0"
fi

# --------------------------------------------------------------- KEY STABLE
# Two failures of the same module, different exit codes. #3677: a key that
# embeds a measurement mints a new key per event and defeats every window.
make_world 3
run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module >/dev/null
printf '#!/bin/sh\nexit 7\n' > "$W/repo/apps/backend-rag/.venv/bin/python"
chmod +x "$W/repo/apps/backend-rag/.venv/bin/python"
run_wrapper bash "$W/scripts/wr2-cron-wrapper.sh" some.module >/dev/null
uniq_keys="$(dedup_key | sort -u | grep -c .)"
if [[ "$(call_count)" == "2" && "$uniq_keys" == "1" ]]; then
    ok "KEY: two failures, different exit codes, ONE dedup key"
else
    bad "KEY: unstable dedup key" "calls=$(call_count) distinct keys=$uniq_keys — $(dedup_key | sort -u | tr '\n' ' ')"
fi

echo
echo "  $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
