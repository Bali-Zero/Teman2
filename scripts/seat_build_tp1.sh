#!/usr/bin/env bash
# Sourced by scripts/seat_build.sh — see its `tp1)` case arms. A parallel lane
# owns seat_build.sh's tier/effort/ctx work, so every TP1-specific line lives
# here instead of growing that file's diff (coordination note, tp1-routes-0826).
#
# SCOPE BOUNDARY, stated explicitly because it is easy to assume otherwise:
# TP1 (Alibaba Token Plan) has no agentic coding CLI behind it — scripts/tp1_call.py
# is a raw chat-completions call. A tp1 "build" therefore produces a TEXT ANSWER
# (an implementer's proposed diff/analysis, or a refuter's verdict) written to
# the seat log, never a worktree edit the way codex/kimi/qwen make one — those
# three are agentic CLIs that read/write files themselves inside $WORKTREE; TP1
# cannot. A caller that needs code actually applied must read $LOG_PATH and
# apply it deliberately. This matches how the only other TP1 consumer in this
# repo already treats these models: freeze_worker_plane_review.py's retired
# glm/deepseek council routes used them as opinion-only review seats, never as
# file-editors. MODEL_ROSTER.md's own TP1 table agrees: "Implementer/refuter
# only" for all seven, and final-gate "no" for all seven. Quorum is NOT uniform:
# six say "no", but qwen3.8-max says YES — it is in COUNCIL_REVIEW_SEATS
# (scripts/evidence_pack_lint.py, R9) because it is the one TP1 seat promoted
# ARMED (2026-08-14, 459 calls / 74.1M tokens). This line claimed "no" for all
# seven until 2026-09-02, which was the doc side of a live contradiction with
# that lint; see the note under MODEL_ROSTER.md's TP1 table.
#
# This file only ever runs SOURCED (from seat_build.sh); it defines no top-level
# side effects of its own.

# Workhorse-first default (MODEL_ROSTER.md Throughput doctrine, ruling Zero
# 2026-08-19): qwen3.7-plus is explicitly named as a default-tier TP1 seat.
# Override per-call with TP1_MODEL=<slug> in the environment.
TP1_DEFAULT_MODEL="qwen3.7-plus"

tp1_binary_path() {
    # Absolute path, not a bare name: tp1_call.py is not installed on PATH.
    # `command -v` (seat_build.sh's own resolution step) accepts an absolute
    # executable path exactly like a PATH-resolved binary name.
    printf '%s/tp1_call.py\n' "$SCRIPT_DIR"
}
