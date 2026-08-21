#!/bin/bash
# test_ollama_model_ready.sh — guilt+innocence+mutation corpus for _ollama_model_ready(),
# the model-presence precheck added 2026-08-20 to claude-cascade.sh and
# regulatory-watcher-run.sh's Ollama tier (team-lead mandate: "il probe della cascata
# deve verificare il MODELLO, non il binario").
#
# Extracts the function body from BOTH wrapper files (rather than sourcing the whole
# script, which would run real cascade/watcher logic) and drives it against a fake
# local /api/tags HTTP server, so no real Ollama daemon or network call is required.
#
# Also asserts the two copies are byte-identical: the function is intentionally
# DUPLICATED (not factored into a shared lib) to keep this fix's surface small, which
# means nothing stops the two copies from drifting apart under a future edit to only
# one of them — this test is the tripwire for that specific risk.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CASCADE_SH="$REPO_ROOT/infra/launchagents/wrappers/claude-cascade.sh"
WATCHER_SH="$REPO_ROOT/infra/launchagents/wrappers/regulatory-watcher-run.sh"

PASS=0
FAIL=0
SERVER_PID=""
TMPDIR="$(mktemp -d)"
trap 'kill "$SERVER_PID" 2>/dev/null; rm -rf "$TMPDIR"' EXIT

extract_fn() {
    # Pulls the _ollama_model_ready() function body out of a wrapper file by
    # matching from its def line to the first line that is exactly "}".
    awk '/^_ollama_model_ready\(\) \{/{flag=1} flag{print} flag && /^}$/{exit}' "$1"
}

FN_CASCADE="$(extract_fn "$CASCADE_SH")"
FN_WATCHER="$(extract_fn "$WATCHER_SH")"

if [ -z "$FN_CASCADE" ]; then
    echo "FAIL: could not extract _ollama_model_ready() from claude-cascade.sh — did the def line change?"
    exit 1
fi

# --- drift tripwire: both copies must be byte-identical ---
if [ "$FN_CASCADE" = "$FN_WATCHER" ]; then
    echo "PASS: claude-cascade.sh and regulatory-watcher-run.sh copies are byte-identical"
    PASS=$((PASS + 1))
else
    echo "FAIL: the two _ollama_model_ready() copies have DRIFTED — fix one, fix both"
    diff <(echo "$FN_CASCADE") <(echo "$FN_WATCHER")
    FAIL=$((FAIL + 1))
fi

# Load the (real) function under test into this shell.
eval "$FN_CASCADE"

start_fake_ollama() {
    # $1 = python inline script body producing the /api/tags response
    # Sets NEXT_PORT (bumped each call): a just-closed port can sit in TIME_WAIT
    # and refuse an immediate rebind, so each server gets a fresh port rather
    # than reusing the last one.
    local port=$NEXT_PORT
    local handler=$1
    NEXT_PORT=$((NEXT_PORT + 1))
    python3 -c "
import http.server, socketserver, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        $handler
    def log_message(self, *a): pass
class Srv(socketserver.TCPServer):
    allow_reuse_address = True
with Srv(('127.0.0.1', $port), H) as httpd:
    httpd.serve_forever()
" &
    SERVER_PID=$!
    CURRENT_PORT=$port
    # wait for the port to accept connections (bounded, no fixed sleep race)
    for _ in $(seq 1 30); do
        curl -sf -m 1 "http://127.0.0.1:$port/api/tags" >/dev/null 2>&1 && return 0
        sleep 0.1
    done
    return 1
}

stop_fake_ollama() {
    kill "$SERVER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
    SERVER_PID=""
}

check() {
    local desc="$1" expect_rc="$2"; shift 2
    local out rc
    out="$("$@" 2>&1)"
    rc=$?
    if [ "$rc" -eq "$expect_rc" ]; then
        echo "PASS: $desc (rc=$rc)"
        PASS=$((PASS + 1))
    else
        echo "FAIL: $desc — expected rc=$expect_rc got rc=$rc; output: $out"
        FAIL=$((FAIL + 1))
    fi
}

NEXT_PORT=18765
CURRENT_PORT=""

# --- Innocence 1: model present, exact match ---
start_fake_ollama '
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{\"models\":[{\"name\":\"qwen3.5:9b\"},{\"name\":\"bge-m3:latest\"}]}")
'
OLLAMA_API_BASE="http://127.0.0.1:$CURRENT_PORT" check "innocence: model present in tags -> ready" 0 _ollama_model_ready "qwen3.5:9b"

# --- Innocence 2: a DIFFERENT present model, still exact-matches (no prefix laxity) ---
OLLAMA_API_BASE="http://127.0.0.1:$CURRENT_PORT" check "innocence: second present model also ready" 0 _ollama_model_ready "bge-m3:latest"
stop_fake_ollama

# --- Guilt 1: daemon reachable, but the requested model is NOT in the tags list ---
start_fake_ollama '
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{\"models\":[{\"name\":\"bge-m3:latest\"}]}")
'
out="$(OLLAMA_API_BASE="http://127.0.0.1:$CURRENT_PORT" _ollama_model_ready "qwen3.5:9b" 2>&1)"; rc=$?
if [ "$rc" -eq 1 ] && printf '%s' "$out" | grep -q "not installed"; then
    echo "PASS: guilt: missing model reported as 'not installed', rc=1"
    PASS=$((PASS + 1))
else
    echo "FAIL: guilt: missing-model case — rc=$rc output=$out"
    FAIL=$((FAIL + 1))
fi
stop_fake_ollama

# --- Guilt 2: daemon unreachable (nothing listening on this fresh, never-bound port) ---
UNBOUND_PORT=$NEXT_PORT
NEXT_PORT=$((NEXT_PORT + 1))
out="$(OLLAMA_API_BASE="http://127.0.0.1:$UNBOUND_PORT" _ollama_model_ready "qwen3.5:9b" 2>&1)"; rc=$?
if [ "$rc" -eq 1 ] && printf '%s' "$out" | grep -q "unreachable"; then
    echo "PASS: guilt: unreachable daemon reported distinctly, rc=1"
    PASS=$((PASS + 1))
else
    echo "FAIL: guilt: unreachable-daemon case — rc=$rc output=$out"
    FAIL=$((FAIL + 1))
fi

# --- Guilt 3: daemon reachable but returns malformed JSON (must not crash, must fail closed) ---
start_fake_ollama '
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"not json at all")
'
OLLAMA_API_BASE="http://127.0.0.1:$CURRENT_PORT" check "guilt: malformed JSON fails closed (never a false-ready)" 1 _ollama_model_ready "qwen3.5:9b"
stop_fake_ollama

# --- Mutation check: prove the corpus is not vacuous by running Guilt 1's case
# through a deliberately-broken mutant (name check removed -> always "ready" once
# reachable) and confirming it now WRONGLY passes where the real function correctly
# fails. If this block ever reports the mutant "still fails", the corpus is not
# actually discriminating on model presence.
_ollama_model_ready_MUTANT() {
    local model="$1"
    local base="${OLLAMA_API_BASE:-http://127.0.0.1:11434}"
    local tags
    tags="$(curl -sf -m 5 "${base}/api/tags" 2>/dev/null)"
    [ -z "$tags" ] && return 1
    return 0   # <-- mutation: model-name check deleted
}
start_fake_ollama '
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{\"models\":[{\"name\":\"bge-m3:latest\"}]}")
'
if OLLAMA_API_BASE="http://127.0.0.1:$CURRENT_PORT" _ollama_model_ready_MUTANT "qwen3.5:9b"; then
    echo "PASS: mutation check — broken mutant (no name check) wrongly reports ready, proving Guilt-1 is a real discriminator"
    PASS=$((PASS + 1))
else
    echo "FAIL: mutation check — mutant should have wrongly passed but didn't; Guilt-1 may be vacuous"
    FAIL=$((FAIL + 1))
fi
stop_fake_ollama

# --- Dead self-heal label regression pin (scripts/ollama_cron_window.sh) ---
# `homebrew.mxcl.ollama` was retired 2026-08-18 on Pro in favor of the capped
# single-manager `com.nuzantara.ollama` (see ollama-single-manager.sh genesis
# comment); the cron-window script's recovery kickstart had kept targeting the
# dead label, silently no-op'ing under `2>/dev/null || true` every time it fired
# (it never has, since the primary check has stayed green since the label moved
# — "armed to nothing", not yet observed failing).
CRON_WINDOW_SH="$REPO_ROOT/scripts/ollama_cron_window.sh"
# Only the live `launchctl kickstart` line matters — the retired label is
# expected to still appear in the explanatory comment above it (why the fix
# exists), so this checks the ACTUAL kickstart invocation, not the whole file.
if grep "launchctl kickstart" "$CRON_WINDOW_SH" 2>/dev/null | grep -q "homebrew\.mxcl\.ollama"; then
    echo "FAIL: ollama_cron_window.sh's kickstart line still targets the retired label homebrew.mxcl.ollama"
    FAIL=$((FAIL + 1))
else
    echo "PASS: ollama_cron_window.sh's kickstart line no longer targets the retired label"
    PASS=$((PASS + 1))
fi
if grep -q 'OLLAMA_LAUNCHD_LABEL:-com\.nuzantara\.ollama' "$CRON_WINDOW_SH" 2>/dev/null; then
    echo "PASS: ollama_cron_window.sh kickstarts the live label com.nuzantara.ollama by default"
    PASS=$((PASS + 1))
else
    echo "FAIL: ollama_cron_window.sh does not default to the live label com.nuzantara.ollama"
    FAIL=$((FAIL + 1))
fi

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
