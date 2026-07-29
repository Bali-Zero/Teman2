#!/usr/bin/env bash
# test_connectome_alert_honesty.sh — the connectome alert must not lie to its reader.
#
# Three properties, each with guilt AND innocence, exercised on the REAL wrapper
# inside a fake world (fake repo, fake verifier, fake gateway, fake curl, fake
# HOME). Nothing here asserts that the script CONTAINS a string: every case runs
# scripts/verify_connectome_run.sh and reads the message it actually built.
#
#   1. FRESHNESS  — a verdict judged on a checkout behind origin/main must say so
#                   IN THE ALERT, not only on stderr. The stderr warning shipped
#                   earlier the same day went to a log nobody reads while the
#                   Telegram message stayed identical at 0 and at 258 commits
#                   behind.
#   2. TRUNCATION — `head -10` is a display cap; 10 of 23 rendered as a bare list
#                   reads as the complete set (W97). Say "showing 10 of 23".
#   3. DELIVERY   — the send goes through scripts/tg_notify.py, which judges the
#                   reply body, never a bare curl that judges its own delivery by
#                   an exit code that is 0 even for {"ok":false} (W104). A fake
#                   curl on PATH proves the bare path is not merely unused but
#                   unreachable.
#
# Exit 0 = all pass. Any failure prints what it expected and what it got.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$REPO_ROOT/scripts/verify_connectome_run.sh"
FAILURES=0
CASES=0

fail() {
    FAILURES=$((FAILURES + 1))
    echo "  ✗ FAIL: $1"
    [[ $# -gt 1 ]] && printf '    %s\n' "${@:2}"
}
pass() { echo "  ✓ $1"; }

if [[ ! -x "$WRAPPER" && ! -f "$WRAPPER" ]]; then
    echo "FATAL: wrapper not found at $WRAPPER"
    exit 2
fi

# The alarm resolves an absolute interpreter (W108). If this box has none of the
# three, say so instead of reporting a green built on an untaken branch.
SYS_PY=""
for c in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    [[ -x "$c" ]] && { SYS_PY="$c"; break; }
done
if [[ -z "$SYS_PY" ]]; then
    echo "FATAL: no absolute python3 on this machine — the corpus cannot exercise the gateway branch"
    exit 2
fi

# ─────────────────────────────────────────────────────────── fake world builder
# Returns a dir containing: origin/ (bare-ish source), work/ (the checkout the
# wrapper runs against), home/ (fake HOME), bin/ (fake curl), out/ (recordings).
build_world() {
    local behind="$1" n_regressed="$2" with_gateway="$3"
    local root; root="$(mktemp -d)"
    mkdir -p "$root/out" "$root/bin" "$root/home"

    # --- origin repo -------------------------------------------------------
    local origin="$root/origin"
    mkdir -p "$origin/docs/connectome/edges" "$origin/scripts" "$origin/apps/backend-rag/.venv/bin"
    echo "edges: []" > "$origin/docs/connectome/edges/fake.yaml"
    cp "$WRAPPER" "$origin/scripts/verify_connectome_run.sh"

    # Fake verifier, invoked as "$PYBIN scripts/verify_connectome.py ...".
    # PYBIN is the venv python; making THAT the emitter keeps the fake world free
    # of any PyYAML dependency (the wrapper's system-python fallback demands it).
    cat > "$origin/apps/backend-rag/.venv/bin/python3" <<EOF
#!/bin/bash
for i in \$(seq 1 $n_regressed); do
  echo "REGRESSED edge-\$i: declared ALIVE, probe failed"
done
exit 1
EOF
    chmod +x "$origin/apps/backend-rag/.venv/bin/python3"
    : > "$origin/scripts/verify_connectome.py"

    if [[ "$with_gateway" == "yes" ]]; then
        # Fake gateway: records argv + message, exits 0 like the real contract.
        cat > "$origin/scripts/tg_notify.py" <<EOF
#!/usr/bin/env python3
import sys, pathlib
out = pathlib.Path("$root/out")
(out / "gateway_argv.txt").write_text("\n".join(sys.argv[1:]))
msg = sys.argv[-1] if len(sys.argv) > 1 else ""
(out / "gateway_msg.txt").write_text(msg)
sys.exit(0)
EOF
        chmod +x "$origin/scripts/tg_notify.py"
    fi

    git -C "$origin" init -q -b main
    git -C "$origin" -c user.email=t@t -c user.name=t add -A >/dev/null
    git -C "$origin" -c user.email=t@t -c user.name=t commit -qm base

    # --- the checkout the wrapper runs against -----------------------------
    git clone -q "$origin" "$root/work"
    git -C "$root/work" checkout -q -B main origin/main

    # Advance origin so the checkout trails it by exactly $behind commits.
    local i
    for ((i = 0; i < behind; i++)); do
        git -C "$origin" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "ahead $i"
    done
    git -C "$root/work" fetch -q origin main
    git -C "$root/work" update-ref refs/remotes/origin/main "$(git -C "$origin" rev-parse main)"

    # --- fake curl: any bare-curl path would leave this marker -------------
    cat > "$root/bin/curl" <<EOF
#!/bin/bash
echo "BARE CURL CALLED: \$*" >> "$root/out/curl_called.txt"
exit 0
EOF
    chmod +x "$root/bin/curl"

    echo "$root"
}

run_wrapper() {  # $1=world root  → stdout+stderr into out/run.log, rc into out/run.rc
    local root="$1"
    (
        cd "$root/work" || exit 2
        PATH="$root/bin:$PATH" HOME="$root/home" REPO_ROOT="$root/work" \
            bash "$root/work/scripts/verify_connectome_run.sh" > "$root/out/run.log" 2>&1
        echo $? > "$root/out/run.rc"
    )
}

msg_of() { cat "$1/out/gateway_msg.txt" 2>/dev/null || true; }

# ══════════════════════════════════════════════════ 1. FRESHNESS — guilt
CASES=$((CASES + 1))
W="$(build_world 3 2 yes)"; run_wrapper "$W"; MSG="$(msg_of "$W")"
if [[ -z "$MSG" ]]; then
    fail "freshness/guilt: the gateway was never invoked" "run.log:" "$(cat "$W/out/run.log")"
elif [[ "$MSG" != *"3 commits behind origin/main"* ]]; then
    fail "freshness/guilt: alert does not name the staleness" "got:" "$MSG"
else
    pass "freshness/guilt — a 3-behind checkout says so IN the alert"
fi
rm -rf "$W"

# ══════════════════════════════════════════════════ 2. FRESHNESS — innocence
CASES=$((CASES + 1))
W="$(build_world 0 2 yes)"; run_wrapper "$W"; MSG="$(msg_of "$W")"
if [[ -z "$MSG" ]]; then
    fail "freshness/innocence: the gateway was never invoked" "run.log:" "$(cat "$W/out/run.log")"
elif [[ "$MSG" == *"behind origin/main"* || "$MSG" == *"freshness UNKNOWN"* ]]; then
    fail "freshness/innocence: a level checkout was branded stale" "got:" "$MSG"
else
    pass "freshness/innocence — a level checkout adds no caveat"
fi
rm -rf "$W"

# ══════════════════════════════════════════════════ 3. TRUNCATION — guilt
CASES=$((CASES + 1))
W="$(build_world 0 23 yes)"; run_wrapper "$W"; MSG="$(msg_of "$W")"
if [[ "$MSG" != *"showing 10 of 23"* ]]; then
    fail "truncation/guilt: 23 regressions shown as a bare list of 10" "got:" "$MSG"
else
    pass "truncation/guilt — 23 regressions declare 'showing 10 of 23'"
fi
rm -rf "$W"

# ══════════════════════════════════════════════════ 4. TRUNCATION — innocence
CASES=$((CASES + 1))
W="$(build_world 0 3 yes)"; run_wrapper "$W"; MSG="$(msg_of "$W")"
if [[ "$MSG" == *"showing"* ]]; then
    fail "truncation/innocence: 3 regressions claimed a truncation" "got:" "$MSG"
else
    pass "truncation/innocence — 3 regressions claim no truncation"
fi
rm -rf "$W"

# ══════════════════════════════════════════════════ 5. DELIVERY — via gateway only
CASES=$((CASES + 1))
W="$(build_world 0 2 yes)"; run_wrapper "$W"
ARGV="$(cat "$W/out/gateway_argv.txt" 2>/dev/null || true)"
if [[ -f "$W/out/curl_called.txt" ]]; then
    fail "delivery: a bare curl was reached" "$(cat "$W/out/curl_called.txt")"
elif [[ "$ARGV" != *"--tier"$'\n'"p0"* ]]; then
    fail "delivery: gateway not invoked as a p0" "argv:" "$ARGV"
elif [[ "$ARGV" != *"--dedup-key"* ]]; then
    fail "delivery: no dedup key — a weekly-red guardian would repeat forever" "argv:" "$ARGV"
else
    pass "delivery — gateway as p0 with a dedup key, zero bare curl"
fi
rm -rf "$W"

# ══════════════════════════════════════════════════ 6. GATEWAY MISSING — loud
CASES=$((CASES + 1))
W="$(build_world 0 2 no)"; run_wrapper "$W"
LOG="$(cat "$W/out/run.log")"; RC="$(cat "$W/out/run.rc")"
if [[ "$LOG" != *"alert gateway is unusable"* ]]; then
    fail "missing-gateway: silent about being armed to nothing" "log:" "$LOG"
elif [[ "$LOG" != *"connectome REGRESSED on"* ]]; then
    fail "missing-gateway: the alert body was not preserved in the log" "log:" "$LOG"
elif [[ "$RC" != "1" ]]; then
    fail "missing-gateway: exit code changed" "expected 1, got $RC"
else
    pass "missing-gateway — says which half is missing, keeps body, still exits 1"
fi
rm -rf "$W"

echo
if (( FAILURES > 0 )); then
    echo "FAIL: $FAILURES of $CASES connectome-alert cases"
    exit 1
fi
echo "PASS: $CASES/$CASES connectome-alert honesty cases"
