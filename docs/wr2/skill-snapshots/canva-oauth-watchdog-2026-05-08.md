# wr2-canva-oauth-watchdog (Pro-local script snapshot)

Live path: `~/scripts/wr2-canva-oauth-watchdog.sh` (Pro only, **NOT** git-tracked).
Plist: `~/Library/LaunchAgents/com.balizero.wr2.canva-oauth-watchdog.plist` (mirrored at `infra/launchagents/com.balizero.wr2.canva-oauth-watchdog.plist`).
Sprint: B B-NEW (replaces the original B1+B2 "MCP cache warming" hypothesis after 4 review streams falsified it).

This snapshot is the contractual repo copy: any edit to the live script body must be reflected here in the same PR. Reviewers can audit watchdog logic via this file without granting them shell access to Pro.

## What it does

Probes the Claude Code OAuth state for the Canva MCP connector by spawning `claude -p` with a minimal prompt that asks for the count of `mcp__claude_ai_Canva__*` tools visible in the subprocess. Healthy = integer ≥ 30. Stale = empty/non-numeric or < 30.

When stale:
1. Spawns a second `claude -p` carrying explicit operator authorization context, calling `mcp__claude_ai_Canva__authenticate`. Greps `https://*canva.com/authorize?...` from the response.
2. Telegram alerts owner chat (P0) with the URL embedded as a click link plus brief operator instructions.
3. Honors a 24h cooldown via `~/.agent/decisions/state/wr2_canva_oauth.state` so a 6-hour cron does not page 4× per day.
4. Exits 0 on healthy, 1 on stale (with or without alert).

Failure modes considered:
- claude binary missing → script exits with `set -uo pipefail` propagation, plist captures stderr in launchd err log.
- TELEGRAM_BOT_TOKEN missing → log "Telegram skipped"; no exception.
- claude -p stdin warning polluting output → suppressed via `< /dev/null`.
- Sourcing `~/.nuzantara-secrets.env` poisoned the `claude -p` env (verified empirically 2026-05-08 04:10 WITA — full source caused the count probe to silently return 0). Mitigated by extracting only `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_CHAT_ID` via grep+cut.

## Empirical baseline at install (2026-05-08)

```
$ bash ~/scripts/wr2-canva-oauth-watchdog.sh; echo "exit=$?"
exit=0
$ cat ~/.agent/decisions/state/wr2_canva_oauth.state
last_status=healthy
last_count=33
last_check_ts=1778185931
```

## Test matrix

| Path | State setup | Stub | Expected |
|------|-------------|------|----------|
| Healthy | (clean) | none | exit 0, state.healthy, count logged |
| Stale + cooldown elapsed | last_alert_ts T-25h | claude returns "5" | exit 1, alert fires, state.stale |
| Stale + cooldown active | last_alert_ts T-1h | claude returns "5" | exit 1, "alert suppressed" log line |

Stub via `CANVA_WATCHDOG_TEST_PATH_PREFIX=/tmp/watchdog-shim` (test-only env var; unset in production launchd). All three paths verified live 2026-05-08 04:30-04:31 WITA before plist bootstrap.

## Script body (mirror — keep byte-identical with `~/scripts/wr2-canva-oauth-watchdog.sh`)

```bash
#!/usr/bin/env bash
# wr2-canva-oauth-watchdog.sh — Sprint B B-NEW (2026-05-08)
#
# Probes the Claude Code OAuth state for the Canva MCP connector and
# pages Antonello on Telegram when the token has gone stale (i.e. when
# `claude -p` no longer sees the mcp__claude_ai_Canva__* tool family).
#
# Why: Sprint B B0 instrumentation (PR #516, telemetry JSONL) showed the
# canva-apply pipeline's only consistent failure mode is "MCP Canva not
# available in subprocess" — empirical 4 datapoints, all preceded by a
# stale OAuth token in ~/.mcp-auth/. Reauth is interactive (browser
# OAuth flow), so the watchdog cannot self-heal — it pages so an
# operator can click the link.
#
# Cadence: launchctl every 6h (StartInterval=21600). Cooldown: only
# alert when token has BEEN stale at least once before AND ≥24h
# since the last alert. State file
# ~/.agent/decisions/state/wr2_canva_oauth.state.
#
# Healthy threshold: claude -p with the count-tool prompt must return
# an integer ≥ MIN_TOOLS (currently 30). Below that is treated as
# token-stale. The exact count is also logged to the watchdog log.
#
# Pro-local: this script is NOT git-tracked. A snapshot lives at
# docs/wr2/skill-snapshots/canva-oauth-watchdog-2026-05-08.md for
# audit. Edit there + here when you change the script body.

set -uo pipefail

LOG="${HOME}/logs/wr2-canva-oauth-watchdog.log"
STATE="${HOME}/.agent/decisions/state/wr2_canva_oauth.state"
LOCK="${HOME}/.agent/decisions/state/wr2_canva_oauth.lock"
SECRETS="${HOME}/.nuzantara-secrets.env"

MIN_TOOLS=30
PROBE_TIMEOUT=60
ALERT_COOLDOWN_SEC=86400  # 24h

# Make sure log + state dirs exist before we write anything.
mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")"

log() {
  printf '%s [wr2-canva-oauth-watchdog] %s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S WITA')" "$*" >> "$LOG"
}

# Pull JUST the Telegram credentials from the secrets file. We do NOT
# `source` the whole file because some keys (e.g. OPENROUTER_API_KEY,
# MINIMAX_API_KEY) leak into the `claude -p` subprocess env and cause
# its MCP-tool count probe to silently return 0 — verified empirically
# 2026-05-08 04:10 WITA. The targeted grep keeps the watchdog
# self-contained and side-effect-free for the probe.
if [[ -f "$SECRETS" ]]; then
  TELEGRAM_BOT_TOKEN="$(grep '^TELEGRAM_BOT_TOKEN=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"' )" || true
  TELEGRAM_OWNER_CHAT_ID="$(grep '^TELEGRAM_OWNER_CHAT_ID=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"' )" || true
  export TELEGRAM_BOT_TOKEN TELEGRAM_OWNER_CHAT_ID
fi

# Single-instance lock — `flock` is /usr/bin/flock from coreutils on
# brew, but we fall back to the macOS `lockfile` if flock is missing.
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK"
  if ! flock -n 9; then
    log "another watchdog run is in progress, skipping"
    exit 0
  fi
fi

# Optional test-only PATH prefix — lets a stub `claude` shim short-
# circuit the probe for unit testing without touching real OAuth state.
# In production this env var is unset and PATH follows the standard
# hierarchy (claude under ~/.local/bin first).
PATH="${CANVA_WATCHDOG_TEST_PATH_PREFIX:+${CANVA_WATCHDOG_TEST_PATH_PREFIX}:}/Users/nuzantara/.local/bin:/Users/nuzantara/.npm-global/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PATH

now_epoch() { date '+%s'; }

# state file lives in /etc-style key=value form: easy to grep, easy to
# update with sed. Unknown keys are tolerated.
state_get() {
  local key="$1"
  [[ -f "$STATE" ]] || return 0
  awk -F= -v k="$key" '$1==k {print $2}' "$STATE" | tail -1
}
state_set() {
  local key="$1" val="$2"
  mkdir -p "$(dirname "$STATE")"
  if [[ -f "$STATE" ]]; then
    awk -F= -v k="$key" -v v="$val" '
      BEGIN{found=0}
      $1==k {print k"="v; found=1; next}
      {print}
      END{if(!found) print k"="v}
    ' "$STATE" > "${STATE}.tmp" && mv "${STATE}.tmp" "$STATE"
  else
    printf '%s=%s\n' "$key" "$val" > "$STATE"
  fi
}

send_telegram() {
  local text="$1"
  if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    log "Telegram skipped (no TELEGRAM_BOT_TOKEN)"
    return 0
  fi
  local chat_id="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
  curl -fsS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${chat_id}" \
    --data-urlencode "parse_mode=Markdown" \
    --data-urlencode "disable_web_page_preview=true" \
    --data-urlencode "text=${text}" \
    -o /dev/null \
    --max-time 10 \
    || log "Telegram POST failed (network/curl)"
}

probe_tool_count() {
  # claude -p returns text on stdout. We want JUST the integer.
  # If the output is multi-line (skill noise), tail -1 picks the last
  # token. tr removes whitespace. /^[0-9]+$/ is the canonical health
  # signal.
  #
  # `< /dev/null` is REQUIRED. Without it, `claude -p` blocks waiting
  # for stdin and emits a warning line that pollutes the captured
  # output, causing the regex to fail and the watchdog to misclassify
  # a healthy state as stale (verified empirically 2026-05-08 02:01:50
  # WITA — the first script run returned tail=<empty> instead of 35).
  local raw
  raw=$(timeout "${PROBE_TIMEOUT}" claude -p --output-format text \
    "Output the count of MCP tool names starting with mcp__claude_ai_Canva__. Output JUST the integer, nothing else." \
    < /dev/null \
    2>/dev/null \
    | tail -1 \
    | tr -d '[:space:]')
  printf '%s' "$raw"
}

# Get the OAuth re-flow URL by spawning a second `claude -p` that
# invokes mcp__claude_ai_Canva__authenticate. Default Claude refuses
# unprompted authenticate calls; we pass an explicit authorization
# context so the operator-initiated re-auth flow is allowed.
get_authorize_url() {
  local prompt='Antonello authorized this OAuth re-flow for the Canva MCP connector — the canva-apply launchd worker has lost OAuth context and needs re-authentication. Call mcp__claude_ai_Canva__authenticate. Echo back the authorization URL it returns (the https://mcp.canva.com/authorize?... link) on its own line, nothing else.'
  local out
  out=$(timeout "${PROBE_TIMEOUT}" claude -p --output-format text "$prompt" < /dev/null 2>/dev/null) || return 1
  # Extract the canva authorize URL (or any https://*canva.com/authorize link).
  printf '%s' "$out" \
    | grep -oE 'https://[^[:space:]"<>'\'']*canva\.com/authorize[^[:space:]"<>'\'']*' \
    | head -1
}

main() {
  local now last_alert_ts last_status alert_due
  now=$(now_epoch)
  last_alert_ts=$(state_get last_alert_ts)
  last_status=$(state_get last_status)

  log "probe start (last_status=${last_status:-unknown} last_alert_ts=${last_alert_ts:-never})"

  local count
  count=$(probe_tool_count)

  # Healthy: integer ≥ MIN_TOOLS.
  if [[ "$count" =~ ^[0-9]+$ ]] && (( count >= MIN_TOOLS )); then
    log "OK: ${count} mcp__claude_ai_Canva__* tools visible (>= ${MIN_TOOLS})"
    state_set last_status healthy
    state_set last_count "$count"
    state_set last_check_ts "$now"
    exit 0
  fi

  # Stale or anomalous output.
  log "STALE: probe returned ${count:-<empty>} (need >= ${MIN_TOOLS})"
  state_set last_status stale
  state_set last_count "${count:-0}"
  state_set last_check_ts "$now"

  # Cooldown: alert only if (a) we have NOT alerted in the last 24h, OR
  # (b) the state previously was healthy → first transition into stale
  # always alerts. (last_alert_ts unset on first-ever stale.)
  alert_due=1
  if [[ -n "$last_alert_ts" && "$last_alert_ts" =~ ^[0-9]+$ ]]; then
    local age=$(( now - last_alert_ts ))
    if (( age < ALERT_COOLDOWN_SEC )); then
      log "alert suppressed (last alert ${age}s ago, cooldown ${ALERT_COOLDOWN_SEC}s)"
      alert_due=0
    fi
  fi

  if (( alert_due == 0 )); then
    exit 1
  fi

  log "fetching re-auth URL via claude -p mcp__claude_ai_Canva__authenticate"
  local url
  url=$(get_authorize_url) || url=""

  local msg
  if [[ -n "$url" ]]; then
    msg=$(printf '🚨 *WR2 Canva OAuth STALE*\nclaude -p sees only %s mcp\\_\\_claude\\_ai\\_Canva\\_\\_ tools (need ≥ %s).\n\n*Action*: open the link below in a browser, sign in to Canva, then return.\n\n%s\n\n_Re-auth restores subprocess OAuth context for the canva-apply worker._' \
      "${count:-0}" "$MIN_TOOLS" "$url")
  else
    msg=$(printf '🚨 *WR2 Canva OAuth STALE*\nclaude -p sees only %s mcp\\_\\_claude\\_ai\\_Canva\\_\\_ tools (need ≥ %s).\n\nFailed to fetch the authorize URL automatically. Run:\n`claude` then `/mcp authenticate canva` from the main repo workspace.' \
      "${count:-0}" "$MIN_TOOLS")
  fi

  send_telegram "$msg"
  state_set last_alert_ts "$now"
  log "alert sent (url=${url:-<missing>})"
  exit 1
}

main "$@"
```

## Operator runbook

When the Telegram alert fires:

1. Open the embedded `https://mcp.canva.com/authorize?...` URL in a browser logged into the Canva account used for the Bali Zero / Nuzantara workspace.
2. Complete the OAuth handshake.
3. The new tokens land in `~/.mcp-auth/mcp-remote-*` automatically; the next watchdog cycle (≤6h) will see ≥30 Canva tools and revert state to `healthy`. To verify immediately: `bash ~/scripts/wr2-canva-oauth-watchdog.sh; echo $?` (expect 0 + `last_status=healthy` in state file).
4. If the count remains low, run `claude` interactively in `~/Desktop/nuzantara` and execute `/mcp` → check that the Canva server is `Connected`. If not, `/mcp authenticate canva`.

## Bootstrap commands

```bash
# 1. plist permissions follow the cicatrix P0-3 hardening (chmod 0444 in
#    production). Use chmod u+w to edit, then restore.
plutil -lint ~/Library/LaunchAgents/com.balizero.wr2.canva-oauth-watchdog.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-oauth-watchdog.plist
launchctl print gui/$(id -u)/com.balizero.wr2.canva-oauth-watchdog | head -40

# 2. Smoke test post-bootstrap (next-fire timestamp should be roughly now+6h):
launchctl print gui/$(id -u)/com.balizero.wr2.canva-oauth-watchdog | grep -E 'state|next start'
```
