#!/bin/bash
# fix_skills_agents_drift.sh — opus-mythos TAC Skills&Agents organ (2026-06-16).
#
# Cures the HOME-fork + stale-model drift the TAC found in ~/.claude/{skills,agents}.
# These files are HOME-only (not repo-tracked) and host_boundary-protected, so an
# AI session can't edit them — the operator runs THIS from a terminal.
#
# The TAC gated the subagents' scary numbers (931 HOME-fork / 644 stale-model) down
# to ~16 + 6 REAL ones (the rest were inside historical .log files). This script
# fixes only the live, load-bearing ones, PATH-AWARE (uses $HOME, not a hardcoded
# user — so it stays correct on Pro/Mini where the user is `nuzantara`, not
# `balizero`). Then it installs a lint VACCINE that catches future drift.
#
# USAGE (terminal, NOT from inside the Claude agent — needs host_boundary off):
#   HOST_BOUNDARY_OFF=1 bash scripts/fix_skills_agents_drift.sh
#   HOST_BOUNDARY_OFF=1 bash scripts/fix_skills_agents_drift.sh --dry-run   # preview only
#
# Idempotent. Backs up each file (chmod 600 backup). Self-verifies at the end.
set -uo pipefail

DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
CL="$HOME/.claude"
TS="$(date +%Y%m%d-%H%M%S)"
say(){ printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
note(){ printf '   %s\n' "$*"; }

# sed -i portable (BSD/macOS needs '' after -i)
sedi(){ sed -i '' "$@" 2>/dev/null || sed -i "$@"; }

backup(){ # $1=file
  [ -f "$1" ] || { note "SKIP (absent): ${1#$CL/}"; return 1; }
  if [ "$DRY" = 0 ]; then cp "$1" "$1.bak-drift-$TS"; chmod 600 "$1.bak-drift-$TS"; fi
  return 0
}

apply(){ # $1=file $2=sed-expr $3=human-label
  backup "$1" || return 0
  local before after
  before=$(grep -cE "${4:-.}" "$1" 2>/dev/null || echo 0)
  if [ "$DRY" = 1 ]; then
    note "[dry] $3 — would run: sed $2"
    grep -nE "${4:-XXXNOMATCHXXX}" "$1" 2>/dev/null | sed 's/^/        /' | head -4
  else
    sedi "$2" "$1"
    note "✓ $3"
  fi
}

say "0. Target check"
for f in "$CL/skills/agent-session-discipline/SKILL.md" \
         "$CL/skills/bali-zero-brand/_manual_inject_runner.py" \
         "$CL/skills/bali-zero-brand/_damar-queue-server.py" \
         "$CL/skills/bali-zero-brand/_reflexion-synthesis.py" \
         "$CL/agents/devils-advocate.md" \
         "$CL/agents/client-case-quote-generator.md"; do
  [ -f "$f" ] && note "found: ${f#$CL/}" || note "ABSENT: ${f#$CL/}"
done

# --- HOME-fork fixes: /Users/nuzantara → $HOME-relative -----------------------
# SKILL.md is documentation; the path appears in prose/examples. The cleanest
# machine-agnostic doc is "the main checkout" (~/nuzantara). We rewrite
# the literal /Users/nuzantara/nuzantara → $HOME/nuzantara form
# (in .md as the literal "~/nuzantara" so it reads on any machine).
# Strategy: `/Users/nuzantara/nuzantara` is the REPO root — identical on
# every machine, so → `~/nuzantara` (.md docs) or `$HOME/nuzantara`
# (.py runtime). NON-repo /Users/nuzantara paths (Voice-Corpus, ~/scripts wrappers)
# are machine-specific or genuinely portable-via-$HOME — handled per-file below.
say "1. HOME-fork: doc files (.md) — /Users/nuzantara → ~ (portable on any machine)"
for md in \
  "skills/agent-session-discipline/SKILL.md" \
  "skills/canva-apply.md" \
  "skills/regulatory-ingest.md" \
  "skills/bali-zero-brand/_canva_apply_import_pattern.md" \
  "agents/wr2-ig-metrics-analyst.md" \
  "agents/wr3-audio-asset-producer.md" \
  "agents/wr3-shot-director.md"; do
  apply "$CL/$md" \
    's#/Users/nuzantara#~#g' \
    "$md: /Users/nuzantara → ~" '/Users/nuzantara'
done

# Python scripts: literal /Users/nuzantara → $HOME (this script runs AS the
# operator on the target machine, so $HOME resolves correctly per-host).
say "2. HOME-fork: bali-zero-brand Python scripts (hardcoded → \$HOME)"
for py in _manual_inject_runner.py _damar-queue-server.py; do
  apply "$CL/skills/bali-zero-brand/$py" \
    "s#/Users/nuzantara#$HOME#g" \
    "$py: /Users/nuzantara → $HOME" '/Users/nuzantara'
done

# --- stale model IDs: claude-opus-4-7 → claude-opus-4-8, deepseek-reasoner → v4-pro
say "3. Stale model IDs → current roster"
apply "$CL/agents/devils-advocate.md" \
  's/deepseek-reasoner/deepseek-v4-pro/g' \
  "devils-advocate: deepseek-reasoner → deepseek-v4-pro" 'deepseek-reasoner'
apply "$CL/agents/devils-advocate.md" \
  's/DeepSeek Reasoner/DeepSeek V4 Pro/g' \
  "devils-advocate prose: DeepSeek Reasoner → V4 Pro" 'DeepSeek Reasoner'
apply "$CL/skills/bali-zero-brand/_manual_inject_runner.py" \
  's/claude-opus-4-7/claude-opus-4-8/g' \
  "_manual_inject_runner: opus-4-7 → opus-4-8" 'claude-opus-4-7'
apply "$CL/skills/bali-zero-brand/_reflexion-synthesis.py" \
  's/claude-opus-4-7/claude-opus-4-8/g' \
  "_reflexion-synthesis: opus-4-7 → opus-4-8" 'claude-opus-4-7'
apply "$CL/agents/client-case-quote-generator.md" \
  's/Opus 4\.7/Opus 4.8/g; s/claude-opus-4-7/claude-opus-4-8/g; s/deepseek-reasoner/deepseek-v4-pro/g; s/DeepSeek Reasoner/DeepSeek V4 Pro/g' \
  "client-case-quote: Opus 4.7→4.8 + deepseek-reasoner→v4-pro (incl. curl :85)" 'Opus 4\.7\|deepseek-reasoner'

# --- install the lint VACCINE -------------------------------------------------
say "4. Install drift lint vaccine"
LINT="$CL/scripts/lint_skills_agents_drift.py"
if [ "$DRY" = 1 ]; then
  note "[dry] would install lint at $LINT"
else
  mkdir -p "$CL/scripts"
  # the lint script source travels WITH this fixer in the repo; copy the sibling
  SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lint_skills_agents_drift.py"
  if [ -f "$SRC" ]; then
    cp "$SRC" "$LINT"; chmod 755 "$LINT"
    note "✓ installed $LINT"
  else
    note "⚠ lint source not found at $SRC — install manually"
  fi
fi

# --- self-verify --------------------------------------------------------------
say "5. Self-verify (the vaccine reports remaining LIVE drift)"
if [ "$DRY" = 1 ]; then
  note "[dry] skipped — no changes applied"
else
  if [ -f "$CL/scripts/lint_skills_agents_drift.py" ]; then
    python3 "$CL/scripts/lint_skills_agents_drift.py" || true
  fi
fi

say "DONE"
note "Backups: $CL/**/*.bak-drift-$TS (chmod 600)"
note "Re-run the lint anytime: python3 $CL/scripts/lint_skills_agents_drift.py"
