#!/usr/bin/env bash
# One-shot cleanup for T3 live-test residue.
#
# Why this exists:
# - The T3 live test created a production CRM client row (id=19037) and an
#   orphan Google Drive file.
# - This script soft-deletes only the CRM row, after printing the identifying
#   row for operator review.
# - Drive deletion is intentionally manual because this script has no Drive
#   credentials and must not fabricate a file id.
#
# Safe to delete this file after Zero runs and reviews the cleanup.

set -euo pipefail

CLIENT_ID=19037
PSQL_BIN="${PSQL_BIN:-psql}"
PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-15432}"
PGDATABASE="${PGDATABASE:-nuzantara_rag}"
PGWRITE_CONN="${PGWRITE_CONN:-}"

usage() {
  cat <<'EOF'
Usage:
  scripts/cleanup_t3_test_residue.sh --confirm

Required:
  --confirm       Required guardrail. The script refuses to run without it.

Database credentials:
  Provide either:
    PGWRITE_CONN='host=127.0.0.1 port=15432 dbname=nuzantara_rag user=<write_role> sslmode=disable'
  or:
    PGUSER=<write_role> PGPASSWORD=<password>

Defaults mirror the production proxy shape documented in scripts/pg.sh:
  PGHOST=127.0.0.1
  PGPORT=15432
  PGDATABASE=nuzantara_rag

This script does not start fly proxy and does not contain credentials.
EOF
}

if [[ "${1:-}" != "--confirm" || $# -ne 1 ]]; then
  usage
  exit 2
fi

if [[ -n "${PGWRITE_CONN}" ]]; then
  PSQL_TARGET="${PGWRITE_CONN}"
else
  if [[ -z "${PGUSER:-}" || -z "${PGPASSWORD:-}" ]]; then
    echo "ERROR: provide PGWRITE_CONN or PGUSER+PGPASSWORD for a WRITE role." >&2
    exit 2
  fi
  PSQL_TARGET="host=${PGHOST} port=${PGPORT} dbname=${PGDATABASE} user=${PGUSER} sslmode=disable"
fi

echo "T3 live-test residue cleanup"
echo "CRM action: inspect then soft-delete clients.id=${CLIENT_ID} by setting deleted_at = NOW()."
echo "Drive action: manual only; no Drive delete is performed by this script."
echo "Target DB: ${PGHOST}:${PGPORT}/${PGDATABASE} (or PGWRITE_CONN if supplied)."
echo

echo "[1/3] Operator review: printing the CRM row before mutation."
"${PSQL_BIN}" "${PSQL_TARGET}" -v ON_ERROR_STOP=1 -P pager=off -c \
  "SELECT id, name, created_at, assigned_to FROM clients WHERE id = ${CLIENT_ID};"

echo
echo "[2/3] Soft-deleting CRM row if it is not already deleted."
"${PSQL_BIN}" "${PSQL_TARGET}" -v ON_ERROR_STOP=1 -P pager=off -c \
  "UPDATE clients SET deleted_at = NOW() WHERE id = ${CLIENT_ID} AND deleted_at IS NULL;"

echo
echo "[3/3] Manual Google Drive orphan cleanup required."
cat <<'EOF'
No Drive file id is hardcoded here. It was not discoverable as a fixed artifact
from this worktree, and this script must not invent one.

Find the orphan Drive file id by inspecting one of these production sources:
  - documents rows tied to client_id=19037: file_id, file_url, google_drive_file_url
  - intake_commit_audit.plan -> 'crm_push' for the T3 proposal/document
  - document_routing_proposal joined to intake_queue for the T3 live-test row
  - backend intake delivery logs around the T3 live test; the relevant logger is
    zantara.intake.crm_delivery

After confirming the file is the T3 test artifact, move/trash it manually in
Google Drive.
EOF

echo
echo "Done. CRM cleanup statement was idempotent; Drive cleanup remains manual."
