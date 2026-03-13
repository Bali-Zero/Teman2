#!/usr/bin/env bash
# ============================================================
# nz-connect — Nuzantara Pro-Air Bilateral Sync
# Works from both Pro and Air. Uses mDNS (ssh pro / ssh air).
# ============================================================
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[nz]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[!!]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*"; }

# ---- Detect machine ----
WHOAMI=$(whoami)
HOSTNAME_SHORT=$(hostname -s)

if [[ "$WHOAMI" == "nuzantara" ]]; then
    MACHINE="Pro"
    PEER="air"
    LOCAL_REPO="$HOME/Desktop/nuzantara"
    PEER_REPO="~/Projects/nuzantara"
elif [[ "$WHOAMI" == "antonellosiano" ]]; then
    MACHINE="Air"
    PEER="pro"
    LOCAL_REPO="$HOME/Projects/nuzantara"
    PEER_REPO="~/Desktop/nuzantara"
else
    err "Unknown machine: $WHOAMI@$HOSTNAME_SHORT"
    exit 1
fi

log "Machine: ${MACHINE} ($WHOAMI@$HOSTNAME_SHORT)"

# ---- Check SSH to peer ----
log "Checking SSH to ${PEER}..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$PEER" 'echo ok' &>/dev/null; then
    err "Cannot reach ${PEER} via SSH. Are both machines on the same network?"
    exit 1
fi
PEER_HOST=$(ssh -o ConnectTimeout=3 "$PEER" 'hostname -s' 2>/dev/null)
ok "Peer reachable: ${PEER} ($PEER_HOST)"

# ---- Git status ----
cd "$LOCAL_REPO"

# Stash local changes if dirty
LOCAL_DIRTY=false
if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet HEAD 2>/dev/null; then
    LOCAL_DIRTY=true
    warn "Local repo has uncommitted changes — stashing..."
    git stash push -m "nz-connect auto-stash $(date +%Y%m%d-%H%M%S)" --include-untracked
fi

# Fetch origin
log "Fetching origin..."
git fetch origin --quiet 2>/dev/null || warn "Could not fetch origin (offline?)"

# Get commit hashes
LOCAL_HEAD=$(git rev-parse HEAD)
LOCAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)
ORIGIN_HEAD=$(git rev-parse origin/"$LOCAL_BRANCH" 2>/dev/null || echo "unknown")
PEER_HEAD=$(ssh -o ConnectTimeout=5 "$PEER" "cd $PEER_REPO && git rev-parse HEAD" 2>/dev/null || echo "unknown")
PEER_BRANCH=$(ssh -o ConnectTimeout=5 "$PEER" "cd $PEER_REPO && git rev-parse --abbrev-ref HEAD" 2>/dev/null || echo "unknown")

LOCAL_SHORT=$(git rev-parse --short HEAD)
ORIGIN_SHORT=$(git rev-parse --short origin/"$LOCAL_BRANCH" 2>/dev/null || echo "???")
PEER_SHORT=$(echo "$PEER_HEAD" | cut -c1-7)

log "Branch: $LOCAL_BRANCH"
log "Local:  $LOCAL_SHORT"
log "Origin: $ORIGIN_SHORT"
log "Peer:   $PEER_SHORT ($PEER_BRANCH on $PEER)"

# ---- Determine sync action ----
if [[ "$LOCAL_HEAD" == "$PEER_HEAD" && "$LOCAL_HEAD" == "$ORIGIN_HEAD" ]]; then
    ok "All in sync! Nothing to do."

elif [[ "$LOCAL_HEAD" == "$PEER_HEAD" && "$LOCAL_HEAD" != "$ORIGIN_HEAD" ]]; then
    # Both machines same commit, but origin differs
    if git merge-base --is-ancestor "$ORIGIN_HEAD" "$LOCAL_HEAD" 2>/dev/null; then
        log "Local & peer ahead of origin. Pushing..."
        git push origin "$LOCAL_BRANCH"
        ok "Pushed to origin."
    else
        log "Origin ahead of local & peer. Pulling..."
        git pull --rebase origin "$LOCAL_BRANCH"
        ok "Pulled from origin. Syncing peer..."
        ssh -o ConnectTimeout=5 "$PEER" "cd $PEER_REPO && git fetch origin --quiet && git pull --rebase origin $LOCAL_BRANCH" 2>/dev/null
        ok "Peer synced."
    fi

elif [[ "$LOCAL_HEAD" != "$PEER_HEAD" ]]; then
    # Machines out of sync — determine who's ahead
    LOCAL_AHEAD=false
    PEER_AHEAD=false

    if git merge-base --is-ancestor "$PEER_HEAD" "$LOCAL_HEAD" 2>/dev/null; then
        LOCAL_AHEAD=true
    fi
    if git merge-base --is-ancestor "$LOCAL_HEAD" "$PEER_HEAD" 2>/dev/null; then
        PEER_AHEAD=true
    fi

    if [[ "$LOCAL_AHEAD" == true && "$PEER_AHEAD" == false ]]; then
        log "Local ($MACHINE) is ahead. Pushing to origin, then pulling on peer..."
        git push origin "$LOCAL_BRANCH" 2>/dev/null || warn "Push failed (may need manual resolve)"
        ssh -o ConnectTimeout=5 "$PEER" "cd $PEER_REPO && git fetch origin --quiet && git pull --rebase origin $LOCAL_BRANCH" 2>/dev/null
        ok "Peer synced to local."

    elif [[ "$PEER_AHEAD" == true && "$LOCAL_AHEAD" == false ]]; then
        log "Peer ($PEER) is ahead. Pushing from peer, then pulling locally..."
        ssh -o ConnectTimeout=5 "$PEER" "cd $PEER_REPO && git push origin $PEER_BRANCH" 2>/dev/null || warn "Peer push failed"
        git pull --rebase origin "$LOCAL_BRANCH"
        ok "Local synced to peer."

    else
        # Diverged — both have unique commits
        warn "DIVERGED: both machines have unique commits!"
        log "Attempting merge via origin..."

        # Push local first
        git push origin "$LOCAL_BRANCH" 2>/dev/null || true

        # Pull peer's changes
        ssh -o ConnectTimeout=5 "$PEER" "cd $PEER_REPO && git push origin $PEER_BRANCH" 2>/dev/null || true

        # Now pull everything
        git fetch origin --quiet
        if ! git pull --rebase origin "$LOCAL_BRANCH"; then
            warn "Rebase conflict detected. Checking for data file conflicts..."

            # Auto-resolve known data files with --theirs
            CONFLICT_FILES=$(git diff --name-only --diff-filter=U 2>/dev/null || true)
            DATA_CONFLICTS=false
            for f in $CONFLICT_FILES; do
                if [[ "$f" == *"bali-intel-scraper/data/"* || "$f" == *"published_articles.json"* ]]; then
                    log "Auto-resolving data file: $f (using theirs)"
                    git checkout --theirs "$f"
                    git add "$f"
                    DATA_CONFLICTS=true
                fi
            done

            REMAINING=$(git diff --name-only --diff-filter=U 2>/dev/null || true)
            if [[ -n "$REMAINING" ]]; then
                err "Unresolved conflicts in:"
                echo "$REMAINING"
                err "Fix manually, then: git rebase --continue"
                exit 1
            fi

            if [[ "$DATA_CONFLICTS" == true ]]; then
                git rebase --continue 2>/dev/null || git commit --no-edit 2>/dev/null || true
                ok "Data conflicts auto-resolved."
            fi
        fi

        # Sync peer
        ssh -o ConnectTimeout=5 "$PEER" "cd $PEER_REPO && git fetch origin --quiet && git reset --hard origin/$PEER_BRANCH" 2>/dev/null
        ok "Both machines synced via origin."
    fi
fi

# ---- Restore stash if needed ----
if [[ "$LOCAL_DIRTY" == true ]]; then
    log "Restoring stashed changes..."
    git stash pop || warn "Stash pop failed — check 'git stash list'"
fi

# ---- Final status ----
echo ""
LOCAL_FINAL=$(git log --oneline -1)
PEER_FINAL=$(ssh -o ConnectTimeout=3 "$PEER" "cd $PEER_REPO && git log --oneline -1" 2>/dev/null || echo "???")

if [[ "$LOCAL_FINAL" == "$PEER_FINAL" ]]; then
    ok "SYNC COMPLETE"
    echo -e "  ${GREEN}Local:${NC} $LOCAL_FINAL"
    echo -e "  ${GREEN}Peer:${NC}  $PEER_FINAL"
else
    warn "Still out of sync (may need manual intervention)"
    echo -e "  ${YELLOW}Local:${NC} $LOCAL_FINAL"
    echo -e "  ${YELLOW}Peer:${NC}  $PEER_FINAL"
fi
