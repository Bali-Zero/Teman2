#!/usr/bin/env bash
# ai-dispatch.sh v2 — Universal AI Dispatch for Nuzantara Federation
#
# Works on both Pro and Air. Auto-detects available CLIs.
# Claude Code (Opus 4.6) = Il Re — orchestra, sintetizza, decide, esegue
# Gemini CLI (3.1 Pro)   = Il Consigliere — 1M ctx, Google Search, codebase_investigator
# Codex CLI (GPT-5.4)    = Il Soldato in Fortezza — sandbox kernel-level
#
# v2 improvements over v1:
#   - Cache layer (SHA-256 hash, 24h TTL for explore/search)
#   - JSON structured output ({ok, duration_s, output, word_count, machine})
#   - Robust parallel dispatch with per-job exit codes
#   - Machine-aware (auto-detects Pro vs Air)
#   - Gemini model pinned to gemini-3.1-pro-preview
#   - All v1 commands preserved + new parallel/cache commands
#
# Usage:
#   ./scripts/ai-dispatch.sh <command> "prompt"
#   ./scripts/ai-dispatch.sh parallel explore:"q1" search:"q2"
#   ./scripts/ai-dispatch.sh help

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

CMD="${1:-help}"
PROMPT="${2:-}"
EXTRA="${3:-}"

# ═══════════════════════════════════════════════════════
# Machine detection
# ═══════════════════════════════════════════════════════
MACHINE="unknown"
if [ "$(whoami)" = "nuzantara" ]; then
    MACHINE="pro"
elif [ "$(whoami)" = "antonellosiano" ]; then
    MACHINE="air"
fi

# Bypass alias --yolo that exists in .zshrc on Air
GEMINI_BIN="command gemini"
CODEX_BIN="command codex"

# Gemini model — pinned to 3.1 Pro (1M ctx)
GEMINI_MODEL="gemini-3.1-pro-preview"

# ═══════════════════════════════════════════════════════
# Timeout: macOS has no native timeout, use gtimeout if available
# ═══════════════════════════════════════════════════════
TIMEOUT_CMD=""
if command -v gtimeout &>/dev/null; then
    TIMEOUT_CMD="gtimeout"
elif command -v timeout &>/dev/null; then
    TIMEOUT_CMD="timeout"
fi

run_with_timeout() {
    local secs="$1"
    shift
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD "$secs" "$@"
    else
        "$@"
    fi
}

# ═══════════════════════════════════════════════════════
# Directories
# ═══════════════════════════════════════════════════════
OUTPUT_DIR="$PROJECT_ROOT/ai-dispatch-output"
CACHE_DIR="$PROJECT_ROOT/.ai-dispatch-cache"
mkdir -p "$OUTPUT_DIR" "$CACHE_DIR"

# ═══════════════════════════════════════════════════════
# Colors
# ═══════════════════════════════════════════════════════
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${BLUE}[dispatch:${MACHINE}]${NC} $1"; }
warn() { echo -e "${YELLOW}[dispatch:${MACHINE}]${NC} $1"; }
err() { echo -e "${RED}[dispatch:${MACHINE}]${NC} $1" >&2; }
ok() { echo -e "${GREEN}[dispatch:${MACHINE}]${NC} $1"; }
info() { echo -e "${CYAN}[dispatch:${MACHINE}]${NC} $1"; }

# ═══════════════════════════════════════════════════════
# Safety: block dangerous terms in prompts
# ═══════════════════════════════════════════════════════
check_safety() {
    local prompt="$1"
    local blocked_patterns=(
        "rm -rf" "rm -f" "git push" "git reset" "fly deploy"
        "pip install" "npm install" "brew install"
        "drop table" "truncate"
        "zantara_core.py" "dependencies.py"
        "fly.toml" "alembic/env.py"
        "--yolo" "--dangerously" "danger-full-access"
    )
    for pattern in "${blocked_patterns[@]}"; do
        if echo "$prompt" | grep -qiF -- "$pattern"; then
            err "BLOCKED: prompt contains '$pattern'"
            exit 1
        fi
    done
}

# ═══════════════════════════════════════════════════════
# Cache: SHA-256 hash → skip if <24h old
# ═══════════════════════════════════════════════════════
cache_check() {
    local key="$1"
    local hash
    hash=$(echo "$key" | shasum -a 256 | cut -d' ' -f1)
    local cached="$CACHE_DIR/${hash}.json"
    if [ -f "$cached" ]; then
        local age=$(( $(date +%s) - $(stat -f%m "$cached" 2>/dev/null || stat -c%Y "$cached" 2>/dev/null || echo 0) ))
        if [ "$age" -lt 86400 ]; then
            echo "$cached"
            return 0
        fi
    fi
    return 1
}

cache_save() {
    local key="$1"
    local content="$2"
    local hash
    hash=$(echo "$key" | shasum -a 256 | cut -d' ' -f1)
    echo "$content" > "$CACHE_DIR/${hash}.json"
}

# ═══════════════════════════════════════════════════════
# Structured JSON output
# ═══════════════════════════════════════════════════════
json_output() {
    local cmd_name="$1"
    local duration="$2"
    local output="$3"
    local exit_code="$4"
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # Pass output via stdin to avoid ARG_MAX limits on large outputs
    echo "$output" | python3 -c "
import json, sys
output = sys.stdin.read()
print(json.dumps({
    'command': sys.argv[1],
    'machine': sys.argv[2],
    'timestamp': sys.argv[3],
    'duration_s': int(sys.argv[4]),
    'exit_code': int(sys.argv[5]),
    'ok': int(sys.argv[5]) == 0,
    'word_count': len(output.split()),
    'char_count': len(output),
    'output': output.rstrip()
}, ensure_ascii=False, indent=2))
" "$cmd_name" "$MACHINE" "$ts" "$duration" "$exit_code"
}

# ═══════════════════════════════════════════════════════
# Save output to file (markdown for v1 compat + JSON)
# ═══════════════════════════════════════════════════════
save_output() {
    local cmd_name="$1"
    local output="$2"
    local duration="${3:-0}"
    local timestamp
    timestamp=$(date '+%Y%m%d-%H%M%S')
    local hash
    hash=$(echo "$output" | md5 -q 2>/dev/null || echo "$RANDOM")
    local outfile="$OUTPUT_DIR/${timestamp}-${cmd_name}-${hash:0:8}.md"
    local char_count=${#output}
    local word_count
    word_count=$(echo "$output" | wc -w | tr -d ' ')

    cat > "$outfile" <<HEADER
<!-- dispatch-metrics: {"cmd":"${cmd_name}","machine":"${MACHINE}","duration_s":${duration},"chars":${char_count},"words":${word_count},"timestamp":"${timestamp}"} -->
HEADER
    echo "$output" >> "$outfile"
    info "Saved: $outfile (${duration}s, ${word_count} words)"
}

# ═══════════════════════════════════════════════════════
# CLI availability check
# ═══════════════════════════════════════════════════════
require_gemini() {
    if ! command -v gemini &>/dev/null; then
        err "Gemini CLI not installed. Install: npm i -g @google/gemini-cli"
        exit 1
    fi
    # Check if authenticated (gemini stores creds after first OAuth)
    if [ ! -d "$HOME/.gemini" ] && [ ! -d "$HOME/.config/gemini" ]; then
        warn "Gemini may need first-time auth. Run 'gemini' interactively first."
    fi
}

require_codex() {
    if ! command -v codex &>/dev/null; then
        err "Codex CLI not installed. Install: npm i -g @openai/codex-cli"
        exit 1
    fi
}

# ═══════════════════════════════════════════════════════
# Core runners
# ═══════════════════════════════════════════════════════
run_gemini() {
    local mode="$1"
    local prompt="$2"
    local timeout="${3:-120}"
    require_gemini
    check_safety "$prompt"
    log "Gemini 3.1 Pro (1M ctx) → $mode [sandbox + plan, model=$GEMINI_MODEL]"

    local start_time exit_code output
    start_time=$(date +%s)
    output=$(run_with_timeout "$timeout" $GEMINI_BIN -m "$GEMINI_MODEL" --sandbox --approval-mode plan -p "$prompt" -o text 2>&1) && exit_code=0 || exit_code=$?
    local duration=$(( $(date +%s) - start_time ))

    save_output "gemini-$mode" "$output" "$duration"

    if [ "$exit_code" -eq 0 ]; then
        echo "$output"
    elif [ "$exit_code" -eq 124 ]; then
        err "TIMEOUT: Gemini did not respond in ${timeout}s"
        return 1
    else
        err "Gemini failed (exit $exit_code) after ${duration}s"
        echo "$output"
        return 1
    fi
}

run_codex() {
    local sandbox="$1"
    local prompt="$2"
    local timeout="${3:-180}"
    require_codex
    check_safety "$prompt"
    log "Codex GPT-5.4 → sandbox=$sandbox"

    local start_time exit_code output
    start_time=$(date +%s)
    output=$(run_with_timeout "$timeout" $CODEX_BIN exec --sandbox "$sandbox" "$prompt" 2>&1) && exit_code=0 || exit_code=$?
    local duration=$(( $(date +%s) - start_time ))

    save_output "codex-$sandbox" "$output" "$duration"

    if [ "$exit_code" -eq 0 ]; then
        echo "$output"
    elif [ "$exit_code" -eq 124 ]; then
        err "TIMEOUT: Codex did not respond in ${timeout}s"
        return 1
    else
        err "Codex failed (exit $exit_code) after ${duration}s"
        echo "$output"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════
case "$CMD" in

    # ╔══════════════════════════════════════════════════╗
    # ║  CORE 4 — High-value delegation commands        ║
    # ╚══════════════════════════════════════════════════╝

    # EXPLORE: Gemini 1M ctx for codebase investigation (cached 24h)
    explore)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh explore \"question\""; exit 1; }
        check_safety "$PROMPT"
        if cached=$(cache_check "explore:$PROMPT"); then
            info "CACHE HIT: $cached"
            cat "$cached"
            exit 0
        fi
        start=$(date +%s)
        output=$(run_gemini "explore" "Use your codebase_investigator tool to deeply analyze: $PROMPT. Trace all dependencies, map the architecture, find the root cause. Return findings as structured list with file:line references." 180) && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        result=$(json_output "explore" "$duration" "$output" "$ec")
        cache_save "explore:$PROMPT" "$result"
        echo "$result"
        ;;

    # SEARCH: Gemini Google grounded for regulation/web (cached 24h)
    search)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh search \"query\""; exit 1; }
        check_safety "$PROMPT"
        if cached=$(cache_check "search:$PROMPT"); then
            info "CACHE HIT: $cached"
            cat "$cached"
            exit 0
        fi
        start=$(date +%s)
        output=$(run_gemini "search" "Use google_web_search to find: $PROMPT. Provide a summary with sources and citations." 120) && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        result=$(json_output "search" "$duration" "$output" "$ec")
        cache_save "search:$PROMPT" "$result"
        echo "$result"
        ;;

    # SANDBOX: Codex kernel-level for risky fixes (no cache — side effects)
    sandbox)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh sandbox \"task\""; exit 1; }
        check_safety "$PROMPT"
        start=$(date +%s)
        output=$(run_codex "workspace-write" "$PROMPT" 300) && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        json_output "sandbox" "$duration" "$output" "$ec"
        ;;

    # REDTEAM: Gemini critiques solution pre-deploy (no cache — must be fresh)
    redteam)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh redteam \"solution description\""; exit 1; }
        check_safety "$PROMPT"
        start=$(date +%s)
        output=$(run_gemini "redteam" "Analizza questa soluzione proposta. Il tuo obiettivo è demolirla.
Cerca: edge case non gestiti, race condition, breaking change per API esistenti,
problemi di performance sotto carico, vulnerabilità di sicurezza,
incompatibilità con la normativa indonesiana vigente.
Se non trovi problemi, dichiara esplicitamente 'NESSUN PROBLEMA TROVATO'
con la tua confidence level (alta/media/bassa).

Soluzione da analizzare:
$PROMPT" 180) && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        json_output "redteam" "$duration" "$output" "$ec"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  GEMINI — Extended commands (all read-only)     ║
    # ╚══════════════════════════════════════════════════╝

    gemini-review)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-review \"prompt\""; exit 1; }
        run_gemini "review" "$PROMPT"
        ;;

    gemini-scan)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-scan \"prompt\""; exit 1; }
        run_gemini "scan" "$PROMPT"
        ;;

    gemini-explain)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-explain \"prompt\""; exit 1; }
        run_gemini "explain" "$PROMPT"
        ;;

    gemini-docs)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-docs \"prompt\""; exit 1; }
        run_gemini "docs" "Generate documentation (output as markdown, do NOT modify any files): $PROMPT"
        ;;

    gemini-investigate)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-investigate \"question\""; exit 1; }
        run_gemini "investigate" "Use your codebase_investigator tool to deeply analyze: $PROMPT. Trace all dependencies, map the architecture, find the root cause." 180
        ;;

    gemini-search)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-search \"query\""; exit 1; }
        run_gemini "search" "Use google_web_search to find: $PROMPT. Provide a summary with sources and citations."
        ;;

    gemini-vision)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-vision \"file_path\" \"analysis\""; exit 1; }
        local_file="$PROMPT"
        analysis="${EXTRA:-Analyze this file in detail}"
        check_safety "$analysis"
        if [ ! -f "$local_file" ]; then
            err "File not found: $local_file"
            exit 1
        fi
        log "Gemini → Vision: $local_file"
        run_gemini "vision" "Read and analyze the file at '$local_file'. $analysis"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  CODEX — Extended commands (sandboxed)          ║
    # ╚══════════════════════════════════════════════════╝

    codex-fix)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-fix \"prompt\""; exit 1; }
        run_codex "workspace-write" "$PROMPT"
        ;;

    codex-review)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-review \"prompt\""; exit 1; }
        require_codex
        check_safety "$PROMPT"
        log "Codex → native code review (sandbox read-only)"
        start=$(date +%s)
        output=$(run_with_timeout 180 $CODEX_BIN review --sandbox read-only "$PROMPT" 2>&1) && exit_code=0 || exit_code=$?
        duration=$(( $(date +%s) - start ))
        save_output "codex-review" "$output" "$duration"
        if [ "$exit_code" -eq 0 ]; then
            echo "$output"
        else
            err "Codex review failed (exit $exit_code)"
            echo "$output"
        fi
        ;;

    codex-test)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-test \"prompt\""; exit 1; }
        run_codex "workspace-write" "Write tests for the following. Only create files in tests/ directory. Run the tests after writing them: $PROMPT"
        ;;

    codex-fix-batch)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-fix-batch \"test pattern\""; exit 1; }
        run_codex "workspace-write" "Fix ALL failing tests matching this pattern: $PROMPT. Run each test after fixing to verify. Report results for each file." 300
        ;;

    codex-migrate)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-migrate \"migration description\""; exit 1; }
        log "Codex → Alembic migration in sandbox (test upgrade + downgrade)"
        run_codex "workspace-write" "Generate an Alembic migration for: $PROMPT.
Steps:
1. Generate the migration .py file
2. Test upgrade on isolated test DB
3. Test downgrade
4. Verify both directions work
5. Output the migration .py content ONLY if all tests pass
6. If any test fails, report the error and do NOT output the file.
Working directory: apps/backend-rag/" 300
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  COMBO — Multi-agent patterns                   ║
    # ╚══════════════════════════════════════════════════╝

    analyze-then-fix)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh analyze-then-fix \"what to analyze and fix\""; exit 1; }
        check_safety "$PROMPT"
        log "COMBO: Gemini analyzes → Codex fixes (sandbox)"

        info "Step 1/2: Gemini analyzing..."
        ANALYSIS=$($GEMINI_BIN -m "$GEMINI_MODEL" --sandbox --approval-mode plan -p "Analyze and list ALL issues with specific file:line references for: $PROMPT. Output as a numbered list of issues with exact file paths and line numbers." -o text 2>&1) || true

        echo ""
        info "Gemini found:"
        echo "$ANALYSIS" | head -50
        echo ""
        save_output "combo-analysis" "$ANALYSIS"

        info "Step 2/2: Codex fixing in sandbox..."
        FIX_OUTPUT=$($CODEX_BIN exec --sandbox workspace-write "Based on this analysis, fix the issues listed below. Only modify the files mentioned. Run tests after each fix.

Analysis:
$ANALYSIS" 2>&1) || true
        save_output "combo-fix" "$FIX_OUTPUT"
        echo "$FIX_OUTPUT"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  PARALLEL — Run multiple commands concurrently   ║
    # ╚══════════════════════════════════════════════════╝

    parallel)
        shift
        if [ $# -lt 2 ]; then
            err "Usage: ai-dispatch.sh parallel cmd1:\"prompt1\" cmd2:\"prompt2\""
            exit 1
        fi
        pids=()
        tmpdir=$(mktemp -d)
        trap "rm -rf '$tmpdir'" EXIT INT TERM
        i=0
        for arg in "$@"; do
            # Split on first colon: command:prompt
            local_cmd="${arg%%:*}"
            local_prompt="${arg#*:}"
            log "Parallel [$i]: $local_cmd"
            "$0" "$local_cmd" "$local_prompt" > "$tmpdir/$i.json" 2>"$tmpdir/$i.err" &
            pids+=($!)
            ((i++))
        done

        # Wait and collect
        results="["
        for j in "${!pids[@]}"; do
            wait "${pids[$j]}" 2>/dev/null && job_exit=0 || job_exit=$?
            [ "$j" -gt 0 ] && results+=","
            if [ -s "$tmpdir/$j.json" ]; then
                results+=$(cat "$tmpdir/$j.json")
            else
                local_err=$(cat "$tmpdir/$j.err" 2>/dev/null || echo "unknown error")
                # Use python to safely escape error string into JSON
                results+=$(echo "$local_err" | python3 -c "import json,sys; print(json.dumps({'error':sys.stdin.read().strip(),'exit_code':$job_exit}))")
            fi
        done
        results+="]"
        rm -rf "$tmpdir"
        echo "$results"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  CACHE — Management                             ║
    # ╚══════════════════════════════════════════════════╝

    cache-clear)
        count=$(find "$CACHE_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
        rm -f "$CACHE_DIR"/*.json
        ok "Cache cleared ($count entries removed)"
        ;;

    cache-stats)
        count=$(find "$CACHE_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
        size=$(du -sh "$CACHE_DIR" 2>/dev/null | cut -f1 || echo "0")
        echo "Cache: $count entries, $size"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  INFO                                           ║
    # ╚══════════════════════════════════════════════════╝

    status)
        echo "=== AI Dispatch v2 — Federation [$MACHINE] ==="
        echo ""
        echo -n "  Claude Code (Re):           " && (command claude --version 2>/dev/null || echo "NOT INSTALLED")
        echo -n "  Gemini CLI (Consigliere):    " && (command gemini --version 2>/dev/null || echo "NOT INSTALLED")
        echo -n "  Codex CLI (Soldato):         " && (command codex --version 2>/dev/null || echo "NOT INSTALLED")
        echo -n "  Aider (Mercenario):          " && (aider --version 2>/dev/null || echo "NOT INSTALLED")
        echo -n "  Ollama (Locale):             " && (ollama --version 2>/dev/null || echo "NOT INSTALLED")
        echo ""
        echo "Config files:"
        [ -f "$PROJECT_ROOT/CLAUDE.md" ] && ok "  CLAUDE.md ✓" || warn "  CLAUDE.md MISSING"
        [ -f "$PROJECT_ROOT/GEMINI.md" ] && ok "  GEMINI.md ✓" || warn "  GEMINI.md MISSING"
        [ -f "$PROJECT_ROOT/codex.md" ] && ok "  codex.md  ✓" || warn "  codex.md MISSING"
        echo ""
        echo "Directories:"
        out_count=$(find "$OUTPUT_DIR" -name "*.md" -o -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
        cache_count=$(find "$CACHE_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
        ok "  Output: $OUTPUT_DIR/ ($out_count files)"
        ok "  Cache:  $CACHE_DIR/ ($cache_count entries)"
        echo ""
        echo "Gemini alias check:"
        if alias gemini 2>/dev/null | grep -q "yolo" 2>/dev/null; then
            warn "  gemini alias has --yolo! Dispatch uses 'command gemini' to bypass."
        else
            ok "  gemini alias is clean"
        fi
        echo ""
        echo "Peer machine:"
        peer=""
        if [ "$MACHINE" = "pro" ]; then peer="air"; else peer="pro"; fi
        if ssh -o ConnectTimeout=2 "$peer" 'echo "reachable"' 2>/dev/null; then
            ok "  $peer: REACHABLE"
        else
            warn "  $peer: UNREACHABLE"
        fi
        ;;

    help|*)
        cat <<'HELP'
ai-dispatch.sh v2 — Universal AI Dispatch for Nuzantara Federation
══════════════════════════════════════════════════════════════════

CORE 4 (high-value delegation — use these first):
  explore    "question"           Gemini 1M ctx, codebase analysis (cached 24h)
  search     "query"              Gemini Google grounded (cached 24h)
  sandbox    "task"               Codex kernel-level sandbox (no cache)
  redteam    "solution"           Gemini red team pre-deploy (no cache)

GEMINI (read-only, 1M context):
  gemini-review      "prompt"     Code review / analysis
  gemini-scan        "prompt"     Find patterns in codebase
  gemini-explain     "prompt"     Explain code/architecture
  gemini-docs        "prompt"     Generate documentation
  gemini-investigate "question"   Deep codebase investigation
  gemini-search      "query"      Google Search grounded
  gemini-vision      "file" "q"   Analyze images/PDF

CODEX (sandbox kernel-level):
  codex-fix          "prompt"     Fix bug/test (sandbox write)
  codex-review       "prompt"     Code review (read-only)
  codex-test         "prompt"     Generate and run tests
  codex-fix-batch    "pattern"    Batch fix multiple tests
  codex-migrate      "desc"       Alembic migration in sandbox

COMBO:
  analyze-then-fix   "prompt"     Gemini analyzes → Codex fixes

PARALLEL:
  parallel cmd1:"p1" cmd2:"p2"    Run multiple commands concurrently
  Example: parallel explore:"routing" search:"KBLI 2025"

CACHE:
  cache-clear                     Clear all cached results
  cache-stats                     Show cache statistics

INFO:
  status                          System status + peer check
  help                            This guide

DELEGATION CHECKPOINT (ask before every task):
  1. Need to explore >5 files?     → explore
  2. Need real-time web info?      → search
  3. Risky change to the repo?     → sandbox
  4. Critical deploy coming?       → redteam
  All "No"? → Do it yourself. Don't delegate for sport.

SECURITY:
  ✓ Gemini: --sandbox --approval-mode plan (read-only absolute)
  ✓ Codex:  --sandbox (read-only or workspace-write)
  ✓ Timeout: 120s Gemini, 180-300s Codex
  ✓ Prompt filter blocks dangerous commands + critical files
  ✓ --yolo alias bypassed via 'command gemini'
  ✗ NEVER: --yolo, --dangerously-bypass, danger-full-access
HELP
        ;;
esac
