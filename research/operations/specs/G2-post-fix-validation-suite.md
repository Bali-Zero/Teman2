---
spec_id: G2
title: Post-fix validation suite — confirm orchestration regression closed
tier: gate
priority: P0 (final gate after Wave 4 / R-series complete)
effort_estimate: 60 min spec, 30 min per validation run
status: DRAFT
basis: DS panel missing_specs 2026-05-21 "POST-FIX-VALIDATION-SUITE"
---

# G2 — Post-fix validation suite

## Problem

DS panel: _"No empirical tests defined to run after each wave (or at end) to confirm that orchestration decay has been reduced."_

Plan può completare 23 spec senza che orchestration regression sia effettivamente risolta. Servono test empirici post-execution che misurino la metric originale (subagent dispatch ratio in sessione lunga).

## Context

Baseline data (from diagnosi 2026-05-21):

- Sessione 18.5K lines 2026-05-16: 61 subagent dispatches
- Sessione b2f02a45 today 2026-05-21: 0 dispatches in 7500+ lines (decay)
- Target post-fix: ≥ 30 dispatches in equivalent 7500+ line session (50% of baseline)

## Acceptance criteria

- [ ] `~/scripts/validate-orchestration-fix.sh` exists
- [ ] Runs 6 empirical tests
- [ ] Output PASS/FAIL with metrics
- [ ] Comparison vs baseline saved to memory entry
- [ ] Telegram report on completion

## 6 validation tests

### Test 1 — Subagent dispatch ratio in active session

```bash
# Run AFTER opening new Claude Code session and working 30-60 min
# Use T3.4 /dispatch-stat slash command:
SESSION_LINES=$(wc -l ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/<session>.jsonl)
AGENT_CALLS=$(grep -c '"name":"Agent"' <session>.jsonl)
TARGET=$((SESSION_LINES * 30 / 7500))  # scaled: 30 dispatches per 7500 lines
[ $AGENT_CALLS -ge $TARGET ] && echo "✅ PASS: $AGENT_CALLS dispatches (target $TARGET)"
```

Target: ≥ 30 dispatches in 7500+ lines (50% of 2026-05-16 baseline 61).

### Test 2 — Hook engagement empirical

Verify T1.1 dispatch_nudge fires when long session + no dispatch:

```bash
# Look for systemMessage injection in transcripts after threshold
grep -c "ORCHESTRATION REMINDER" ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/*.jsonl | head
# Expected: > 0 instances since hook installed
```

### Test 3 — Skills invocation count

T1.4 karpathy-discipline + T2.1 superpowers should be invoked at least 5x/week:

```bash
grep -c '"name":"Skill"' ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/*.jsonl | tail
# Expected: ≥ 5 per session week
```

### Test 4 — MCP usage diversification

Pre-fix: 100% Bash + 30% nuzantara-mcp.
Post-fix target: 50% Bash + 40% nuzantara-mcp + 10% github/vercel/postgres (T2.3/T2.4/T3.2).

```bash
TOTAL=$(grep -c '"name":' <session>.jsonl)
BASH=$(grep -c '"name":"Bash"' <session>.jsonl)
MCP=$(grep -c '"name":"mcp__' <session>.jsonl)
echo "Bash: $(echo "$BASH * 100 / $TOTAL" | bc)%"
echo "MCP: $(echo "$MCP * 100 / $TOTAL" | bc)%"
```

### Test 5 — Memory orphan count

T0.1 should have removed all orphan; alzheimer check should report 0:

```bash
bash ~/.claude/scripts/alzheimer-hook.sh | grep -c "Orphaned"
# Expected: 0
```

### Test 6 — Anti-hallucination compliance

Spot-check 5 recent sessions for hallucinated tool output:

```bash
# Manual: review 5 random sessions, check claims match tool outputs
# Programmatic proxy: count "verify" instances (T3.4 /verify slash usage)
grep -c '/verify' ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/*.jsonl | tail
# Expected: ≥ 3 /verify usage per dense session
```

## Implementation

### Step 1 — Create validation script

Path: `~/scripts/validate-orchestration-fix.sh`

```bash
#!/bin/bash
# G2 — Post-fix validation suite
# Reference: research/operations/specs/G2-post-fix-validation-suite.md

set -uo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULTS=~/.claude/state/validation-orchestration-$TIMESTAMP.json
SESSION_PATTERN=~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/*.jsonl

# Find newest session
LATEST_SESSION=$(ls -t $SESSION_PATTERN 2>/dev/null | head -1)
if [ -z "$LATEST_SESSION" ]; then
    echo "❌ No session found"
    exit 1
fi

LINES=$(wc -l < "$LATEST_SESSION" | tr -d ' ')
AGENT_CALLS=$(grep -c '"name":"Agent"' "$LATEST_SESSION" 2>/dev/null || echo 0)
SKILL_CALLS=$(grep -c '"name":"Skill"' "$LATEST_SESSION" 2>/dev/null || echo 0)
BASH_CALLS=$(grep -c '"name":"Bash"' "$LATEST_SESSION" 2>/dev/null || echo 0)
MCP_CALLS=$(grep -c '"name":"mcp__' "$LATEST_SESSION" 2>/dev/null || echo 0)
TOTAL=$(grep -c '"name":' "$LATEST_SESSION" 2>/dev/null || echo 1)

# Targets
TARGET_AGENT=$((LINES * 30 / 7500))
TARGET_SKILL=5
ORCHESTRATION_REMINDER=$(grep -c "ORCHESTRATION REMINDER" "$LATEST_SESSION" 2>/dev/null || echo 0)

# Orphan count (T0.1 verify)
ORPHAN=$(bash ~/.claude/scripts/alzheimer-hook.sh 2>/dev/null | grep -c "Orphaned" || echo 0)

PASS=0
FAIL=0

check() {
    local name="$1"
    local cond="$2"
    if [ "$cond" = "PASS" ]; then
        echo "✅ $name"
        ((PASS++))
    else
        echo "❌ $name"
        ((FAIL++))
    fi
}

echo "=== G2 Post-fix validation: $TIMESTAMP ==="
echo "Latest session: $(basename "$LATEST_SESSION") ($LINES lines)"
echo ""

# Test 1: subagent dispatch
[ "$AGENT_CALLS" -ge "$TARGET_AGENT" ] && R=PASS || R=FAIL
check "Test 1 — Subagent dispatch (${AGENT_CALLS}/${TARGET_AGENT})" "$R"

# Test 2: hook engagement
[ "$ORCHESTRATION_REMINDER" -gt 0 ] && R=PASS || R=FAIL
check "Test 2 — Hook engagement (${ORCHESTRATION_REMINDER} reminders)" "$R"

# Test 3: skills usage
[ "$SKILL_CALLS" -ge "$TARGET_SKILL" ] && R=PASS || R=FAIL
check "Test 3 — Skills invocation (${SKILL_CALLS}/${TARGET_SKILL})" "$R"

# Test 4: MCP usage diversification
MCP_PCT=$((MCP_CALLS * 100 / TOTAL))
[ "$MCP_PCT" -ge 30 ] && R=PASS || R=FAIL
check "Test 4 — MCP usage ratio (${MCP_PCT}% >= 30%)" "$R"

# Test 5: memory orphan
[ "$ORPHAN" -eq 0 ] && R=PASS || R=FAIL
check "Test 5 — Memory orphan (${ORPHAN}/0)" "$R"

# Test 6: anti-hallucination /verify usage
VERIFY=$(grep -c '/verify' "$LATEST_SESSION" 2>/dev/null || echo 0)
[ "$VERIFY" -ge 3 ] && R=PASS || R=FAIL
check "Test 6 — /verify usage (${VERIFY}/3)" "$R"

echo ""
echo "PASS: $PASS / 6"
echo "FAIL: $FAIL / 6"

cat > "$RESULTS" << JSON
{
  "timestamp": "$TIMESTAMP",
  "session_lines": $LINES,
  "agent_calls": $AGENT_CALLS,
  "skill_calls": $SKILL_CALLS,
  "bash_calls": $BASH_CALLS,
  "mcp_calls": $MCP_CALLS,
  "mcp_pct": $MCP_PCT,
  "orphan_count": $ORPHAN,
  "verify_usage": $VERIFY,
  "orchestration_reminders": $ORCHESTRATION_REMINDER,
  "pass": $PASS,
  "fail": $FAIL,
  "verdict": "$([ $FAIL -le 1 ] && echo SUCCESS || echo PARTIAL)"
}
JSON

echo "Results: $RESULTS"

# Telegram report
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    MSG="G2 validation $TIMESTAMP: $PASS/6 pass. Verdict: $([ $FAIL -le 1 ] && echo SUCCESS || echo PARTIAL)"
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" -d "text=$MSG" > /dev/null
fi

[ $FAIL -le 1 ] && exit 0 || exit 1
```

### Step 2 — Schedule manual + cron

```bash
chmod +x ~/scripts/validate-orchestration-fix.sh

# Optional: weekly cron via LaunchAgent
cat > ~/Library/LaunchAgents/com.balizero.orch-validate.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.balizero.orch-validate</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/nuzantara/scripts/validate-orchestration-fix.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>8</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>/tmp/orch-validate.log</string>
    <key>StandardErrorPath</key><string>/tmp/orch-validate.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TELEGRAM_BOT_TOKEN</key><string></string>
        <key>TELEGRAM_OWNER_CHAT_ID</key><string>1125336968</string>
    </dict>
</dict>
</plist>
EOF
# Loaded by user manually with launchctl bootstrap when ready
```

## Verification

```bash
# Script exists + executable
ls -la ~/scripts/validate-orchestration-fix.sh

# Dry run on current session
~/scripts/validate-orchestration-fix.sh

# JSON results created
ls -la ~/.claude/state/validation-orchestration-*.json
```

## Rollback

Read-only script. Delete to remove:

```bash
launchctl bootout gui/$(id -u)/com.balizero.orch-validate 2>/dev/null
rm ~/Library/LaunchAgents/com.balizero.orch-validate.plist
rm ~/scripts/validate-orchestration-fix.sh
```

## Open questions

1. **Test 4 MCP target**: 30% empirical? Or higher if T3.2+T2.3+T2.4 install many tools?
2. **Time horizon**: post-Wave 4 immediate run vs 1-week observation period?
3. **Pass threshold**: 4/6 = SUCCESS o 5/6 = PARTIAL? Default = 5/6 strict.

## Estimated breakdown

| Step        | Tempo                       |
| ----------- | --------------------------- |
| Spec script | 40 min                      |
| Cron plist  | 10 min                      |
| Verify      | 10 min                      |
| **Total**   | **60 min** + 30 min per run |
