#!/usr/bin/env bash
# ai-dispatch.sh — Orchestratore AI multi-agente per Nuzantara
#
# ARCHITETTURA:
#   Claude Code (Opus 4.6) = Il Re — orchestra, sintetizza, decide, esegue
#   Gemini CLI (3.1 Pro)   = Il Consigliere — 1M ctx, Google Search, codebase_investigator
#   Codex CLI (GPT-5.4)    = Il Soldato in Fortezza — sandbox kernel-level, code review nativo
#
# Tutti via CLI con abbonamento fisso. Zero API a pagamento.
#
# Usage:
#   ./scripts/ai-dispatch.sh <command> "prompt"
#   ./scripts/ai-dispatch.sh help

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

CMD="${1:-help}"
PROMPT="${2:-}"
EXTRA="${3:-}"

# Bypass alias --yolo che esiste in .zshrc su Air
GEMINI_BIN="command gemini"
CODEX_BIN="command codex"

# timeout: macOS non ha timeout nativo, usa gtimeout se disponibile
if command -v gtimeout &>/dev/null; then
    TIMEOUT_CMD="gtimeout"
elif command -v timeout &>/dev/null; then
    TIMEOUT_CMD="timeout"
else
    # Fallback: nessun timeout, esegui direttamente
    TIMEOUT_CMD=""
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

# Output directory per log
OUTPUT_DIR="$PROJECT_ROOT/ai-dispatch-output"
mkdir -p "$OUTPUT_DIR"

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${BLUE}[dispatch]${NC} $1"; }
warn() { echo -e "${YELLOW}[dispatch]${NC} $1"; }
err() { echo -e "${RED}[dispatch]${NC} $1" >&2; }
ok() { echo -e "${GREEN}[dispatch]${NC} $1"; }
info() { echo -e "${CYAN}[dispatch]${NC} $1"; }

# Safety: blocca termini pericolosi nel prompt
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
            err "BLOCKED: prompt contiene '$pattern' — operazione vietata per worker AI"
            exit 1
        fi
    done
}

# Save output to file and return path
save_output() {
    local cmd_name="$1"
    local output="$2"
    local timestamp=$(date '+%Y%m%d-%H%M%S')
    local hash=$(echo "$output" | md5 -q 2>/dev/null || echo "$RANDOM")
    local outfile="$OUTPUT_DIR/${timestamp}-${cmd_name}-${hash:0:8}.md"
    echo "$output" > "$outfile"
    info "Output salvato: $outfile"
}

run_gemini() {
    local mode="$1"
    local prompt="$2"
    local timeout="${3:-120}"
    check_safety "$prompt"
    log "Gemini 3.1 Pro (1M ctx) → $mode [sandbox + plan, read-only]"

    local output
    if output=$(run_with_timeout "$timeout" $GEMINI_BIN --sandbox --approval-mode plan -p "$prompt" -o text 2>&1); then
        save_output "gemini-$mode" "$output"
        echo "$output"
    else
        local exit_code=$?
        if [ "$exit_code" -eq 124 ]; then
            err "TIMEOUT: Gemini non ha risposto in ${timeout}s. Riprova con prompt più semplice."
        else
            err "Gemini ha fallito (exit $exit_code)"
            echo "$output"
        fi
        return 1
    fi
}

run_codex() {
    local sandbox="$1"
    local prompt="$2"
    local timeout="${3:-180}"
    check_safety "$prompt"
    log "Codex GPT-5.4 → sandbox=$sandbox"

    local output
    if output=$(run_with_timeout "$timeout" $CODEX_BIN exec --sandbox "$sandbox" "$prompt" 2>&1); then
        save_output "codex-$sandbox" "$output"
        echo "$output"
    else
        local exit_code=$?
        if [ "$exit_code" -eq 124 ]; then
            err "TIMEOUT: Codex non ha risposto in ${timeout}s. Riprova."
        else
            err "Codex ha fallito (exit $exit_code)"
            echo "$output"
        fi
        return 1
    fi
}

case "$CMD" in

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  GEMINI CLI — Il Consigliere                                ║
    # ║  1M context, Google Search grounded, codebase_investigator  ║
    # ║  Abbonamento fisso, read-only                               ║
    # ╚══════════════════════════════════════════════════════════════╝

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

    gemini-search)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-search \"query\""; exit 1; }
        check_safety "$PROMPT"
        log "Gemini → Google Web Search (grounded, con citazioni)"
        run_gemini "search" "Use google_web_search to find: $PROMPT. Provide a summary with sources and citations."
        ;;

    gemini-vision)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-vision \"file_path\" \"what to analyze\""; exit 1; }
        local_file="$PROMPT"
        analysis="${EXTRA:-Analyze this file in detail}"
        check_safety "$analysis"
        if [ ! -f "$local_file" ]; then
            err "File not found: $local_file"
            exit 1
        fi
        log "Gemini → Analisi immagine/PDF: $local_file"
        run_gemini "vision" "Read and analyze the file at '$local_file'. $analysis"
        ;;

    gemini-investigate)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-investigate \"question\""; exit 1; }
        run_gemini "investigate" "Use your codebase_investigator tool to deeply analyze: $PROMPT. Trace all dependencies, map the architecture, find the root cause." 180
        ;;

    # RED TEAM — Gemini critica una soluzione proposta prima del deploy
    gemini-redteam)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh gemini-redteam \"descrizione soluzione\""; exit 1; }
        log "Gemini → RED TEAM (critica pre-deploy)"
        run_gemini "redteam" "Analizza questa soluzione proposta. Il tuo obiettivo è demolirla.
Cerca: edge case non gestiti, race condition, breaking change per API esistenti,
problemi di performance sotto carico, vulnerabilità di sicurezza,
incompatibilità con la normativa indonesiana vigente.
Se non trovi problemi, dichiara esplicitamente 'NESSUN PROBLEMA TROVATO'
con la tua confidence level (alta/media/bassa).

Soluzione da analizzare:
$PROMPT" 180
        ;;

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  CODEX CLI — Il Soldato in Fortezza                         ║
    # ║  Sandbox kernel-level, code review nativo, web search       ║
    # ║  Abbonamento fisso                                          ║
    # ╚══════════════════════════════════════════════════════════════╝

    codex-fix)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-fix \"prompt\""; exit 1; }
        run_codex "workspace-write" "$PROMPT"
        ;;

    codex-review)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-review \"prompt\""; exit 1; }
        check_safety "$PROMPT"
        log "Codex → code review nativo (sandbox read-only)"
        local output
        if output=$(run_with_timeout 180 $CODEX_BIN review --sandbox read-only "$PROMPT" 2>&1); then
            save_output "codex-review" "$output"
            echo "$output"
        else
            err "Codex review ha fallito"
            echo "$output"
        fi
        ;;

    codex-test)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-test \"prompt\""; exit 1; }
        run_codex "workspace-write" "Write tests for the following. Only create files in tests/ directory. Run the tests after writing them: $PROMPT"
        ;;

    codex-search)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-search \"query\""; exit 1; }
        run_codex "read-only" "Search the web for: $PROMPT. Provide a detailed summary with sources."
        ;;

    codex-fix-batch)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh codex-fix-batch \"test pattern\""; exit 1; }
        run_codex "workspace-write" "Fix ALL failing tests matching this pattern: $PROMPT. Run each test after fixing to verify. Report results for each file." 300
        ;;

    # MIGRATION ALEMBIC — Genera, testa upgrade+downgrade, restituisce solo se passa
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

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  COMBO — Pattern multi-agente                               ║
    # ╚══════════════════════════════════════════════════════════════╝

    analyze-then-fix)
        [ -z "$PROMPT" ] && { err "Usage: ai-dispatch.sh analyze-then-fix \"what to analyze and fix\""; exit 1; }
        check_safety "$PROMPT"
        log "COMBO: Gemini analizza → Codex fixa (sandbox)"

        info "Step 1/2: Gemini analizza..."
        ANALYSIS=$($GEMINI_BIN --sandbox --approval-mode plan -p "Analyze and list ALL issues with specific file:line references for: $PROMPT. Output as a numbered list of issues with exact file paths and line numbers." -o text 2>&1) || true

        echo ""
        info "Gemini ha trovato:"
        echo "$ANALYSIS" | head -50
        echo ""
        save_output "combo-analysis" "$ANALYSIS"

        info "Step 2/2: Codex fixa in sandbox..."
        FIX_OUTPUT=$($CODEX_BIN exec --sandbox workspace-write "Based on this analysis, fix the issues listed below. Only modify the files mentioned. Run tests after each fix.

Analysis:
$ANALYSIS" 2>&1) || true
        save_output "combo-fix" "$FIX_OUTPUT"
        echo "$FIX_OUTPUT"
        ;;

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  INFO                                                       ║
    # ╚══════════════════════════════════════════════════════════════╝

    status)
        echo "=== AI Dispatch — Sistema Multi-Agente ==="
        echo ""
        echo -n "  Claude Code (Re):           " && (command claude --version 2>/dev/null || echo "NOT INSTALLED")
        echo -n "  Gemini CLI (Consigliere):    " && (command gemini --version 2>/dev/null || echo "NOT INSTALLED")
        echo -n "  Codex CLI (Soldato):         " && (command codex --version 2>/dev/null || echo "NOT INSTALLED")
        echo ""
        echo "Config files:"
        [ -f "$PROJECT_ROOT/CLAUDE.md" ] && ok "  CLAUDE.md ✓" || warn "  CLAUDE.md MISSING"
        [ -f "$PROJECT_ROOT/GEMINI.md" ] && ok "  GEMINI.md ✓" || warn "  GEMINI.md MISSING"
        [ -f "$PROJECT_ROOT/codex.md" ] && ok "  codex.md  ✓" || warn "  codex.md MISSING"
        echo ""
        echo "Output directory:"
        count=$(find "$OUTPUT_DIR" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
        ok "  $OUTPUT_DIR/ ($count file)"
        echo ""
        echo "Gemini alias check:"
        if alias gemini 2>/dev/null | grep -q "yolo"; then
            warn "  gemini alias has --yolo! Dispatch uses 'command gemini' to bypass."
        else
            ok "  gemini alias is clean"
        fi
        ;;

    help|*)
        cat <<'HELP'
ai-dispatch.sh — Sistema AI Multi-Agente per Nuzantara
═══════════════════════════════════════════════════════

RUOLI (tutti CLI con abbonamento fisso, zero API):
  Claude Code (Opus 4.6)  = Il Re — orchestra, sintetizza, decide, esegue
  Gemini CLI (3.1 Pro)    = Il Consigliere — 1M ctx, Google Search, analisi
  Codex CLI (GPT-5.4)     = Il Soldato — sandbox kernel-level, fix isolati

GEMINI (read-only, abbonamento fisso, 1M context):
  gemini-review      "prompt"              Code review / analisi
  gemini-scan        "prompt"              Cerca pattern nel codebase
  gemini-explain     "prompt"              Spiega codice/architettura
  gemini-docs        "prompt"              Genera documentazione
  gemini-search      "query"              Google Search grounded con citazioni
  gemini-vision      "file" "analysis"    Analisi immagini/PDF
  gemini-investigate "question"           Deep codebase investigation (sub-agent)
  gemini-redteam     "soluzione"          Red team: critica pre-deploy

CODEX (sandbox kernel-level, abbonamento fisso):
  codex-fix          "prompt"              Fix bug/test (sandbox write)
  codex-review       "path or prompt"      Code review nativo
  codex-test         "prompt"              Genera e run test (sandbox write)
  codex-search       "query"              Web search
  codex-fix-batch    "test pattern"        Fix multipli test in parallelo
  codex-migrate      "description"         Migration Alembic in sandbox

COMBO:
  analyze-then-fix   "prompt"              Gemini analizza → Codex fixa

INFO:
  status                                   Stato sistema
  help                                     Questa guida

OUTPUT:
  Ogni comando salva in ./ai-dispatch-output/[timestamp]-[cmd]-[hash].md

SICUREZZA:
  ✓ Gemini: --sandbox --approval-mode plan (read-only assoluto)
  ✓ Codex:  --sandbox (read-only o workspace-write)
  ✓ Timeout: 120s Gemini, 180s Codex (configurabile)
  ✓ Prompt filter blocca comandi pericolosi + file critici
  ✓ Alias --yolo bypassato
  ✗ MAI: --yolo, --dangerously-bypass, danger-full-access
HELP
        ;;
esac
