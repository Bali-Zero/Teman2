#!/bin/bash
# Shared helpers for Codex-owned automations.
#
# Keep this file small and dependency-light: LaunchAgents source it from
# non-interactive shells.

codex_auto_slug() {
    local raw="${1:-task}"
    printf '%s' "$raw" \
        | tr '[:upper:]' '[:lower:]' \
        | sed -E 's#[^a-z0-9._-]+#-#g; s#/#-#g; s#^-+##; s#-+$##'
}

codex_auto_state_key() {
    local job="${1:?job required}"
    printf 'codex_%s' "$job" | tr '.-' '__'
}

codex_auto_create_run_worktree() {
    local repo_root="${1:?repo root required}"
    local worktrees_root="${2:?worktrees root required}"
    local branch_name="${3:?branch name required}"
    local base_ref="${4:-origin/main}"
    local slug
    local worktree
    local suffix=0

    slug="$(codex_auto_slug "$branch_name")"
    worktree="${worktrees_root}/${slug}"
    mkdir -p "$worktrees_root"

    while [ -e "$worktree" ]; do
        suffix=$((suffix + 1))
        worktree="${worktrees_root}/${slug}-${suffix}"
    done

    if git -C "$repo_root" show-ref --verify --quiet "refs/heads/${branch_name}"; then
        branch_name="${branch_name}-$(date +%Y%m%d_%H%M%S)"
    fi

    git -C "$repo_root" worktree add -q -b "$branch_name" "$worktree" "$base_ref"
    printf '%s\n' "$worktree"
}

codex_auto_write_state() {
    local job="${1:?job required}"
    local outcome="${2:?outcome required}"
    local action="${3:-}"
    local message="${4:-}"
    local branch="${5:-}"
    local worktree="${6:-}"
    local state_dir="${CODEX_AUTOMATION_STATE_DIR:-${HOME}/.agent/decisions/state}"
    local key
    local target
    local tmp

    key="$(codex_auto_state_key "$job")"
    mkdir -p "$state_dir"
    target="${state_dir}/${key}.state.json"
    tmp="${target}.tmp.$$"

    CODEX_AUTO_TARGET="$tmp" \
    CODEX_AUTO_JOB="$job" \
    CODEX_AUTO_OUTCOME="$outcome" \
    CODEX_AUTO_ACTION="$action" \
    CODEX_AUTO_MESSAGE="$message" \
    CODEX_AUTO_BRANCH="$branch" \
    CODEX_AUTO_WORKTREE="$worktree" \
    python3 - <<'PY'
import json
import os
import time
from datetime import datetime, timezone

target = os.environ["CODEX_AUTO_TARGET"]
payload = {
    "job": os.environ["CODEX_AUTO_JOB"],
    "outcome": os.environ["CODEX_AUTO_OUTCOME"],
    "action": os.environ.get("CODEX_AUTO_ACTION", ""),
    "message": os.environ.get("CODEX_AUTO_MESSAGE", ""),
    "branch": os.environ.get("CODEX_AUTO_BRANCH", ""),
    "worktree": os.environ.get("CODEX_AUTO_WORKTREE", ""),
    "ts": time.time(),
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
with open(target, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
    mv "$tmp" "$target"
}

codex_auto_notify() {
    local message="${1:-}"
    local token=""
    local chat_id=""

    [ -n "$message" ] || return 0

    if [ -f "${HOME}/.nuzantara-secrets.env" ]; then
        set -a
        # shellcheck disable=SC1091
        source "${HOME}/.nuzantara-secrets.env" 2>/dev/null || true
        set +a
    fi

    token="${TELEGRAM_BOT_TOKEN:-}"
    chat_id="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ZERO_CHAT_ID:-${TELEGRAM_ADMIN_CHAT_ID:-}}}"
    [ -n "$token" ] && [ -n "$chat_id" ] || return 0

    curl -s --max-time 5 \
        -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -d chat_id="${chat_id}" \
        --data-urlencode "text=${message}" \
        > /dev/null 2>&1 || true
}

codex_auto_ensure_runtime_worktree() {
    local primary_repo="${1:?primary repo required}"
    local runtime_repo="${2:?runtime repo required}"
    local base_ref="${3:-origin/main}"

    if git -C "$runtime_repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        return 0
    fi

    if [ -e "$runtime_repo" ] && [ -n "$(find "$runtime_repo" -mindepth 1 -maxdepth 1 2>/dev/null | head -1)" ]; then
        printf 'Runtime path exists but is not a git worktree: %s\n' "$runtime_repo" >&2
        return 1
    fi

    mkdir -p "$(dirname "$runtime_repo")"
    git -C "$primary_repo" fetch origin main >/dev/null 2>&1 || true
    git -C "$primary_repo" worktree add --detach "$runtime_repo" "$base_ref" >/dev/null
}
