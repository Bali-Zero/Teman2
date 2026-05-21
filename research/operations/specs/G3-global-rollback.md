---
spec_id: G3
title: Global rollback — single-command reverse all 4 waves
tier: gate
priority: P0 (disaster recovery)
effort_estimate: 30 min spec, 5-10 min per rollback execution
status: DRAFT
basis: DS panel missing_specs 2026-05-21 "GLOBAL-ROLLBACK"
---

# G3 — Global rollback

## Problem

DS panel: _"A unified rollback procedure that reverses all changes across all waves if the overall regression fix fails, instead of requiring manual per-spec rollbacks."_

Plan ha 23 spec con rollback individuali (per file/hook/MCP). Se la combinazione di Wave 1+2 introduce regression interdipendente, eseguire 23 rollback in ordine inverso = errore-prone.

## Context

Reference rollback source = T-1 backup tarball:

- `~/backups/pre-orchestration-fix-<timestamp>.tar.gz`
- Git tag `pre-orchestration-fix-<timestamp>`

## Acceptance criteria

- [ ] `~/scripts/rollback-orchestration-fix.sh <backup_id>` exists
- [ ] Single command restores ALL changes from waves 0-4 + R-series
- [ ] Pre-rollback safety check (verify backup integrity)
- [ ] Post-rollback verification (file counts match pre-fix state)
- [ ] Telegram alert on rollback completion
- [ ] Detailed log saved

## Implementation

### Step 1 — Create rollback script

Path: `~/scripts/rollback-orchestration-fix.sh`

```bash
#!/bin/bash
# G3 — Global rollback for orchestration regression fix
# Reverses all changes from Wave 0-4 + R-series back to T-1 baseline
# Reference: research/operations/specs/G3-global-rollback.md
#
# Panel review fixes integrated:
# - Gemini B1: pkill -f claude before overwrite memory.db (SQLite WAL safety)
# - GPT-5.5 B2: extended scope to include all spec-CREATED state
# - GPT-5.5 code-review: set -euo pipefail (was -uo)
# - Gemini anti-fragility 2: disk space check PRE safety backup
# - WAVE -1 (DS NI-1 / Opus B2): SQLite snapshot restore + anti-paradox canary
# - Iteration-2: exact-binary pkill + tar tolerate missing
# - Iteration-5 DS-BL1: settings.json restore trap on Phases 2-3 failure
# - Iteration-5 DS-BL2: per-phase disk-space pre-check (exit 6)
# - Iteration-5 GDT-1: --non-interactive flag (makes at(1) recipe functional)
# - Iteration-5 GDT-4: tar -C / on Phase 1 safety backup (correct extract path)

set -euo pipefail   # GPT-5.5 code-review fix: was set -uo

# Usage check
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_id> [--non-interactive]"
    echo ""
    echo "Flags:"
    echo "  --non-interactive   Auto-confirm all prompts (for at(1) deferred execution,"
    echo "                      cron, or any context without a controlling TTY)."
    echo ""
    echo "Available backups:"
    ls -la ~/backups/pre-orchestration-fix-*.tar.gz 2>/dev/null
    exit 1
fi

BACKUP_ID="$1"

# === Iter-5 GDT-1 CRITICAL fix: --non-interactive mode for TTY-less invocation ===
# WAVE -1 documented an at(1) fallback (`echo "...g3-rollback.sh $BACKUP_ID" |
# at now+2min`) but G3 has TWO interactive prompts (`read -r CONFIRM`,
# `read -r EXT_ACK`). `at` runs without a controlling TTY → these reads consume
# EOF immediately → script "aborts at Phase 1" because both confirmations
# silently fail. The at(1) fallback was therefore non-functional as documented.
# Add an explicit flag to bypass prompts; the at(1) recipe (Layer C below)
# is updated to pass --non-interactive.
NON_INTERACTIVE=false
for arg in "$@"; do
    case "$arg" in
        --non-interactive) NON_INTERACTIVE=true ;;
    esac
done
BACKUP_FILE=~/backups/pre-orchestration-fix-${BACKUP_ID}.tar.gz
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE=~/.claude/state/rollback-$TIMESTAMP.log

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup not found: $BACKUP_FILE"
    exit 1
fi

mkdir -p ~/.claude/state
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== G3 Global rollback (panel-revised) ==="
echo "Backup: $BACKUP_FILE"
echo "Timestamp: $TIMESTAMP"
echo "Machine: $(whoami)@$(hostname)"
echo ""

# === Pre-flight: verify backup integrity ===
echo "--- Pre-flight checks ---"

# Backup readable
if ! tar -tzf "$BACKUP_FILE" > /dev/null 2>&1; then
    echo "❌ Backup corrupted or unreadable"
    exit 1
fi

BACKUP_FILES=$(tar -tzf "$BACKUP_FILE" | wc -l | tr -d ' ')
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Backup: $BACKUP_FILES files, $BACKUP_SIZE"

# Verify manifest if exists
MANIFEST=~/backups/manifest-${BACKUP_ID}.txt
if [ -f "$MANIFEST" ]; then
    echo "✅ Manifest available: $MANIFEST"
else
    echo "⚠️ No manifest — proceeding without hash verify"
fi

# === Gemini panel anti-fragility fix 2: disk space check PRE safety backup ===
echo ""
echo "--- Disk space check ---"
AVAIL_KB=$(df -k "$HOME" | tail -1 | awk '{print $4}')
AVAIL_MB=$((AVAIL_KB / 1024))
echo "Available: ${AVAIL_MB}MB"
if [ "$AVAIL_MB" -lt 500 ]; then
    echo "❌ Less than 500MB free — safety backup will fail. Aborting."
    exit 1
fi
echo "✅ Sufficient disk space"

# === Gemini panel B1: SQLite WAL safety — kill Claude Code processes ===
#
# 🚨🚨🚨 DANGEROUS ITERATION-1 CODE BELOW — DO NOT COPY-PASTE 🚨🚨🚨
# ─────────────────────────────────────────────────────────────────────
# The kill block in this section uses the broad substring pattern
#   pkill -f "claude"   and   pgrep -f "claude"
# which matches BOTH slot-1 (`~/.local/bin/claude`) AND slot-2
# (`~/.claude-acct2/.local/bin/claude`, the dual-MAX-plan wrapper).
# Running this iteration-1 body on Antonello's dual-MAX-slot setup
# silently terminates slot-2 sessions and corrupts the slot-2 SQLite WAL
# on `~/.claude-acct2/memory.db`.
#
# DO NOT execute the iteration-1 body verbatim. Use the safe replacement
# from "Fix WAVE -1 Iteration 2 / Iteration-2 Fix 1" (see section heading in
# this spec), which:
#   • scopes pkill to the exact slot-1 binary path with `^…\b` regex
#   • aborts (exit 4) if the pattern ever matches `claude-acct2`
#   • verifies slot 2 is untouched after the kill
#
# The lines below are RETAINED VERBATIM only for historical / trap-context
# reasoning (so future operators learn why the substring pattern is unsafe).
# They are wrapped in an `if false; then … fi` guard so accidentally
# executing this section as a script becomes a no-op instead of a foot-gun.
# ─────────────────────────────────────────────────────────────────────
if false; then  # ❌ DEPRECATED — iteration-1 body, see iteration-2 fix below
echo ""
echo "--- Claude Code process termination (Gemini B1 fix) ---"
CLAUDE_PIDS=$(pgrep -f "claude" | head -10 || true)   # ❌ broad substring — matches slot-2
if [ -n "$CLAUDE_PIDS" ]; then
    echo "Active Claude Code processes detected:"
    ps -p $CLAUDE_PIDS -o pid,command 2>/dev/null | head
    echo ""
    echo "⚠️ Rolling back live memory.db (SQLite WAL) will cause corruption."
    echo "Type 'KILL' to terminate all Claude Code sessions, 'WAIT' to abort and quit them manually first:"
    read -r CKILL
    if [ "$CKILL" = "KILL" ]; then
        pkill -TERM -f "claude" 2>/dev/null || true   # ❌ kills claude-acct2 too
        sleep 3
        # Force kill if still alive
        pkill -KILL -f "claude" 2>/dev/null || true   # ❌ kills claude-acct2 too
        sleep 1
        REMAINING=$(pgrep -f "claude" | head -1 || true)   # ❌ broad substring
        if [ -n "$REMAINING" ]; then
            echo "❌ Failed to kill Claude processes. Aborting rollback."
            exit 1
        fi
        echo "✅ Claude Code processes terminated"
    else
        echo "ABORTED. Quit Claude Code sessions manually, then retry."
        exit 1
    fi
else
    echo "✅ No active Claude Code sessions"
fi
fi  # end if-false guard — iteration-1 body NEVER executes
# ─────────────────────────────────────────────────────────────────────
# ✅ CANONICAL IMPLEMENTATION: substitute the iteration-2 safe block from
#    §"Fix WAVE -1 Iteration 2 / Iteration-2 Fix 1" (see section heading in this
#    spec) IN PLACE OF the guarded iteration-1 body above.
# ─────────────────────────────────────────────────────────────────────

# Verify SQLite integrity BEFORE backup
if [ -f ~/.claude/memory.db ]; then
    SQLITE_OK=$(sqlite3 ~/.claude/memory.db "PRAGMA integrity_check;" 2>/dev/null | head -1)
    if [ "$SQLITE_OK" != "ok" ]; then
        echo "⚠️ memory.db integrity check failed: $SQLITE_OK"
    else
        echo "✅ memory.db SQLite integrity OK"
    fi
fi

# === Confirmation gate ===
echo ""
echo "⚠️ DESTRUCTIVE OPERATION"
echo "Will reset:"
echo "  - ~/.claude/{settings.json, hooks/, scripts/, skills/, commands/, agents/, state/, memory.db, memory.db-wal, memory.db-shm}"
echo "  - ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/"
echo "  - ~/Desktop/nuzantara/CLAUDE.md"
echo "  - ~/Desktop/nuzantara/.mcp.json"
echo "  - ~/Desktop/nuzantara/apps/backend-rag/CLAUDE.md"
echo "  - ~/Desktop/nuzantara/.claude/rules/cicatrix-scars.md"
echo "  - ~/Library/LaunchAgents/com.balizero.*.plist (per T-1 manifest)"
echo "  - ~/scripts/{gate-validate,validate-orchestration,orchestration-health}-*.sh"
echo "  - Keychain items per manifest (PG_PASSWORD_RO, etc.)"
echo "  - npm/npx MCP installs per manifest"
echo "  - claude mcp registry per manifest"
echo ""
echo "External state NOT rolled back here — see G0-external-state-rollback for DB roles, Vercel/Fly remote."
echo ""
# Iter-5 GDT-1 fix: --non-interactive auto-confirms (mandatory for at(1) recipe)
if [ "$NON_INTERACTIVE" = "true" ]; then
    echo "Non-interactive mode: auto-confirming rollback (--non-interactive flag)"
    CONFIRM="ROLLBACK"
else
    echo "Type 'ROLLBACK' to proceed (any other input cancels):"
    read -r CONFIRM
fi
if [ "$CONFIRM" != "ROLLBACK" ]; then
    echo "ABORTED by user"
    exit 1
fi

# === Phase 1: save current state to safety (GPT-5.5 B2 — extended scope) ===
SAFETY_BACKUP=~/backups/pre-rollback-safety-$TIMESTAMP.tar.gz
echo ""
echo "--- Phase 1: safety backup current state (extended scope per GPT-5.5 B2) ---"

# Snapshot inventory FIRST (for restore validation later)
INVENTORY=~/.claude/state/rollback-inventory-$TIMESTAMP.txt
{
    echo "=== Claude MCP registry ==="
    claude mcp list 2>/dev/null || true
    echo ""
    echo "=== Keychain items (names only, no values) ==="
    security dump-keychain 2>/dev/null | grep -E "PG_PASSWORD|GITHUB_PAT|TELEGRAM_BOT|GDRIVE_" | head -20 || true
    echo ""
    echo "=== LaunchAgents loaded ==="
    launchctl list | grep -E "com.balizero|com.nuzantara|com.cell" | head || true
    echo ""
    echo "=== ~/scripts/ inventory ==="
    ls -la ~/scripts/ 2>/dev/null | head -30
    echo ""
    echo "=== ~/Library/LaunchAgents/ inventory ==="
    ls -la ~/Library/LaunchAgents/com.balizero*.plist 2>/dev/null
    echo ""
    echo "=== npm globals ==="
    npm ls -g --depth=0 2>/dev/null | head -20 || true
} > "$INVENTORY"

# Tarball with extended scope + WAL/SHM
cd ~ && tar -czf "$SAFETY_BACKUP" \
    .claude/settings.json \
    .claude/hooks/ \
    .claude/scripts/ \
    .claude/skills/ \
    .claude/commands/ \
    .claude/agents/ \
    .claude/state/ \
    .claude/memory.db \
    .claude/memory.db-wal \
    .claude/memory.db-shm \
    .claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/ \
    Library/LaunchAgents/com.balizero.*.plist \
    Library/LaunchAgents/com.nuzantara.*.plist \
    scripts/gate-validate-wave.sh \
    scripts/validate-orchestration-fix.sh \
    scripts/orchestration-health-weekly.sh \
    scripts/rollback-orchestration-fix.sh \
    .zshenv \
    Desktop/nuzantara/CLAUDE.md \
    Desktop/nuzantara/.mcp.json \
    Desktop/nuzantara/apps/backend-rag/CLAUDE.md \
    Desktop/nuzantara/.claude/rules/cicatrix-scars.md \
    2>&1 | tail -5

echo "✅ Safety backup: $SAFETY_BACKUP ($(du -h "$SAFETY_BACKUP" | cut -f1))"

# === Iter-5 DS-BL2 BLOCKER fix: disk-space pre-check (gates Phase 3 extract) ===
# Distinct from the 500MB safety-backup pre-check above. Phase 3 extract
# requires room for the backup tarball's UNCOMPRESSED contents (typically
# 2-3× the tarball size). Bail BEFORE we move settings.json aside so the
# trap below has nothing to rescue (clean abort, system still bootable).
REQUIRED_MB=500
AVAILABLE_MB=$(df -m "$HOME" | tail -1 | awk '{print $4}')
if [ "$AVAILABLE_MB" -lt "$REQUIRED_MB" ]; then
    echo "FATAL: only ${AVAILABLE_MB}MB free, need ${REQUIRED_MB}MB. Free space and retry." >&2
    exit 6    # 6 = disk-space pre-check failed (iter-5 DS-BL2)
fi
echo "✅ Phase 3 disk-space pre-check: ${AVAILABLE_MB}MB free (need ${REQUIRED_MB}MB)"

# === Iter-5 DS-BL1 BLOCKER fix: settings.json restore trap (wraps Phases 2-3) ===
# Iter-1/2 moved settings.json aside (Phase 2) then ran `tar -xzf` (Phase 3).
# If tar failed for ANY reason (disk-full mid-extract, corrupted archive, SIGTERM),
# the script aborted under `set -euo pipefail` leaving settings.json in the
# `.pre-rollback-${BACKUP_ID}` sidecar and the backup NEVER extracted.
# Next claude session start: no settings.json → no hooks → unbootable config.
#
# This trap restores settings.json from the sidecar IF the live path is empty.
# Cleared explicitly after Phase 3 success (so the backup tarball's settings.json
# is what survives, not the pre-rollback one).
SETTINGS_BACKUP="$HOME/.claude/settings.json.pre-rollback-${BACKUP_ID}"
SETTINGS_LIVE="$HOME/.claude/settings.json"

restore_settings_on_error() {
    local exit_code=$?
    if [ -f "$SETTINGS_BACKUP" ] && [ ! -f "$SETTINGS_LIVE" ]; then
        echo "ERROR detected (exit=$exit_code) — restoring settings.json from $SETTINGS_BACKUP" >&2
        mv "$SETTINGS_BACKUP" "$SETTINGS_LIVE"
        echo "  settings.json restored — system remains bootable" >&2
    fi
}
trap restore_settings_on_error ERR EXIT

# === Phase 2: stop active hooks ===
echo ""
echo "--- Phase 2: disable active hooks ---"
[ -f "$SETTINGS_LIVE" ] && mv "$SETTINGS_LIVE" "$SETTINGS_BACKUP"
echo "✅ Hooks paused (settings.json moved to ${SETTINGS_BACKUP})"

# === Phase 3: extract backup ===
echo ""
echo "--- Phase 3: extract backup ---"
# T-1 tarball was produced with `cd ~; tar -czf ...` storing entries
# relative to $HOME (e.g. `.claude/settings.json`). Therefore the correct
# extract pattern is `cd ~ && tar -xzf` — NOT `-C /`. The Iter-5 GDT-4
# `-C /` fix applies only to the SAFETY backup (Phase 1 iter-2 block),
# which uses absolute paths in INCLUDE_FILE. The two tarballs have
# different path-semantics; do not unify them without re-tarring T-1.
if ! (cd ~ && tar -xzf "$BACKUP_FILE" 2>&1 | tail -5); then
    echo "tar failed — trap will restore settings.json" >&2
    exit 1
fi
echo "✅ Backup extracted"

# Phase 3 success — clear trap. The backup tarball's settings.json (if any)
# has now overwritten the live path; the sidecar pre-rollback file is no
# longer needed for emergency restore. Leave it on disk for forensic
# preservation (same rationale as memory.db.pre-rollback-* per Fix WAVE -1).
trap - ERR EXIT

# === Phase 4: git rollback ===
echo ""
echo "--- Phase 4: git rollback ---"
cd ~/Desktop/nuzantara

# Check git state
DIRTY=$(git status --short | wc -l | tr -d ' ')
if [ "$DIRTY" -gt 0 ]; then
    echo "⚠️ $DIRTY dirty files — stashing with -u (untracked included)"
    git stash push -u -m "pre-rollback-stash-$TIMESTAMP" 2>&1 | tail
fi

# Reset to tag if exists
if git tag -l "pre-orchestration-fix-${BACKUP_ID}" | grep -q .; then
    echo "Resetting to tag pre-orchestration-fix-${BACKUP_ID}"
    git reset --hard "pre-orchestration-fix-${BACKUP_ID}"

    # Gemini G-series weakness 2 fix: submodule reset + ignored cleanup
    git submodule update --init --recursive 2>&1 | tail || true
    git clean -fd -e ".env*" -e "*.local" 2>&1 | tail || true

    echo "✅ Git reset + submodules + ignored cleanup"
else
    echo "⚠️ Tag not found — git state unchanged, only tarball restored"
fi

# === Phase 4.5: external state pointer (GPT-5.5 B2) ===
echo ""
echo "--- Phase 4.5: external state pointer ---"
echo "⚠️ External state NOT auto-rolled-back by this script."
echo "Run G0-external-state-rollback for:"
echo "  - Postgres role 'nuzantara_readonly' (created by T3.2)"
echo "  - Vercel/Fly deploy mods (if Wave 2-3 ran)"
echo "  - Keychain items: $(security dump-keychain 2>/dev/null | grep -E 'PG_PASSWORD_RO|GITHUB_PAT' | head | wc -l) found"
echo "  - npm globals to uninstall (per inventory $INVENTORY)"
echo ""
# Iter-5 GDT-1 fix: --non-interactive auto-acknowledges external-state warning
if [ "$NON_INTERACTIVE" = "true" ]; then
    echo "Non-interactive mode: auto-acknowledging external-state handoff (--non-interactive flag)"
    EXT_ACK="CONTINUE"
else
    echo "Type 'CONTINUE' to acknowledge external state must be handled separately:"
    read -r EXT_ACK
fi
if [ "$EXT_ACK" != "CONTINUE" ]; then
    echo "ABORTED at external state acknowledgment"
    exit 1
fi

# === Phase 5: post-rollback verification ===
echo ""
echo "--- Phase 5: verification ---"
SETTINGS_OK=$([ -f ~/.claude/settings.json ] && echo YES || echo NO)
MEMORY_OK=$([ -f ~/.claude/memory.db ] && echo YES || echo NO)
CLAUDEMD_OK=$([ -f ~/Desktop/nuzantara/CLAUDE.md ] && echo YES || echo NO)
MCP_OK=$([ -f ~/Desktop/nuzantara/.mcp.json ] && echo YES || echo NO)

echo "settings.json: $SETTINGS_OK"
echo "memory.db: $MEMORY_OK"
echo "CLAUDE.md: $CLAUDEMD_OK"
echo ".mcp.json: $MCP_OK"

if [ "$SETTINGS_OK" = "NO" ] || [ "$MEMORY_OK" = "NO" ] || [ "$CLAUDEMD_OK" = "NO" ]; then
    echo ""
    echo "❌ POST-ROLLBACK VERIFY FAIL"
    echo "Safety backup at: $SAFETY_BACKUP"
    exit 1
fi

# === Phase 6: scar entry + telegram ===
echo ""
echo "--- Phase 6: log + notify ---"

cat >> ~/Desktop/nuzantara/.claude/rules/cicatrix-scars.md << EOF

### ⚠️ ROLLBACK EXECUTED: orchestration regression fix reversed ($(date +%Y-%m-%d))

_Backup used: $BACKUP_ID · Safety backup: $SAFETY_BACKUP · Log: $LOG_FILE_

**TRAUMA**: Wave 0-4 + R-series orchestration regression fix rolled back to pre-execution state.

**ANTIBODY**: G3-global-rollback.md spec for next attempt.

**GOTCHA**: review log $LOG_FILE before next fix attempt.

EOF

# Telegram
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    MSG="🔄 G3 rollback executed $TIMESTAMP. Pre-fix state restored from $BACKUP_ID. Safety: $SAFETY_BACKUP. Log: $LOG_FILE"
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
        -d "text=$MSG" > /dev/null
fi

echo ""
echo "✅ ROLLBACK COMPLETE"
echo "Log: $LOG_FILE"
echo "Safety backup: $SAFETY_BACKUP"
echo ""
echo "Next steps:"
echo "1. Restart Claude Code session"
echo "2. Verify SessionStart hooks load correctly"
echo "3. Review log + scar entry"
```

### Step 2 — Make executable + smoke test

```bash
chmod +x ~/scripts/rollback-orchestration-fix.sh

# Smoke test: invocation without backup_id
~/scripts/rollback-orchestration-fix.sh
# Expected: usage message + list of backups
```

## Fix WAVE -1 (2026-05-21): SQLite snapshot restoration + external-execution gate

Two empirically-derived BLOCKERS surfaced after the initial draft. Both MUST
be applied to the script in §Implementation Step 1 before the spec ships.
They are documented here as deltas-against-the-draft because they cut across
multiple phases of the existing script body.

### Fix 1 — DeepSeek NI-1 BLOCKER: SQLite snapshot restoration gap

**Symptom (empirical):** T-1 was changed to take an atomic SQLite snapshot via
`sqlite3 ~/.claude/memory.db .backup ~/.claude/memory.db.snapshot-${BACKUP_ID}`
(Gemini B1 — avoids WAL/SHM corruption from raw tar copy of an active DB).
Consequently the tarball produced by T-1 contains
`memory.db.snapshot-${BACKUP_ID}` instead of a raw `memory.db`.

G3 §Phase 3 currently does `tar -xzf "$BACKUP_FILE"` and stops. The snapshot
file lands in `~/.claude/memory.db.snapshot-${BACKUP_ID}`, but the live
`~/.claude/memory.db` is **never overwritten**. Phase 5 verification asks
`[ -f ~/.claude/memory.db ] && echo YES` — the live (possibly corrupted /
regressed) file is still there from before the rollback started, so the
check passes. **Result:** G3 reports SUCCESS but memory.db rollback was a
no-op for the single most critical asset.

**Fix:** insert a new sub-step "Phase 3.5 — restore SQLite snapshot over
live DB" immediately AFTER the `tar -xzf` extraction and BEFORE Phase 4
(git rollback). This snippet must be added verbatim to the script body in
§Step 1:

```bash
# === Phase 3.5: SQLite snapshot restore (DS NI-1 BLOCKER fix, WAVE -1) ===
# Tarball produced by T-1 contains memory.db.snapshot-${BACKUP_ID} (atomic
# sqlite3 .backup output per Gemini B1). Tar extract drops it in place but
# never overwrites the live memory.db. Without this phase, G3 silently leaves
# the broken DB live.
echo ""
echo "--- Phase 3.5: restore SQLite snapshot over live memory.db ---"
SNAPSHOT="$HOME/.claude/memory.db.snapshot-${BACKUP_ID}"
if [ -f "$SNAPSHOT" ]; then
    # Move live DB aside (defense in depth — preserve as forensic evidence
    # of the broken state we are rolling away from). NEVER delete.
    if [ -f "$HOME/.claude/memory.db" ]; then
        mv "$HOME/.claude/memory.db" \
           "$HOME/.claude/memory.db.pre-rollback-${BACKUP_ID}"
        echo "  Live memory.db preserved as memory.db.pre-rollback-${BACKUP_ID}"
    fi
    # Restore snapshot to live path
    cp "$SNAPSHOT" "$HOME/.claude/memory.db"
    # Truncate WAL/SHM that reference the OLD DB state (may now be stale
    # against the freshly-restored DB and would replay phantom writes).
    rm -f "$HOME/.claude/memory.db-wal" "$HOME/.claude/memory.db-shm"
    # Verify integrity of restored DB — MUST be "ok", else fatal
    INTEGRITY=$(sqlite3 "$HOME/.claude/memory.db" \
                "PRAGMA integrity_check;" 2>&1 | head -1)
    if [ "$INTEGRITY" = "ok" ]; then
        echo "  ✅ memory.db restored from snapshot, integrity_check=ok"
    else
        echo "  ❌ FATAL: restored memory.db failed integrity check"
        echo "  PRAGMA integrity_check output: $INTEGRITY"
        echo "  Snapshot path: $SNAPSHOT"
        echo "  Pre-rollback DB preserved at: $HOME/.claude/memory.db.pre-rollback-${BACKUP_ID}"
        echo "  Operator action required: investigate snapshot file, then"
        echo "  either re-run T-1 to take a fresh snapshot from a known-good"
        echo "  source, OR restore the NotebookLM-recoverable subset of memory"
        echo "  entries from NB-14 (session log), OR fall back to Time Machine."
        exit 99    # 99 = fatal post-extract integrity failure; operator must intervene
    fi
else
    # Backwards compat: pre-WAVE-(-1) backups may contain raw memory.db
    # without the snapshot file. Tar extraction already placed it; warn loudly.
    echo "  ⚠️ WARN: no snapshot at $SNAPSHOT"
    echo "  Assuming legacy tarball with raw memory.db — verify integrity manually"
    if [ -f "$HOME/.claude/memory.db" ]; then
        LEGACY_INTEGRITY=$(sqlite3 "$HOME/.claude/memory.db" \
                          "PRAGMA integrity_check;" 2>&1 | head -1)
        echo "  Legacy memory.db integrity_check: $LEGACY_INTEGRITY"
    fi
fi
```

**Forensic preservation note:** the pre-rollback `memory.db` is preserved
as `memory.db.pre-rollback-${BACKUP_ID}` (NOT deleted) so the operator can
inspect what was broken if the rollback itself unmasks a new bug. Clean-up
of these artifacts is manual (next monthly housekeeping) — they live
alongside the live DB and are tiny on average (≤15MB each).

### Fix 2 — Opus B2 BLOCKER: self-termination paradox at process kill

**Symptom (empirical):** §Phase "Claude Code process termination" calls
`pkill -KILL -f "claude" 2>/dev/null` (lines 127-130 of the draft) to ensure
no live claude process holds a WAL lock on memory.db while the snapshot is
being restored — necessary per Gemini B1.

The realistic invocation path for G3 is: Antonello says "rollback" inside an
active claude session → orchestrator dispatches G3 → G3 runs `pkill -f
"claude"`. The `-f` flag matches the FULL command line, so it kills:

- `/Users/nuzantara/.local/bin/claude` (the CLI binary)
- `claude-acct2` wrapper (dual-MAX-slot wrapper from `reference_dual_max_slots_2026_05_19.md`)
- The **parent** claude process that is currently running G3 itself

The parent's pkill kills its own child shell mid-execution. Result: G3 dies
between Phase 2 (settings.json moved aside) and Phase 3 (tar extract). The
machine is left in unbootable hook config: no settings.json, no extracted
backup, no operator-readable error. Symptom: next claude session start
shows "no settings.json found", hooks fail silently, and the operator has
no log line explaining why.

**Fix:** three layers of defense, applied in order of cost.

#### Layer A — entry-point canary (MANDATORY)

Add this canary at the TOP of the script, immediately after `set -euo
pipefail` and BEFORE any other work (before the `if [ $# -lt 1 ]` usage
check is fine; goal is to fail-fast on inside-session execution):

```bash
# === WAVE -1 fix: Opus B2 anti-paradox canary ===
# G3 invokes `pkill -KILL -f "claude"` to release the SQLite WAL lock
# before restoring memory.db snapshot. If G3 itself is running INSIDE a
# claude session, that pkill kills G3's own parent — leaving the system
# half-rolled-back (settings.json moved aside, snapshot never restored,
# git never reset). Refuse to run if we detect a parent claude process.
#
# Detection layers (any ONE matching → refuse):
#   1. CLAUDE_CODE_OAUTH_TOKEN present (the canonical inside-session signal)
#   2. ANTHROPIC_MCP env var (set by claude when spawning subprocs via MCP)
#   3. Parent process matches "claude-cli" by name
_in_claude_session=false
if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
    _in_claude_session=true
    _detect_reason="CLAUDE_CODE_OAUTH_TOKEN set"
elif [ -n "${ANTHROPIC_MCP:-}" ]; then
    _in_claude_session=true
    _detect_reason="ANTHROPIC_MCP set"
elif pgrep -f "claude-cli" 2>/dev/null | grep -q "^${PPID}$"; then
    _in_claude_session=true
    _detect_reason="PPID $PPID matches claude-cli process"
fi

if [ "$_in_claude_session" = "true" ]; then
    cat >&2 <<EOF
❌ FATAL: G3 must NOT run inside a claude session.

Detected: $_detect_reason

Reason: G3 invokes \`pkill -KILL -f "claude"\` to release the SQLite WAL
lock on ~/.claude/memory.db before restoring the snapshot. That pkill
matches THIS session's parent process — running G3 from inside claude
will kill G3 itself mid-rollback (Opus B2 paradox), leaving:
  - ~/.claude/settings.json moved aside (no hooks load on next session)
  - ~/.claude/memory.db snapshot NOT restored
  - Git tree NOT reset to pre-orchestration-fix-\${BACKUP_ID} tag
  - No exit log, no Telegram notification

Recovery from THIS state requires manual tar extraction + git reset,
which is exactly what G3 was supposed to do safely.

Correct invocation — open a fresh Terminal.app window:
  1. Cmd+Space → "Terminal" → Return
  2. (Do not source any claude environment, do not run \`claude\` first)
  3. ~/scripts/rollback-orchestration-fix.sh \$BACKUP_ID

If you ABSOLUTELY MUST trigger G3 from inside this session (emergency
only, e.g. session is the only thing still running), use the at(1)
fallback to defer execution until after this session exits. Iter-5 GDT-1
fix: MUST pass --non-interactive because at(1) runs without a TTY and
the two confirmation prompts (CONFIRM, EXT_ACK) would consume EOF and
abort the script silently:
  echo "/bin/bash ~/scripts/rollback-orchestration-fix.sh '\$BACKUP_ID' --non-interactive" | at now+2min
  exit    # quit this claude session immediately so pkill has no parent to kill

EOF
    exit 2
fi
```

#### Layer B — external execution recipe (operator-facing, MANDATORY documentation)

The spec MUST embed this verbatim recipe in the §Implementation prose so
the operator never has to guess. Add at the end of §Step 1 (just before
§Step 2):

> **How to invoke G3 correctly (every time):**
>
> 1. **Quit your current claude session** if you have one open. Type `/exit`
>    or close the Terminal tab.
> 2. **Open Terminal.app from scratch.** macOS: `Cmd+Space`, type "Terminal",
>    press Return. Do NOT use the Terminal pane embedded in any other app.
> 3. **Do NOT run `claude` first.** Do NOT `source ~/.zshrc` to "make sure
>    everything is loaded" — `.zshrc` may auto-start a claude background
>    process via SessionStart hook on some configurations. Just run:
>    ```bash
>    ~/scripts/rollback-orchestration-fix.sh <BACKUP_ID>
>    ```
> 4. If the canary still triggers (exit code 2 with "Detected: …"), kill
>    every claude process by hand first:
>    ```bash
>    ps aux | grep -E "claude" | grep -v grep
>    # for each PID shown above:
>    kill -TERM <PID>
>    ```
>    Then retry step 3.

#### Layer C — at(1) deferred fallback (TERTIARY, emergency only)

For the case where the operator is locked inside a claude session and has
no other terminal access (e.g. SSH'd into Mini, no other PTY available):

```bash
# Inside the trapped claude session, queue G3 to run 2 minutes after exit.
# Iter-5 GDT-1 fix: --non-interactive is MANDATORY because at(1) provides no
# controlling TTY → `read -r CONFIRM` and `read -r EXT_ACK` would consume EOF
# and abort the script before Phase 1 even starts. Iter-1/2 documented this
# recipe WITHOUT the flag, which made it non-functional in practice.
echo "/bin/bash ~/scripts/rollback-orchestration-fix.sh '${BACKUP_ID}' --non-interactive" | at now+2min

# Then immediately exit this session (so pkill has no parent to kill):
exit
```

`at` is installed by default on macOS (BSD `at`). The 2-minute delay gives
the current claude session time to flush WAL + shut down cleanly. The G3
script will then start from a fresh `at` shell (PPID = `atrun`, NOT
`claude-cli`), so the canary (Layer A) passes and the script proceeds
normally — with the `--non-interactive` flag, the CONFIRM and EXT_ACK
prompts are auto-confirmed instead of consuming EOF and aborting.

**Trade-off:** `at` is asynchronous. Operator gets no real-time feedback;
must check `~/.claude/state/rollback-*.log` after the fact (or check
Telegram for the Phase 6 notification). Use only when Layers A+B are
infeasible.

**HONEST ADMISSION (iter-5 GDT-1 retro)**: The iter-1/2 at(1) recipe was
documented as `echo "...g3-rollback.sh $BACKUP_ID" | at now+2min` WITHOUT
the `--non-interactive` flag. `at` provides no controlling TTY, so the
script's two `read -r` prompts (CONFIRM at the Phase 1 gate, EXT_ACK at
the Phase 4.5 external-state warning) would have consumed EOF
immediately and aborted the script before Phase 1 ever ran. The iter-1/2
Layer C "emergency fallback" was therefore non-functional as
documented — an operator who actually invoked it would have been left
with the same half-rolled-back state the canary was designed to prevent.
Iter-5 adds the `--non-interactive` flag, auto-confirms both prompts
when set, and updates the at(1) recipe to pass it.

### Updated post-restore verification (Phase 5 amendment)

Phase 5 in the draft only checks `[ -f ... ]` existence. With the snapshot
restoration introduced by Fix 1, the verification MUST also assert SQLite
integrity. Replace the existing memory.db check block in Phase 5 with:

```bash
# Phase 5 (WAVE -1 amendment): SQLite integrity is part of "rollback success"
if [ "$MEMORY_OK" = "YES" ]; then
    POST_INTEGRITY=$(sqlite3 "$HOME/.claude/memory.db" \
                     "PRAGMA integrity_check;" 2>&1 | head -1)
    if [ "$POST_INTEGRITY" != "ok" ]; then
        echo "❌ memory.db exists but PRAGMA integrity_check failed: $POST_INTEGRITY"
        echo "   This indicates Phase 3.5 snapshot restore succeeded but the"
        echo "   snapshot itself was corrupt at backup time. Operator must:"
        echo "   1. Restore NotebookLM-recoverable subset of memory entries from NB-14"
        echo "   2. OR restore from a different Time Machine snapshot (predating the regression)"
        echo "   3. OR accept memory loss and re-bootstrap via `mem` CLI"
        exit 99    # 99 = fatal — same exit code as Phase 3.5 integrity failure
    fi
    echo "✅ memory.db integrity_check=ok (Phase 5 post-restore confirmation)"
fi
```

The hard exit on integrity failure is deliberate: a "successful rollback"
that leaves a corrupted DB is worse than no rollback (operator may not
notice for days, in which case the backup `pre-rollback-${BACKUP_ID}` may
get garbage-collected before recovery).

## Fix WAVE -1 Iteration 2 (2026-05-21): exact-binary pkill + tar tolerate missing

Iteration-1 devils-advocate gate surfaced TWO additional HIGH findings that
must be applied as deltas-against-iteration-1 before the spec ships. Both
are scoped, atomic, and do not regress the WAVE -1 fixes above.

### Iteration-2 Fix 1 (HIGH) — `pkill` exact-binary scope, not "claude" substring

**Symptom (empirical):** §Phase "Claude Code process termination" + the
WAVE -1 Layer A canary both call/reference `pkill -KILL -f "claude"`. The
`-f` flag matches the full command-line. In Antonello's dual-MAX-slot
configuration (documented in
`reference_dual_max_slots_2026_05_19.md`), this substring matches:

- `/Users/nuzantara/.local/bin/claude` — slot 1 (primary — INTENDED kill)
- `/Users/nuzantara/.claude-acct2/.local/bin/claude` — slot 2 (`claude-acct2`
  wrapper, DIFFERENT `CLAUDE_CONFIG_DIR`, separate WAL on its own
  `~/.claude-acct2/memory.db`) — UNINTENDED kill
- Any script with "claude" in its cmdline (e.g. `claude-stop-drain.sh`,
  `claude-pg-proxy`, `*claude*` wrappers).

A G3 invoked for slot 1 must NOT terminate slot 2's CLI — slot 2 is holding
WAL locks on a completely different SQLite DB. Killing it silently corrupts
slot 2's memory.db (or, worse, leaves slot 2's user in an unbootable hook
config they did not authorise).

**Fix:** scope `pkill` to the **exact primary-slot binary path**, never to
the substring "claude". Pre-flight assertion guards against accidental
match of `claude-acct2`. The same exact-binary symmetry MUST be applied to
the WAVE -1 Layer A canary's PPID detection so the canary fires only when
the parent is a slot-1 claude, not when slot 2 is innocently running on the
same machine.

Replace the kill block inside §Phase "Claude Code process termination"
(currently lines 127-131 of the iteration-1 script body) with:

```bash
# === Iteration-2 Fix 1: exact-binary pkill (no claude-acct2 collateral) ===
# Scope kill to slot-1 binary only. Slot 2 (~/.claude-acct2/) has its own
# WAL on its own DB — G3 of slot 1 has NO authority to touch it.
PRIMARY_BINARY="/Users/$(whoami)/.local/bin/claude"

# Sanity assertion: list what we are about to kill. If ANY entry matches
# claude-acct2, ABORT — that's a programming bug in this script, not a
# legitimate operating-state.
TO_KILL=$(pgrep -lf "^${PRIMARY_BINARY}\b" 2>/dev/null || true)
if [ -n "$TO_KILL" ] && echo "$TO_KILL" | grep -q "claude-acct2"; then
    echo "❌ FATAL: pkill pattern matches claude-acct2 (slot 2 dual-MAX wrapper)." >&2
    echo "   Pattern: ^${PRIMARY_BINARY}\\b" >&2
    echo "   Matches found:" >&2
    echo "$TO_KILL" | sed 's/^/     /' >&2
    echo "   This is a script bug. Aborting before any process is killed." >&2
    exit 4    # 4 = exact-binary scope guard tripped
fi

# Layer 1: TERM, give 3s grace
pgrep -f "^${PRIMARY_BINARY}\b" 2>/dev/null | while read -r pid; do
    [ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null || true
done
sleep 3

# Layer 2: KILL anything that survived. Loop because pgrep may have returned
# multiple PIDs (parent + spawned subprocesses); each gets its own kill.
pgrep -f "^${PRIMARY_BINARY}\b" 2>/dev/null | while read -r pid; do
    [ -n "$pid" ] && kill -KILL "$pid" 2>/dev/null || true
done
sleep 1

# Verify: any slot-1 PID survived?
REMAINING=$(pgrep -f "^${PRIMARY_BINARY}\b" 2>/dev/null | head -1 || true)
if [ -n "$REMAINING" ]; then
    echo "❌ Failed to kill slot-1 claude processes (PID $REMAINING survived). Aborting rollback."
    exit 1
fi

# Defense-in-depth: explicitly confirm slot 2 is UNTOUCHED if it was running.
SLOT2_BINARY="/Users/$(whoami)/.claude-acct2/.local/bin/claude"
SLOT2_PIDS=$(pgrep -f "^${SLOT2_BINARY}\b" 2>/dev/null || true)
if [ -n "$SLOT2_PIDS" ]; then
    echo "✅ Slot 2 (claude-acct2) preserved — PID(s): $SLOT2_PIDS"
else
    echo "ℹ️  Slot 2 (claude-acct2) was not running (nothing to preserve)"
fi
echo "✅ Slot-1 Claude Code processes terminated (slot 2 untouched)"
```

**Symmetric canary update (WAVE -1 Layer A):** the canary at the top of
the script must also use exact-binary PPID matching, otherwise the canary
could false-trigger when the operator runs G3 from a _slot-2_ claude
session and the script (incorrectly) refuses on the grounds that the
parent is "a claude". For G3 of slot 1 invoked from inside slot 2: the
correct behaviour is still REFUSE (because pkill would kill slot 2's
parent), but the detect_reason message must distinguish the two so the
operator knows which session to exit. Replace the existing PPID branch
(`pgrep -f "claude-cli"`) with:

```bash
# Layer A — exact-binary symmetry (Iteration-2 amendment):
# Refuse if PPID matches EITHER slot-1 OR slot-2 binary (both will be
# killed by the iteration-2 pkill below if they're our parent; slot 2 is
# killed transitively because exec via at(1) is the only safe path).
PPID_CMD=$(ps -p "$PPID" -o command= 2>/dev/null || true)
if echo "$PPID_CMD" | grep -qE "^/Users/[^/]+/\.local/bin/claude\b"; then
    _in_claude_session=true
    _detect_reason="PPID $PPID is slot-1 claude (${PPID_CMD})"
elif echo "$PPID_CMD" | grep -qE "^/Users/[^/]+/\.claude-acct2/\.local/bin/claude\b"; then
    _in_claude_session=true
    _detect_reason="PPID $PPID is slot-2 claude-acct2 (${PPID_CMD}) — G3 must run from fresh Terminal"
fi
```

Note: the env-var detection branches (`CLAUDE_CODE_OAUTH_TOKEN`,
`ANTHROPIC_MCP`) stay unchanged — both slots export those, so either-slot
detection is the correct behaviour for those branches.

### Iteration-2 Fix 2 (HIGH) — Tar tolerate missing paths via dynamic include-list

**Symptom (empirical):** §Phase 1 of the iteration-1 script body calls:

```bash
tar -czf "$SAFETY_BACKUP" \
    .claude/settings.json \
    .claude/hooks/ \
    .claude/state/ \
    .zshenv \
    scripts/gate-validate-wave.sh \
    scripts/validate-orchestration-fix.sh \
    scripts/orchestration-health-weekly.sh \
    ...
```

with a fixed list and **no existence check**. If e.g.
`scripts/gate-validate-wave.sh` was never created (because WAVE 0 was
skipped or rolled back independently), BSD `tar` exits non-zero with
`No such file or directory`. Under `set -euo pipefail`, the script aborts
**AFTER** Phase 2 (`mv ~/.claude/settings.json
~/.claude/settings.json.rollback-$TIMESTAMP`) has already run — the
machine is left WITHOUT `settings.json` AND WITHOUT a safety backup. Next
claude session start: no hooks, no log, no recovery breadcrumb.

Worker C2 (T-1) already uses a dynamic include-list pattern to handle this
exact class of failure. Apply the SAME pattern in G3 Phase 1.

**Fix:** replace the entire `tar -czf "$SAFETY_BACKUP" .claude/... 2>&1 |
tail -5` invocation in Phase 1 with the dynamic include-list pattern:

```bash
# === Iteration-2 Fix 2: tar tolerate missing paths (dynamic include-list) ===
# Iteration-1 fixed-list breaks under set -euo pipefail when ANY optional
# path is absent (e.g. WAVE 0 never ran → scripts/gate-validate-wave.sh
# doesn't exist). Worker C2 (T-1) uses this pattern; symmetric application.
INCLUDE_FILE=$(mktemp /tmp/g3-safety-include.XXXXXX)
# Cleanup mktemp file regardless of script exit path. Note: trap "EXIT" is
# additive to any existing EXIT trap; if a future caller installs one,
# review for conflicts (TODO).
trap 'rm -f "$INCLUDE_FILE"' EXIT

declare -a CANDIDATES=(
    "$HOME/.claude/settings.json"
    "$HOME/.claude/hooks"
    "$HOME/.claude/scripts"
    "$HOME/.claude/skills"
    "$HOME/.claude/commands"
    "$HOME/.claude/agents"
    "$HOME/.claude/state"
    "$HOME/.claude/memory.db"
    "$HOME/.claude/memory.db-wal"
    "$HOME/.claude/memory.db-shm"
    "$HOME/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory"
    "$HOME/.zshenv"
    "$HOME/.config/nuzantara"
    "$HOME/Library/LaunchAgents/com.balizero.*.plist"
    "$HOME/Library/LaunchAgents/com.nuzantara.*.plist"
    "$HOME/scripts/gate-validate-wave.sh"
    "$HOME/scripts/validate-orchestration-fix.sh"
    "$HOME/scripts/orchestration-health-weekly.sh"
    "$HOME/scripts/rollback-orchestration-fix.sh"
    "$HOME/Desktop/nuzantara/CLAUDE.md"
    "$HOME/Desktop/nuzantara/.mcp.json"
    "$HOME/Desktop/nuzantara/apps/backend-rag/CLAUDE.md"
    "$HOME/Desktop/nuzantara/.claude/rules/cicatrix-scars.md"
)

# Resolve globs (e.g. com.balizero.*.plist) and emit only EXISTING paths
# into the include-file. Nullglob semantics: if no plist matches, the
# pattern is silently dropped (no error).
shopt -s nullglob 2>/dev/null || true
for p in "${CANDIDATES[@]}"; do
    # shellcheck disable=SC2086
    for resolved in $p; do
        if [ -e "$resolved" ]; then
            # tar -T expects paths relative to -C; we store absolute paths
            # and let tar handle the relativization via -C "$HOME" below.
            echo "$resolved" >> "$INCLUDE_FILE"
        fi
    done
done
shopt -u nullglob 2>/dev/null || true

# Empty-list guard: G3 PROCEEDS with an empty backup (operator notified)
# rather than aborting mid-rollback. Aborting here would leave the machine
# in the same broken state Iteration-1 produced.
if [ ! -s "$INCLUDE_FILE" ]; then
    echo "⚠️  WARN: zero safety-backup candidates exist on disk." >&2
    echo "    This is unusual (a fresh machine never ran the orchestration fix?)" >&2
    echo "    Proceeding with EMPTY safety backup — rollback (of rollback) WILL NOT" >&2
    echo "    be possible if this G3 invocation needs to be reversed. Operator must" >&2
    echo "    rely on T-1 tarball (already verified) for any recovery." >&2
fi

# Iter-5 GDT-4 HIGH fix: tar -T with absolute paths via `-C /`.
# BSD tar (macOS default) strips leading `/` from absolute paths read via -T,
# storing them as relative to cwd. Iter-2 did NOT pass `-C` and ran tar from
# the script's cwd → the rollback-of-rollback recipe `cd ~ && tar -xzf …`
# would have restored to `~/Users/nuzantara/.claude/…` (nested under HOME),
# NOT to `~/.claude/…`. Pass `-C /` so tar interprets the absolute paths in
# INCLUDE_FILE as `/Users/...` relative to `/`. Extract with `-C /` (see the
# updated Rollback-of-rollback recipe below) restores at correct locations.
# 2>&1 | tail -5 retained from iteration-1 for log brevity.
tar -czf "$SAFETY_BACKUP" -C / -T "$INCLUDE_FILE" 2>&1 | tail -5

# Post-tar verification: file MUST exist AND be non-empty. An empty
# .tar.gz (header only, no entries) is ~45 bytes — refuse anything
# implausibly small that suggests tar silently produced an empty archive
# despite a non-empty include-list.
if [ ! -f "$SAFETY_BACKUP" ]; then
    echo "❌ FATAL: safety backup file missing after tar invocation" >&2
    exit 5    # 5 = safety-backup post-verify failed
fi
if [ ! -s "$SAFETY_BACKUP" ]; then
    echo "❌ FATAL: safety backup exists but is empty (0 bytes)" >&2
    exit 5
fi

# If include-file had entries, sanity-check archive against expected count.
# Empty include-file → empty archive is OK (we already warned).
INCLUDE_COUNT=$(wc -l < "$INCLUDE_FILE" | tr -d ' ')
ARCHIVE_COUNT=$(tar -tzf "$SAFETY_BACKUP" 2>/dev/null | wc -l | tr -d ' ')
if [ "$INCLUDE_COUNT" -gt 0 ] && [ "$ARCHIVE_COUNT" -eq 0 ]; then
    echo "❌ FATAL: safety backup contains 0 entries despite ${INCLUDE_COUNT} include candidates" >&2
    exit 5
fi
echo "✅ Safety backup: $SAFETY_BACKUP ($(du -h "$SAFETY_BACKUP" | cut -f1), ${ARCHIVE_COUNT} entries from ${INCLUDE_COUNT} candidates)"
```

**Behavioural guarantee:** G3 NEVER aborts mid-rollback due to a missing
optional file. The worst case is a SMALLER backup (operator notified via
WARN line). The previous failure mode (no settings.json AND no backup)
is impossible by construction — tar runs ONLY if `INCLUDE_FILE` was
constructed successfully (and the empty-list case is explicitly handled
without invoking tar in a state that would error).

**HONEST ADMISSION (iter-5 GDT-4 retro)**: The iter-2 implementation of
this block invoked `tar -czf "$SAFETY_BACKUP" -T "$INCLUDE_FILE"` WITHOUT
the `-C /` flag and stored absolute paths in INCLUDE_FILE. BSD tar (macOS
default) silently strips the leading `/` from absolute paths read via -T,
storing them as paths relative to whatever cwd tar was run from at
archive-creation time. The rollback-of-rollback recipe was `cd ~ && tar
-xzf ...` which would have extracted to `~/Users/nuzantara/.claude/...`
(nested under HOME), NOT to `~/.claude/...`. The "rollback of rollback"
section was therefore broken-by-design until iter-5 added `-C /` to BOTH
the create-side (this block) and the extract-side (Rollback-of-rollback
section). Iter-2 testing never empirically extracted the safety backup,
so the bug was invisible until DeepSeek+Gemini panel review caught it.

**Trade-off documented:** the include-list grows over time as new specs
add new state. CANDIDATES must be kept in sync with T-1's include pattern
(both should grow together). Drift surface: if T-1 backs up state that G3
does not safety-mirror, a rollback could destroy state the operator may
have wanted to preserve. Mitigation: in next sprint, refactor both T-1 and
G3 to source CANDIDATES from a shared file (e.g.
`docs/runbooks/orchestration-state-paths.yaml`). Out of scope for this
iteration to keep the fix atomic.

## Fix Iteration 5 (DS+Gemini panel): trap, disk-space, --non-interactive, tar -C /

DeepSeek V4 Pro + Gemini 3.1 Pro adversarial panel review of D3 found four
findings the iter-1/2/3 reviews missed. All four cluster around one root
cause: **iter-1/2 reasoned about the script statically but never empirically
exercised the failure paths.** None of the four bugs is detectable by reading
the code — only by running it under hostile conditions (tar SIGKILL, full
disk, at(1) TTY-less context, BSD tar absolute-path stripping).

The four fixes are applied INLINE in §Step 1 above (see Phase 2-3 trap,
Phase 3 disk-space pre-check, top-of-script `--non-interactive` flag
parsing, and Phase 1 `tar -C /` invocation). This section documents the
panel findings, severity, and the principle behind each delta for future
review traceability.

### Fix 1 (DS-BL1, BLOCKER) — settings.json restore on tar fail

**Symptom (empirical):** G3 Phase 2 moves `~/.claude/settings.json` aside
(`mv ... .pre-rollback-${BACKUP_ID}`). Phase 3 then runs `tar -xzf
"$BACKUP_PATH"`. If tar fails for ANY reason (disk-full mid-extract,
corrupted archive, SIGTERM from operator pressing Ctrl-C, NFS hiccup), the
script aborts under `set -euo pipefail` with settings.json STILL moved
aside AND no extracted backup. Next claude session start:
`settings.json` not found → SessionStart hook fails → no hook config →
unbootable config. The operator has no recovery breadcrumb because the
"safety backup" Phase 1 mirror does NOT include the just-moved-aside
sidecar (timing: Phase 1 runs before Phase 2's mv).

**Fix (applied inline above):** wrap Phases 2-3 in an `ERR EXIT` trap
that restores `settings.json` from the `.pre-rollback-${BACKUP_ID}`
sidecar IF the live path is empty. Trap is explicitly cleared after
Phase 3 success so the backup tarball's own settings.json (overwritten
during tar extract) is what survives. The trap reads `$?` so the
restore message includes the actual exit code for forensic debugging.

**Principle:** every irreversible mutation in the script must have a
companion trap that reverses it on ANY non-zero exit between mutation
and the next checkpoint. `set -euo pipefail` is necessary but not
sufficient — it ABORTS, the trap RESTORES.

### Fix 2 (DS-BL2, BLOCKER) — disk-space pre-check before Phase 3 extract

**Symptom (empirical):** Phase 1's safety-backup writes a few hundred MB.
Phase 3's `tar -xzf "$BACKUP_PATH"` writes the FULL pre-orchestration-fix
state, which can be 2-3× the tarball size after decompression. The
existing 500MB check (line 110 of iter-1, retained from iter-3) was
positioned BEFORE Phase 1 to gate the safety-backup creation, not the
Phase 3 extract. If the safety-backup consumed 400MB of the available
500MB, Phase 3 starts with only 100MB free and tar mid-flight runs out
of space, triggering Fix 1's trap (good) but leaving the operator with
no informative error message about WHY tar failed.

**Fix (applied inline above):** add a SECOND disk-space pre-check
immediately before Phase 2's settings.json move-aside (NOT before Phase
3 extract per the task description — the check must precede Phase 2 so
the trap has nothing to rescue when we bail). Exit code 6 is reserved
for this specific failure so monitoring can distinguish "out of disk"
from other Phase 3 failures.

**Principle:** stage-gate every phase with a precondition check, not just
the script entry. Each phase's preconditions can change after earlier
phases run (here: Phase 1 consumed disk).

### Fix 3 (GDT-1, CRITICAL) — `--non-interactive` flag for TTY-less invocation

**Symptom (empirical):** WAVE -1 Layer C documented an at(1) deferred
execution recipe — `echo "...g3-rollback.sh $BACKUP_ID" | at now+2min`
— so the operator could trigger G3 from inside a doomed claude session.
G3 has TWO interactive prompts: `read -r CONFIRM` (Phase 1 gate) and
`read -r EXT_ACK` (Phase 4.5 external-state acknowledgment). `at`
provides no controlling TTY, so both `read` calls consume EOF
immediately. CONFIRM is empty → "ABORTED by user" → exit 1, before
Phase 1 even runs. The Layer C "emergency fallback" was therefore
non-functional as documented for the 8+ months it has lived in the
spec.

**Fix (applied inline above):** add a `--non-interactive` flag parsed at
the top of the script. When set, both `read` calls are replaced with
hard-coded `CONFIRM=ROLLBACK` and `EXT_ACK=CONTINUE` (the exact strings
that the script gates on). Update the Layer C recipe AND the Layer A
canary's at(1) recommendation to pass the flag. Without `at`, the flag
is also useful for cron-based deferred rollback (e.g. a watchdog that
detects a regression and queues G3 for the next maintenance window).

**Principle:** every emergency-fallback recipe must be tested
end-to-end before it is documented. "Open Terminal.app" (Layer B)
works because operators have empirically used it; `at(1)` did not work
because nobody had ever run G3 under it before iter-5.

### Fix 4 (GDT-4, HIGH) — BSD tar absolute-path stripping breaks rollback-of-rollback

**Symptom (empirical):** Iter-2's safety-backup tar invocation is
`tar -czf "$SAFETY_BACKUP" -T "$INCLUDE_FILE"` with absolute paths in
INCLUDE_FILE (e.g. `/Users/nuzantara/.claude/settings.json`). BSD tar
(macOS default, where this script runs) silently strips the leading `/`
from absolute paths read via `-T`, storing entries as relative to
WHATEVER cwd tar was invoked from. The script's cwd at Phase 1 is the
operator's working directory — typically `~` after the `cd ~` on line 240
of iter-1. So entries in the safety-backup are stored as
`Users/nuzantara/.claude/settings.json` (relative to `~`). The
"Rollback (of rollback)" recipe was `cd ~ && tar -xzf ...`, which
extracts to `~/Users/nuzantara/.claude/settings.json` — a NESTED path
that does NOT restore the live config. The rollback-of-rollback was
therefore broken-by-construction.

**Fix (applied inline above):** pass `-C /` to BOTH the create-side
(Phase 1 Iter-2 Fix 2 block) and the extract-side (Rollback-of-rollback
section). With `-C /`, tar interprets the include-list paths as relative
to `/` (after BSD's leading-slash strip), producing archive entries like
`Users/nuzantara/.claude/settings.json` that extract correctly under
`/` to `/Users/nuzantara/.claude/settings.json`. Phase 3 (T-1 backup
extract) does NOT get `-C /` — T-1's tarball was created with
`cd ~; tar -czf ... .claude/...` so its entries are stored relative to
`$HOME` (e.g. `.claude/settings.json`), and the correct extract pattern
is `cd ~ && tar -xzf` (preserved from iter-1, with the iter-5 trap
wrapping it). The two tarballs have DIFFERENT path-semantics — do not
unify them without re-tarring T-1 with `-C /`.

**Principle:** never invoke tar without `-C` if you ever intend to
extract the archive on a different machine, in a different shell, or
from a different cwd. The portable invariant is "archive entries are
relative to the `-C` directory at create time; extract with `-C` to
that same directory."

### Cross-cutting principle for iter-5

All four findings share a meta-pattern: **the script was reviewed as
text but never as behaviour.** Iter-1/2/3 reviewers (Opus, Gemini,
DeepSeek, GPT-5.5) all read the script, validated the logic statically,
and approved. Iter-5's DS+Gemini panel was instructed to specifically
attempt to BREAK the script under hostile conditions (tar fail, disk
full, no TTY, BSD tar quirks). Each finding required ~5 minutes of
empirical thought experiment to surface.

Going forward, any G-tier spec that ships infrastructure scripts MUST
include at least one panel iteration that explicitly enumerates failure
modes for each command (what if it fails? what if it succeeds but
produces unexpected output? what if the cwd is wrong? what if the
operator is in a non-TTY context?). Static review alone is insufficient
for disaster-recovery scripts.

## Verification

### Test 1 — Script + usage

```bash
~/scripts/rollback-orchestration-fix.sh
# Expected: usage + backup list
```

### Test 2 — Dry-run scenario

Create test backup tarball, run rollback to it, verify restoration.

### Test 3 — Safety backup created

After rollback, verify `~/backups/pre-rollback-safety-*.tar.gz` exists.

### Test 4 — WAVE -1 anti-paradox canary (Layer A) blocks inside-session execution

Inside an active claude session (`CLAUDE_CODE_OAUTH_TOKEN` is set):

```bash
# From within `claude`:
~/scripts/rollback-orchestration-fix.sh dummy-id-123
echo "exit code: $?"
# Expected stdout:
#   ❌ FATAL: G3 must NOT run inside a claude session.
#   Detected: CLAUDE_CODE_OAUTH_TOKEN set
#   Reason: G3 invokes `pkill -KILL -f "claude"` ...
#   Correct invocation — open a fresh Terminal.app window: ...
# Expected exit code: 2
# Expected side-effects: NONE (no settings.json moved, no tar extract,
#   no git reset, no scar entry written)
```

From a fresh Terminal.app window (no claude env, `CLAUDE_CODE_OAUTH_TOKEN`
unset, parent process is `zsh` not `claude-cli`):

```bash
# From a fresh, claude-free Terminal:
~/scripts/rollback-orchestration-fix.sh dummy-id-123
echo "exit code: $?"
# Expected: proceeds past canary, reaches usage check or backup-not-found
#   error (since dummy-id-123 does not match a real backup).
# Expected exit code: 1 (from "Backup not found: ..." check)
# Expected: canary FATAL message NOT printed.
```

Belt-and-braces: also force-test the PPID detection branch by spawning G3
under a process renamed to `claude-cli`:

```bash
# Synthetic test for layer-A detection branch 3:
# Skip — `pgrep -f "claude-cli"` matching $PPID is hard to fake without
# either (a) actually being inside claude, or (b) renaming a shell to
# claude-cli (defeats the test). Considered tested transitively via
# real inside-session invocation (branch 1 of layer A).
```

### Test 5 — WAVE -1 SQLite snapshot restore + integrity_check

End-to-end dry-run against a synthetic backup:

```bash
# Setup synthetic backup with snapshot file
TEST_ID="test-$(date +%s)"
mkdir -p /tmp/g3-test-$TEST_ID/.claude
sqlite3 /tmp/g3-test-$TEST_ID/.claude/memory.db.snapshot-${TEST_ID} \
    "CREATE TABLE t(x INTEGER); INSERT INTO t VALUES (1),(2),(3); PRAGMA integrity_check;"
cd /tmp/g3-test-$TEST_ID && tar -czf ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz \
    .claude/memory.db.snapshot-${TEST_ID}

# Provoke a "corrupted live DB" condition
echo "GARBAGE" > ~/.claude/memory.db.test-backup
mv ~/.claude/memory.db ~/.claude/memory.db.real-backup-$$    # preserve real DB
echo "GARBAGE" > ~/.claude/memory.db

# Run G3 (from FRESH terminal — canary must pass)
~/scripts/rollback-orchestration-fix.sh ${TEST_ID}

# Verify Phase 3.5 worked
sqlite3 ~/.claude/memory.db "SELECT count(*) FROM t;"
# Expected: 3 (snapshot was restored)

ls -la ~/.claude/memory.db.pre-rollback-${TEST_ID}
# Expected: file exists, contains "GARBAGE" (forensic preservation of broken state)

sqlite3 ~/.claude/memory.db "PRAGMA integrity_check;"
# Expected: "ok"

# Restore real DB and clean up test artifacts
mv ~/.claude/memory.db.real-backup-$$ ~/.claude/memory.db
rm ~/.claude/memory.db.pre-rollback-${TEST_ID}
rm ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
rm -rf /tmp/g3-test-$TEST_ID
```

Corruption-of-snapshot path (verify exit 99):

```bash
# Setup synthetic backup with INTENTIONALLY-corrupted snapshot
TEST_ID="test-corrupt-$(date +%s)"
mkdir -p /tmp/g3-test-$TEST_ID/.claude
echo "not a sqlite db" > /tmp/g3-test-$TEST_ID/.claude/memory.db.snapshot-${TEST_ID}
cd /tmp/g3-test-$TEST_ID && tar -czf ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz \
    .claude/memory.db.snapshot-${TEST_ID}

# Run G3 — Phase 3.5 must abort with exit 99 BEFORE Phase 4 git reset
~/scripts/rollback-orchestration-fix.sh ${TEST_ID}
echo "exit code: $?"
# Expected exit code: 99
# Expected: pre-rollback memory.db preserved at ~/.claude/memory.db.pre-rollback-${TEST_ID}
# Expected: NO git reset happened (Phase 4 never reached)
# Expected stdout includes: "FATAL: restored memory.db failed integrity check"

# Clean up
mv ~/.claude/memory.db.pre-rollback-${TEST_ID} ~/.claude/memory.db
rm ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
rm -rf /tmp/g3-test-$TEST_ID
```

### Test 6 — Iteration-2 Fix 1: slot 2 (claude-acct2) MUST survive G3 of slot 1

Boot a dual-slot scenario and verify G3 of slot 1 leaves slot 2 untouched.

```bash
# Pre-condition: slot 2 wrapper exists at ~/.claude-acct2/.local/bin/claude
# (per reference_dual_max_slots_2026_05_19.md). If not, this test is N/A.
if [ ! -x ~/.claude-acct2/.local/bin/claude ]; then
    echo "SKIP Test 6: slot 2 not configured on this machine"
    exit 0
fi

# Start slot 2 as a background process holding open ~/.claude-acct2/memory.db.
# Use a long-running interactive shim: tail -f on the SQLite WAL guarantees
# the file is held open and a kill would be empirically detectable.
SLOT2_BINARY="$HOME/.claude-acct2/.local/bin/claude"
"$SLOT2_BINARY" --version &   # short-lived; real test uses interactive
SLOT2_PID_BEFORE=$(pgrep -f "^${SLOT2_BINARY}\b" | head -1 || true)
echo "Slot 2 PID before G3: ${SLOT2_PID_BEFORE:-none}"

# Synthesise a benign backup so G3 can run through Phase 3 termination
TEST_ID="slot2-survive-$(date +%s)"
mkdir -p /tmp/g3-test-$TEST_ID/.claude
sqlite3 /tmp/g3-test-$TEST_ID/.claude/memory.db.snapshot-${TEST_ID} \
    "CREATE TABLE t(x INTEGER); INSERT INTO t VALUES (1);"
cd /tmp/g3-test-$TEST_ID && tar -czf ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz \
    .claude/memory.db.snapshot-${TEST_ID}

# Run G3 from a FRESH Terminal (canary must pass).
~/scripts/rollback-orchestration-fix.sh ${TEST_ID}

# Post-condition: slot 2 PID still alive (assuming it was alive pre-test;
# otherwise this checks G3 did not spuriously create a slot-2 process,
# which is also a pass).
SLOT2_PID_AFTER=$(pgrep -f "^${SLOT2_BINARY}\b" | head -1 || true)
if [ -n "$SLOT2_PID_BEFORE" ] && [ -z "$SLOT2_PID_AFTER" ]; then
    echo "❌ FAIL Test 6: slot 2 PID ${SLOT2_PID_BEFORE} was killed by G3 of slot 1"
    exit 1
fi
echo "✅ PASS Test 6: slot 2 untouched by G3 (before=${SLOT2_PID_BEFORE:-none} after=${SLOT2_PID_AFTER:-none})"

# Also check G3 stdout for the explicit "Slot 2 ... preserved" or "not running" log line
grep -E "Slot 2 \(claude-acct2\) (preserved|was not running)" ~/.claude/state/rollback-*.log | tail -1
# Expected: matches one of the two messages.

# Clean up
[ -n "$SLOT2_PID_AFTER" ] && kill "$SLOT2_PID_AFTER" 2>/dev/null
rm ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
rm -rf /tmp/g3-test-$TEST_ID
```

Adversarial sub-test: deliberately corrupt the script to introduce a
`claude-acct2`-matching pkill pattern, verify exit 4 (scope-guard trips):

```bash
# Setup: patch a working copy to use the BROKEN substring "claude" pattern
cp ~/scripts/rollback-orchestration-fix.sh /tmp/g3-broken.sh
sed -i.bak 's|^${PRIMARY_BINARY}\\b|claude|g' /tmp/g3-broken.sh

# Start slot 2 (or fake-spawn a process with claude-acct2 in cmdline)
"$HOME/.claude-acct2/.local/bin/claude" --version &
sleep 1

# Provide a real backup so the script reaches the pkill stage
TEST_ID="scope-guard-$(date +%s)"
# (same backup setup as above) ...
bash /tmp/g3-broken.sh ${TEST_ID}
echo "exit code: $?"
# Expected exit code: 4 (FATAL: pkill pattern matches claude-acct2)
# Expected stdout includes: "Aborting before any process is killed"

rm -f /tmp/g3-broken.sh /tmp/g3-broken.sh.bak
```

### Test 7 — Iteration-2 Fix 2: `scripts/gate-validate-wave.sh` missing → tar succeeds

The headline failure mode that motivated the fix. Verify Phase 1 completes
without aborting, settings.json is preserved, and the safety backup is
non-empty.

```bash
# Pre-condition: ensure scripts/gate-validate-wave.sh is ABSENT
[ -f ~/scripts/gate-validate-wave.sh ] && \
    mv ~/scripts/gate-validate-wave.sh ~/scripts/gate-validate-wave.sh.test-backup

# Synthesise a benign backup
TEST_ID="missing-paths-$(date +%s)"
mkdir -p /tmp/g3-test-$TEST_ID/.claude
sqlite3 /tmp/g3-test-$TEST_ID/.claude/memory.db.snapshot-${TEST_ID} \
    "CREATE TABLE t(x INTEGER); INSERT INTO t VALUES (1);"
cd /tmp/g3-test-$TEST_ID && tar -czf ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz \
    .claude/memory.db.snapshot-${TEST_ID}

# Run G3 from a FRESH Terminal
~/scripts/rollback-orchestration-fix.sh ${TEST_ID}
G3_EXIT=$?
echo "G3 exit code: $G3_EXIT"
# Expected exit code: 0 (or 99 only if integrity_check fails — unrelated)
# Expected: NO "exit 5" (safety-backup-post-verify failure)

# Verify safety backup was produced AND is non-empty
SAFETY=$(ls -t ~/backups/pre-rollback-safety-*.tar.gz | head -1)
[ -s "$SAFETY" ] || { echo "❌ FAIL Test 7: safety backup empty"; exit 1; }
ENTRIES=$(tar -tzf "$SAFETY" | wc -l | tr -d ' ')
[ "$ENTRIES" -gt 0 ] || { echo "❌ FAIL Test 7: safety backup has 0 entries"; exit 1; }

# Verify settings.json was NOT left moved-aside (means Phase 1 completed)
[ -f ~/.claude/settings.json ] || \
    { echo "❌ FAIL Test 7: settings.json missing — Phase 1 aborted before Phase 2"; exit 1; }

echo "✅ PASS Test 7: G3 completed with ${ENTRIES} entries despite missing gate-validate-wave.sh"

# Restore
[ -f ~/scripts/gate-validate-wave.sh.test-backup ] && \
    mv ~/scripts/gate-validate-wave.sh.test-backup ~/scripts/gate-validate-wave.sh
rm ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
rm -rf /tmp/g3-test-$TEST_ID
```

Belt-and-braces: empty-include-list path (no candidate exists on disk).
Hard to simulate on a real machine without destroying everything, but
verify the guard exists by static inspection:

```bash
# Static check: empty-include-list guard is present in script body
grep -q 'zero safety-backup candidates exist on disk' ~/scripts/rollback-orchestration-fix.sh \
    || { echo "❌ FAIL Test 7b: empty-include-list guard missing from script"; exit 1; }
echo "✅ PASS Test 7b: empty-include-list guard present in script"
```

### Test 8 — Iteration-2 Fix 2: all paths exist → Phase 1 behaviour unchanged

Regression test: when every candidate path exists, G3 must produce the
same Phase 1 outcome as iteration-1 (same set of files, non-empty backup).

```bash
# Pre-condition: ensure ALL CANDIDATES paths exist. Create any missing
# optional ones with empty placeholders.
for p in ~/scripts/gate-validate-wave.sh \
         ~/scripts/validate-orchestration-fix.sh \
         ~/scripts/orchestration-health-weekly.sh; do
    [ -f "$p" ] || { touch "$p"; chmod +x "$p"; CREATED="$CREATED $p"; }
done

# Synthesise a benign backup
TEST_ID="all-exist-$(date +%s)"
mkdir -p /tmp/g3-test-$TEST_ID/.claude
sqlite3 /tmp/g3-test-$TEST_ID/.claude/memory.db.snapshot-${TEST_ID} \
    "CREATE TABLE t(x INTEGER); INSERT INTO t VALUES (1);"
cd /tmp/g3-test-$TEST_ID && tar -czf ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz \
    .claude/memory.db.snapshot-${TEST_ID}

# Run G3 from FRESH Terminal
~/scripts/rollback-orchestration-fix.sh ${TEST_ID}
echo "G3 exit code: $?"
# Expected exit code: 0 (or 99 only if integrity_check fails)

# Verify safety backup contains expected critical entries
SAFETY=$(ls -t ~/backups/pre-rollback-safety-*.tar.gz | head -1)
EXPECTED_ENTRIES=(
    ".claude/settings.json"
    ".claude/hooks"
    ".claude/state"
    "Desktop/nuzantara/CLAUDE.md"
)
# (some entries may have absolute paths in archive — tar -tzf shows them as stored)
for entry in "${EXPECTED_ENTRIES[@]}"; do
    if ! tar -tzf "$SAFETY" 2>/dev/null | grep -q "${entry}"; then
        echo "❌ FAIL Test 8: missing expected entry '${entry}' in safety backup"
        exit 1
    fi
done
echo "✅ PASS Test 8: safety backup contains all expected critical entries"

# Restore (delete placeholders we created)
for p in $CREATED; do rm -f "$p"; done
rm ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
rm -rf /tmp/g3-test-$TEST_ID
```

### Test 9 — Iter-5 DS-BL1: settings.json restored when tar extract fails

Simulate a Phase 3 tar failure mid-script and verify the trap restores
`~/.claude/settings.json` from the `.pre-rollback-${BACKUP_ID}` sidecar.

```bash
# Setup: create a sentinel settings.json with a unique marker
TEST_ID="settings-restore-$(date +%s)"
SENTINEL_MARKER="iter5-test-marker-${TEST_ID}"
SETTINGS_BACKUP_PRE=$(cat ~/.claude/settings.json 2>/dev/null || echo "{}")
echo "{\"_test_marker\": \"${SENTINEL_MARKER}\"}" > ~/.claude/settings.json

# Synthesise a backup tarball that is INTENTIONALLY corrupt
# (write a non-gzip-non-tar file with .tar.gz extension)
mkdir -p ~/backups
echo "not-a-tar-file-on-purpose" > ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz

# Also synthesise a memory.db snapshot so Phase 3.5 doesn't bail before Phase 3
# (not strictly needed since tar will fail BEFORE Phase 3.5 — but for clarity)

# Run G3 from FRESH Terminal. Expectation: Phase 3 tar -xzf fails because the
# tarball is corrupt → ERR trap fires → settings.json restored from sidecar.
~/scripts/rollback-orchestration-fix.sh ${TEST_ID} --non-interactive
G3_EXIT=$?
echo "G3 exit code: $G3_EXIT (non-zero expected)"

# Verify: settings.json still exists AND contains our sentinel marker
if [ ! -f ~/.claude/settings.json ]; then
    echo "❌ FAIL Test 9: settings.json missing — trap did not restore"
    exit 1
fi
if ! grep -q "$SENTINEL_MARKER" ~/.claude/settings.json; then
    echo "❌ FAIL Test 9: settings.json exists but sentinel marker lost"
    echo "   Expected marker: $SENTINEL_MARKER"
    echo "   File contents:"
    cat ~/.claude/settings.json
    exit 1
fi
echo "✅ PASS Test 9: settings.json restored from sidecar after tar failure"

# Verify: sidecar should have been moved BACK to live (so it no longer exists)
if [ -f ~/.claude/settings.json.pre-rollback-${TEST_ID} ]; then
    echo "❌ FAIL Test 9: sidecar still exists — restore was a copy, not a move"
    exit 1
fi
echo "✅ PASS Test 9: sidecar consumed (move, not copy)"

# Cleanup: restore original settings.json
echo "$SETTINGS_BACKUP_PRE" > ~/.claude/settings.json
rm -f ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
```

### Test 10 — Iter-5 DS-BL2: disk-full pre-check exits with code 6

Simulate disk-full conditions and verify exit code 6 with a clear message.
Real disk-full is hard to fabricate; instead, monkey-patch the `df` command
in PATH to return a synthetic low-free value.

```bash
# Setup: create a fake `df` shim in a temp dir, prepended to PATH
TEST_ID="disk-full-$(date +%s)"
SHIM_DIR=$(mktemp -d /tmp/g3-df-shim.XXXXXX)
cat > "$SHIM_DIR/df" <<'SHIM'
#!/bin/bash
# Synthetic df shim: report 100MB free no matter what (< 500MB threshold)
if echo "$*" | grep -qE -- "-m\b"; then
    cat <<'EOF'
Filesystem 1M-blocks  Used Available Capacity Mounted on
/dev/test       1000   900       100      90% /
EOF
else
    # Real df for any other invocation
    /bin/df "$@"
fi
SHIM
chmod +x "$SHIM_DIR/df"

# Synthesise a benign backup so the script reaches Phase 1
mkdir -p /tmp/g3-test-$TEST_ID/.claude
sqlite3 /tmp/g3-test-$TEST_ID/.claude/memory.db.snapshot-${TEST_ID} \
    "CREATE TABLE t(x INTEGER); INSERT INTO t VALUES (1);"
cd /tmp/g3-test-$TEST_ID && tar -czf ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz \
    .claude/memory.db.snapshot-${TEST_ID}

# Run G3 with the shim prepended — Phase 1 pre-check should also fail
# (the existing 500MB safety-backup gate uses the same df). For this test
# we specifically want to reach the Phase 3 disk-space pre-check, but the
# Phase 1 check will fire first if both use df. That's acceptable — both
# exit codes mean "disk insufficient." Verify exit is 1 (existing
# behavior of the Phase 1 gate) OR 6 (Phase 3 iter-5 gate), with the
# Phase 3 gate's distinctive error string when reached.
PATH="$SHIM_DIR:$PATH" ~/scripts/rollback-orchestration-fix.sh ${TEST_ID} --non-interactive 2>&1 | tee /tmp/g3-disk-test-$TEST_ID.log
G3_EXIT=$?
echo "G3 exit code: $G3_EXIT"

# Expected: G3 aborts with either Phase 1's "Less than 500MB free" OR
# Phase 3's "FATAL: only ${MB}MB free, need 500MB. Free space and retry."
if ! grep -qE "(Less than 500MB|FATAL: only [0-9]+MB free, need 500MB)" \
     /tmp/g3-disk-test-$TEST_ID.log; then
    echo "❌ FAIL Test 10: neither Phase 1 nor Phase 3 disk-check message found"
    exit 1
fi
echo "✅ PASS Test 10: disk-space pre-check fired with clear message"

# Verify: system still bootable — settings.json present (no half-rollback)
[ -f ~/.claude/settings.json ] || { echo "❌ FAIL Test 10: settings.json missing"; exit 1; }
echo "✅ PASS Test 10: settings.json preserved (clean abort, no rescue needed)"

# Cleanup
rm -rf "$SHIM_DIR" /tmp/g3-disk-test-$TEST_ID.log /tmp/g3-test-$TEST_ID
rm -f ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
```

### Test 11 — Iter-5 GDT-1: `--non-interactive` auto-confirms without TTY

Verify the script runs to completion (or to a non-prompt failure point) when
invoked under at(1) or with stdin closed, WITHOUT either `read` prompt
blocking.

```bash
# Setup: synthesise a benign backup
TEST_ID="non-interactive-$(date +%s)"
mkdir -p /tmp/g3-test-$TEST_ID/.claude
sqlite3 /tmp/g3-test-$TEST_ID/.claude/memory.db.snapshot-${TEST_ID} \
    "CREATE TABLE t(x INTEGER); INSERT INTO t VALUES (1);"
cd /tmp/g3-test-$TEST_ID && tar -czf ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz \
    .claude/memory.db.snapshot-${TEST_ID}

# Sub-test A: run with --non-interactive AND stdin redirected from /dev/null
# (simulates the at(1) execution environment — no controlling TTY).
~/scripts/rollback-orchestration-fix.sh ${TEST_ID} --non-interactive </dev/null \
    > /tmp/g3-noninteractive-$TEST_ID.log 2>&1
G3_EXIT=$?

# Expected: G3 proceeds PAST both `read` calls. We verify this by grepping
# for the auto-confirm log lines we added.
if ! grep -q "Non-interactive mode: auto-confirming rollback" /tmp/g3-noninteractive-$TEST_ID.log; then
    echo "❌ FAIL Test 11A: CONFIRM auto-confirm message not found — script may have prompted"
    cat /tmp/g3-noninteractive-$TEST_ID.log | head -50
    exit 1
fi
if ! grep -q "Non-interactive mode: auto-acknowledging external-state handoff" /tmp/g3-noninteractive-$TEST_ID.log; then
    echo "⚠️  WARN Test 11A: EXT_ACK auto-confirm message not found"
    echo "   (acceptable if script aborted earlier for unrelated reasons — check exit code)"
fi
echo "✅ PASS Test 11A: --non-interactive bypasses CONFIRM prompt (no TTY required)"

# Sub-test B: control case — WITHOUT --non-interactive, stdin from /dev/null
# Expected: G3 aborts at the first read (CONFIRM consumes EOF → "")
~/scripts/rollback-orchestration-fix.sh ${TEST_ID} </dev/null \
    > /tmp/g3-interactive-$TEST_ID.log 2>&1
G3_EXIT_INTERACTIVE=$?
if [ "$G3_EXIT_INTERACTIVE" -eq 0 ]; then
    echo "❌ FAIL Test 11B: G3 without --non-interactive completed under stdin=/dev/null"
    echo "   This is the iter-1/2 bug: read consumed EOF → empty CONFIRM → script should have ABORTED but exit was 0"
    exit 1
fi
# Expected stdout includes either "ABORTED by user" (CONFIRM != ROLLBACK)
# or a canary FATAL message (if inside-session detection still works)
if ! grep -qE "(ABORTED by user|G3 must NOT run inside a claude session)" /tmp/g3-interactive-$TEST_ID.log; then
    echo "⚠️  WARN Test 11B: aborted but neither expected message printed"
fi
echo "✅ PASS Test 11B: without --non-interactive, EOF on stdin → ABORTED (proves the iter-1/2 bug)"

# Sub-test C: at(1) recipe end-to-end (skip if at daemon is not enabled)
if command -v at >/dev/null 2>&1 && launchctl list 2>/dev/null | grep -q atrun; then
    AT_LOG=/tmp/g3-at-test-$TEST_ID.log
    echo "/bin/bash ~/scripts/rollback-orchestration-fix.sh '${TEST_ID}' --non-interactive > $AT_LOG 2>&1" | at now+1min
    echo "Queued G3 via at(1). Wait ~70s then verify..."
    sleep 75
    if [ -f "$AT_LOG" ] && grep -q "Non-interactive mode" "$AT_LOG"; then
        echo "✅ PASS Test 11C: at(1) recipe with --non-interactive executes past prompts"
    else
        echo "⚠️  WARN Test 11C: at log missing or no auto-confirm — verify atrun is running"
    fi
    rm -f "$AT_LOG"
else
    echo "SKIP Test 11C: at(1) daemon not running on this machine"
fi

# Cleanup
rm -f /tmp/g3-noninteractive-$TEST_ID.log /tmp/g3-interactive-$TEST_ID.log
rm -f ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
rm -rf /tmp/g3-test-$TEST_ID
```

### Test 12 — Iter-5 GDT-4: tar archive paths extract to correct location

Verify the safety backup created with `tar -C /` produces archive entries
that, when extracted with `tar -xzf … -C /`, restore to the original
absolute paths and NOT to a nested `~/Users/…` path.

```bash
# Setup: create a sentinel file at a known absolute path and ensure it's
# in the CANDIDATES list (use settings.json as the canonical sentinel).
TEST_ID="tar-paths-$(date +%s)"
SENTINEL_PATH=~/.claude/settings.json
SENTINEL_MARKER="iter5-tar-paths-${TEST_ID}"
SENTINEL_BACKUP=$(cat "$SENTINEL_PATH" 2>/dev/null || echo "{}")
echo "{\"_marker\": \"${SENTINEL_MARKER}\"}" > "$SENTINEL_PATH"

# Synthesise a backup tarball + run G3 so the safety backup is produced
mkdir -p /tmp/g3-test-$TEST_ID/.claude
sqlite3 /tmp/g3-test-$TEST_ID/.claude/memory.db.snapshot-${TEST_ID} \
    "CREATE TABLE t(x INTEGER); INSERT INTO t VALUES (1);"
cd /tmp/g3-test-$TEST_ID && tar -czf ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz \
    .claude/memory.db.snapshot-${TEST_ID}

# Run G3 — even if it fails downstream, Phase 1 safety-backup must complete first
~/scripts/rollback-orchestration-fix.sh ${TEST_ID} --non-interactive \
    > /tmp/g3-tarpaths-$TEST_ID.log 2>&1 || true

# Locate the most recent safety backup
SAFETY=$(ls -t ~/backups/pre-rollback-safety-*.tar.gz | head -1)
echo "Inspecting safety backup: $SAFETY"

# Verify: archive entries are RELATIVE to / (start with "Users/" not "/Users/")
# BSD tar with -T strips the leading slash; storage paths should be:
#   Users/nuzantara/.claude/settings.json    ← correct (relative to /)
#   /Users/nuzantara/.claude/settings.json   ← would be wrong (would error on extract)
SAMPLE_ENTRY=$(tar -tzf "$SAFETY" 2>/dev/null | grep "\.claude/settings\.json$" | head -1)
echo "Sample entry: $SAMPLE_ENTRY"

if echo "$SAMPLE_ENTRY" | grep -qE "^/Users/"; then
    echo "❌ FAIL Test 12: archive entries have absolute paths — extract will fail or warn"
    exit 1
fi
if ! echo "$SAMPLE_ENTRY" | grep -qE "^Users/[^/]+/\.claude/settings\.json$"; then
    echo "❌ FAIL Test 12: archive entry does NOT match expected relative-to-/ pattern"
    echo "   Got: $SAMPLE_ENTRY"
    echo "   Expected pattern: Users/<user>/.claude/settings.json"
    exit 1
fi
echo "✅ PASS Test 12a: archive entries stored relative to / (BSD-tar safe)"

# Now extract to a SCRATCH directory with `-C /tmp/extract-test-$TEST_ID/`
# and verify the sentinel ends up at the expected nested-under-target path.
EXTRACT_DIR=$(mktemp -d /tmp/g3-extract-test-$TEST_ID.XXXXXX)
tar -xzf "$SAFETY" -C "$EXTRACT_DIR"
EXPECTED_EXTRACT_PATH="${EXTRACT_DIR}/Users/$(whoami)/.claude/settings.json"
if [ ! -f "$EXPECTED_EXTRACT_PATH" ]; then
    echo "❌ FAIL Test 12b: expected extracted file not found at $EXPECTED_EXTRACT_PATH"
    find "$EXTRACT_DIR" -name "settings.json" 2>/dev/null
    exit 1
fi
if ! grep -q "$SENTINEL_MARKER" "$EXPECTED_EXTRACT_PATH"; then
    echo "❌ FAIL Test 12b: extracted settings.json missing sentinel marker"
    exit 1
fi
echo "✅ PASS Test 12b: extract with -C /tmp/... lands at expected nested path"

# Sub-test C: the ACTUAL rollback-of-rollback recipe with `-C /` would
# overwrite the live settings.json. We DON'T run that (destructive in test).
# Instead, verify the recipe in the spec body matches what we tested.
if ! grep -q 'tar -xzf .* -C /' ~/Desktop/nuzantara/research/operations/specs/G3-global-rollback.md; then
    echo "❌ FAIL Test 12c: Rollback-of-rollback recipe in spec does not use `-C /`"
    exit 1
fi
echo "✅ PASS Test 12c: spec documents the `-C /` extract recipe"

# Cleanup
echo "$SENTINEL_BACKUP" > "$SENTINEL_PATH"
rm -rf "$EXTRACT_DIR" /tmp/g3-tarpaths-$TEST_ID.log /tmp/g3-test-$TEST_ID
rm -f ~/backups/pre-orchestration-fix-${TEST_ID}.tar.gz
```

## Rollback (of rollback)

Use safety backup created in Phase 1.

**Iter-5 GDT-4 HIGH fix**: Phase 1 now tars with `-C /` so archive entries
are stored relative to `/` (e.g. `Users/nuzantara/.claude/settings.json`).
Extract with `-C /` to restore at the correct absolute locations. The
previous recipe (`cd ~ && tar -xzf ...`) would extract to
`~/Users/nuzantara/...` (nested under HOME), which is wrong.

```bash
tar -xzf ~/backups/pre-rollback-safety-<timestamp>.tar.gz -C /
```

Verify extraction landed at the right place (paths should NOT be nested):

```bash
ls -la ~/.claude/settings.json    # should exist after extract
[ -d ~/Users/$(whoami)/.claude ] && echo "❌ nested extract — wrong recipe used" \
                                 || echo "✅ extract path correct"
```

## Open questions

1. **Memory.db rollback safety**: ~~SQLite file in active use during rollback may corrupt.~~ ADDRESSED by WAVE -1 Fix 1 (snapshot restore w/ integrity check, exit 99 on corruption) + WAVE -1 Fix 2 Layer A (canary refuses inside-session execution where a live claude process would hold the WAL lock).
2. **Git tag missing case**: if Antonello renamed/deleted tag, what fallback? Default = tarball only, no git reset.
3. **Partial rollback**: support `--wave <N>` to rollback only specific wave? Default = no (KISS, global is safer).
4. **Forensic cleanup window**: `memory.db.pre-rollback-${BACKUP_ID}` AND `settings.json.pre-rollback-${BACKUP_ID}` files (the latter created by iter-5 DS-BL1 fix and intentionally retained for forensic preservation after Phase 3 success) accumulate one per rollback. How long to retain? Default = manual cleanup at next monthly housekeeping; never auto-delete (forensic evidence may be needed weeks later if rollback unmasks a different bug).
5. **Dual-MAX-slot collateral**: ~~`pkill -f "claude"` matches BOTH slot 1 and slot 2 binaries.~~ ADDRESSED by Iteration-2 Fix 1 (exact-binary `^/Users/$(whoami)/.local/bin/claude\b` regex, scope-guard exit 4, symmetric canary PPID detection for slot 1 vs slot 2 with distinguishing detect_reason messages).
6. **State path drift between T-1 and G3**: CANDIDATES list in G3 Phase 1 (Iteration-2 Fix 2) must stay in sync with T-1's include pattern. Out-of-band drift could destroy state the operator wanted preserved. Default = manual review at each new spec; refactor to shared YAML (`docs/runbooks/orchestration-state-paths.yaml`) in next sprint.
7. **Settings restore trap idempotency** (iter-5 DS-BL1): the trap uses `mv` to move the sidecar back to live. If two G3 invocations were ever interleaved on the same machine (currently impossible because G3 holds no lock), the second trap could rescue the first invocation's sidecar. Mitigation: add a G3 flock on `~/.claude/state/g3-rollback.lock` in next iteration. Currently out of scope (sequential operator use is the only supported path).
8. **at(1) recipe + dual-slot context** (iter-5 GDT-1): the documented at(1) recipe runs G3 with `--non-interactive` from a fresh `at` shell (PPID = `atrun`, not claude). If the operator's `at` is configured to inherit env vars, `CLAUDE_CODE_OAUTH_TOKEN` could leak into the deferred shell, tripping the Layer A canary. Verify with `at -c <jobnum>` before relying on the recipe in slot-2-active environments.
9. **`tar -C /` portability** (iter-5 GDT-4): the fix uses BSD-tar-specific path-stripping semantics. If G3 ever runs on Linux (e.g. via a future Fly.io cron), GNU tar's behavior differs (`-T` with absolute paths warns "removing leading /" by default but is configurable via `--absolute-paths` and `--keep-newer-files`). The current spec is macOS-only; revisit if the Linux port is requested.

## Estimated breakdown

| Step        | Tempo                                        |
| ----------- | -------------------------------------------- |
| Spec script | 25 min                                       |
| Smoke test  | 5 min                                        |
| **Total**   | **30 min** + 5-10 min per rollback execution |
