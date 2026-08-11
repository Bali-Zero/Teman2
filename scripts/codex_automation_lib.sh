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

# A bare `git worktree add` copies no UNTRACKED state, so the runtime worktree has
# no `apps/backend-rag/.venv`. The path-aware pre-push gate needs that venv to run
# the backend suite and is FAIL-CLOSED: suite required + unrunnable = refuse, with
# "PUSH NOT VERIFIED LOCALLY". Measured on Pro 2026-08-10: nightly_autofix_ci died
# at the push on 11 of 14 days while its 14 Telegram alerts said only "Exit: 1"
# (the gate's own message even names the cure: "symlink it from the main checkout,
# or create the worktree via scripts/agent_start.py").
#
# This is deliberately NOT the interactive broker's SYMLINK_TARGETS.  The broker
# receives a human-selected task in an already trusted checkout; this organ checks
# out a failed branch and feeds its log to an unattended Codex run.  It needs only
# the backend virtualenv for the mandatory pre-push suite.  Lending `.env`, either
# node_modules tree, or Husky's generated dispatcher would let branch-controlled
# code read credentials or control the outer push.  Keep this fixed, not env-
# configurable: a cron environment must not be able to widen the trust boundary.
CODEX_RUNTIME_LINKS="apps/backend-rag/.venv"

codex_auto_runtime_registered() {
    local primary_repo="${1:?primary repo required}"
    local runtime_repo="${2:?runtime repo required}"
    local primary_root runtime_top runtime_root

    primary_root="$(git -C "$primary_repo" rev-parse --show-toplevel 2>/dev/null)" || return 1
    primary_root="$(cd "$primary_root" && pwd -P)" || return 1
    runtime_top="$(git -C "$runtime_repo" rev-parse --show-toplevel 2>/dev/null)" || return 1
    runtime_root="$(cd "$runtime_top" && pwd -P)" || return 1

    # `git -C child rev-parse` walks up to the primary checkout.  A runtime must
    # be its OWN top-level worktree, never the primary or a symlink resolving to it.
    [ "$runtime_root" != "$primary_root" ] || return 1
    [ "$runtime_root" = "$(cd "$runtime_repo" && pwd -P)" ] || return 1
    git -C "$primary_root" worktree list --porcelain | grep -Fqx "worktree $runtime_root"
}

codex_auto_runtime_link_parents_safe() {
    local runtime_root="${1:?runtime root required}"
    local parent parent_root

    for parent in "$runtime_root/apps" "$runtime_root/apps/backend-rag"; do
        if [ -L "$parent" ]; then
            printf 'Runtime dependency parent must not be a symlink: %s\n' "$parent" >&2
            return 1
        fi
        if [ -e "$parent" ] && [ ! -d "$parent" ]; then
            printf 'Runtime dependency parent is not a directory: %s\n' "$parent" >&2
            return 1
        fi
        if [ -d "$parent" ]; then
            parent_root="$(cd "$parent" && pwd -P)" || return 1
            case "$parent_root" in
                "$runtime_root"/*) ;;
                *)
                    printf 'Runtime dependency parent escapes the worktree: %s\n' "$parent" >&2
                    return 1
                    ;;
            esac
        fi
    done
}

codex_auto_link_runtime_deps() {
    local primary_repo="${1:?primary repo required}"
    local runtime_repo="${2:?runtime repo required}"
    local primary_root runtime_root target link current_target link_parent

    # This check turns any attempted environment override into a refusal, not
    # a widened capability.  Keep the literal path duplicated in the policy
    # definition above so callers and tests can audit the allowlist directly.
    [ "$CODEX_RUNTIME_LINKS" = "apps/backend-rag/.venv" ] || {
        printf 'Runtime dependency allowlist was modified; refusing to link dependencies\n' >&2
        return 1
    }
    primary_root="$(cd "$primary_repo" && pwd -P)" || return 1
    runtime_root="$(cd "$runtime_repo" && pwd -P)" || return 1
    target="$primary_root/$CODEX_RUNTIME_LINKS"
    link="$runtime_root/$CODEX_RUNTIME_LINKS"
    link_parent="$(dirname "$link")"

    # Do this before inspecting or removing the managed link: a branch can put
    # `apps` behind a symlink and otherwise redirect maintenance writes outside
    # the runtime worktree.
    codex_auto_runtime_link_parents_safe "$runtime_root" || return 1

    # An old managed link must be repaired even when the current primary no
    # longer has a venv. Leaving it makes the runtime certify an obsolete host
    # environment. Only the exact, live current target is retained.
    if [ -L "$link" ]; then
        current_target="$(readlink "$link" 2>/dev/null || true)"
        if [ -e "$target" ] && [ "$current_target" = "$target" ]; then
            return 0
        fi
        if ! rm -f "$link"; then
            printf 'Could not replace stale runtime dependency link: %s\n' "$link" >&2
            return 1
        fi
    fi

    # Nothing to lend after stale-link cleanup: leave no dangling substitute.
    [ -d "$target" ] || return 0
    [ -e "$link" ] && return 0

    if ! mkdir -p "$link_parent"; then
        printf 'Could not create runtime dependency directory: %s\n' "$link_parent" >&2
        return 1
    fi
    # Re-check after mkdir for a concurrent or pre-existing symlink component.
    codex_auto_runtime_link_parents_safe "$runtime_root" || return 1
    if ! ln -s "$target" "$link"; then
        printf 'Could not link runtime dependency: %s -> %s\n' "$link" "$target" >&2
        return 1
    fi
}

codex_auto_ensure_runtime_worktree() {
    local primary_repo="${1:?primary repo required}"
    local runtime_repo="${2:?runtime repo required}"
    local base_ref="${3:-origin/main}"

    if codex_auto_runtime_registered "$primary_repo" "$runtime_repo"; then
        # REPAIR, not just accept. Linking only on create would have healed nothing:
        # the worktree that has been failing for 11 days already exists, so it takes
        # this branch every run and would keep its missing venv forever. This is the
        # half that matters (W116: a cure on a path the failing case never reaches is
        # dead code).
        codex_auto_link_runtime_deps "$primary_repo" "$runtime_repo" || return 1
        return 0
    fi

    # A Git repository here is not enough. It could be the primary reached by
    # upward traversal, a symlink to it, or a wholly unrelated checkout.
    if git -C "$runtime_repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        printf 'Runtime path is not this primary repository\047s registered worktree: %s\n' "$runtime_repo" >&2
        return 1
    fi

    if [ -e "$runtime_repo" ] && [ -n "$(find "$runtime_repo" -mindepth 1 -maxdepth 1 2>/dev/null | head -1)" ]; then
        printf 'Runtime path exists but is not a git worktree: %s\n' "$runtime_repo" >&2
        return 1
    fi

    mkdir -p "$(dirname "$runtime_repo")"
    git -C "$primary_repo" fetch origin main >/dev/null 2>&1 || true
    if ! git -C "$primary_repo" worktree add --detach "$runtime_repo" "$base_ref" >/dev/null; then
        printf 'Could not create Codex runtime worktree: %s at %s\n' \
            "$runtime_repo" "$base_ref" >&2
        return 1
    fi
    if ! codex_auto_runtime_registered "$primary_repo" "$runtime_repo"; then
        printf 'Created runtime path is not this primary repository\047s registered worktree: %s\n' "$runtime_repo" >&2
        return 1
    fi
    codex_auto_link_runtime_deps "$primary_repo" "$runtime_repo"
}

# The unattended CI repair checks out the failed branch before pushing its
# follow-up branch.  Git's normal relative Husky dispatcher would therefore
# execute hook infrastructure supplied by that failed branch.  Build a tiny,
# immutable-in-practice hook root from a fixed trusted commit instead.  This
# is deliberately separate from the runtime worktree dependency allowlist:
# a virtualenv lends test tooling, whereas a hook controls a host-side push.
codex_auto_trusted_prepush_paths() {
    printf '%s\n' \
        .husky/pre-push \
        scripts/prepush_classify.py \
        scripts/prepush_suite_lock.sh \
        scripts/ci/prepush_tip_drift.sh
}

codex_auto_quote_sh() {
    # POSIX-shell single-quote escaping for a generated hook wrapper.
    printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

codex_auto_trusted_prepush_wrapper() {
    local bundle="${1:?bundle required}"
    local tree_root quoted_tree quoted_hook

    tree_root="$bundle/tree"
    quoted_tree="$(codex_auto_quote_sh "$tree_root")"
    quoted_hook="$(codex_auto_quote_sh "$tree_root/.husky/pre-push")"
    printf '%s\n' '#!/bin/sh' 'set -eu'
    printf 'export NUZ_PREPUSH_TRUST_ROOT=%s\n' "$quoted_tree"
    printf 'exec /bin/sh %s "$@"\n' "$quoted_hook"
}

codex_auto_verify_trusted_prepush() {
    local primary_repo="${1:?primary repo required}"
    local bundle="${2:?bundle required}"
    local primary_root trusted_sha rel bundled_path expected_wrapper actual_wrapper

    [ ! -L "$bundle" ] && [ -d "$bundle" ] && [ ! -L "$bundle/tree" ] && [ -d "$bundle/tree" ] || return 1
    [ -x "$bundle/pre-push" ] && [ -f "$bundle/trusted-commit" ] || return 1
    trusted_sha="$(cat "$bundle/trusted-commit" 2>/dev/null || true)"
    [ "${#trusted_sha}" -eq 40 ] || return 1
    case "$trusted_sha" in *[!0123456789abcdef]*) return 1 ;; esac

    primary_root="$(git -C "$primary_repo" rev-parse --show-toplevel 2>/dev/null)" || return 1
    primary_root="$(cd "$primary_root" && pwd -P)" || return 1
    git -C "$primary_root" cat-file -e "${trusted_sha}^{commit}" 2>/dev/null || return 1

    while IFS= read -r rel; do
        bundled_path="$bundle/tree/$rel"
        [ -f "$bundled_path" ] && [ ! -L "$bundled_path" ] && [ -x "$bundled_path" ] || return 1
        git -C "$primary_root" show "${trusted_sha}:${rel}" | cmp -s - "$bundled_path" || return 1
    done < <(codex_auto_trusted_prepush_paths)

    expected_wrapper="$(codex_auto_trusted_prepush_wrapper "$bundle")" || return 1
    actual_wrapper="$(cat "$bundle/pre-push" 2>/dev/null || true)"
    [ "$actual_wrapper" = "$expected_wrapper" ] || return 1
}

codex_auto_prepare_trusted_prepush() {
    local primary_repo="${1:?primary repo required}"
    local state_dir="${2:?state dir required}"
    local trusted_ref="${3:-origin/main}"
    local primary_root trusted_sha bundle_root bundle tree_root rel source_path target_path

    primary_root="$(git -C "$primary_repo" rev-parse --show-toplevel 2>/dev/null)" || return 1
    primary_root="$(cd "$primary_root" && pwd -P)" || return 1
    trusted_sha="$(git -C "$primary_root" rev-parse "${trusted_ref}^{commit}" 2>/dev/null)" || return 1
    bundle_root="${state_dir}/codex-autofix-trusted-prepush"
    bundle="${bundle_root}/${trusted_sha}"

    mkdir -p "$bundle_root" || return 1
    if [ -e "$bundle" ] || [ -L "$bundle" ]; then
        codex_auto_verify_trusted_prepush "$primary_root" "$bundle" || return 1
        printf '%s\n' "$bundle"
        return 0
    fi
    mkdir "$bundle" || return 1
    tree_root="$bundle/tree"
    if ! mkdir -p "$tree_root"; then
        rm -rf "$bundle"
        return 1
    fi

    while IFS= read -r rel; do
        source_path="${trusted_sha}:${rel}"
        target_path="$tree_root/$rel"
        if ! mkdir -p "$(dirname "$target_path")" || \
            ! git -C "$primary_root" show "$source_path" > "$target_path"; then
            rm -rf "$bundle"
            return 1
        fi
        chmod a+rx "$target_path" || {
            rm -rf "$bundle"
            return 1
        }
    done < <(codex_auto_trusted_prepush_paths)

    if ! codex_auto_trusted_prepush_wrapper "$bundle" > "$bundle/pre-push"; then
        rm -rf "$bundle"
        return 1
    fi
    chmod a+rx "$bundle/pre-push" || {
        rm -rf "$bundle"
        return 1
    }
    printf '%s\n' "$trusted_sha" > "$bundle/trusted-commit" || {
        rm -rf "$bundle"
        return 1
    }
    # Do not make the tree directories read-only: that would leave an orphaned
    # cache that even the same job cannot clean up.  Integrity comes from the
    # pinned commit comparison immediately before push, so keep directories
    # traversable/removable and make only the copied artifacts read-only.
    chmod a-w "$bundle/pre-push" "$bundle/trusted-commit" || {
        rm -rf "$bundle"
        return 1
    }
    while IFS= read -r rel; do
        chmod a-w "$tree_root/$rel" || {
            rm -rf "$bundle"
            return 1
        }
    done < <(codex_auto_trusted_prepush_paths)

    if ! codex_auto_verify_trusted_prepush "$primary_root" "$bundle"; then
        rm -rf "$bundle"
        return 1
    fi
    printf '%s\n' "$bundle"
}
