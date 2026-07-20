#!/usr/bin/env bash
# vault_mirror_tigris.sh — durability mirror for the GARUDA-FILIERA
# raw-evidence vault onto Tigris (S3-compatible), per
# research/operations/2026-07-16-kbli-garuda-filiera-workflow.md §7:
#   "Vault: Mini is primary, Tigris versioned mirror is the durability
#    layer, the git manifest is the integrity layer."
#
# Credential pattern follows scripts/fly-pg-backup.sh: source
# ~/.nuzantara-secrets.env for AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
# (Tigris creds) — never cat/echo/embed the secret itself (cicatrix
# superscar #4, "secret in the clear").
#
# Usage:
#   scripts/kbli_filiera/vault_mirror_tigris.sh [<vault-root>]
#   VAULT_ROOT=/custom/path scripts/kbli_filiera/vault_mirror_tigris.sh
set -euo pipefail

VAULT_ROOT="${1:-${VAULT_ROOT:-$HOME/nuzantara-vault}}"

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] && [ -f "$HOME/.nuzantara-secrets.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$HOME/.nuzantara-secrets.env"
  set +a
fi

# Destination constants are asserted AFTER sourcing the secrets env, which
# uses `set -a` and may export its own TIGRIS_BUCKET (live-proven 2026-07-18:
# the env's TIGRIS_BUCKET silently redirected the first mirror run to the
# warroom-images bucket). The vault destination is fixed, never env-steered.
TIGRIS_ENDPOINT="https://fly.storage.tigris.dev"
TIGRIS_BUCKET="nuzantara-backups"
TIGRIS_PREFIX="kbli-vault"

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  echo "vault_mirror_tigris.sh: no Tigris credentials (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)." >&2
  echo "  Expected in ~/.nuzantara-secrets.env (never printed/committed — scar #4)." >&2
  exit 2
fi

if [ ! -d "$VAULT_ROOT" ]; then
  echo "vault_mirror_tigris.sh: vault root not found: $VAULT_ROOT" >&2
  exit 2
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "vault_mirror_tigris.sh: aws CLI not found on PATH." >&2
  exit 2
fi

echo "vault_mirror_tigris.sh: syncing $VAULT_ROOT -> s3://$TIGRIS_BUCKET/$TIGRIS_PREFIX/ ..."
aws s3 sync "$VAULT_ROOT" "s3://$TIGRIS_BUCKET/$TIGRIS_PREFIX/" \
  --endpoint-url "$TIGRIS_ENDPOINT" \
  --only-show-errors

echo "vault_mirror_tigris.sh: sync complete."
