#!/bin/bash
# install_fly_pg_tunnel.sh — idempotent installer for the Fly Postgres tunnel
# supervisor LaunchAgent (M5 only).
#
# WHY: the postgres-nuzantara MCP (.mcp.json) connects to localhost:15432, a `fly proxy`
# wireguard tunnel to Fly prod that is chronically flaky from M5 (superscar #8). Without a
# supervisor keeping it alive, the MCP fails with -32603 (tunnel down). This arms a
# KeepAlive LaunchAgent around scripts/fly_pg_tunnel_supervisor.sh — a BLOCKING loop with
# end-to-end heartbeat (SELECT 1) + capped back-off respawn, so launchd never storm-restarts
# (superscar #7) and the tunnel self-heals across network flaps "for ever".
#
# M5-ONLY: the proxy + Keychain RO secret live on M5 (Law 6 / PII boundary). The Pro has its
# own stable Fly net and does not need this. Refuses to install on any other host.
#
# WHY NOT MINI (decided 2026-07-11, PENDING-ARMS ledger ~56): Mini had 2 legacy
# pre-supervisor plists (com.nuzantara.fly-pg-tunnel{,.local}) chasing this same tunnel
# via ~/.local/bin/fly-pg-tunnel-from-config — retired (archived, not deleted) after
# confirming a THREE-layer blocker, not a "just wire it up" gap: (1) Mini's `fly` CLI has
# NO access token at all (`fly auth whoami` → "no access token available", interactive
# `fly auth login` required — operator[secret], can't be scripted); (2) even once
# authed, Mini's Keychain has no `nuzantara-postgres-readonly` entry this supervisor's
# heartbeat_ok() requires; (3) even once seeded, a headless SSH session cannot read a
# GUI-session Keychain item on macOS (the same wall that blocks direct Postgres access
# from Mini, W87 family) — so the supervisor's `security find-generic-password` call
# would still fail non-interactively. Extending the `whoami=balizero` guard to include
# Mini would arm a supervisor that heartbeats FALSE FOREVER, which is worse than the
# retired plists' honest churn. If Mini access is ever wanted: operator runs
# `fly auth login` interactively on Mini + seeds the Keychain entry via a GUI-unlocked
# session, THEN this guard can be relaxed — not before.
#
# TCC NOTE: launchd cannot exec scripts under ~/Desktop on M5 (macOS TCC → status 126
# "Operation not permitted"). The installer therefore STAGES the supervisor into ~/.fly/bin/
# (outside the protected tree) and points the LaunchAgent there. Verified 2026-06-15.
#
# Re-run after script changes: re-stages + bootout+bootstraps cleanly.
# /bin/bash 3.2-compatible.
set -uo pipefail

LABEL="com.nuzantara.fly-pg-tunnel"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO_ROOT="$HOME/nuzantara"
SRC_RUNNER="$REPO_ROOT/scripts/fly_pg_tunnel_supervisor.sh"
# TCC: launchd CANNOT execute files under ~/Desktop on M5 (macOS TCC blocks it →
# the agent crashes with status 126 "Operation not permitted"). So we STAGE a copy
# of the supervisor outside the protected tree and point the LaunchAgent there. The
# script is self-contained (absolute paths only, never reads the repo), so the staged
# copy runs identically. Re-running this installer re-stages the latest version.
STAGE_DIR="$HOME/.fly/bin"
RUNNER="$STAGE_DIR/fly_pg_tunnel_supervisor.sh"
LOG_DIR="$HOME/.fly/logs"
mkdir -p "$LOG_DIR" "$STAGE_DIR"

# ── Guard: M5 only ──────────────────────────────────────────────────────────
if [[ "$(whoami)" != "balizero" ]]; then
    echo "[install] SKIP: fly-pg-tunnel is M5-only (whoami=$(whoami), expected balizero)" >&2
    exit 0
fi

if [[ ! -f "$SRC_RUNNER" ]]; then
    echo "[install] SKIP: supervisor not found at $SRC_RUNNER" >&2
    exit 0
fi
# Stage outside ~/Desktop (TCC) so launchd can actually exec it.
cp "$SRC_RUNNER" "$RUNNER"
chmod 0755 "$RUNNER"

# ── Preflight (warn, don't block — supervisor degrades gracefully) ───────────
if ! /opt/homebrew/bin/fly auth whoami >/dev/null 2>&1; then
    echo "[install] WARN: 'fly auth whoami' failed — run 'fly auth login' on M5 or the tunnel will idle." >&2
fi
if ! security find-generic-password -s nuzantara-postgres-readonly -w >/dev/null 2>&1; then
    echo "[install] WARN: Keychain entry 'nuzantara-postgres-readonly' missing — heartbeat will fail." >&2
    echo "          Add via: RO=\$(ssh pro \"security find-generic-password -s nuzantara-postgres-readonly -w\"); \\" >&2
    echo "                   security add-generic-password -U -s nuzantara-postgres-readonly -a nuzantara_readonly -w \"\$RO\"" >&2
fi

cat > "$DEST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$RUNNER</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>FLY_PG_TUNNEL_ENABLED</key><string>true</string>
        <key>PATH</key><string>/opt/homebrew/bin:/opt/homebrew/opt/postgresql@17/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key><string>$HOME</string>
    </dict>
    <key>KeepAlive</key><true/>
    <key>RunAtLoad</key><true/>
    <key>ThrottleInterval</key><integer>10</integer>
    <key>StandardOutPath</key><string>$LOG_DIR/pg-tunnel-launchd.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/pg-tunnel-launchd.log</string>
</dict>
</plist>
PLIST
chmod 0400 "$DEST"

UID_VAL="$(id -u)"
launchctl bootout "gui/$UID_VAL" "$DEST" 2>/dev/null || true
launchctl bootstrap "gui/$UID_VAL" "$DEST"
RC=$?
if [[ $RC -eq 0 ]]; then
    echo "[install] $LABEL armed (KeepAlive supervisor → localhost:15432 → nuzantara-postgres)"
    echo "[install] verify: lsof -nP -iTCP:15432 -sTCP:LISTEN  (give it ~10s)"
    echo "[install] kill switch: set FLY_PG_TUNNEL_ENABLED=false in $DEST + bootout/bootstrap"
else
    echo "[install] ERROR: bootstrap failed rc=$RC" >&2
fi
exit $RC
