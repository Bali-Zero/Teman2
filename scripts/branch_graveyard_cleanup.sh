#!/bin/bash
# branch_graveyard_cleanup.sh - SOTA L4 2026-05-24
#
# Identify stale branches on origin and (optionally) delete merged-safe ones.
#
# Categories:
#   1. Merged & deletable     : branch SHA is an ancestor of main, any age, safe
#   2. Content-on-main & del.  : SHA NOT ancestor BUT `git diff main...branch` is
#                                empty or pure-deletion -> squash-merged / reworked
#                                onto main / strict-subset; safe to delete. This is
#                                the MANDATORY antidote to the "git cherry says +
#                                so it must be unmerged" trap (see content_on_main).
#   3. Zombie claude/*        : claude/* branch, >30d, content NOT on main -> report
#   4. Stale others           : any branch, >90d, content NOT on main -> report
#
# Defaults to DRY-RUN. Use --apply to delete categories 1 AND 2 (both verified
# safe by CONTENT). NEVER deletes category 3 or 4 without explicit human review.
#
# Output: formatted Markdown report on stdout + optional --output <file>
#
# Kill-switch: BRANCH_CLEANUP_ENABLED=false -> exit 0
#
# Bash 3.2 compatible (macOS default /bin/bash). No mapfile, no associative
# arrays. State is kept in tab-separated tmp files under /tmp.

set -uo pipefail

# === Kill-switch ===
if [[ "${BRANCH_CLEANUP_ENABLED:-true}" == "false" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] branch_cleanup disabled via BRANCH_CLEANUP_ENABLED=false" >&2
    exit 0
fi

# === Args ===
APPLY=false
OUTPUT_FILE=""
REMOTE="${BRANCH_CLEANUP_REMOTE:-origin}"
MAIN_BRANCH="${BRANCH_CLEANUP_MAIN:-main}"
CLAUDE_AGE_DAYS="${BRANCH_CLEANUP_CLAUDE_AGE_DAYS:-30}"
STALE_AGE_DAYS="${BRANCH_CLEANUP_STALE_AGE_DAYS:-90}"
TELEGRAM_ALERT=false
TELEGRAM_THRESHOLD="${BRANCH_CLEANUP_TELEGRAM_THRESHOLD:-10}"

usage() {
    cat <<EOF
Usage: $0 [--apply] [--output <file>] [--telegram-alert]

Options:
  --apply             Execute deletion of categories 1 + 2 (verified safe by content)
  --output <file>     Write report to file (default: stdout only)
  --telegram-alert    Send Telegram alert if zombie count > $TELEGRAM_THRESHOLD
  --help              Show this help

Env vars:
  BRANCH_CLEANUP_ENABLED=false        Disable entirely
  BRANCH_CLEANUP_REMOTE=origin
  BRANCH_CLEANUP_MAIN=main
  BRANCH_CLEANUP_CLAUDE_AGE_DAYS=30
  BRANCH_CLEANUP_STALE_AGE_DAYS=90
  BRANCH_CLEANUP_TELEGRAM_THRESHOLD=10
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply) APPLY=true; shift ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        --telegram-alert) TELEGRAM_ALERT=true; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown arg: $1" >&2; usage; exit 64 ;;
    esac
done

# Path-aware: M5 user is `balizero` (/Users/balizero), Pro/Mini are `nuzantara`.
# A hardcoded /Users/nuzantara/... is DEAD on M5 (superscar #1 HOME-fork). Resolve
# from the repo containing THIS script unless overridden.
if [[ -n "${REPOMAP_REPO_ROOT:-}" ]]; then
    REPO_ROOT="$REPOMAP_REPO_ROOT"
else
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "$REPO_ROOT" || { echo "FATAL: cd $REPO_ROOT failed" >&2; exit 1; }

NOW_EPOCH=$(date +%s)
TODAY=$(date +%Y-%m-%d)

# === Fetch latest remote state ===
echo "[branch_cleanup] fetching $REMOTE (with prune)..." >&2
git fetch "$REMOTE" --prune --quiet 2>&1 || {
    echo "[branch_cleanup] WARN: git fetch failed; proceeding with stale local refs" >&2
}

# === Resolve main ref ===
MAIN_REF="$REMOTE/$MAIN_BRANCH"
if ! git rev-parse --verify "$MAIN_REF" >/dev/null 2>&1; then
    echo "FATAL: $MAIN_REF not found" >&2
    exit 1
fi
MAIN_SHA=$(git rev-parse "$MAIN_REF")

# === Tmp state files (bash 3.2 portable, no mapfile/arrays) ===
BRANCHES_TSV="/tmp/branch_cleanup_branches.$$"
MERGED_TSV="/tmp/branch_cleanup_merged.$$"
CONTENT_TSV="/tmp/branch_cleanup_content.$$"
ZOMBIE_TSV="/tmp/branch_cleanup_zombie.$$"
STALE_TSV="/tmp/branch_cleanup_stale.$$"
REPORT_TMP="/tmp/branch_cleanup_report.$$"

cleanup_tmp() {
    rm -f "$BRANCHES_TSV" "$MERGED_TSV" "$CONTENT_TSV" "$ZOMBIE_TSV" "$STALE_TSV" "$REPORT_TMP"
}
trap cleanup_tmp EXIT

# === Enumerate remote branches with metadata ===
# Format: <refname>\t<committerdate:unix>\t<sha>
# Filter out: main, the bare remote HEAD symref, and any */HEAD entries.
git for-each-ref \
    --format='%(refname:short)%09%(committerdate:unix)%09%(objectname:short)' \
    "refs/remotes/$REMOTE/" \
| awk -F'\t' -v main="$REMOTE/$MAIN_BRANCH" -v bare="$REMOTE" '
    $1 != main && $1 != bare && $1 !~ /\/HEAD$/ { print }
' > "$BRANCHES_TSV"

# === Content-on-main check (MANDATORY — superscar #1/#9 antidote) ===
#
# WHY THIS EXISTS — read before touching:
#   `git merge-base --is-ancestor` (and `git cherry`) classify a branch as
#   "not on main" the moment the branch SHA is not an ancestor — but a
#   SQUASH-merged branch, or one whose content reached main via rework, is
#   ALREADY ON MAIN by content while its SHA is NOT an ancestor and its
#   patch-id diverges. Trusting the ancestor/cherry signal alone produces a
#   graveyard report that is ~80% stale (verified 2026-06-27: a 28-branch
#   "orphan report" had ~5 truly-live branches; the rest were squash-merged
#   or reworked onto main, several REGRESSING published content if rebased).
#
# THE RULE (mandatory, never bypass): a branch is deletable-safe ONLY when its
# CONTENT is on main — i.e. `git diff origin/main...<branch>` is EMPTY. Verify
# by CONTENT, never by patch-equivalence / ancestor-only. A non-empty diff that
# is purely DELETIONS (branch is a strict subset / older revision of main) is
# ALSO content-on-main: keeping it would only regress. This function encodes
# exactly that test.
#
# Returns 0 (content already on main, safe to delete) / 1 (genuine unmerged work).
content_on_main() {
    local branch="$1"
    # Fast path: --quiet exits 0 on EMPTY diff (stops at first hunk, never
    # materializes output) => every line of the branch is already on main
    # (covers squash-merge, rework, cherry-picked-elsewhere). Authoritative.
    if git diff --quiet "$MAIN_REF...$branch" 2>/dev/null; then
        return 0
    fi
    # Non-empty diff. Only ONE more question matters: does the branch ADD any
    # line main lacks? If it adds nothing (pure-deletion / strict-subset / stale
    # revision), it is still fully represented on main and rebasing it would only
    # regress => treat as content-on-main. `git diff --numstat` is cheap (no
    # context lines); summing the "added" column is enough — 0 added => subset.
    local added
    added=$(git diff --numstat "$MAIN_REF...$branch" 2>/dev/null | awk '{a += $1} END {print a + 0}')
    [[ "$added" -eq 0 ]]
}

# === Classify ===
: > "$MERGED_TSV"
: > "$CONTENT_TSV"
: > "$ZOMBIE_TSV"
: > "$STALE_TSV"

while IFS=$'\t' read -r branch ts sha; do
    [[ -z "$branch" ]] && continue
    age_days=$(( (NOW_EPOCH - ts) / 86400 ))
    short="${branch#$REMOTE/}"
    # Merged check via merge-base ancestor lookup against main (fast path:
    # true/ff merges where the branch SHA IS an ancestor of main).
    if git merge-base --is-ancestor "$sha" "$MAIN_SHA" 2>/dev/null; then
        printf '%s\t%s\t%s\t%s\n' "$branch" "$age_days" "$sha" "$short" >> "$MERGED_TSV"
        continue
    fi
    # Ancestor-check FAILED — but the content may still be on main via squash /
    # rework. MANDATORY second check by CONTENT, never trust ancestor alone.
    if content_on_main "$branch"; then
        printf '%s\t%s\t%s\t%s\n' "$branch" "$age_days" "$sha" "$short" >> "$CONTENT_TSV"
        continue
    fi
    # claude/* zombies
    if [[ "$short" == claude/* ]] && (( age_days >= CLAUDE_AGE_DAYS )); then
        printf '%s\t%s\t%s\t%s\n' "$branch" "$age_days" "$sha" "$short" >> "$ZOMBIE_TSV"
        continue
    fi
    # Other stale unmerged
    if (( age_days >= STALE_AGE_DAYS )); then
        printf '%s\t%s\t%s\t%s\n' "$branch" "$age_days" "$sha" "$short" >> "$STALE_TSV"
    fi
done < "$BRANCHES_TSV"

# === Sort each category by age descending (in-place) ===
for f in "$MERGED_TSV" "$CONTENT_TSV" "$ZOMBIE_TSV" "$STALE_TSV"; do
    if [[ -s "$f" ]]; then
        sort -t$'\t' -k2 -n -r -o "$f" "$f"
    fi
done

MERGED_COUNT=$(wc -l < "$MERGED_TSV" | tr -d ' ')
CONTENT_COUNT=$(wc -l < "$CONTENT_TSV" | tr -d ' ')
ZOMBIE_COUNT=$(wc -l < "$ZOMBIE_TSV" | tr -d ' ')
STALE_COUNT=$(wc -l < "$STALE_TSV" | tr -d ' ')

# === Build report ===
emit_section() {
    local title="$1" tsv="$2" verb="$3"
    echo "### $title"
    if [[ ! -s "$tsv" ]]; then
        echo "_(none)_"
    else
        while IFS=$'\t' read -r branch age sha short; do
            echo "  - \`$branch\` ($verb ${age}d ago, $sha)"
        done < "$tsv"
    fi
    echo ""
}

{
    echo "## Branch Graveyard Report ($TODAY)"
    echo ""
    echo "Repository: \`$REPO_ROOT\`"
    echo "Remote: \`$REMOTE\`  Main: \`$MAIN_BRANCH\` (\`$MAIN_SHA\`)"
    if $APPLY; then
        echo "Mode: APPLY (category 1 deletions live)"
    else
        echo "Mode: DRY-RUN"
    fi
    echo ""
    echo "Summary:"
    echo "- Merged & deletable (SHA ancestor of main): $MERGED_COUNT"
    echo "- Content-on-main & deletable (squash/rework, verified by diff): $CONTENT_COUNT"
    echo "- Zombie claude/* (>${CLAUDE_AGE_DAYS}d, content NOT on main): $ZOMBIE_COUNT"
    echo "- Stale others (>${STALE_AGE_DAYS}d, content NOT on main): $STALE_COUNT"
    echo ""

    emit_section "Merged & deletable (SHA ancestor of main, safe to remove)" "$MERGED_TSV" "merged,"
    emit_section "Content-on-main & deletable (squash/rework — diff vs main is empty or pure-deletion, safe to remove)" "$CONTENT_TSV" "last commit"
    emit_section "Zombie claude/* (>${CLAUDE_AGE_DAYS}d, content NOT on main) — REPORT ONLY" "$ZOMBIE_TSV" "last commit"
    emit_section "Stale others (>${STALE_AGE_DAYS}d, content NOT on main) — REPORT ONLY" "$STALE_TSV" "last commit"
} > "$REPORT_TMP"

cat "$REPORT_TMP"
if [[ -n "$OUTPUT_FILE" ]]; then
    cp "$REPORT_TMP" "$OUTPUT_FILE"
    echo "[branch_cleanup] report written to $OUTPUT_FILE" >&2
fi

# === Apply phase: delete BOTH safe categories (ancestor-merged + content-on-main) ===
# Content-on-main is verified by `git diff` being empty / pure-deletion, so it is
# exactly as safe to delete as an ancestor-merge — never trust patch-id/ancestor
# alone (see content_on_main() above). Zombie/stale stay REPORT-ONLY.
delete_tsv() {
    local tsv="$1" label="$2" count
    count=$(wc -l < "$tsv" | tr -d ' ')
    [[ "$count" -eq 0 ]] && return 0
    echo "" >&2
    echo "[branch_cleanup] --apply: deleting $count $label branches on $REMOTE..." >&2
    while IFS=$'\t' read -r branch age sha short; do
        [[ -z "$short" ]] && continue
        echo "  -> git push $REMOTE --delete $short" >&2
        if git push "$REMOTE" --delete "$short" >&2 2>&1; then
            echo "     OK" >&2
        else
            echo "     FAIL (continuing)" >&2
        fi
    done < "$tsv"
}

if $APPLY; then
    if [[ "$MERGED_COUNT" -eq 0 && "$CONTENT_COUNT" -eq 0 ]]; then
        echo "" >&2
        echo "[branch_cleanup] --apply: nothing to delete." >&2
    else
        delete_tsv "$MERGED_TSV"  "ancestor-merged"
        delete_tsv "$CONTENT_TSV" "content-on-main (squash/rework)"
    fi
fi

# === Telegram alert ===
if $TELEGRAM_ALERT && (( ZOMBIE_COUNT > TELEGRAM_THRESHOLD )); then
    if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
        # shellcheck disable=SC1091
        set -a; source "$HOME/.nuzantara-secrets.env"; set +a
    fi
    TG_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
    TG_CHAT="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
    if [[ -n "$TG_TOKEN" && -n "$TG_CHAT" ]]; then
        MSG="Branch graveyard: $ZOMBIE_COUNT claude/* zombies + $STALE_COUNT stale (threshold $TELEGRAM_THRESHOLD). Report: ${OUTPUT_FILE:-stdout-only}"
        curl -sS --max-time 10 \
            -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
            -d "chat_id=${TG_CHAT}" \
            --data-urlencode "text=${MSG}" >/dev/null 2>&1 \
            && echo "[branch_cleanup] telegram alert sent (chat=$TG_CHAT)" >&2 \
            || echo "[branch_cleanup] WARN: telegram alert failed" >&2
    else
        echo "[branch_cleanup] WARN: TELEGRAM_BOT_TOKEN missing; skipping alert" >&2
    fi
fi

# Exit code: 0 always (report-only nature; --apply failures logged but don't fail run).
exit 0
