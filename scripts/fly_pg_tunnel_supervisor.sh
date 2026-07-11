#!/usr/bin/env bash
# fly_pg_tunnel_supervisor.sh — keep the Fly Postgres proxy alive "for ever" on M5.
#
# WHY THIS EXISTS (superscar #8 — network flap / proxy fragility):
#   The `fly proxy 15432:5432 -a nuzantara-postgres` wireguard tunnel from M5 to Fly
#   `sin` is documented as chronically flaky (wr3_supervisor.py:79 — "~102 reconnects in
#   a 495-line log"; nuz_db_refresh.sh — "drops mid-dump"). A bare `fly proxy &` therefore
#   dies silently and the postgres-nuzantara MCP starts failing with -32603 (tunnel down).
#
# THE FIX (keep-alive supervisor, NOT a bare proxy):
#   A real blocking loop that (1) (re)spawns the proxy, (2) waits for :15432 to LISTEN,
#   (3) heartbeats `SELECT 1` over the tunnel every HEARTBEAT_SEC, and (4) on any failure
#   kills the proxy and respawns it with capped back-off. This is a BLOCKING loop on
#   purpose so the LaunchAgent can use KeepAlive without a restart-storm (superscar #7).
#
# Used by: .mcp.json postgres-nuzantara (localhost:15432, readonly) + every script that
#   expects `fly proxy 15432` (wr2_smoke_test.py, probes/wr2_e2e_probe.py, start-cost-dashboard.sh).
#
# Install: bash infra/launchagents/install_fly_pg_tunnel.sh
# Kill switch: FLY_PG_TUNNEL_ENABLED=false in the LaunchAgent env (graceful no-op exit 0).

set -uo pipefail

# ── Config (override via env / LaunchAgent) ─────────────────────────────────
FLY_PG_TUNNEL_ENABLED="${FLY_PG_TUNNEL_ENABLED:-true}"
PROXY_PORT="${PROXY_PORT:-15432}"
FLY_PG_APP="${FLY_PG_APP:-nuzantara-postgres}"
FLY_BIN="${FLY_BIN:-/opt/homebrew/bin/fly}"          # REAL binary — NOT the ssh-wrapper shell fn
PSQL_BIN="${PSQL_BIN:-/opt/homebrew/opt/postgresql@17/bin/psql}"
RO_DB="${RO_DB:-nuzantara_rag}"
RO_ROLE="${RO_ROLE:-nuzantara_readonly}"
KEYCHAIN_SVC="${KEYCHAIN_SVC:-nuzantara-postgres-readonly}"
HEARTBEAT_SEC="${HEARTBEAT_SEC:-30}"                 # SELECT 1 cadence over the tunnel
HANDSHAKE_WAIT="${HANDSHAKE_WAIT:-25}"               # seconds to wait for :PORT to LISTEN
POST_SPAWN_GRACE="${POST_SPAWN_GRACE:-3}"            # settle time after LISTEN before first heartbeat
HEARTBEAT_RETRIES="${HEARTBEAT_RETRIES:-2}"          # consecutive SELECT 1 misses before recycling
BACKOFF_MIN="${BACKOFF_MIN:-2}"                      # respawn back-off floor (s)
BACKOFF_MAX="${BACKOFF_MAX:-60}"                     # respawn back-off ceiling (s)
WG_RESET_AFTER="${WG_RESET_AFTER:-2}"                # proxy recycles in a row before `fly wg reset`
WG_ORG="${WG_ORG:-personal}"                         # fly org whose wireguard peer to refresh
WG_RESET_COOLDOWN="${WG_RESET_COOLDOWN:-300}"        # min seconds between wg resets (avoid thrash)
LOG_FILE="${LOG_FILE:-$HOME/.fly/logs/pg-tunnel-supervisor.log}"

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

log() { printf '%s [pg-tunnel] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" | tee -a "$LOG_FILE" >&2; }

# ── Kill switch ─────────────────────────────────────────────────────────────
if [ "$FLY_PG_TUNNEL_ENABLED" != "true" ]; then
  log "FLY_PG_TUNNEL_ENABLED=$FLY_PG_TUNNEL_ENABLED → disabled, graceful exit 0"
  exit 0
fi

# ── Auth: export FLY_ACCESS_TOKEN from config.yml ────────────────────────────
# WHY (scar 2026-06-25): in the LaunchAgent env `fly auth whoami` does NOT pick up the
# token from ~/.fly/config.yml (no FLY_ACCESS_TOKEN exported, config-dir resolution differs
# from an interactive shell) → preflight fails → exit 0 → KeepAlive storm-restarts forever
# (1401 runs observed) even though the config token is perfectly valid. Empirically verified:
# `FLY_ACCESS_TOKEN=<config-token> fly auth whoami` → zero@balizero.com. So we hoist the token
# from the config into the env, which every `fly` subcommand (whoami/proxy/wg reset) honours.
FLY_CONFIG_FILE="${FLY_CONFIG_FILE:-$HOME/.fly/config.yml}"
if [ -z "${FLY_ACCESS_TOKEN:-}" ] && [ -r "$FLY_CONFIG_FILE" ]; then
  # config.yml line:  access_token: "<token>"   (quoted or bare)
  _tok=$(sed -n 's/^[[:space:]]*access_token:[[:space:]]*//p' "$FLY_CONFIG_FILE" | head -1 \
          | sed 's/^["'"'"']//; s/["'"'"']$//')
  if [ -n "$_tok" ]; then export FLY_ACCESS_TOKEN="$_tok"; log "exported FLY_ACCESS_TOKEN from $FLY_CONFIG_FILE (${#_tok} chars)"; fi
fi

# ── Preflight (fail fast, but exit 0 so LaunchAgent doesn't storm-restart) ───
if [ ! -x "$FLY_BIN" ]; then log "FATAL: fly binary not executable at $FLY_BIN"; sleep 30; exit 0; fi
if ! "$FLY_BIN" auth whoami >/dev/null 2>&1; then
  log "FATAL: '$FLY_BIN auth whoami' failed even with FLY_ACCESS_TOKEN — token missing/expired. Run 'fly auth login' on M5. Sleeping 60s."
  sleep 60; exit 0
fi

PROXY_PID=""
LAST_WG_RESET=0   # epoch of last `fly wg reset` (cooldown gate)

# Auto-cure the ROOT CAUSE of the flakiness: a stale WireGuard peer. M5 roams (changing IP)
# which destabilizes the UDP wireguard session — measured 33% SELECT-1 success on a stale peer
# vs 100% immediately after `fly wg reset` (panel + empirical, 2026-06-15). Regenerating the peer
# is what makes this "stable for ever" rather than a proxy that fights a dead tunnel.
maybe_wg_reset() {
  local now; now=$(date +%s)
  if [ $(( now - LAST_WG_RESET )) -lt "$WG_RESET_COOLDOWN" ]; then
    log "wg reset skipped (cooldown: $(( WG_RESET_COOLDOWN - (now - LAST_WG_RESET) ))s left)"
    return 0
  fi
  log "sustained heartbeat failure → 'fly wg reset $WG_ORG' (regenerating wireguard peer)"
  "$FLY_BIN" wg reset "$WG_ORG" >>"$LOG_FILE" 2>&1 \
    && log "wg reset OK" || log "wg reset returned non-zero (continuing)"
  LAST_WG_RESET=$(date +%s)
  sleep 3
}

cleanup() {
  if [ -n "$PROXY_PID" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
    log "cleanup: killing proxy pid=$PROXY_PID"
    kill "$PROXY_PID" 2>/dev/null
    wait "$PROXY_PID" 2>/dev/null
  fi
}
trap 'cleanup; log "received TERM/INT — exiting"; exit 0' TERM INT

port_listening() { lsof -nP -iTCP:"$PROXY_PORT" -sTCP:LISTEN >/dev/null 2>&1; }

reap_orphan_proxy() {
  # A previous supervisor (or a manual `fly proxy &`) may hold the port. Reclaim it.
  local pids
  pids=$(lsof -ti tcp:"$PROXY_PORT" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    log "orphan listener on :$PROXY_PORT (pids: $pids) — reaping"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null; sleep 1
  fi
}

spawn_proxy() {
  reap_orphan_proxy
  log "spawning: $FLY_BIN proxy $PROXY_PORT:5432 -a $FLY_PG_APP"
  "$FLY_BIN" proxy "$PROXY_PORT":5432 -a "$FLY_PG_APP" >>"$LOG_FILE" 2>&1 &
  PROXY_PID=$!
  local waited=0
  while [ "$waited" -lt "$HANDSHAKE_WAIT" ]; do
    if port_listening; then
      log "proxy up (pid=$PROXY_PID) — :$PROXY_PORT LISTEN after ${waited}s"
      sleep "$POST_SPAWN_GRACE"   # let the wireguard session settle before first heartbeat
      return 0
    fi
    if ! kill -0 "$PROXY_PID" 2>/dev/null; then log "proxy pid=$PROXY_PID died during handshake"; return 1; fi
    sleep 1; waited=$((waited+1))
  done
  log "proxy did not LISTEN within ${HANDSHAKE_WAIT}s"; return 1
}

heartbeat_ok() {
  # SELECT 1 over the tunnel — proves the END-TO-END path, not just the local socket
  # (superscar #2: green ≠ working — verify the real outcome, not the PID).
  local pw
  pw=$(security find-generic-password -s "$KEYCHAIN_SVC" -a "$RO_ROLE" -w 2>/dev/null) || return 1
  [ -n "$pw" ] || return 1
  PGPASSWORD="$pw" PGCONNECT_TIMEOUT=8 "$PSQL_BIN" \
    "postgresql://${RO_ROLE}@127.0.0.1:${PROXY_PORT}/${RO_DB}?sslmode=disable" \
    -tAc "SELECT 1" >/dev/null 2>&1
}

# ── Supervisor loop (blocking — LaunchAgent KeepAlive never cycles it) ───────
log "supervisor start: port=$PROXY_PORT app=$FLY_PG_APP heartbeat=${HEARTBEAT_SEC}s"
backoff="$BACKOFF_MIN"
recycles=0   # consecutive proxy recycles (heartbeat-dead in a row) → triggers wg reset
while true; do
  if ! port_listening || { [ -n "$PROXY_PID" ] && ! kill -0 "$PROXY_PID" 2>/dev/null; }; then
    # If we've recycled repeatedly, the proxy is fine but the wireguard PEER is stale → cure it.
    if [ "$recycles" -ge "$WG_RESET_AFTER" ]; then maybe_wg_reset; recycles=0; fi
    if spawn_proxy; then backoff="$BACKOFF_MIN"; else
      log "respawn failed — back-off ${backoff}s"; cleanup; PROXY_PID=""
      sleep "$backoff"; backoff=$(( backoff*2 > BACKOFF_MAX ? BACKOFF_MAX : backoff*2 )); continue
    fi
  fi

  # Heartbeat with a small retry budget — a single missed SELECT 1 (transient flap) must
  # NOT recycle a healthy tunnel (that would be a self-inflicted restart loop).
  hb_miss=0
  while [ "$hb_miss" -le "$HEARTBEAT_RETRIES" ]; do
    if heartbeat_ok; then hb_miss=0; break; fi
    hb_miss=$((hb_miss+1))
    log "heartbeat miss $hb_miss/$HEARTBEAT_RETRIES (SELECT 1 over tunnel)"
    [ "$hb_miss" -le "$HEARTBEAT_RETRIES" ] && sleep 2
  done

  if [ "$hb_miss" -eq 0 ]; then
    backoff="$BACKOFF_MIN"; recycles=0
    sleep "$HEARTBEAT_SEC"
  else
    recycles=$((recycles+1))
    log "heartbeat failed ${hb_miss}x — recycling proxy (consecutive recycle #$recycles)"
    cleanup; PROXY_PID=""
    sleep "$backoff"; backoff=$(( backoff*2 > BACKOFF_MAX ? BACKOFF_MAX : backoff*2 ))
  fi
done
