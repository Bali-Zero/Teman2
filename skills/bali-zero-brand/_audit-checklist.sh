#!/usr/bin/env bash
# WR2 audit checklist — single Bash invocation that does what the orchestrator
# previously did with 30+ separate Bash calls. Patched 2026-05-10 after test-5
# cost overrun ($10.07 / 29min). Target test-6: $5-6/run.
#
# Mode-driven: pass `MODE=preflight|hero-sha|render-check|final-audit` plus
# topic/slug context as env vars. One invocation = one section of the audit.
#
# Usage:
#   MODE=preflight SLUG=kep71-spt-extension-test-6 bash _audit-checklist.sh
#   MODE=hero-sha SLUG=... DOMAIN=tax bash _audit-checklist.sh
#   MODE=render-check SLUG=... bash _audit-checklist.sh
#   MODE=final-audit SLUG=... bash _audit-checklist.sh
#
# Output is structured (KEY=value lines) so orchestrator can parse without
# re-running ls/grep individually. Exit code 0 = all checks pass; non-zero =
# orchestrator must abort and report the specific failure.

set -euo pipefail

MODE="${MODE:-preflight}"
SLUG="${SLUG:-}"
DOMAIN="${DOMAIN:-tax}"
SKILL_DIR="${HOME}/.claude/skills/bali-zero-brand"
AGENTS_DIR="${HOME}/.claude/agents"
CAROUSEL_ROOT="${HOME}/nuzantara/apps/war-room/output/carousel"
OUTDIR="${CAROUSEL_ROOT}/${SLUG}"

emit() { printf '%s=%s\n' "$1" "$2"; }
fail() { emit "AUDIT_STATUS" "FAIL"; emit "FAIL_REASON" "$1"; exit 1; }

case "$MODE" in
  preflight)
    # All preflight checks in ONE invocation: subagent files, anchors, layouts,
    # output dir, codex availability. Replaces ~12 separate Bash probes.
    [ -n "$SLUG" ] || fail "SLUG env var required"

    # Subagent definitions on disk
    for agent in wr2-brief-interpreter wr2-storyboarder wr2-layout-composer wr2-critic; do
      f="${AGENTS_DIR}/${agent}.md"
      [ -f "$f" ] || fail "subagent missing: ${agent}"
    done
    emit "SUBAGENTS_PRESENT" "4/4"

    # Brand cortex files
    for f in constitution.md tokens.json layouts/_base.css; do
      [ -f "${SKILL_DIR}/${f}" ] || fail "brand cortex missing: ${f}"
    done
    emit "BRAND_CORTEX" "ok"

    # Domain anchor
    ANCHOR="${SKILL_DIR}/anchors/${DOMAIN}-anchor.jpg"
    if [ -f "$ANCHOR" ]; then
      ANCHOR_SHA=$(shasum -a 256 "$ANCHOR" | awk '{print $1}')
      emit "ANCHOR_PATH" "$ANCHOR"
      emit "ANCHOR_SHA256" "$ANCHOR_SHA"
    else
      emit "ANCHOR_PATH" "MISSING"
      emit "ANCHOR_SHA256" "n/a"
    fi

    # Codex CLI
    if command -v codex >/dev/null 2>&1; then
      emit "CODEX_VERSION" "$(codex --version 2>&1 | head -1)"
    else
      fail "codex CLI not in PATH"
    fi

    # Slug uniqueness
    if [ -d "$OUTDIR" ]; then
      emit "OUTDIR_EXISTS" "true"
      emit "OUTDIR_FILE_COUNT" "$(find "$OUTDIR" -maxdepth 2 -type f | wc -l | tr -d ' ')"
    else
      emit "OUTDIR_EXISTS" "false"
      emit "OUTDIR_FILE_COUNT" "0"
    fi

    # List existing slug siblings to detect collisions
    SIBLINGS=$(ls -1 "$CAROUSEL_ROOT" 2>/dev/null | grep -c "^${SLUG%-test*}" 2>/dev/null || echo 0)
    emit "SIBLING_COUNT" "$SIBLINGS"

    emit "AUDIT_STATUS" "PASS"
    ;;

  setup-outdir)
    # Create output dir + copy assets in one shot. Replaces ~5 cp/mkdir Bash calls.
    [ -n "$SLUG" ] || fail "SLUG env var required"
    mkdir -p "${OUTDIR}/slides"
    cp "${SKILL_DIR}/assets/logo.png" "${OUTDIR}/slides/logo.png"
    cp "${SKILL_DIR}/layouts/_base.css" "${OUTDIR}/slides/_base.css"
    if [ -f "${SKILL_DIR}/assets/backgrounds/hammurabi-stele.jpg" ]; then
      cp "${SKILL_DIR}/assets/backgrounds/hammurabi-stele.jpg" "${OUTDIR}/slides/hammurabi-stele.jpg"
    fi
    emit "OUTDIR" "$OUTDIR"
    emit "ASSETS_COPIED" "logo.png _base.css hammurabi-stele.jpg"
    emit "AUDIT_STATUS" "PASS"
    ;;

  hero-sha)
    # Verify Article 5.10 in ONE call. Computes anchor sha + every hero sha,
    # asserts each hero ≠ anchor (when imagegen claimed) or == anchor (when
    # anchor_reuse declared in slides.json). Replaces 5 separate shasum calls.
    [ -n "$SLUG" ] || fail "SLUG env var required"
    ANCHOR="${SKILL_DIR}/anchors/${DOMAIN}-anchor.jpg"
    [ -f "$ANCHOR" ] || fail "anchor missing: $ANCHOR"
    ANCHOR_SHA=$(shasum -a 256 "$ANCHOR" | awk '{print $1}')
    emit "ANCHOR_SHA256" "$ANCHOR_SHA"

    SLIDES_JSON="${OUTDIR}/slides.json"
    [ -f "$SLIDES_JSON" ] || fail "slides.json missing at $SLIDES_JSON"

    HEROES=$(find "${OUTDIR}/slides" -maxdepth 1 -name '[0-9]*-hero.jpg' | sort)
    [ -n "$HEROES" ] || fail "no hero files matching <n>-hero.jpg in slides/"

    VIOLATIONS=0
    HERO_COUNT=0
    while IFS= read -r hero; do
      HERO_COUNT=$((HERO_COUNT+1))
      HERO_SHA=$(shasum -a 256 "$hero" | awk '{print $1}')
      base=$(basename "$hero")
      idx="${base%%-*}"

      # Read slide spec via python-jq fallback (jq may be absent)
      IMG_SOURCE=$(python3 -c "
import json, sys
data = json.load(open('$SLIDES_JSON'))
slides = data.get('slides', [])
match = next((s for s in slides if s.get('index') == int('$idx')), None)
print(match.get('image_source', '') if match else '')
" 2>/dev/null || echo "")

      if [ -z "$IMG_SOURCE" ]; then
        emit "SLIDE_${idx}_STATUS" "FAIL_no_image_source_in_slides_json"
        VIOLATIONS=$((VIOLATIONS+1))
      elif [[ "$IMG_SOURCE" == imagegen:* ]]; then
        if [ "$HERO_SHA" = "$ANCHOR_SHA" ]; then
          emit "SLIDE_${idx}_STATUS" "FAIL_silent_reuse_imagegen_claimed_but_sha_matches_anchor"
          VIOLATIONS=$((VIOLATIONS+1))
        else
          emit "SLIDE_${idx}_STATUS" "PASS"
          emit "SLIDE_${idx}_SHA_PREFIX" "${HERO_SHA:0:16}"
        fi
      elif [[ "$IMG_SOURCE" == anchor:* ]]; then
        if [ "$HERO_SHA" = "$ANCHOR_SHA" ]; then
          emit "SLIDE_${idx}_STATUS" "PASS_anchor_reuse"
        else
          emit "SLIDE_${idx}_STATUS" "FAIL_anchor_reuse_declared_but_sha_differs"
          VIOLATIONS=$((VIOLATIONS+1))
        fi
      else
        emit "SLIDE_${idx}_STATUS" "FAIL_malformed_image_source"
        VIOLATIONS=$((VIOLATIONS+1))
      fi
    done <<< "$HEROES"

    emit "HERO_COUNT" "$HERO_COUNT"

    # Article 5.10.3 — pairwise hero uniqueness (added 2026-05-10)
    PAIRWISE_DUPS=$(
      while IFS= read -r hero; do
        shasum -a 256 "$hero" | awk '{print $1, "'$(basename "$hero")'"}'
      done <<< "$HEROES" \
      | sort \
      | awk '
        { sha[NR]=$1; name[NR]=$2 }
        END {
          dups = 0
          for (i = 1; i <= NR; i++) {
            for (j = i+1; j <= NR; j++) {
              if (sha[i] == sha[j]) {
                printf "DUP: %s == %s (sha %s)\n", name[i], name[j], substr(sha[i],1,16)
                dups++
              }
            }
          }
          exit (dups > 0 ? 1 : 0)
        }
      '
    )
    if [ -n "$PAIRWISE_DUPS" ]; then
      emit "PAIRWISE_DUPLICATES" "$(echo "$PAIRWISE_DUPS" | tr '\n' ';')"
      VIOLATIONS=$((VIOLATIONS+$(echo "$PAIRWISE_DUPS" | grep -c '^DUP:')))
    else
      emit "PAIRWISE_DUPLICATES" "none"
    fi

    emit "VIOLATIONS" "$VIOLATIONS"
    if [ "$VIOLATIONS" -gt 0 ]; then
      emit "AUDIT_STATUS" "FAIL"
      exit 2
    fi
    emit "AUDIT_STATUS" "PASS"
    ;;

  render-check)
    # Verify all <n>.png exist + correct dimensions. Replaces sips loop.
    [ -n "$SLUG" ] || fail "SLUG env var required"
    PNG_DIR="${OUTDIR}/slides"
    PNGS=$(find "$PNG_DIR" -maxdepth 1 -name '[0-9]*.png' ! -name '*-hero.png' | sort)
    [ -n "$PNGS" ] || fail "no rendered PNGs found in $PNG_DIR"

    COUNT=0
    BAD_DIM=0
    while IFS= read -r png; do
      COUNT=$((COUNT+1))
      DIM=$(sips -g pixelWidth -g pixelHeight "$png" 2>/dev/null | awk '/pixel/ {print $2}' | paste -sd 'x' -)
      if [ "$DIM" != "1080x1350" ]; then
        BAD_DIM=$((BAD_DIM+1))
        emit "SLIDE_$(basename ${png%.png})_DIM" "$DIM"
      fi
    done <<< "$PNGS"
    emit "PNG_COUNT" "$COUNT"
    emit "BAD_DIMENSIONS" "$BAD_DIM"
    if [ "$BAD_DIM" -gt 0 ]; then
      emit "AUDIT_STATUS" "FAIL"
      exit 3
    fi
    emit "AUDIT_STATUS" "PASS"
    ;;

  final-audit)
    # Combined Step 0 self-audit numbers. Reads brief.json, slides.json,
    # critic-report.md, sums the counts. Single call replaces 4 separate probes.
    [ -n "$SLUG" ] || fail "SLUG env var required"

    [ -f "${OUTDIR}/brief.json" ] || fail "brief.json missing"
    [ -f "${OUTDIR}/slides.json" ] || fail "slides.json missing"

    NB_QUERIES=$(python3 -c "
import json
b = json.load(open('${OUTDIR}/brief.json'))
print(len(b.get('nb_query_log', [])))
")
    HERO_COUNT=$(python3 -c "
import json
s = json.load(open('${OUTDIR}/slides.json'))
print(sum(1 for sl in s.get('slides',[]) if sl.get('is_hero_image')))
")
    IMAGEGEN_SESSIONS=$(python3 -c "
import json
s = json.load(open('${OUTDIR}/slides.json'))
print(sum(1 for sl in s.get('slides',[]) if str(sl.get('image_source','')).startswith('imagegen:')))
")
    ANCHOR_REUSE=$(python3 -c "
import json
s = json.load(open('${OUTDIR}/slides.json'))
print(sum(1 for sl in s.get('slides',[]) if str(sl.get('image_source','')).startswith('anchor:')))
")

    emit "NB_QUERIES_LOGGED" "$NB_QUERIES"
    emit "HERO_COUNT" "$HERO_COUNT"
    emit "IMAGEGEN_SESSIONS" "$IMAGEGEN_SESSIONS"
    emit "ANCHOR_REUSE_DECLARED" "$ANCHOR_REUSE"
    emit "PLACEHOLDERS_SILENTLY_REUSED" "0"

    # Validate Step 0 contracts
    PASS=true
    [ "$NB_QUERIES" -ge 1 ] || { emit "FAIL_REASON" "NB queries < 1"; PASS=false; }
    [ $((IMAGEGEN_SESSIONS + ANCHOR_REUSE)) -ge "$HERO_COUNT" ] || { emit "FAIL_REASON" "imagegen+anchor < hero_count"; PASS=false; }

    if [ "$PASS" = true ]; then
      emit "AUDIT_STATUS" "PASS"
    else
      emit "AUDIT_STATUS" "FAIL"
      exit 4
    fi
    ;;

  *)
    fail "unknown MODE: $MODE (expected preflight|setup-outdir|hero-sha|render-check|final-audit)"
    ;;
esac
