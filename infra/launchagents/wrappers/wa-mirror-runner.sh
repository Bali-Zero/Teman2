#!/bin/zsh
set -euo pipefail

export HOME="${HOME:-/Users/nuzantara}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export NODE_ENV="${NODE_ENV:-production}"

ENV_FILE="${WA_MIRROR_ENV_FILE:-${HOME}/.wa-mirror.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

mkdir -p "${HOME}/logs"

cd "${WA_MIRROR_APP_DIR:-${HOME}/Desktop/nuzantara/apps/wa-mirror}"
exec /opt/homebrew/bin/node --enable-source-maps dist/bridge/index.js
