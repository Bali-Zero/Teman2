---
spec_id: G1
title: Inter-wave validation gate — auto-halt on regression detection
tier: gate
priority: P0 (gate between every wave)
effort_estimate: 30 min spec, 5 min per gate run
status: DRAFT
basis: DS panel high concern 2026-05-21 "no validation gate fra wave"
---

# G1 — Inter-wave validation gate

## Problem

Plan ha 4 wave (Wave 0, 1, 2, 3 + Wave 4 T2.7) ma nessun gate fra wave per detect regression. DS panel: "Plan relies on empirical observation in future sessions, but no A/B metric plan included."

Senza gate, esecutore può procedere Wave 2 anche se Wave 1 ha regressed orchestration health → compound errors.

## Context

Metrics da misurare ad ogni gate:

- **Subagent dispatch ratio**: target ≥ baseline (61 in 2026-05-16 sessione)
- **MCP server reachability**: critical 5 (nuzantara-mcp, notebooklm, postgres, github, vercel)
- **Memory file integrity**: orphan count ≤ baseline (post-T0.1)
- **CLAUDE.md hash**: no unintended drift between waves
- **Sanity check 3-turn**: open new session, run 3 standard queries, verify no regression in tool engagement

## Acceptance criteria

- [ ] `~/scripts/gate-validate-wave.sh <wave_id>` exists
- [ ] Script outputs PASS/FAIL with metrics table
- [ ] FAIL exits 1 + Telegram alert
- [ ] PASS exits 0 + log to `~/.claude/state/gate-results-<wave>-<timestamp>.json`
- [ ] Run mandatory between waves (operator must invoke before next wave)

## Implementation

### Step 1 — Create gate script

Path: `~/scripts/gate-validate-wave.sh`

```bash
#!/bin/bash
# G1 — Inter-wave validation gate for orchestration regression fix
# Usage: ~/scripts/gate-validate-wave.sh <wave_id>
# Reference: research/operations/specs/G1-inter-wave-validation-gate.md

set -uo pipefail

WAVE="${1:-unknown}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR=~/.claude/state
mkdir -p "$RESULTS_DIR"
RESULTS_FILE="$RESULTS_DIR/gate-results-wave${WAVE}-${TIMESTAMP}.json"

FAILS=0
WARNINGS=0

echo "=== G1 gate validation: Wave $WAVE — $(date) ==="
echo ""

# === Metric 1: MCP critical servers reachable ===
echo "--- MCP reachability ---"
MCP_CRITICAL=(
    "https://nuzantara-rag.fly.dev/health"
)
for url in "${MCP_CRITICAL[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$url" 2>/dev/null)
    if [ "$status" = "200" ]; then
        echo "✅ $url: $status"
    else
        echo "❌ $url: $status"
        ((FAILS++))
    fi
done

# === Metric 2: Memory integrity ===
echo ""
echo "--- Memory integrity ---"
MEM_DIR=~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory
MEM_FILE_COUNT=$(find "$MEM_DIR" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
MEMORY_MD_SIZE=$(wc -c < "$MEM_DIR/MEMORY.md" 2>/dev/null || echo 0)

echo "Memory file count: $MEM_FILE_COUNT"
echo "MEMORY.md size: $MEMORY_MD_SIZE bytes (cutoff 25600)"

if [ "$MEMORY_MD_SIZE" -gt 25600 ]; then
    echo "⚠️ MEMORY.md exceeds cutoff — silent truncation risk"
    ((WARNINGS++))
fi

# Orphan detection (matches T0.1 + alzheimer)
ORPHAN_COUNT=0
if [ -f ~/.claude/scripts/alzheimer-hook.sh ]; then
    bash ~/.claude/scripts/alzheimer-hook.sh > /tmp/gate-alzheimer-$TIMESTAMP.txt 2>&1 || true
    ORPHAN_COUNT=$(grep -c "Orphaned" /tmp/gate-alzheimer-$TIMESTAMP.txt 2>/dev/null || echo 0)
fi
echo "Orphan files: $ORPHAN_COUNT"
if [ "$ORPHAN_COUNT" -gt 5 ]; then
    echo "⚠️ Orphan count exceeds threshold 5"
    ((WARNINGS++))
fi

# === Metric 3: CLAUDE.md hash drift ===
echo ""
echo "--- CLAUDE.md hash check ---"
CURRENT_HASH=$(shasum -a 256 ~/Desktop/nuzantara/CLAUDE.md | cut -d' ' -f1)
LAST_HASH_FILE=~/.claude/state/claude-md-last-hash.txt
if [ -f "$LAST_HASH_FILE" ]; then
    LAST_HASH=$(cat "$LAST_HASH_FILE")
    if [ "$CURRENT_HASH" != "$LAST_HASH" ]; then
        echo "ℹ️ CLAUDE.md changed: $LAST_HASH → $CURRENT_HASH (expected if T2.7 ran)"
    else
        echo "✅ CLAUDE.md unchanged: $CURRENT_HASH"
    fi
fi
echo "$CURRENT_HASH" > "$LAST_HASH_FILE"

# === Metric 4: Hook configuration valid ===
echo ""
echo "--- Hook configuration ---"
if ! jq empty ~/.claude/settings.json 2>/dev/null; then
    echo "❌ settings.json malformed — JSON parse fail"
    ((FAILS++))
else
    HOOK_COUNT=$(jq '.hooks | to_entries | map(.value | length) | add' ~/.claude/settings.json)
    echo "✅ settings.json valid, hook events: $HOOK_COUNT"
fi

# === Metric 5: Backup integrity (T-1) ===
echo ""
echo "--- T-1 backup intact ---"
BACKUP=$(ls -t ~/backups/pre-orchestration-fix-*.tar.gz 2>/dev/null | head -1)
if [ -z "$BACKUP" ]; then
    echo "❌ T-1 pre-execution backup missing"
    ((FAILS++))
else
    echo "✅ Backup: $(basename "$BACKUP") ($(du -h "$BACKUP" | cut -f1))"
fi

# === Metric 6: Git state ===
echo ""
echo "--- Git state ---"
cd ~/Desktop/nuzantara
DIRTY_COUNT=$(git status --short | wc -l | tr -d ' ')
echo "Dirty files: $DIRTY_COUNT"
if [ "$DIRTY_COUNT" -gt 30 ]; then
    echo "⚠️ Many dirty files — uncommitted state high"
    ((WARNINGS++))
fi

# === Verdict ===
echo ""
echo "=== VERDICT ==="
echo "Failures: $FAILS"
echo "Warnings: $WARNINGS"

# Write JSON results
cat > "$RESULTS_FILE" << JSON
{
    "wave": "$WAVE",
    "timestamp": "$TIMESTAMP",
    "failures": $FAILS,
    "warnings": $WARNINGS,
    "memory_files": $MEM_FILE_COUNT,
    "memory_md_size": $MEMORY_MD_SIZE,
    "orphan_count": $ORPHAN_COUNT,
    "dirty_files": $DIRTY_COUNT,
    "claude_md_hash": "$CURRENT_HASH",
    "verdict": "$([ $FAILS -eq 0 ] && echo PASS || echo FAIL)"
}
JSON

echo "Results: $RESULTS_FILE"

if [ $FAILS -gt 0 ]; then
    echo ""
    echo "❌ GATE FAIL — DO NOT PROCEED to next wave"
    # Telegram alert
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$TELEGRAM_OWNER_CHAT_ID" \
            -d "text=🚨 G1 gate FAIL Wave $WAVE: $FAILS failures, $WARNINGS warnings. See $RESULTS_FILE" > /dev/null
    fi
    exit 1
else
    echo ""
    echo "✅ GATE PASS — proceed to next wave"
    exit 0
fi
```

### Step 2 — Make executable + dry-run

```bash
chmod +x ~/scripts/gate-validate-wave.sh
~/scripts/gate-validate-wave.sh 0  # dry-run on current state
```

### Step 3 — Document in 00-INDEX.md

Add gate invocation BETWEEN each wave row.

## Verification

### Test 1 — Script exists + executable

```bash
ls -la ~/scripts/gate-validate-wave.sh
# Expected: -rwxr-xr-x
```

### Test 2 — Dry-run current state

```bash
~/scripts/gate-validate-wave.sh 0
echo "exit=$?"
# Expected: prints metrics, exit 0 (current state) or 1 (if T0.2 not done — nuzantara-mcp DNS fail)
```

### Test 3 — JSON results

```bash
ls -la ~/.claude/state/gate-results-*.json | tail
jq . ~/.claude/state/gate-results-wave0-*.json
```

## Rollback

Pure read-only script. No rollback needed. Delete to disable:

```bash
rm ~/scripts/gate-validate-wave.sh
```

## Open questions

1. **Subagent dispatch ratio**: spec mentions but script doesn't measure (requires session-active state). Default = measure manually via T3.4 `/dispatch-stat` slash command after each wave.
2. **MCP critical list**: only `nuzantara-rag.fly.dev/health` currently. Add notebooklm + github + vercel reachability? Default = yes after T0.2 + T2.3 + T2.4 done.
3. **Failure threshold**: 1 failure = FAIL? Or weighted? Default = 1 strict (defensive).
4. **Frequency**: only between waves, OR also during session continuity check? Default = between waves only.

## Estimated breakdown

| Step                      | Tempo                                 |
| ------------------------- | ------------------------------------- |
| Spec script               | 20 min                                |
| Make executable + dry-run | 3 min                                 |
| Document in INDEX         | 5 min                                 |
| Test 1-3                  | 2 min                                 |
| **Total**                 | **30 min** + 5 min per gate execution |
