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
