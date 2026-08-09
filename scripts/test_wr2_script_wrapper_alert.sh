#!/usr/bin/env bash
# Proof for the failure voice in infra/openclaw/wr2/wr2-script-wrapper.sh.
#
# TRAUMA (2026-08-06). #3686 gave wr2-cron-wrapper.sh a voice and stopped
# there. Going back the same day to ask "did it actually fire?", the census of
# LaunchAgent ProgramArguments found a SECOND wrapper in the same directory —
# wr2-script-wrapper.sh, eight jobs: daily-metrics, draft-generator,
# fact-checker, fact-extractor, image-generator, supervisor,
# supervisor-watchdog, topic-selector — against nine on the one that got cured.
# W107 with the names swapped: curing one wrapper of a pair does not cut the
# risk, it moves which cohort dies quietly.
#
# Two independent mechanisms, measured on the live copy before writing a line:
#
#   * EIGHT silent non-zero exits (64, 74, 74, 66, and four distinct 75 in the
#     venv auto-heal), none of which said anything to anyone;
#   * the file ended in `exec "$VENV_PY" "$FULL_SCRIPT"`, which REPLACED the
#     shell — so the script's own failure, the normal way these jobs die, never
#     returned to the wrapper at all. There was no "after" to put a trap in.
#
# Its only Telegram call was a raw `curl … || true` reachable solely from the
# venv-missing branch: no tier, no budget, no dedup, and in launchd's
# token-poor environment it did nothing AND left no trace of doing nothing.
#
#   GUILT ×5     — every exit must speak, not the one that bit us: the job
#                  itself, the DATABASE_URL_LOCAL guard, the pg-proxy guard,
#                  the script-not-found exit (armed-at-nothing, W81), and the
#                  no-argument usage exit.
#   VENV NOTICE  — the ex-curl must now reach the GATEWAY, at digest tier, and
#                  a heal that then fails must still raise p0. Both, one run.
#   INNOCENCE ×2 — success must not alert; the alert kill switch must hold.
#   FAIL-OPEN ×2 — a missing gateway and an exploding gateway must both leave
#                  the exit code untouched. That code is the contract.
#   W108         — the alarm must survive a poisoned python3 on PATH and in the
#                  venv. This wrapper's entire job is finding and repairing a
#                  venv, so an alarm on a PATH-resolved python3 would run on
#                  the very interpreter whose breakage it must report.
#   KEY STABLE   — two failures, different exit codes, ONE dedup key (#3677).
#
# Run: bash scripts/test_wr2_script_wrapper_alert.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SRC="$SCRIPT_DIR/../infra/openclaw/wr2/wr2-script-wrapper.sh"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n     -> %s\n' "$1" "${2:-}"; }

# ---------------------------------------------------------------- fake world
# Rich enough to REACH the code under test. A poor fake world measures its own
# poverty (W108 GOTCHA-2), and this wrapper has more gates than its sibling:
# secrets file, DATABASE_URL_LOCAL, a live pg-proxy, an existing script, and a
# venv whose python can actually `import asyncpg`. Every one is provided, and
# each case asserts it got as far as it meant to.
#
# Fake binaries go in $HOME/.local/bin, NOT an arbitrary dir prepended to PATH:
# the wrapper force-exports PATH="$HOME/.local/bin:/opt/homebrew/bin:...:$PATH",
# so anything placed after that prefix is shadowed by the real /usr/bin/nc and
# the case would silently measure nothing. Found by reading the wrapper's own PATH
# line rather than assuming the sibling's harness transferred.
make_world() {  # make_world <script_exit> [--no-gateway|--boom-gateway|--no-venv]
    local script_exit="$1"; shift || true
    local mode="${1:-normal}"
    W="$(mktemp -d)"
    mkdir -p "$W/repo/scripts" "$W/repo/apps/backend-rag/.venv/bin" "$W/.local/bin"
    mkdir -p "$W/.claude"
    cp "$WRAPPER_SRC" "$W/wr2-script-wrapper.sh"
    chmod +x "$W/wr2-script-wrapper.sh"

    if [[ "$mode" != "--no-gateway" ]]; then
        if [[ "$mode" == "--boom-gateway" ]]; then
            cat > "$W/repo/scripts/tg_notify.py" <<'PYX'
import sys
sys.stderr.write("gateway exploded\n")
raise SystemExit(9)
PYX
        else
            cat > "$W/repo/scripts/tg_notify.py" <<'PYX'
import json, os, sys
with open(os.environ["FAKE_TG_CALLS"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
PYX
        fi
    fi

    # The job the wrapper is asked to run.
    : > "$W/repo/scripts/wr2_fake_job.py"

    # The venv interpreter. It is called TWICE with different intent: once as
    # `python -c "import asyncpg"` for the health probe (must pass, or every
    # case detours into auto-heal and measures that instead), and once to run
    # the job (must exit with the code under test).
    if [[ "$mode" != "--no-venv" ]]; then
        cat > "$W/repo/apps/backend-rag/.venv/bin/python" <<EOF
#!/bin/sh
case "\$1" in
  -c) exit 0 ;;
   *) exit $script_exit ;;
esac
EOF
        chmod +x "$W/repo/apps/backend-rag/.venv/bin/python"
    fi

    # pg-proxy reachability probe: succeed unless a case overrides it.
    printf '#!/bin/sh\nexit 0\n' > "$W/.local/bin/nc"; chmod +x "$W/.local/bin/nc"

    printf 'DATABASE_URL_LOCAL=postgres://x@127.0.0.1:15432/y\n' > "$W/.nuzantara-secrets.env"
    : > "$W/calls.jsonl"
}

run_wrapper() {  # run_wrapper [env assignments...] -- <args>
    env FAKE_TG_CALLS="$W/calls.jsonl" \
        WR2_REPO_ROOT="$W/repo" \
        HOME="$W" \
        "$@" >"$W/stdout.txt" 2>"$W/stderr.txt"
    echo $?
}

calls() { cat "$W/calls.jsonl" 2>/dev/null; }
# `grep -c` PRINTS 0 and EXITS 1 on no match, so `grep -c . f || echo 0` emits
# TWO zeros and every comparison fails. The probe that measures a disease can
# have it (W107) — this cost two false reds in the sibling's harness.
call_count() { awk 'NF{n++} END{print n+0}' "$W/calls.jsonl" 2>/dev/null || echo 0; }
dedup_key()  { python3 -c '
import json,sys
for line in open(sys.argv[1]):
    a=json.loads(line)
    if "--dedup-key" in a: print(a[a.index("--dedup-key")+1])
' "$W/calls.jsonl" 2>/dev/null; }

echo
echo "wr2-script-wrapper failure voice"
echo

# ------------------------------------------------------------------- GUILT 1
# THE one the `exec` made structurally impossible.
make_world 3
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
if [[ "$rc" == "3" && "$(call_count)" == "1" ]] && calls | grep -q '"cron-fail:wr2.wr2_fake_job.job"'; then
    ok "GUILT: the job exits 3 — alert fires and the wrapper still exits 3 (the exec killed this)"
else
    bad "GUILT: job failure" "rc=$rc calls=$(call_count) $(calls)"
fi

# ------------------------------------------------------------------- GUILT 2
make_world 0
printf '' > "$W/.nuzantara-secrets.env"
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
if [[ "$rc" == "74" && "$(call_count)" == "1" ]] && calls | grep -q '"cron-fail:wr2.wr2_fake_job.guard"'; then
    ok "GUILT: the DATABASE_URL_LOCAL guard speaks"
else
    bad "GUILT: DATABASE_URL_LOCAL guard" "rc=$rc calls=$(call_count) $(calls)"
fi

# ------------------------------------------------------------------- GUILT 3
make_world 0
printf '#!/bin/sh\nexit 1\n' > "$W/.local/bin/nc"; chmod +x "$W/.local/bin/nc"
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
if [[ "$rc" == "74" && "$(call_count)" == "1" ]] && calls | grep -q '"cron-fail:wr2.wr2_fake_job.guard"'; then
    ok "GUILT: the pg-proxy guard speaks"
else
    bad "GUILT: pg-proxy guard" "rc=$rc calls=$(call_count) $(calls) stderr=$(cat "$W/stderr.txt")"
fi

# ------------------------------------------------------------------- GUILT 4
# Armed at nothing (W81): the plist names a script that is not in the repo.
make_world 0
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_does_not_exist.py)"
if [[ "$rc" == "66" && "$(call_count)" == "1" ]] && calls | grep -q '"cron-fail:wr2.wr2_does_not_exist.script"'; then
    ok "GUILT: a plist pointed at a missing script — armed at nothing, and now audible"
else
    bad "GUILT: script not found" "rc=$rc calls=$(call_count) $(calls)"
fi

# ------------------------------------------------------------------- GUILT 5
make_world 0
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh")"
if [[ "$rc" == "64" && "$(call_count)" == "1" ]] && calls | grep -q 'startup'; then
    ok "GUILT: invoked with no script at all — the most invisible exit"
else
    bad "GUILT: usage exit" "rc=$rc calls=$(call_count) $(calls)"
fi

# -------------------------------------------------------------- VENV NOTICE
# The ex-curl. Venv absent, so: (1) the notice must reach the GATEWAY at
# DIGEST tier — it is a warning, the heal may well succeed — and (2) the heal
# then fails on a missing pyenv, exit 75, which must raise p0 through the trap.
# One run, two calls, two different tiers. A cure that only moved the curl
# would produce one call; a cure that made the notice p0 would produce two p0.
make_world 0 --no-venv
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
n_digest="$(calls | grep -c '"digest"')"
n_p0="$(calls | grep -c '"p0"')"
if [[ "$rc" == "75" && "$n_digest" == "1" && "$n_p0" == "1" ]] \
   && calls | grep -q '"wr2-venv-missing.wr2_fake_job"'; then
    ok "VENV: the ex-curl reaches the gateway at digest, and the failed heal still raises p0"
else
    bad "VENV notice" "rc=$rc digest=$n_digest p0=$n_p0 $(calls)"
fi

# --------------------------------------------------------------- INNOCENCE 1
make_world 0
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
if [[ "$rc" == "0" && "$(call_count)" == "0" ]]; then
    ok "INNOCENCE: a succeeding job does not alert"
else
    bad "INNOCENCE: success" "rc=$rc calls=$(call_count) $(calls) stderr=$(cat "$W/stderr.txt")"
fi

# --------------------------------------------------------------- INNOCENCE 2
make_world 3
rc="$(run_wrapper WR2_CRON_ALERT=false bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
if [[ "$rc" == "3" && "$(call_count)" == "0" ]]; then
    ok "INNOCENCE: WR2_CRON_ALERT=false silences the alert without touching the exit code"
else
    bad "INNOCENCE: alert kill switch" "rc=$rc calls=$(call_count) $(calls)"
fi

# ---------------------------------------------------------------- FAIL-OPEN 1
make_world 5 --no-gateway
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
if [[ "$rc" == "5" ]]; then
    ok "FAIL-OPEN: no gateway on disk — the job's exit code survives untouched"
else
    bad "FAIL-OPEN: missing gateway" "rc=$rc (expected 5)"
fi

# ---------------------------------------------------------------- FAIL-OPEN 2
make_world 5 --boom-gateway
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
if [[ "$rc" == "5" ]]; then
    ok "FAIL-OPEN: a gateway that raises does not rewrite the exit code"
else
    bad "FAIL-OPEN: exploding gateway" "rc=$rc (expected 5)"
fi

# --------------------------------------------------------------------- W108
# Poison BOTH interpreters a naive implementation would reach for. $HOME/.local/bin
# is FIRST in the PATH this wrapper exports, so this really does shadow the
# system python3 for anything PATH-resolved. A bare-`python3` alarm scores 0
# calls here — precisely how run_nb5_t4_monitor.sh stayed mute.
make_world 4
printf '#!/bin/sh\nexit 127\n' > "$W/.local/bin/python3"; chmod +x "$W/.local/bin/python3"
cp "$W/.local/bin/python3" "$W/repo/apps/backend-rag/.venv/bin/python3"
rc="$(run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py)"
if [[ "$rc" == "4" && "$(call_count)" == "1" ]]; then
    ok "W108: the alarm survives a poisoned python3 on PATH and in the venv"
else
    bad "W108: poisoned interpreter" "rc=$rc calls=$(call_count) — a PATH-resolved python3 would score 0"
fi

# --------------------------------------------------------------- KEY STABLE
make_world 3
run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py >/dev/null
cat > "$W/repo/apps/backend-rag/.venv/bin/python" <<'EOF'
#!/bin/sh
case "$1" in
  -c) exit 0 ;;
   *) exit 7 ;;
esac
EOF
chmod +x "$W/repo/apps/backend-rag/.venv/bin/python"
run_wrapper bash "$W/wr2-script-wrapper.sh" scripts/wr2_fake_job.py >/dev/null
uniq_keys="$(dedup_key | sort -u | grep -c .)"
if [[ "$(call_count)" == "2" && "$uniq_keys" == "1" ]]; then
    ok "KEY: two failures, different exit codes, ONE dedup key"
else
    bad "KEY: unstable dedup key" "calls=$(call_count) distinct=$uniq_keys — $(dedup_key | sort -u | tr '\n' ' ')"
fi

echo
echo "  $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
