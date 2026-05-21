---
spec_id: G0
title: External state rollback — Postgres roles, Vercel/Fly remote, MCP registry, npm globals
tier: gate
priority: P0 (companion to G3 global rollback)
effort_estimate: 30 min spec, 10-20 min per rollback execution
status: DRAFT
basis: Gemini panel new_spec G0-external-state-rollback + GPT-5.5 panel B2 ghost state
---

# G0 — External state rollback

## Problem

G3 (global rollback) revertes LOCAL files via tarball + git reset. But state CREATED BY specs that lives EXTERNALLY can't be rolled back by file restore:

- Postgres role `nuzantara_readonly` (created by T3.2 on remote `nuzantara-postgres.flycast`)
- Vercel deployments triggered (T2.4 deploy_to_vercel)
- Fly.io machine restart side effects
- Claude MCP registry mutations (`claude mcp add postgres ...`)
- npm globals installed (Playwright, GitHub server)
- Keychain items added (PG_PASSWORD_RO, GITHUB_PAT)

Repeated G3 rollback/retry cycles without G0 = ghost state accumulation.

## Acceptance criteria

- [ ] `~/scripts/rollback-external-state.sh` exists
- [ ] Reads inventory file from T-1 backup (`external-inventory-${DATE}.txt`)
- [ ] Confirms each external state item with operator before teardown
- [ ] Teardown ordered: MCP unregister → npm uninstall → Keychain delete → Postgres role drop
- [ ] Idempotent (safe to run twice)
- [ ] Logs to `~/.claude/state/external-rollback-<timestamp>.log`

## Implementation

### Step 1 — External state inventory verification

```bash
#!/bin/bash
# G0 — External state rollback
# Reference: research/operations/specs/G0-external-state-rollback.md

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_ID="${1:-}"

if [ -z "$BACKUP_ID" ]; then
    echo "Usage: $0 <backup_id>"
    echo ""
    echo "Available T-1 external inventories:"
    ls -la ~/backups/external-inventory-*.txt 2>/dev/null
    exit 1
fi

INVENTORY=~/backups/external-inventory-${BACKUP_ID}.txt
LOG=~/.claude/state/external-rollback-${TIMESTAMP}.log

if [ ! -f "$INVENTORY" ]; then
    echo "❌ Inventory not found: $INVENTORY"
    exit 1
fi

mkdir -p ~/.claude/state
exec > >(tee -a "$LOG") 2>&1

echo "=== G0 External state rollback ==="
echo "Inventory: $INVENTORY"
echo "Timestamp: $TIMESTAMP"
echo ""
cat "$INVENTORY"
echo ""
echo "===================================="
```

### Step 2 — Phase 1: MCP registry unregister

```bash
echo ""
echo "--- Phase 1: MCP registry teardown ---"
echo "Current MCP servers:"
claude mcp list 2>/dev/null | head -20

# Specs that added MCP servers (review which to remove):
SPECS_ADDED_MCP=(
    "postgres"   # T3.2
    "qdrant"     # T3.2 (alt)
    "playwright" # T2.2
    "github"     # T2.3
    "vercel"     # T2.4 (HTTP)
    "exa"        # R2
)

echo ""
echo "MCP servers to potentially remove (only those added by specs):"
for srv in "${SPECS_ADDED_MCP[@]}"; do
    if claude mcp list 2>/dev/null | grep -q "$srv"; then
        echo "  - $srv (FOUND)"
    fi
done

echo ""
echo "Type 'REMOVE-MCP' to unregister all spec-added MCP servers, 'SKIP' to skip:"
read -r MCP_ACK
if [ "$MCP_ACK" = "REMOVE-MCP" ]; then
    for srv in "${SPECS_ADDED_MCP[@]}"; do
        claude mcp remove "$srv" 2>&1 | tail -1 || true
    done
    echo "✅ MCP servers unregistered"
elif [ "$MCP_ACK" = "SKIP" ]; then
    echo "⚠️ Skipped MCP teardown — manual cleanup required"
else
    echo "ABORTED at MCP phase"
    exit 1
fi
```

### Step 3 — Phase 2: npm globals uninstall

```bash
echo ""
echo "--- Phase 2: npm globals teardown ---"
echo "Current npm globals (filtering spec-related):"
npm ls -g --depth=0 2>/dev/null | grep -iE "playwright|github|vercel|claude" | head -10

PACKAGES_ADDED=(
    "@playwright/mcp"
    "@modelcontextprotocol/server-postgres"
    "@modelcontextprotocol/server-github"
)

echo ""
echo "Type 'REMOVE-NPM' to uninstall spec-added packages, 'SKIP' to skip:"
read -r NPM_ACK
if [ "$NPM_ACK" = "REMOVE-NPM" ]; then
    for pkg in "${PACKAGES_ADDED[@]}"; do
        npm uninstall -g "$pkg" 2>&1 | tail -1 || true
    done
    echo "✅ npm packages uninstalled"
elif [ "$NPM_ACK" = "SKIP" ]; then
    echo "⚠️ Skipped npm teardown"
else
    echo "ABORTED at npm phase"
    exit 1
fi
```

### Step 4 — Phase 3: Keychain teardown

```bash
echo ""
echo "--- Phase 3: Keychain items teardown ---"
echo "Spec-created Keychain items:"

KEYCHAIN_ITEMS=(
    "PG_PASSWORD_RO"          # T3.2
    "GITHUB_PAT"              # T2.3
    "TELEGRAM_BOT_TOKEN"      # G4 (existed before, but check)
)

echo "Items to potentially remove (existence check):"
for item in "${KEYCHAIN_ITEMS[@]}"; do
    if security find-generic-password -s "$item" > /dev/null 2>&1; then
        echo "  - $item (EXISTS)"
    fi
done

echo ""
echo "⚠️ TELEGRAM_BOT_TOKEN may pre-exist before spec execution — handle with care"
echo ""
echo "Type 'REMOVE-KEYCHAIN' to delete spec-created items only (excluding TELEGRAM), 'SKIP' to skip:"
read -r KC_ACK
if [ "$KC_ACK" = "REMOVE-KEYCHAIN" ]; then
    # Only remove items created by these specs, NOT pre-existing
    security delete-generic-password -s "PG_PASSWORD_RO" 2>/dev/null && echo "Removed PG_PASSWORD_RO" || true
    security delete-generic-password -s "GITHUB_PAT" 2>/dev/null && echo "Removed GITHUB_PAT" || true
    # TELEGRAM_BOT_TOKEN intentionally skipped (may pre-exist)
    echo "✅ Keychain spec items removed"
elif [ "$KC_ACK" = "SKIP" ]; then
    echo "⚠️ Skipped Keychain teardown"
else
    echo "ABORTED at Keychain phase"
    exit 1
fi
```

### Step 5 — Phase 4: Postgres role drop (T3.2)

```bash
echo ""
echo "--- Phase 4: Postgres role teardown ---"
echo ""
echo "⚠️ This connects to REMOTE Fly Postgres and DROPs the 'nuzantara_readonly' role."
echo "Connection: postgres://backend_rag_v2@localhost:15432/postgres (via fly-pg-proxy)"
echo ""
echo "Type 'DROP-ROLE' to drop nuzantara_readonly role, 'SKIP' to skip:"
read -r ROLE_ACK
if [ "$ROLE_ACK" = "DROP-ROLE" ]; then
    # Verify proxy is up
    if ! psql "postgres://backend_rag_v2@localhost:15432/postgres" -c "SELECT 1" > /dev/null 2>&1; then
        echo "❌ Cannot connect to fly-pg-proxy. Start it first: ~/scripts/fly-pg-proxy-wrapper.sh"
        exit 1
    fi

    psql "postgres://backend_rag_v2@localhost:15432/postgres" << SQL
-- Revoke grants first (idempotent if already revoked)
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM nuzantara_readonly;
REVOKE USAGE ON SCHEMA public FROM nuzantara_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM nuzantara_readonly;

-- Drop role
DROP ROLE IF EXISTS nuzantara_readonly;

-- Verify
SELECT rolname FROM pg_roles WHERE rolname = 'nuzantara_readonly';
SQL

    # Expected: SELECT rolname returns 0 rows (role gone)
    echo "✅ Postgres role nuzantara_readonly dropped"
elif [ "$ROLE_ACK" = "SKIP" ]; then
    echo "⚠️ Skipped Postgres role teardown — manual cleanup required"
else
    echo "ABORTED at Postgres phase"
    exit 1
fi
```

### Step 6 — Phase 5: Vercel/Fly remote teardown (manual)

```bash
echo ""
echo "--- Phase 5: Vercel/Fly remote ---"
echo ""
echo "⚠️ External cloud state requires MANUAL teardown:"
echo ""
echo "Vercel (if T2.4 ran):"
echo "  - Revoke MCP OAuth: https://claude.ai/settings/integrations → Vercel → Revoke"
echo "  - Recent deployments: check https://vercel.com/nuzantara-2026/<project>/deployments"
echo "    (deploys triggered by spec cannot be 'reverted' — but next manual deploy supersedes)"
echo ""
echo "Fly.io (if any Fly-side changes):"
echo "  - Check fly logs -a nuzantara-rag for restart timestamps"
echo "  - No automated teardown (read-only audit)"
echo ""
echo "Type 'ACKNOWLEDGED' to continue:"
read -r CLOUD_ACK
[ "$CLOUD_ACK" = "ACKNOWLEDGED" ] || { echo "ABORTED"; exit 1; }

echo ""
echo "✅ G0 External state rollback complete"
echo "Log: $LOG"

# Telegram report
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
        -d "text=G0 external state rollback complete $TIMESTAMP. Log: $LOG" > /dev/null
fi
```

## Verification

### Test 1 — Script executable

```bash
ls -la ~/scripts/rollback-external-state.sh
# Expected: -rwxr-xr-x
```

### Test 2 — Inventory check

```bash
# Without backup_id arg
~/scripts/rollback-external-state.sh
# Expected: usage message + list of inventories
```

### Test 3 — Dry-run (with all SKIP)

```bash
~/scripts/rollback-external-state.sh <test-id> << 'EOF'
SKIP
SKIP
SKIP
SKIP
ACKNOWLEDGED
EOF
# Expected: no state modified, only log written
```

### Test 4 — Postgres role idempotent

```bash
# Run drop role twice
psql ... -c "DROP ROLE IF EXISTS nuzantara_readonly"
psql ... -c "DROP ROLE IF EXISTS nuzantara_readonly"
# Expected: both succeed (idempotent)
```

## Rollback (of G0)

G0 is itself a rollback — no rollback of rollback. If teardown was wrong:

- Re-run T3.2 Step 1.5 to recreate role
- Re-run T2.3/T2.4 to re-register MCP

## Open questions

1. **Vercel deploy "rollback"**: Vercel doesn't have rollback semantics, only re-deploy. Document as one-way operation.
2. **Fly.io machine restart**: harmless side effect, no rollback needed.
3. **Order of teardown**: MCP → npm → Keychain → DB role. Reverse of T-1 inventory order. OK?
4. **Idempotency**: each phase uses `... 2>/dev/null || true` for "delete if exists" pattern. OK.
5. **No-op safe**: if T3.2 never ran, "DROP ROLE IF EXISTS" still safe. Same for MCP/npm.

## Estimated breakdown

| Step             | Tempo                                         |
| ---------------- | --------------------------------------------- |
| Script structure | 10 min                                        |
| Phase 1-5 logic  | 15 min                                        |
| Testing          | 5 min                                         |
| **Total**        | **30 min** + 10-20 min per rollback execution |
