#!/usr/bin/env bash
# Coordination helpers for Wave 1 parallel sessions.
# Source this from each session's wrap-up script.
#
# Usage:
#   source ~/Desktop/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh
#   coord_commit "feat(p0-X): ..." path1 path2
#   coord_push origin <branch>
#   coord_deploy_fly nuzantara-rag
#
# Locks live in ~/.claude/locks/.
# Each function: acquire lock with timeout, run command, release.

LOCK_DIR="$HOME/.claude/locks"
mkdir -p "$LOCK_DIR"

# Wait for lock with timeout. Returns 0 if acquired, 1 if timeout.
# Args: lock_name, timeout_seconds
_acquire_lock() {
    local lock_name="$1"
    local timeout="${2:-1800}"  # default 30 min
    local lockfile="$LOCK_DIR/$lock_name.lock"
    local start=$(date +%s)

    while true; do
        # Try to acquire (non-blocking)
        if ( set -o noclobber; echo "$$:$(date +%s):$(whoami)@$(hostname)" > "$lockfile" ) 2>/dev/null; then
            return 0
        fi

        # Check timeout
        local now=$(date +%s)
        local elapsed=$((now - start))
        if [ "$elapsed" -ge "$timeout" ]; then
            echo "[coord] TIMEOUT after ${elapsed}s waiting for $lock_name lock" >&2
            local holder=$(cat "$lockfile" 2>/dev/null || echo "unknown")
            echo "[coord] Lock held by: $holder" >&2
            return 1
        fi

        # Inspect holder for staleness (>30 min PID gone)
        if [ -f "$lockfile" ]; then
            local holder_pid=$(cut -d: -f1 "$lockfile" 2>/dev/null)
            local holder_ts=$(cut -d: -f2 "$lockfile" 2>/dev/null)
            if [ -n "$holder_pid" ] && ! kill -0 "$holder_pid" 2>/dev/null; then
                local age=$((now - ${holder_ts:-0}))
                if [ "$age" -gt 1800 ]; then
                    echo "[coord] STALE lock detected (PID $holder_pid gone, age ${age}s); breaking" >&2
                    rm -f "$lockfile"
                    continue
                fi
            fi
        fi

        echo "[coord] Waiting for $lock_name lock (${elapsed}s elapsed)... holder: $(cat $lockfile 2>/dev/null)"
        sleep 30
    done
}

_release_lock() {
    local lock_name="$1"
    local lockfile="$LOCK_DIR/$lock_name.lock"
    rm -f "$lockfile"
}

# Commit with lock. Args: message, files...
coord_commit() {
    local message="$1"; shift
    local files=("$@")

    echo "[coord] Acquiring git-commit lock..."
    _acquire_lock "git-commit" 1800 || return 1

    trap '_release_lock git-commit' RETURN

    if [ "${#files[@]}" -eq 0 ]; then
        git add -A
    else
        git add "${files[@]}"
    fi

    # Verify there's something to commit
    if git diff --staged --quiet; then
        echo "[coord] No staged changes; skipping commit"
        _release_lock git-commit
        trap - RETURN
        return 0
    fi

    git commit -m "$(cat <<EOF
$message

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
    local rc=$?
    _release_lock git-commit
    trap - RETURN
    return $rc
}

# Push with lock. Args: remote, branch
coord_push() {
    local remote="${1:-origin}"
    local branch="${2:-$(git rev-parse --abbrev-ref HEAD)}"

    echo "[coord] Acquiring git-push lock..."
    _acquire_lock "git-push" 1800 || return 1

    trap '_release_lock git-push' RETURN

    git push -u "$remote" "$branch"
    local rc=$?
    _release_lock git-push
    trap - RETURN
    return $rc
}

# Fly deploy with lock. Args: app_name, optional extra flyctl args
coord_deploy_fly() {
    local app="${1:?app name required}"; shift

    echo "[coord] Acquiring fly-deploy lock..."
    _acquire_lock "fly-deploy" 3600 || return 1

    trap '_release_lock fly-deploy' RETURN

    cd "$HOME/Desktop/nuzantara/apps/backend-rag"
    fly deploy --strategy rolling --app "$app" "$@"
    local rc=$?
    _release_lock fly-deploy
    trap - RETURN
    return $rc
}

# Status: show all current locks
coord_status() {
    echo "=== Current locks in $LOCK_DIR ==="
    for lock in "$LOCK_DIR"/*.lock; do
        [ -f "$lock" ] || continue
        local name=$(basename "$lock" .lock)
        local content=$(cat "$lock" 2>/dev/null)
        echo "  $name: $content"
    done
}

# Brainstorm cross-LLM dispatch helper
# Args: topic, brief_file_path
# Outputs: 4 files in ./brainstorm_output/<llm>.md
coord_brainstorm() {
    local topic="$1"
    local brief_file="$2"
    local out_dir="${3:-./brainstorm_output}"

    mkdir -p "$out_dir"

    if [ ! -f "$brief_file" ]; then
        echo "[coord] ERROR: brief file not found: $brief_file" >&2
        return 1
    fi

    echo "[coord] Dispatching cross-LLM brainstorm on '$topic'"
    echo "[coord] Brief: $brief_file ($(wc -c < "$brief_file") bytes)"
    echo "[coord] Output: $out_dir/"

    # Codex (sandbox workspace-write, MCP disabled to avoid OAuth refresh fail)
    (
        echo "[codex] starting $(date)"
        codex exec --full-auto --sandbox workspace-write < "$brief_file" \
            > "$out_dir/codex.md" 2>&1
        echo "[codex] done $(date) ($(wc -l < "$out_dir/codex.md") lines)"
    ) &

    # Gemini 3.1 Pro yolo (no sandbox to allow file ops)
    (
        echo "[gemini] starting $(date)"
        gemini -m gemini-3.1-pro-preview --yolo -p "$(cat "$brief_file")" \
            > "$out_dir/gemini.md" 2>&1
        echo "[gemini] done $(date) ($(wc -l < "$out_dir/gemini.md") lines)"
    ) &

    # DeepSeek v4-pro via API (CLI-only law exception per CLAUDE.md)
    (
        echo "[deepseek] starting $(date)"
        local key=$(grep '^DEEPSEEK_API_KEY=' ~/.nuzantara-secrets.env | cut -d= -f2)
        python3 - "$brief_file" "$key" > "$out_dir/deepseek.md" 2>&1 <<'PYEOF'
import json, sys, urllib.request
brief_file, api_key = sys.argv[1], sys.argv[2]
with open(brief_file) as f: brief = f.read()
payload = {
    "model": "deepseek-v4-pro",
    "messages": [
        {"role": "system", "content": "You are DeepSeek doing implementation strategy brainstorm. Be specific to the codebase, propose concrete code changes, options with tradeoffs."},
        {"role": "user", "content": brief}
    ],
    "max_tokens": 8000, "temperature": 0.3
}
req = urllib.request.Request(
    "https://api.deepseek.com/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=900) as resp:
    result = json.loads(resp.read().decode())
choice = result["choices"][0]["message"]
print("# DeepSeek v4-pro brainstorm\n")
if choice.get("reasoning_content"):
    print("## Reasoning\n")
    print(choice["reasoning_content"])
    print()
print("## Analysis\n")
print(choice.get("content", ""))
PYEOF
        echo "[deepseek] done $(date)"
    ) &

    # NotebookLM via MCP (cross_notebook_query NB-1 architecture + NB-14 sessions)
    # Note: requires nlm-mcp running. We use the wrapper script.
    (
        echo "[nlm] starting $(date)"
        # Use the codebase NB (f6ecd115-...) as ground truth source
        local nb_id="f6ecd115-dd89-4c9b-b3dd-071e0e2f1876"
        local query=$(cat "$brief_file")
        python3 - "$nb_id" > "$out_dir/notebooklm.md" 2>&1 <<PYEOF
import sys, json, subprocess
nb_id = sys.argv[1]
query = """$query"""
# Use mcporter wrapper if available, else fallback to direct cli
try:
    # Try mcporter wrapper for nlm-mcp
    result = subprocess.run(
        ["nlm", "query", nb_id, query[:5000]],
        capture_output=True, text=True, timeout=300
    )
    print("# NotebookLM NB-1 brainstorm\n")
    print(result.stdout)
    if result.returncode != 0:
        print(f"\nSTDERR: {result.stderr}")
except FileNotFoundError:
    print("# NotebookLM NB-1 brainstorm\n")
    print("ERROR: nlm CLI not found. Skipping NotebookLM. Use mcp__notebooklm-mcp__notebook_query interactively in main session if needed.")
except subprocess.TimeoutExpired:
    print("# NotebookLM NB-1 brainstorm\n")
    print("ERROR: NotebookLM timeout (300s). Brief might be too long.")
PYEOF
        echo "[nlm] done $(date)"
    ) &

    wait

    echo "[coord] Brainstorm complete. Files in $out_dir/:"
    ls -lh "$out_dir/"
}
