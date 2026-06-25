#!/bin/bash
# intake-blob-retention-run.sh — wrapper for com.nuzantara.intake-blob-retention.
# Reclaims disk by unlinking BYTES of terminal intake blobs (done/routed/rejected/
# duplicate/dead) older than TTL. NEVER deletes DB rows (dedup registry).
# Local DB + filesystem only — no secrets, no Drive SA needed.
# Source of truth: scripts/intake_blob_retention.py (repo, exec-from-repo, NOT HOME-forked).
set -euo pipefail
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
export INTAKE_BLOB_TTL_DAYS="${INTAKE_BLOB_TTL_DAYS:-7}"
exec /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python \
  /Users/nuzantara/Desktop/nuzantara/scripts/intake_blob_retention.py --apply
