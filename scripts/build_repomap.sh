#!/bin/bash
# build_repomap.sh - SOTA L4 2026-05-24
#
# Build compact repo map for AI session context injection.
# Output: ~/.nuzantara-repomap.txt
#
# Strategy (in order of preference):
#   1. aider --show-repo-map (tree-sitter, function sigs + class defs)
#   2. universal-ctags fallback (json output, parsed to compact form)
#
# Filters: apps/, scripts/, packages/
# Excludes: .venv, node_modules, .worktrees, _archive, _deprecated, dist, build,
#           .next, .turbo, .vercel, coverage, *.min.js (build artifacts — 2026-06-13
#           connectome audit: ctags fallback indexed minified webpack chunks,
#           188kB of noise injected into every session instead of the 4-20kB target)
# Target: 4-20kB output (~1-5k tokens)
#
# Kill-switch: REPOMAP_ENABLED=false → exit 0 (no-op)

set -uo pipefail

# Prepend homebrew bin so command -v ctags resolves to universal-ctags, not BSD /usr/bin/ctags
# (launchd default env passes PATH=/usr/bin:/bin:/usr/sbin:/sbin even when plist sets PATH —
#  see W50/W51/W52 cicatrix family deploy-path coordination)
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"

# === Kill-switch ===
if [[ "${REPOMAP_ENABLED:-true}" == "false" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] repomap disabled via REPOMAP_ENABLED=false" >&2
    exit 0
fi

# === Config ===
REPO_ROOT="${REPOMAP_REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"
OUTPUT_PATH="${REPOMAP_OUTPUT:-$HOME/.nuzantara-repomap.txt}"
OUTPUT_TMP="${OUTPUT_PATH}.tmp.$$"
MAX_TOKENS="${REPOMAP_MAX_TOKENS:-1024}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] [build_repomap]"

cd "$REPO_ROOT" || {
    echo "$LOG_PREFIX FATAL: cannot cd to $REPO_ROOT" >&2
    exit 1
}

echo "$LOG_PREFIX start (repo=$REPO_ROOT, output=$OUTPUT_PATH, max_tokens=$MAX_TOKENS)"

# === Strategy selection ===
build_with_aider() {
    local aider_bin
    # Prefer pyenv version-specific bin over shim (shim may launch GUI in v0.86)
    if [[ -x "/Users/nuzantara/.pyenv/versions/3.11.11/bin/aider" ]]; then
        aider_bin="/Users/nuzantara/.pyenv/versions/3.11.11/bin/aider"
    else
        aider_bin="$(command -v aider 2>/dev/null || true)"
    fi
    if [[ -z "$aider_bin" ]]; then
        # Log the degradation: without this line the aider→ctags fallback is
        # silent and the map quality drop goes unnoticed (W64: esistere ≠ armato).
        echo "$LOG_PREFIX aider unavailable (pyenv bin missing + not on PATH) — falling back to ctags" >&2
        return 1
    fi
    echo "$LOG_PREFIX strategy=aider ($aider_bin)"
    # Flags rationale:
    #   --no-gui --no-browser: prevent streamlit GUI launch (v0.86 quirk)
    #   --subtree-only: aider doesn't walk above CWD (focuses on $REPO_ROOT)
    #   --yes: auto-confirm any prompts
    #   --no-pretty --no-stream: clean stdout, no ANSI codes / streaming
    # Aider requires a git repo here (--no-git rejects directory targets).
    # Timeout 180s prevents launchd lock-up on aider hangs.
    timeout 180 "$aider_bin" \
        --show-repo-map \
        --map-tokens "$MAX_TOKENS" \
        --yes \
        --no-pretty \
        --no-stream \
        --no-gui \
        --no-browser \
        --subtree-only \
        2>/dev/null > "$OUTPUT_TMP"
    local rc=$?
    if [[ $rc -ne 0 ]] || [[ ! -s "$OUTPUT_TMP" ]]; then
        echo "$LOG_PREFIX aider exit=$rc, output size=$(wc -c <"$OUTPUT_TMP" 2>/dev/null || echo 0)" >&2
        return 1
    fi
    # Strip aider preamble (Warnings, "Aider v0.x", "Model:", "Git repo:",
    # tqdm scan bar, "Repo-map can't include ..." chatter) leaving only the
    # actual "Here are summaries ..." map body.
    local cleaned="${OUTPUT_TMP}.cleaned"
    awk '
        /^Here are summaries of some files present/ { keep=1 }
        keep { print }
    ' "$OUTPUT_TMP" > "$cleaned"
    if [[ -s "$cleaned" ]]; then
        mv -f "$cleaned" "$OUTPUT_TMP"
    else
        # Fallback: keep raw output rather than empty file
        rm -f "$cleaned"
    fi
    return 0
}

build_with_ctags() {
    local ctags_bin
    # Try homebrew path first explicitly (launchd PATH override unreliable)
    if [[ -x /opt/homebrew/bin/ctags ]]; then
        ctags_bin=/opt/homebrew/bin/ctags
    else
        ctags_bin="$(command -v ctags 2>/dev/null || true)"
    fi
    if [[ -z "$ctags_bin" ]]; then
        return 1
    fi
    # Under launchd, ctags --help/--version output can be truncated by stderr buffering.
    # Trust that the binary path is universal-ctags if it exists at /opt/homebrew/bin/ctags
    # (homebrew formula 'universal-ctags' is the only ctags published there).
    # For non-homebrew paths, fall back to --output-format=json probe which has predictable output.
    if [[ "$ctags_bin" != "/opt/homebrew/bin/ctags" ]]; then
        if ! "$ctags_bin" --output-format=json /dev/null >/dev/null 2>&1; then
            echo "$LOG_PREFIX WARN: ctags lacks json support (need universal-ctags)" >&2
            return 1
        fi
    fi
    echo "$LOG_PREFIX strategy=ctags ($ctags_bin) — fallback"

    {
        echo "# Repo map (ctags fallback, $(date '+%Y-%m-%d %H:%M:%S'))"
        echo "# Repository: $REPO_ROOT"
        echo ""

        # Build ctags JSON, group by file, emit compact form
        timeout 60 "$ctags_bin" -R \
            --languages=Python,TypeScript,JavaScript \
            --kinds-Python=cf \
            --kinds-TypeScript=cfm \
            --kinds-JavaScript=cfm \
            --output-format=json \
            --fields=+n \
            --exclude='.venv' \
            --exclude='node_modules' \
            --exclude='.worktrees' \
            --exclude='_archive' \
            --exclude='_deprecated' \
            --exclude='dist' \
            --exclude='build' \
            --exclude='.next' \
            --exclude='.turbo' \
            --exclude='.vercel' \
            --exclude='coverage' \
            --exclude='*.min.js' \
            --exclude='tests' \
            --exclude='__tests__' \
            --exclude='test_*.py' \
            --exclude='*.test.ts' \
            --exclude='*.test.tsx' \
            --exclude='conftest.py' \
            --exclude='.git' \
            apps scripts packages 2>/dev/null \
        | python3 -c "
import json, sys
from collections import defaultdict
files = defaultdict(list)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
    except Exception:
        continue
    path = e.get('path', '')
    kind = e.get('kind', '?')
    name = e.get('name', '')
    files[path].append((kind, name))

# Cap output: top 100 files by entry count (tests excluded upstream — a session
# context map wants source signatures, not test-function rosters). 100 files
# ≈ 35-40kB; the SessionStart inject pays this on every session, keep it lean.
ranked = sorted(files.items(), key=lambda kv: -len(kv[1]))[:100]
for path, entries in ranked:
    print(f'\n{path}:')
    # Group by kind
    by_kind = defaultdict(list)
    for k, n in entries:
        by_kind[k].append(n)
    for k in sorted(by_kind.keys()):
        names = sorted(set(by_kind[k]))[:15]  # cap per kind
        print(f'  {k}: {\", \".join(names)}')
"
    } > "$OUTPUT_TMP"

    if [[ ! -s "$OUTPUT_TMP" ]]; then
        echo "$LOG_PREFIX ctags produced empty output" >&2
        return 1
    fi
    return 0
}

# === Execute strategy chain ===
if build_with_aider; then
    STRATEGY=aider
elif build_with_ctags; then
    STRATEGY=ctags
else
    echo "$LOG_PREFIX FATAL: no working strategy (aider+ctags both unavailable)" >&2
    rm -f "$OUTPUT_TMP"
    exit 2
fi

# === Add header + size check ===
HEADER_TMP="${OUTPUT_TMP}.header"
{
    echo "# Nuzantara repo map (auto-generated)"
    echo "# Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "# Strategy: $STRATEGY"
    echo "# Repository: $REPO_ROOT"
    echo "# Refresh cadence: 15min (com.nuzantara.repomap.15min)"
    echo "#"
    cat "$OUTPUT_TMP"
} > "$HEADER_TMP"

SIZE_BYTES=$(wc -c < "$HEADER_TMP")
SIZE_LINES=$(wc -l < "$HEADER_TMP")

# Atomic move
mv -f "$HEADER_TMP" "$OUTPUT_PATH"
rm -f "$OUTPUT_TMP"

echo "$LOG_PREFIX done strategy=$STRATEGY bytes=$SIZE_BYTES lines=$SIZE_LINES"

# Warn (not fail) if outside target band 1kB-30kB
if (( SIZE_BYTES < 1024 )); then
    echo "$LOG_PREFIX WARN: output suspiciously small (<1kB)" >&2
elif (( SIZE_BYTES > 30720 )); then
    echo "$LOG_PREFIX WARN: output >30kB (target 4-20kB); consider lowering REPOMAP_MAX_TOKENS" >&2
fi

exit 0
