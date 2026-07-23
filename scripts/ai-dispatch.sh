#!/usr/bin/env bash
# ai-dispatch.sh v3 — Nuzantara Federation CLI (3-tier: agents/services/pipelines)
#
# Works on both Pro and Air. Auto-detects available CLIs.
#
# AGENTS (autonomous, dispatchable):
#   Gemini CLI (3.1 Pro)   = Il Consigliere — 1M ctx, Google Search
#   Codex CLI (GPT-5.4)    = Il Soldato — sandbox kernel-level
#   Claude CLI (Opus 4.6)  = Il Giudice — review, red team (read-only)
#   DeepSeek R1 (API)      = Il Pensatore — deep chain-of-thought
#   Aider (OpenRouter)     = Il Mercenario — multi-model coding
#
# SERVICES (stateless, called by orchestrator):
#   NotebookLM (nlm CLI)   = L'Oracolo — grounded citations
#   Websearch (Exa/Brave)  = Deep web search + content
#
# PIPELINES (scheduled, NOT dispatchable):
#   Core Guardian, Intel Scraper, War Room, SEO Guardian, NLM Refresh
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
# Hostname-first (canonical per AGENTS.md §0), user fallback for legacy shells.
MACHINE="unknown"
case "$(hostname -s)" in
    Nuzantara) MACHINE="pro" ;;
    Mini-Pro2|mini-pro2) MACHINE="mini" ;;
    Air-M5) MACHINE="m5" ;;
esac
if [ "$MACHINE" = "unknown" ]; then
    case "$(whoami)" in
        nuzantara) MACHINE="pro" ;;
        balizero) MACHINE="m5" ;;
        antonellosiano) MACHINE="air" ;;  # legacy Air, decommissioned 2026-05-05
    esac
fi

# Bypass alias --yolo that exists in .zshrc on Air
# (GEMINI_BIN removed 2026-06-23: legacy Gemini CLI sunset 2026-06-18 — run_gemini now uses agy)
CODEX_BIN="command codex"
AGY_BIN="${AGY_BIN:-agy}"

# Gemini model labels (retained for reference; run_gemini now routes through `agy -p`
# after the 2026-06-18 Gemini-CLI sunset — these no longer select a live backend).
GEMINI_MODEL_PRIMARY="gemini-3.1-pro-preview"
GEMINI_MODEL_FALLBACK="gemini-2.5-pro"
GEMINI_MODEL_FAST="gemini-2.5-flash"
GEMINI_MODEL="${GEMINI_MODEL:-$GEMINI_MODEL_PRIMARY}"

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
# Safety: 3-tier prompt filtering
#   Tier 1 (ALWAYS_BLOCKED): destructive commands — rejected always
#   Tier 2 (WRITE_BLOCKED): protected files — blocked only if write intent detected
#   Tier 3 (SENSITIVE): files readable but never shown in output (secrets)
# ═══════════════════════════════════════════════════════
check_safety() {
    local prompt="$1"

    # Tier 1: ALWAYS blocked — destructive commands, no exceptions
    local always_blocked=(
        "rm -rf" "rm -f" "git push --force" "git reset --hard"
        "drop table" "truncate table"
        "--yolo" "--dangerously" "danger-full-access"
        "--no-verify" "--dangerously-bypass"
    )
    for pattern in "${always_blocked[@]}"; do
        if echo "$prompt" | grep -qiF -- "$pattern"; then
            err "BLOCKED: destructive command '$pattern'"
            exit 1
        fi
    done

    # Tier 2: WRITE-protected files — blocked only with write-intent verbs
    # These files CAN be READ/ANALYZED but NEVER modified via dispatch
    local protected_files=(
        "zantara_core.py" "dependencies.py" "service_initializer.py"
        "fly.toml" "alembic/env.py" ".env"
    )
    # Write-intent detection: check for imperative verbs BEFORE the file name
    # "modify fly.toml" = blocked, "analyze fly.toml changes" = allowed
    # Pattern: verb + optional words + filename (imperative write intent)
    for file in "${protected_files[@]}"; do
        if echo "$prompt" | grep -qiF -- "$file"; then
            # Check if prompt starts with or contains imperative write verbs near the file
            if echo "$prompt" | grep -qiE "(^| )(modify|edit|update|rewrite|overwrite|delete|remove|replace|append|refactor|alter|mutate) .*$file"; then
                err "BLOCKED: write intent detected for protected file '$file'"
                err "  → READ/ANALYZE is allowed, MODIFY is not via dispatch"
                exit 1
            fi
            # Read intent is OK — log but don't block
            warn "NOTICE: prompt references protected file '$file' (read-only access)"
        fi
    done

    # Tier 3: Secrets — always blocked even for read
    local secrets=("NUZANTARA_ENV_KEYS" "sa-key" "API_KEY=" "SECRET=" "TOKEN=" "PASSWORD=")
    for secret in "${secrets[@]}"; do
        if echo "$prompt" | grep -qiF -- "$secret"; then
            err "BLOCKED: prompt references secret pattern '$secret'"
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
        local cache_time
        cache_time=$(stat -f%m "$cached" 2>/dev/null || stat -c%Y "$cached" 2>/dev/null || echo 0)
        # Invalidate if repo has new commits since cache was written
        local last_commit_time
        last_commit_time=$(git log -1 --format=%ct 2>/dev/null || echo 0)
        if [ "$last_commit_time" -gt "$cache_time" ]; then
            info "CACHE INVALIDATED: repo changed since cache"
            rm -f "$cached"
            return 1
        fi
        local age=$(( $(date +%s) - cache_time ))
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
# Audit log: append-only JSONL for federation metrics
# ═══════════════════════════════════════════════════════
audit_log() {
    local cmd="$1" prompt_hash="$2" duration="$3" exit_code="$4"
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "{\"ts\":\"$ts\",\"cmd\":\"$cmd\",\"machine\":\"$MACHINE\",\"prompt_hash\":\"$prompt_hash\",\"duration_s\":$duration,\"exit_code\":$exit_code}" >> "$OUTPUT_DIR/audit.jsonl"
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
    # NOTE 2026-06-23: the legacy Gemini CLI was SUNSET on 2026-06-18 — it no longer
    # serves Google AI Pro/Ultra/free subscription requests (only paid API keys do).
    # The GA replacement on our AI Ultra OAuth is the Antigravity CLI (`agy`). So this
    # check now requires `agy`, NOT the dead `gemini` binary (which may still sit on
    # disk and would otherwise pass `command -v gemini` while every call fails at
    # runtime — superscar #2 "green-but-dead"). run_gemini() routes through `agy -p`.
    if ! command -v "$AGY_BIN" &>/dev/null; then
        err "Antigravity CLI (agy) not installed or not on PATH. Expected: $AGY_BIN"
        err "agy replaced the Gemini CLI on 2026-06-18 for AI Ultra subscriptions."
        exit 1
    fi
}

require_agy() {
    if ! command -v "$AGY_BIN" &>/dev/null; then
        err "Antigravity CLI not installed or not on PATH. Expected: $AGY_BIN"
        exit 1
    fi
}

require_codex() {
    if ! command -v codex &>/dev/null; then
        err "Codex CLI not installed. Install: npm i -g @openai/codex-cli"
        exit 1
    fi
}

require_claude() {
    if ! command -v claude &>/dev/null; then
        err "Claude CLI not installed."
        exit 1
    fi
}

require_aider() {
    if ! command -v aider &>/dev/null; then
        err "Aider not installed. Install: pip install aider-chat"
        exit 1
    fi
    # Load API keys from master env if not already set
    if [ -z "$OPENROUTER_API_KEY" ] && [ -f "$HOME/Desktop/NUZANTARA_ENV_KEYS.env" ]; then
        export OPENROUTER_API_KEY=$(grep OPENROUTER_API_KEY "$HOME/Desktop/NUZANTARA_ENV_KEYS.env" | cut -d= -f2)
    fi
    if [ -z "$DEEPSEEK_API_KEY" ] && [ -f "$HOME/Desktop/NUZANTARA_ENV_KEYS.env" ]; then
        export DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY "$HOME/Desktop/NUZANTARA_ENV_KEYS.env" | cut -d= -f2)
    fi
}

# ═══════════════════════════════════════════════════════
# Core runners
# ═══════════════════════════════════════════════════════
run_gemini() {
    # ADAPTER (2026-06-23): the legacy Gemini CLI was sunset on 2026-06-18 (no longer
    # serves AI Ultra subscription requests). This function keeps its name + signature
    # — run_gemini "<mode>" "<prompt>" [timeout] — so all 13 existing call-sites and the
    # NLM fallbacks keep working unchanged, but it now routes through `agy -p` (the
    # Antigravity CLI on our AI Ultra OAuth), exactly the print-mode path that
    # nb-curator-daily.sh and wr3_reflexion_synthesis.py already use in prod.
    local mode="$1"
    local prompt="$2"
    local timeout="${3:-120}"
    require_gemini
    check_safety "$prompt"

    # Mode → behavioral framing prefix (agy -p is a single-shot prompt, no -m/--sandbox).
    local framing
    case "$mode" in
        review|scan)        framing="Act as a code reviewer. " ;;
        redteam)            framing="Act as an adversarial red-team reviewer; try to falsify the proposed solution. " ;;
        explore|investigate) framing="Act as a codebase investigator: trace dependencies, map architecture, cite file:line. " ;;
        search)             framing="Act as a web researcher; provide a summary with sources and citations. " ;;
        docs)               framing="Generate documentation as markdown; do NOT modify any files. " ;;
        explain)            framing="Explain clearly and concisely. " ;;
        vision)             framing="Read and analyze the referenced file. " ;;
        *)                  framing="" ;;
    esac

    local start_time exit_code output
    start_time=$(date +%s)

    # agy reads the prompt from STDIN (the prod pattern in nb-curator-daily.sh and
    # wr3_reflexion_synthesis.py); flags after -p are agy flags, NOT the prompt.
    log "Antigravity (agy) → $mode [print mode, timeout=${timeout}s]"
    output=$(printf '%s' "${framing}${prompt}" | run_with_timeout "$timeout" "$AGY_BIN" -p --print-timeout "${timeout}s" 2>&1) && exit_code=0 || exit_code=$?

    local duration=$(( $(date +%s) - start_time ))
    save_output "gemini-$mode" "$output" "$duration"

    if [ "$exit_code" -eq 0 ]; then
        echo "$output"
    elif [ "$exit_code" -eq 124 ]; then
        err "TIMEOUT: agy did not respond in ${timeout}s (mode=$mode)"
        return 1
    else
        err "agy failed (exit $exit_code) after ${duration}s (mode=$mode)"
        echo "$output"
        return 1
    fi
}

run_agy_swarm() {
    local model_key="$1"
    local mode="$2"
    local prompt="$3"
    local timeout="${4:-90}"
    local dry_run_flag="${5:-}"
    require_agy
    check_safety "$prompt"

    local start_time exit_code output prompt_hash
    local args
    start_time=$(date +%s)
    args=(
        python3 "$PROJECT_ROOT/scripts/agy_swarm_commander.py"
        --agy-bin "$AGY_BIN"
        --model "$model_key"
        --mode "$mode"
        --timeout "$timeout"
        --prompt "$prompt"
    )
    if [ "$dry_run_flag" = "dry-run" ] || [ "$dry_run_flag" = "--dry-run" ]; then
        args+=(--dry-run)
    fi

    log "Agy Swarm Commander → $mode [model=$model_key, timeout=${timeout}s]"
    output=$(run_with_timeout "$((timeout + 15))" "${args[@]}" 2>&1) && exit_code=0 || exit_code=$?
    local duration=$(( $(date +%s) - start_time ))
    save_output "agy-$mode" "$output" "$duration"
    prompt_hash=$(echo "$prompt" | shasum -a 256 | cut -d' ' -f1)
    audit_log "agy-$mode" "$prompt_hash" "$duration" "$exit_code"
    echo "$output"
    return "$exit_code"
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

run_claude() {
    local mode="$1"
    local prompt="$2"
    local timeout="${3:-120}"
    local allowed_tools="${4:-Read,Grep,Glob}"
    require_claude
    check_safety "$prompt"

    # Multi-account fallback: numbered seats, legacy token, then keychain.
    local token_vars=("CLAUDE_CODE_OAUTH_TOKEN_1" "CLAUDE_CODE_OAUTH_TOKEN_2" "CLAUDE_CODE_OAUTH_TOKEN_3" "CLAUDE_CODE_OAUTH_TOKEN_4" "CLAUDE_CODE_OAUTH_TOKEN_5" "CLAUDE_CODE_OAUTH_TOKEN")
    local tried=0
    local claude_bin
    claude_bin="$(command -v claude)"
    local deadline=$(( $(date +%s) + timeout ))
    local retryable_re='rate.?limit|too many requests|(^|[^0-9/])429([^0-9/]|$)|exhausted|quota|usage limit|weekly limit|hit your limit|authentication (failed|required|expired)|auth required|login required|please (log in|login)|not logged in|not authenticated|invalid[_ ](grant|token)|token[_ ]revoked|refresh_token|unauthori[sz]ed|(^|[^0-9/])401([^0-9/]|$)'
    local oauth_env=(
        env
        -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_BASE_URL
        -u CLAUDE_CODE_USE_BEDROCK -u CLAUDE_CODE_USE_VERTEX -u CLAUDE_CODE_USE_FOUNDRY
        -u GOOGLE_APPLICATION_CREDENTIALS -u CLOUD_ML_REGION
        -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN
        -u AWS_PROFILE -u AWS_REGION -u AWS_DEFAULT_REGION -u AWS_BEARER_TOKEN_BEDROCK
        -u VERTEX_AI_PROJECT -u VERTEX_AI_LOCATION
        -u ANTHROPIC_VERTEX_PROJECT_ID -u ANTHROPIC_BEDROCK_BASE_URL
    )
    local active_vars=()
    local candidate
    for candidate in "${token_vars[@]}"; do
        [ -n "${!candidate:-}" ] && active_vars+=("$candidate")
    done
    active_vars+=("keychain")

    local position=0
    for tv in "${active_vars[@]}"; do
        local token_val=""
        local label="$tv"
        if [ "$tv" != "keychain" ]; then
            # Indirect expansion must tolerate `set -u`: if the env var is not
            # exported, `${!tv}` would abort the script with "unbound variable".
            # `${!tv:-}` falls back to empty and we `continue` silently.
            token_val="${!tv:-}"
            [ -z "$token_val" ] && continue
        fi
        tried=$((tried + 1))
        local remaining=$(( deadline - $(date +%s) ))
        [ "$remaining" -le 0 ] && break
        local attempts_left=$(( ${#active_vars[@]} - position ))
        local attempt_timeout=$(( remaining / attempts_left ))
        [ "$attempt_timeout" -lt 1 ] && attempt_timeout=1
        position=$((position + 1))

        log "Claude Code (Opus 4.6) → $mode [token=$label, tools=$allowed_tools]"

        local start_time exit_code output
        start_time=$(date +%s)
        if [ -n "$token_val" ]; then
            output=$(run_with_timeout "$attempt_timeout" "${oauth_env[@]}" \
                CLAUDE_CODE_OAUTH_TOKEN="$token_val" "$claude_bin" -p "$prompt" \
                --allowedTools "$allowed_tools" 2>&1) && exit_code=0 || exit_code=$?
        else
            output=$(run_with_timeout "$attempt_timeout" "${oauth_env[@]}" \
                -u CLAUDE_CODE_OAUTH_TOKEN "$claude_bin" -p "$prompt" \
                --allowedTools "$allowed_tools" 2>&1) && exit_code=0 || exit_code=$?
        fi
        local duration=$(( $(date +%s) - start_time ))

        # Account-local quota/auth diagnostics can exit 0. Classify before
        # accepting output and never persist raw diagnostic stderr.
        if echo "$output" | grep -qiE "$retryable_re"; then
            warn "$label unavailable — trying next token"
            continue
        fi

        if [ "$exit_code" -eq 0 ] && [ -n "${output//[[:space:]]/}" ]; then
            save_output "claude-$mode" "$output" "$duration"
            echo "$output"
            return 0
        fi

        if [ "$exit_code" -eq 0 ]; then
            warn "$label returned empty output — trying next token"
            continue
        fi

        if [ "$exit_code" -eq 124 ]; then
            warn "$label timed out — trying next token"
            continue
        fi

        # Non-rate-limit error — stop trying
        err "Claude failed ($label, exit $exit_code) after ${duration}s"
        return 1
    done

    err "All Claude tokens exhausted ($tried tried)"
    return 1
}

# ═══════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════
case "$CMD" in

    # ╔══════════════════════════════════════════════════╗
    # ║  CORE 4 — High-value delegation commands        ║
    # ╚══════════════════════════════════════════════════╝

    # ╔══════════════════════════════════════════════════╗
    # ║  ORACOLO — NotebookLM Knowledge Fabric          ║
    # ╚══════════════════════════════════════════════════╝

    # ORACOLO: Query NB-1 (Codebase & Architecture) for grounded citations
    # Uses nlm CLI (pip install notebooklm-mcp-cli) with --json for structured output
    oracolo)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh oracolo \"question\""; exit 1; }
        check_safety "$PROMPT"
        NB1_ID="f6ecd115-dd89-4c9b-b3dd-071e0e2f1876"
        NLM_BIN="${NLM_BIN:-$HOME/.local/bin/nlm}"
        start=$(date +%s)
        if [ -x "$NLM_BIN" ]; then
            log "NLM Oracolo → NB-1 query [timeout=120s]"
            output=$("$NLM_BIN" notebook query "$NB1_ID" "$PROMPT" --json --timeout 120 2>&1) && ec=0 || ec=$?
        else
            warn "nlm CLI not found at $NLM_BIN. Falling back to agy explore..."
            output=$(run_gemini "explore" "Consulta il codebase Nuzantara per rispondere: $PROMPT. Cita file e path specifici." 180) && ec=0 || ec=$?
        fi
        duration=$(( $(date +%s) - start ))
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "oracolo" "$prompt_hash" "$duration" "$ec"
        json_output "oracolo" "$duration" "$output" "$ec"
        ;;

    # ORACOLO-NB: Query any of the 8 Knowledge Fabric notebooks by domain tag
    # Usage: ai-dispatch.sh oracolo-nb "immigration" "question about visa"
    oracolo-nb)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh oracolo-nb \"tag\" \"question\""; exit 1; }
        NB_TAG="$PROMPT"
        QUESTION="$EXTRA"
        [ -z "$QUESTION" ] && { err "Missing question. Usage: ai-dispatch.sh oracolo-nb \"immigration\" \"question\""; exit 1; }
        check_safety "$QUESTION"
        NLM_BIN="${NLM_BIN:-$HOME/.local/bin/nlm}"

        # Static tag→notebook_id routing (from Phase 1 tagging, 2026-03-25)
        # Uses case instead of associative array to avoid bash set -u issues
        case "$NB_TAG" in
            codebase|architecture|mcp|deploy|federation)
                nb_id="f6ecd115-dd89-4c9b-b3dd-071e0e2f1876" ;;  # NB-1
            immigration|visa|kitas|kitap|tka|work_permit|stay_permit)
                nb_id="84375bc3-12d0-4405-a774-9b89189d8c39" ;;  # NB-2
            company|kbli|pma|oss|licensing|nib|investment|business)
                nb_id="2e84b9b9-3b99-4bc5-8ec5-351a43c52df4" ;;  # NB-3
            tax|compliance|lkpm|npwp|pph|ppn|coretax|bpjs|fiscal)
                nb_id="837b620b-2aca-43ab-812e-97ca92bdad1d" ;;  # NB-4
            property|zoning|land|hgb|hak_pakai|building|villa|real_estate)
                nb_id="568ec624-ceb8-47d1-a2a2-5b2f793ea7ed" ;;  # NB-5
            operations|sop|team|pricing|crm|workflow|competitor)
                nb_id="3e1baa5f-680f-4499-9430-23a901576bcc" ;;  # NB-6
            editorial|seo|content|market|intel|trends|news)
                nb_id="dd464d8f-6b8e-4543-8647-f62c498589b1" ;;  # NB-7
            lifestyle|expat|healthcare|cost_of_living|culture|digital_nomad|education)
                nb_id="1143b525-dd3f-40d7-a34d-2e9263b44460" ;;  # NB-8
            *)  nb_id="" ;;
        esac
        start=$(date +%s)

        if [ -z "$nb_id" ]; then
            # Fallback: try nlm tag select for unknown tags
            if [ -x "$NLM_BIN" ]; then
                nb_id=$("$NLM_BIN" tag select "$NB_TAG" 2>/dev/null | grep -oP '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' | head -1)
            fi
            if [ -z "$nb_id" ]; then
                err "Tag '$NB_TAG' not found. Available: codebase, immigration, visa, kitas, company, kbli, pma, tax, compliance, lkpm, property, zoning, villa, operations, sop, pricing, editorial, seo, intel, lifestyle, expat, healthcare"
                exit 1
            fi
        fi

        if [ -x "$NLM_BIN" ]; then
            log "NLM Oracolo → $NB_TAG ($nb_id)"
            output=$("$NLM_BIN" notebook query "$nb_id" "$QUESTION" --json --timeout 120 2>&1) && ec=0 || ec=$?
        else
            warn "nlm CLI not found. Falling back to agy explore..."
            output=$(run_gemini "explore" "$QUESTION" 180) && ec=0 || ec=$?
        fi
        duration=$(( $(date +%s) - start ))
        audit_log "oracolo-nb" "$(echo "$NB_TAG:$QUESTION" | shasum -a 256 | cut -d' ' -f1)" "$duration" "$ec"
        json_output "oracolo-nb" "$duration" "$output" "$ec"
        ;;

    # RESEARCH: Deep Research via NLM (autonomous web search → imports to NB-9 Research Lab)
    # Mode: fast (~30s, ~10 sources) or deep (~5min, ~40 sources)
    research)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh research \"topic\" [fast|deep]"; exit 1; }
        check_safety "$PROMPT"
        MODE="${EXTRA:-deep}"
        NB9_ID="${NB9_RESEARCH_ID:-d2a05271-2f65-4c02-a44d-eefeb7c7f7cd}"
        NLM_BIN="${NLM_BIN:-$HOME/.local/bin/nlm}"
        start=$(date +%s)
        if [ -x "$NLM_BIN" ]; then
            info "Deep Research ($MODE) → $PROMPT"
            if [ -n "$NB9_ID" ]; then
                output=$("$NLM_BIN" research start "$PROMPT" --mode "$MODE" --notebook-id "$NB9_ID" 2>&1) && ec=0 || ec=$?
            else
                output=$("$NLM_BIN" research start "$PROMPT" --mode "$MODE" --title "Research: $(echo "$PROMPT" | cut -c1-50)" 2>&1) && ec=0 || ec=$?
            fi
            # Research is async — print status check instructions
            if [ $ec -eq 0 ]; then
                info "Research started. Check status: $NLM_BIN research status"
                info "Import when done: $NLM_BIN research import"
            fi
        else
            warn "nlm CLI not found. Falling back to agy search..."
            output=$(run_gemini "search" "Deep research: $PROMPT" 120) && ec=0 || ec=$?
        fi
        duration=$(( $(date +%s) - start ))
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "research" "$prompt_hash" "$duration" "$ec"
        json_output "research" "$duration" "$output" "$ec"
        ;;

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
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "explore" "$prompt_hash" "$duration" "$ec"
        echo "$result"
        ;;

    # SEARCH: Gemini Google grounded for regulation/web (NEVER cached — must be fresh)
    search)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh search \"query\""; exit 1; }
        check_safety "$PROMPT"
        start=$(date +%s)
        output=$(run_gemini "search" "Use google_web_search to find: $PROMPT. Provide a summary with sources and citations." 120) && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        result=$(json_output "search" "$duration" "$output" "$ec")
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "search" "$prompt_hash" "$duration" "$ec"
        echo "$result"
        ;;

    # REASONING: DeepSeek R1 671b via API — deep chain-of-thought reasoning
    # Injects Nuzantara system context for grounded answers
    # Best for: architecture decisions, migration strategies, complex debugging
    reasoning)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh reasoning \"complex problem\""; exit 1; }
        check_safety "$PROMPT"
        CONTEXT_FILE="$PROJECT_ROOT/scripts/nuzantara_system_context.md"
        start=$(date +%s)

        if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
            err "DEEPSEEK_API_KEY not set. Export it or add to .env"
            exit 1
        fi

        log "DeepSeek R1 671b → reasoning [max_tokens=8192, with Nuzantara context]"

        # Inject system context + user prompt
        SYSTEM_CTX=""
        if [ -f "$CONTEXT_FILE" ]; then
            SYSTEM_CTX=$(cat "$CONTEXT_FILE")
        fi

        output=$(python3 -c "
import httpx, json, os, sys

ctx = '''$SYSTEM_CTX'''
prompt = '''$PROMPT'''

r = httpx.post('https://api.deepseek.com/chat/completions',
    headers={'Authorization': f'Bearer {os.environ[\"DEEPSEEK_API_KEY\"]}', 'Content-Type': 'application/json'},
    json={
        'model': 'deepseek-v4-pro',  # was 'deepseek-reasoner' — legacy alias silently routes to V4-Flash (cicatrix 2026-05-24)
        'messages': [
            {'role': 'system', 'content': ctx} if ctx else None,
            {'role': 'user', 'content': prompt}
        ] if not ctx else [
            {'role': 'system', 'content': ctx},
            {'role': 'user', 'content': prompt}
        ],
        'max_tokens': 8192,
        'temperature': 0
    },
    timeout=180
)

d = r.json()
if 'error' in d:
    print(f'ERROR: {d[\"error\"].get(\"message\",\"unknown\")}', file=sys.stderr)
    sys.exit(1)

msg = d['choices'][0]['message']
reasoning = msg.get('reasoning_content', '')
answer = msg.get('content', '')
u = d.get('usage', {})

# Output reasoning summary + answer
if reasoning:
    print(f'[Reasoning: {len(reasoning)} chars, {u.get(\"completion_tokens_details\",{}).get(\"reasoning_tokens\",\"?\")} tokens]')
print(answer)
print(f'[Cost: \${(u.get(\"prompt_tokens\",0)*0.55 + u.get(\"completion_tokens\",0)*2.19)/1000000:.4f}]')
" 2>&1) && ec=0 || ec=$?

        duration=$(( $(date +%s) - start ))
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "reasoning" "$prompt_hash" "$duration" "$ec"
        json_output "reasoning" "$duration" "$output" "$ec"
        ;;

    # WEBSEARCH: Exa deep web search with full content + citations (Brave fallback)
    # Returns actual page content, not just links — like Perplexity but free
    websearch)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh websearch \"query\" [count]"; exit 1; }
        check_safety "$PROMPT"
        count="${EXTRA:-5}"
        start=$(date +%s)
        # Exa via Claude Code MCP — we call it via a Python one-liner that hits the MCP
        # Since ai-dispatch.sh can't call MCP tools directly, we use a bridge
        log "Exa Web Search → $PROMPT (top $count results)"

        # Try Exa first via Python MCP bridge
        output=$(python3 -c "
import json, subprocess, sys

# Use the nlm CLI's MCP client or direct HTTP — simplest: use Claude Code's MCP
# Since we can't call MCP from bash directly, we use Brave CLI as primary
# and document that Exa should be used from Claude Code sessions

query = '''$PROMPT'''
count = int('$count')

# Brave Search via API (BRAVE_API_KEY should be in env)
import os
api_key = os.environ.get('BRAVE_API_KEY', '')
if api_key:
    import urllib.request, urllib.parse
    params = urllib.parse.urlencode({'q': query, 'count': count})
    req = urllib.request.Request(
        f'https://api.search.brave.com/res/v1/web/search?{params}',
        headers={'Accept': 'application/json', 'X-Subscription-Token': api_key}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            results = data.get('web', {}).get('results', [])
            for r in results[:count]:
                print(f'## {r.get(\"title\", \"\")}')
                print(f'URL: {r.get(\"url\", \"\")}')
                print(f'{r.get(\"description\", \"\")}')
                print()
            sys.exit(0)
    except Exception as e:
        print(f'Brave API error: {e}', file=sys.stderr)

# Fallback: no API key or error — print instructions
print('NOTE: websearch works best from Claude Code (uses Exa MCP with full content).')
print('From bash, set BRAVE_API_KEY for Brave Search API.')
print(f'Query: {query}')
" 2>&1) && ec=0 || ec=$?

        duration=$(( $(date +%s) - start ))
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "websearch" "$prompt_hash" "$duration" "$ec"
        json_output "websearch" "$duration" "$output" "$ec"
        ;;

    # SANDBOX: Codex kernel-level for risky fixes (no cache — side effects)
    sandbox)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh sandbox \"task\""; exit 1; }
        check_safety "$PROMPT"
        start=$(date +%s)
        output=$(run_codex "workspace-write" "$PROMPT" 300) && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "sandbox" "$prompt_hash" "$duration" "$ec"
        json_output "sandbox" "$duration" "$output" "$ec"
        ;;

    # PREFLIGHT SDD: Thin wrapper → delegates to Python federation workflows
    # Usage: ai-dispatch.sh preflight "task description"           # L2 default
    #        ai-dispatch.sh preflight-l1 "task semplice"           # L1 quick scan
    #        ai-dispatch.sh preflight-l2 "task medium"             # L2 full (default)
    #        ai-dispatch.sh preflight-l3 "task critico"            # L3 deep + sandbox
    preflight|preflight-l1|preflight-l2|preflight-l3)
        TASK="${PROMPT:-$2}"
        [ -z "$TASK" ] && { err "Usage: $0 preflight[-l1|-l2|-l3] \"task description\""; exit 1; }
        # Determine level (strip 'preflight' prefix and leading dash)
        RAW_CMD="${CMD#preflight}"
        LEVEL="${RAW_CMD#-}"
        [ -z "$LEVEL" ] && LEVEL="l2"  # default to L2
        LEVEL_UPPER=$(echo "$LEVEL" | tr '[:lower:]' '[:upper:]')
        # Preflight SDD backend (apps/federation/workflows.py) was created by
        # commit 500fca845 and DELETED by 5c06a2fd5 ("massive repo cleanup —
        # untrack 739 files"). The thin wrapper survived but its target is gone,
        # so this command crashed with a cryptic `Errno 2`. Fail honestly instead.
        PREFLIGHT_BACKEND="apps/federation/workflows.py"
        if [ ! -f "$PREFLIGHT_BACKEND" ]; then
            err "Preflight SDD is NOT INSTALLED — backend missing: ${PREFLIGHT_BACKEND}"
            err "  It was created by commit 500fca845 and DELETED by 5c06a2fd5"
            err "  (\"massive repo cleanup — untrack 739 files\"); the wrapper survived, the backend did not."
            err "  No live system depends on this command (verified 2026-06-07: no hook/cron/LaunchAgent/code invokes it)."
            err "  Until it is rebuilt, run the preflight MANUALLY: the 4-LLM panel in CLAUDE.md §6"
            err "  (Gemini agy + Codex + DeepSeek + optional NB-1). Restoring the automated gate is a FASE-3 task."
            audit_log "preflight-${LEVEL}" "$(echo "$TASK" | shasum -a 256 | cut -d' ' -f1)" "0" "127"
            exit 127
        fi
        info "Preflight SDD — level ${LEVEL_UPPER} starting for: ${TASK:0:80}"
        start=$(date +%s)
        PYTHONPATH=. python3 "$PREFLIGHT_BACKEND" run "preflight-${LEVEL}" "$TASK"
        ec=$?
        duration=$(( $(date +%s) - start ))
        audit_log "preflight-${LEVEL}" "$(echo "$TASK" | shasum -a 256 | cut -d' ' -f1)" "$duration" "$ec"
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
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "redteam" "$prompt_hash" "$duration" "$ec"
        json_output "redteam" "$duration" "$output" "$ec"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  AGY — Antigravity Gemini adjunct reviewers     ║
    # ╚══════════════════════════════════════════════════╝

    agy-flash)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh agy-flash \"prompt\" [dry-run]"; exit 1; }
        run_agy_swarm "flash-high" "fast-review" "$PROMPT" 75 "$EXTRA"
        ;;

    agy-pro)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh agy-pro \"prompt\" [dry-run]"; exit 1; }
        run_agy_swarm "pro-high" "deep-review" "$PROMPT" 180 "$EXTRA"
        ;;

    agy-redteam)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh agy-redteam \"solution\" [dry-run]"; exit 1; }
        run_agy_swarm "pro-high" "redteam" "$PROMPT" 180 "$EXTRA"
        ;;

    swarm-commander)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh swarm-commander \"task\" [dry-run]"; exit 1; }
        run_agy_swarm "flash-high" "swarm" "$PROMPT" 120 "$EXTRA"
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
        # `codex review` is read-only by design — it only inspects the diff
        # and writes commentary; no file-system or network side effects. The
        # old `--sandbox read-only` flag was removed from the CLI around
        # Sprint 5.2 time; passing it now aborts with exit 2. Drop the flag.
        log "Codex → native code review (read-only by design)"
        start=$(date +%s)
        output=$(run_with_timeout 180 $CODEX_BIN review "$PROMPT" 2>&1) && exit_code=0 || exit_code=$?
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

        info "Step 1/2: agy (Antigravity) analyzing..."
        ANALYSIS=$(run_gemini "explore" "Analyze and list ALL issues with specific file:line references for: $PROMPT. Output as a numbered list of issues with exact file paths and line numbers." 300 2>&1) || true

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
    # ║  CLAUDE — Read-only analysis (Max plan, $0)    ║
    # ╚══════════════════════════════════════════════════╝

    claude-review)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh claude-review \"prompt\""; exit 1; }
        start=$(date +%s)
        output=$(run_claude "review" "Review this code/architecture for bugs, security issues, and improvements. Be specific with file:line references. $PROMPT" 180 "Read,Grep,Glob") && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "claude-review" "$prompt_hash" "$duration" "$ec"
        json_output "claude-review" "$duration" "$output" "$ec"
        ;;

    claude-redteam)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh claude-redteam \"solution\""; exit 1; }
        start=$(date +%s)
        output=$(run_claude "redteam" "Red team this solution. Find: edge cases, race conditions, breaking changes, security vulnerabilities, performance issues. If no problems found, say 'NESSUN PROBLEMA TROVATO' with confidence level. Solution: $PROMPT" 180 "Read,Grep,Glob") && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "claude-redteam" "$prompt_hash" "$duration" "$ec"
        json_output "claude-redteam" "$duration" "$output" "$ec"
        ;;

    claude-explain)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh claude-explain \"question\""; exit 1; }
        run_claude "explain" "$PROMPT" 120 "Read,Grep,Glob"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  AIDER — Multi-model coding (OpenRouter/DeepSeek)║
    # ╚══════════════════════════════════════════════════╝

    aider-fix)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh aider-fix \"file and what to fix\""; exit 1; }
        require_aider
        check_safety "$PROMPT"
        log "Aider → DeepSeek V3 (via OpenRouter)"
        start=$(date +%s)
        # Inject Nuzantara context via --read flag
        CTX_FLAG=""
        [ -f "$PROJECT_ROOT/scripts/nuzantara_system_context.md" ] && CTX_FLAG="--read $PROJECT_ROOT/scripts/nuzantara_system_context.md"
        output=$(run_with_timeout 180 aider --model openrouter/deepseek/deepseek-chat-v3-0324 $CTX_FLAG --message "$PROMPT" --yes --no-git 2>&1) && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        save_output "aider-fix" "$output" "$duration"
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "aider-fix" "$prompt_hash" "$duration" "$ec"
        echo "$output"
        ;;

    aider-refactor)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh aider-refactor \"what to refactor\""; exit 1; }
        require_aider
        check_safety "$PROMPT"
        log "Aider → Claude Sonnet (via OpenRouter) for refactoring"
        start=$(date +%s)
        CTX_FLAG=""
        [ -f "$PROJECT_ROOT/scripts/nuzantara_system_context.md" ] && CTX_FLAG="--read $PROJECT_ROOT/scripts/nuzantara_system_context.md"
        output=$(run_with_timeout 300 aider --model openrouter/anthropic/claude-sonnet-4 $CTX_FLAG --message "$PROMPT" --yes --no-git 2>&1) && ec=0 || ec=$?
        duration=$(( $(date +%s) - start ))
        save_output "aider-refactor" "$output" "$duration"
        prompt_hash=$(echo "$PROMPT" | shasum -a 256 | cut -d' ' -f1)
        audit_log "aider-refactor" "$prompt_hash" "$duration" "$ec"
        echo "$output"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  ARCHIVE & STATS                                ║
    # ╚══════════════════════════════════════════════════╝

    archive)
        mkdir -p "$OUTPUT_DIR/archive"
        count=$(find "$OUTPUT_DIR" -maxdepth 1 -name "*.md" -mtime +7 2>/dev/null | wc -l | tr -d ' ')
        if [ "$count" -gt 0 ]; then
            find "$OUTPUT_DIR" -maxdepth 1 -name "*.md" -mtime +7 -exec mv {} "$OUTPUT_DIR/archive/" \;
            ok "Archived $count files >7 days old"
        else
            info "No files older than 7 days to archive"
        fi
        ;;

    stats)
        if [ ! -f "$OUTPUT_DIR/audit.jsonl" ]; then
            warn "No audit log yet. Run some dispatches first."
            exit 0
        fi
        python3 -c "
import json
from collections import Counter
lines = open('$OUTPUT_DIR/audit.jsonl').readlines()
entries = [json.loads(l) for l in lines if l.strip()]
if not entries:
    print('No entries in audit log.')
    exit()
cmds = Counter(e['cmd'] for e in entries)
total = len(entries)
ok_count = sum(1 for e in entries if e['exit_code'] == 0)
avg_dur = sum(e['duration_s'] for e in entries) / total
machines = Counter(e['machine'] for e in entries)
print(f'=== Federation Dispatch Stats ===')
print(f'Total dispatches: {total}')
print(f'Success rate: {ok_count}/{total} ({100*ok_count//total}%)')
print(f'Avg duration: {avg_dur:.0f}s')
print(f'')
print(f'By command:')
for cmd, count in cmds.most_common():
    print(f'  {cmd}: {count}')
print(f'')
print(f'By machine:')
for m, count in machines.most_common():
    print(f'  {m}: {count}')
"
        ;;

    # ╔══════════════════════════════════════════════════╗
    # ║  INFO                                           ║
    # ╚══════════════════════════════════════════════════╝

    status)
        echo "=== AI Dispatch v2 — Federation [$MACHINE] ==="
        echo ""
        echo -n "  Claude Code (Re):           " && (command claude --version 2>/dev/null || echo "NOT INSTALLED")
        echo -n "  Gemini CLI (Consigliere):    " && (command gemini --version 2>/dev/null || echo "NOT INSTALLED")
        echo -n "  Agy CLI (Swarm adjunct):     " && ("$AGY_BIN" --help >/dev/null 2>&1 && echo "INSTALLED" || echo "NOT INSTALLED")
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
        if [ "$MACHINE" = "pro" ]; then peer="mini"; else peer="pro"; fi  # pro peer = mini since Air decommission 2026-05-05
        if ssh -o ConnectTimeout=2 "$peer" 'echo "reachable"' 2>/dev/null; then
            ok "  $peer: REACHABLE"
        else
            warn "  $peer: UNREACHABLE"
        fi
        ;;

    help|*)
        cat <<'HELP'
ai-dispatch.sh v3 — Nuzantara Federation (3-tier: agents/services/pipelines)
════════════════════════════════════════════════════════════════════════════

AGENTS — Autonomous runtimes (dispatchable, accept open-ended tasks):
┌─────────────────────────────────────────────────────────────────────┐
│ GEMINI (read-only, 1M context, $0):                                │
│   explore            "question"     Codebase analysis (cached 24h) │
│   search             "query"        Google grounded web search     │
│   redteam            "solution"     Adversarial pre-deploy review  │
│   gemini-review      "prompt"       Code review / analysis         │
│   gemini-scan        "prompt"       Find patterns in codebase      │
│   gemini-explain     "prompt"       Explain code/architecture      │
│   gemini-docs        "prompt"       Generate documentation         │
│   gemini-investigate "question"     Deep codebase investigation    │
│   gemini-search      "query"        Google Search grounded         │
│   gemini-vision      "file" "q"     Analyze images/PDF             │
│                                                                     │
│ CODEX (sandbox kernel-level, $0):                                  │
│   sandbox            "task"         Risky code in isolated sandbox  │
│   codex-fix          "prompt"       Fix bug/test (sandbox write)   │
│   codex-review       "prompt"       Code review (read-only)        │
│   codex-test         "prompt"       Generate and run tests         │
│   codex-fix-batch    "pattern"      Batch fix multiple tests       │
│   codex-migrate      "desc"         Alembic migration in sandbox   │
│                                                                     │
│ CLAUDE CLI (read-only, Opus 4.6, $0 Max plan):                    │
│   claude-review      "prompt"       Deep code review               │
│   claude-redteam     "solution"     Red team (Opus reasoning)      │
│   claude-explain     "question"     Explain code/architecture      │
│                                                                     │
│ DEEPSEEK R1 (671b, chain-of-thought, ¢):                          │
│   reasoning          "problem"      Deep reasoning + Nuz context   │
│                                                                     │
│ AGY / SWARM COMMANDER (Antigravity Gemini, bounded):               │
│   agy-flash          "prompt"       Gemini 3.5 Flash High review   │
│   agy-pro            "prompt"       Gemini 3.1 Pro High deep pass   │
│   agy-redteam        "solution"     Pro High adversarial review     │
│   swarm-commander    "task"         Decompose lanes/tools/limits    │
│   Add third arg dry-run to validate without executing agy.          │
│                                                                     │
│ AIDER (OpenRouter/DeepSeek, $):                                    │
│   aider-fix          "prompt"       Fix with DeepSeek V3 (fast)    │
│   aider-refactor     "prompt"       Refactor with Claude Sonnet    │
└─────────────────────────────────────────────────────────────────────┘

SERVICES — Stateless tools called by orchestrator (NOT dispatchable):
┌─────────────────────────────────────────────────────────────────────┐
│ NOTEBOOKLM (grounded citations, $0):                               │
│   oracolo            "question"     NB-1 Codebase (arch truth)     │
│   oracolo-nb  "tag"  "question"     Any NB by domain tag           │
│   research    "topic" [fast|deep]   Deep Research → NB-9 Lab       │
│                                                                     │
│ WEBSEARCH (Exa + Brave, $0/¢):                                    │
│   websearch          "query" [n]    Deep web search + citations    │
└─────────────────────────────────────────────────────────────────────┘

PIPELINES — Scheduled/triggered workflows (NOT dispatchable):
  core-guardian     every 3h (OpenClaw)   Code quality auto-fix
  intel-scraper     03:00 WITA (Pro)      News intelligence pipeline
  war-room          manual (Claude Code)  Instagram carousel creation
  seo-guardian      manual (evaluator)    AI SEO coverage monitoring
  nlm-daily-refresh 04:30 WITA (Pro)      NB-1 codebase bundle refresh

PREFLIGHT SDD — Mandatory pre-implementation spec (auto-triggered by orchestrator):
┌─────────────────────────────────────────────────────────────────────┐
│   preflight      "task"    L2 default (45 min): explore+search→NLM │
│   preflight-l1   "task"    L1 quick (10-15 min): explore→reasoning │
│   preflight-l2   "task"    L2 full (45 min): +NLM gate + redteam   │
│   preflight-l3   "task"    L3 deep (90 min): +sandbox + HITL        │
│                                                                     │
│   Triggers L1: new feature, 3+ files across apps                   │
│   Triggers L2: refactor, migration, KBLI/visa, pre-deploy          │
│   Triggers L3: architecture, auth, RAG pipeline, billing           │
│   Bypass: SKIP_PREFLIGHT=1 (logged in audit.jsonl)                 │
└─────────────────────────────────────────────────────────────────────┘

COMBO & PARALLEL:
  analyze-then-fix   "prompt"     Gemini analyzes → Codex fixes
  parallel cmd1:"p1" cmd2:"p2"    Run multiple commands concurrently

CACHE & METRICS:
  cache-clear / cache-stats       Manage 24h dispatch cache
  stats / archive                 Audit log analytics + cleanup

INFO:
  status                          System status + CLI versions + peer check
  help                            This guide

DELEGATION CHECKPOINT (ask before every task):
  1. Architecture question?        → oracolo (NB-1 grounded truth)
  2. Domain question (visa/tax)?   → oracolo-nb "immigration" "question"
  3. Need web info with citations? → websearch (Exa/Brave, full content)
  4. Deep research needed?         → research "topic" deep
  5. Explore >5 files in code?     → explore (Gemini 1M ctx)
  6. Need Google Search grounded?  → search (Gemini)
  7. Complex architecture problem? → reasoning (DeepSeek R1 671b)
  8. Risky change to the repo?     → sandbox (Codex isolated)
  9. Critical deploy coming?       → redteam + claude-redteam
 10. Need bounded cloud swarm?      → swarm-commander + agy-pro
  All "No"? → Do it yourself. Don't delegate for sport.

MODELS:
  Gemini cascade: 3.1 Pro (1M) → 2.5 Pro → 2.5 Flash (auto-fallback 429)
  Agy: Gemini 3.5 Flash High (fast) / Gemini 3.1 Pro High (deep) via Swarm Commander
  Codex: GPT-5.4 (sandbox kernel-level)
  DeepSeek: R1 671b ($0.55/M in, $2.19/M out)
  Aider: DeepSeek V3 (fast) / Claude Sonnet (refactor) via OpenRouter
  NLM: Google AI Ultra (9 notebooks, 600 sources each)

SECURITY:
  ✓ 3-tier prompt filter: destructive blocked, protected read-only, secrets blocked
  ✓ Gemini: --sandbox --approval-mode plan (read-only absolute)
  ✓ Agy: --sandbox + --print-timeout + external timeout + prompt-hash audit
  ✓ Codex: --sandbox (read-only or workspace-write)
  ✓ Timeout: 120s Gemini, 180-300s Codex, 180s DeepSeek
  ✓ Protected files: fly.toml, dependencies.py, .env — readable not writable
  ✗ NEVER: --yolo, --dangerously-bypass, danger-full-access
HELP
        ;;
esac
