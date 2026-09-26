---
spec_id: G4
title: Continuous monitoring — weekly orchestration health check
tier: gate
priority: P2 (post-execution observability)
effort_estimate: 30 min spec, runs autonomous via cron
status: DRAFT
basis: DS panel missing_specs 2026-05-21 "CONTINUOUS-MONITORING"
---

# G4 — Continuous monitoring

## Problem

DS panel: _"A lightweight check (cron or hook) that periodically assesses orchestration health: subagent dispatch ratios, MCP reachability, and memory file integrity over the following week."_

Plan completa fix in 1-2 settimane. Senza monitoring, regression può tornare silenziosa nelle settimane successive. G4 = sentinella autonoma.

## Context

Differenza vs G1 (inter-wave gate) e G2 (post-fix one-shot validation):

- **G1**: manual check between waves during execution (~5 min, operator-invoked)
- **G2**: one-shot validation at end of plan (~30 min, operator-invoked)
- **G4**: cron weekly, observed week-after-week (~5 min auto, sends report)

## Acceptance criteria

- [ ] `~/scripts/orchestration-health-weekly.sh` exists
- [ ] LaunchAgent `com.balizero.orch-health.weekly.plist`
- [ ] Runs every Monday 08:00 WITA
- [ ] Telegram report on completion
- [ ] Saves history `~/.claude/state/orchestration-health-history.jsonl`
- [ ] Alert (P1) if regression detected vs last week

## Implementation

### Step 1 — Create monitoring script

Path: `~/scripts/orchestration-health-weekly.sh`

```bash
#!/bin/bash
# G4 — Continuous orchestration health weekly check
# Reference: research/operations/specs/G4-continuous-monitoring.md

set -uo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
HISTORY=~/.claude/state/orchestration-health-history.jsonl
mkdir -p ~/.claude/state
SESSION_DIR=~/.claude/projects/-Users-nuzantara-Desktop-nuzantara

# === Aggregate metrics last 7 days ===
SESSIONS=$(find "$SESSION_DIR" -name "*.jsonl" -mtime -7 -type f 2>/dev/null)
SESSION_COUNT=$(echo "$SESSIONS" | grep -c . 2>/dev/null || echo 0)

if [ "$SESSION_COUNT" -eq 0 ]; then
    echo "No sessions last 7 days"
    exit 0
fi

# Tool call aggregate
TOTAL_AGENT=0
TOTAL_SKILL=0
TOTAL_BASH=0
TOTAL_MCP=0
TOTAL_LINES=0

for s in $SESSIONS; do
    LINES=$(wc -l < "$s" | tr -d ' ')
    A=$(grep -c '"name":"Agent"' "$s" 2>/dev/null || echo 0)
    K=$(grep -c '"name":"Skill"' "$s" 2>/dev/null || echo 0)
    B=$(grep -c '"name":"Bash"' "$s" 2>/dev/null || echo 0)
    M=$(grep -c '"name":"mcp__' "$s" 2>/dev/null || echo 0)
    TOTAL_LINES=$((TOTAL_LINES + LINES))
    TOTAL_AGENT=$((TOTAL_AGENT + A))
    TOTAL_SKILL=$((TOTAL_SKILL + K))
    TOTAL_BASH=$((TOTAL_BASH + B))
    TOTAL_MCP=$((TOTAL_MCP + M))
done

# === MCP reachability ===
MCP_DOWN=0
MCP_TESTS=(
    "https://nuzantara-rag.fly.dev/health"
)
for url in "${MCP_TESTS[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$url" 2>/dev/null)
    [ "$status" != "200" ] && ((MCP_DOWN++))
done

# === Memory health ===
MEMORY_MD=~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/MEMORY.md
MEMORY_SIZE=$(wc -c < "$MEMORY_MD" 2>/dev/null || echo 0)
ORPHAN=$(bash ~/.claude/scripts/alzheimer-hook.sh 2>/dev/null | grep -c "Orphaned" || echo 0)

# === Compute regression vs last week ===
PREV_AGENT=$(tail -2 "$HISTORY" 2>/dev/null | head -1 | jq -r '.agent_calls // 0' 2>/dev/null || echo 0)
REGRESSION=NO
if [ "$PREV_AGENT" -gt 0 ] && [ "$TOTAL_AGENT" -lt $((PREV_AGENT / 2)) ]; then
    REGRESSION=YES
fi

# === Output ===
RESULT=$(cat << JSON
{
    "timestamp": "$TIMESTAMP",
    "sessions_last_7d": $SESSION_COUNT,
    "total_lines": $TOTAL_LINES,
    "agent_calls": $TOTAL_AGENT,
    "skill_calls": $TOTAL_SKILL,
    "bash_calls": $TOTAL_BASH,
    "mcp_calls": $TOTAL_MCP,
    "mcp_down": $MCP_DOWN,
    "memory_md_bytes": $MEMORY_SIZE,
    "orphan_count": $ORPHAN,
    "regression_vs_last_week": "$REGRESSION"
}
JSON
)

# Append to history
echo "$RESULT" | tr -d '\n' >> "$HISTORY"
echo "" >> "$HISTORY"

echo "=== G4 orchestration health $(date) ==="
echo "$RESULT" | jq .

# === Alert ===
if [ "$REGRESSION" = "YES" ] || [ "$MCP_DOWN" -gt 0 ] || [ "$ORPHAN" -gt 5 ]; then
    SEVERITY="🚨 P1 alert"
else
    SEVERITY="✅ weekly OK"
fi

# Gemini B2 fix: source token from secure file, NOT plist EnvironmentVariables
# Cicatrix scar 2026-04-29 plist hardening — never inject secrets into world-readable plist
SECRET_FILE=~/.config/nuzantara/.env.secret
if [ -f "$SECRET_FILE" ]; then
    # shellcheck disable=SC1090
    source "$SECRET_FILE"
fi

if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    MSG=$(cat << TG
$SEVERITY G4 Weekly $TIMESTAMP
Sessions 7d: $SESSION_COUNT ($TOTAL_LINES lines)
Agent: $TOTAL_AGENT (vs $PREV_AGENT last week)
Skill: $TOTAL_SKILL
MCP: $TOTAL_MCP calls, $MCP_DOWN down
Orphan: $ORPHAN
Regression: $REGRESSION
TG
)
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
        -d "text=$MSG" > /dev/null
fi

[ "$REGRESSION" = "YES" ] && exit 1 || exit 0
```

### Step 2 — Create secure secret file (Gemini B2 fix)

**Cicatrix scar 2026-04-29 compliance**: never inject secrets into plist EnvironmentVariables. Use sourced .env file with 0400 mode.

```bash
mkdir -p ~/.config/nuzantara
chmod 700 ~/.config/nuzantara

# Create secret file (interactive — DO NOT paste token in transcript)
# Use security CLI to retrieve from Keychain instead:
TELEGRAM_TOKEN=$(security find-generic-password -s "TELEGRAM_BOT_TOKEN" -w 2>/dev/null)

if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "TELEGRAM_BOT_TOKEN not in Keychain. Add it first:"
    echo "  security add-generic-password -a \$USER -s 'TELEGRAM_BOT_TOKEN' -w"
    echo "(prompts for value, never echoes to terminal)"
    exit 1
fi

# Write env file 0400 mode (read-only for user, never world-readable)
umask 077
cat > ~/.config/nuzantara/.env.secret << EOF
export TELEGRAM_BOT_TOKEN="$(security find-generic-password -s 'TELEGRAM_BOT_TOKEN' -w)"
export TELEGRAM_OWNER_CHAT_ID="1125336968"
EOF
chmod 0400 ~/.config/nuzantara/.env.secret

ls -la ~/.config/nuzantara/.env.secret
# Expected: -r-------- (0400)
```

### Step 3 — Make executable + LaunchAgent (no secrets in plist)

```bash
chmod +x ~/scripts/orchestration-health-weekly.sh

# LaunchAgent plist — NO secrets, only PATH
cat > ~/Library/LaunchAgents/com.balizero.orch-health.weekly.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.balizero.orch-health.weekly</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/nuzantara/scripts/orchestration-health-weekly.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>8</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>RunAtLoad</key><false/>
    <key>StandardOutPath</key><string>/Users/nuzantara/logs/orch-health.log</string>
    <key>StandardErrorPath</key><string>/Users/nuzantara/logs/orch-health.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# Plist mode 0444 (cicatrix 2026-04-29 standard)
chmod 0444 ~/Library/LaunchAgents/com.balizero.orch-health.weekly.plist

# Verify plist does NOT contain any token
grep -i "token\|password\|secret\|api_key" ~/Library/LaunchAgents/com.balizero.orch-health.weekly.plist
# Expected: NO matches (only PATH env)

# Then load:
# launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.orch-health.weekly.plist
```

### Step 3 — Test first run manually

```bash
~/scripts/orchestration-health-weekly.sh
# Expected: JSON output, telegram message
cat ~/.claude/state/orchestration-health-history.jsonl
# Expected: 1 line JSON
```

## Verification

### Test 1 — Script executable

```bash
ls -la ~/scripts/orchestration-health-weekly.sh
# Expected: -rwxr-xr-x
```

### Test 2 — LaunchAgent loaded

```bash
launchctl list | grep orch-health
# Expected: line present after bootstrap
```

### Test 3 — Manual invoke produces report

```bash
~/scripts/orchestration-health-weekly.sh
cat ~/.claude/state/orchestration-health-history.jsonl | tail -1 | jq .
# Expected: valid JSON object
```

### Test 4 — Regression detection

Simulate: add fake entry to history with high agent_calls, then run script. Expected: REGRESSION=YES + alert.

## Rollback

```bash
launchctl bootout gui/$(id -u)/com.balizero.orch-health.weekly 2>/dev/null
rm ~/Library/LaunchAgents/com.balizero.orch-health.weekly.plist
rm ~/scripts/orchestration-health-weekly.sh
# history file preserved for archeology
```

## Open questions

1. **Cron interval**: weekly Monday 8am OK? Or daily? Default = weekly (week-over-week comparison meaningful).
2. **Regression threshold**: agent_calls drop to <50% of last week = alert. Too sensitive? Adjust empirical.
3. **Multi-machine**: Pro-only or also Mini-Pro2? Default = Pro only (Mini = workhorse, no interactive session).
4. **Alert escalation**: P1 alert on regression → just Telegram? Or also email Antonello + escalate to Adit? Default = Telegram only.
5. **Auto-rollback trigger**: regression detected → auto-invoke G3? Default = NO, manual decision (G3 destructive).

## Estimated breakdown

| Step              | Tempo                              |
| ----------------- | ---------------------------------- |
| Spec script       | 20 min                             |
| LaunchAgent plist | 5 min                              |
| Test manual run   | 5 min                              |
| **Total**         | **30 min** + 5 min auto-run weekly |
