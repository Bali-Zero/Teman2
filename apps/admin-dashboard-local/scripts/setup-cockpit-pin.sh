#!/bin/bash
# setup-cockpit-pin.sh — interactive PIN initialization
# Creates ~/.config/zantara-cockpit/{pin.hash, hmac.key}
# v2 panel: file mode 0600

set -euo pipefail

CONFIG_DIR="$HOME/.config/zantara-cockpit"
PIN_HASH_FILE="$CONFIG_DIR/pin.hash"
HMAC_KEY_FILE="$CONFIG_DIR/hmac.key"

mkdir -p "$CONFIG_DIR"
chmod 0700 "$CONFIG_DIR"

if [ -f "$PIN_HASH_FILE" ]; then
    read -r -p "PIN already exists at $PIN_HASH_FILE. Overwrite? (y/N) " ans
    if [ "$ans" != "y" ]; then exit 0; fi
fi

echo "Enter new cockpit PIN (6-12 digits/chars):"
read -rs -p "PIN: " PIN
echo
read -rs -p "Confirm: " PIN2
echo

if [ "$PIN" != "$PIN2" ]; then
    echo "ERROR: PINs do not match" >&2
    exit 1
fi

if [ ${#PIN} -lt 6 ]; then
    echo "ERROR: PIN must be at least 6 characters" >&2
    exit 1
fi

# Generate bcrypt hash using node (bcryptjs from monorepo)
HASH=$(cd "$(dirname "$0")/.." && node -e "
const bcrypt = require('bcryptjs');
console.log(bcrypt.hashSync(process.argv[1], 12));
" "$PIN")

echo "$HASH" > "$PIN_HASH_FILE"
chmod 0600 "$PIN_HASH_FILE"

# Generate HMAC key if missing (32 random bytes hex)
if [ ! -f "$HMAC_KEY_FILE" ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$HMAC_KEY_FILE"
    chmod 0600 "$HMAC_KEY_FILE"
    echo "Generated new HMAC key at $HMAC_KEY_FILE"
fi

echo "OK: PIN saved to $PIN_HASH_FILE (mode 0600)"
echo "    HMAC key at $HMAC_KEY_FILE"
echo "Now run: bash scripts/start-cockpit.sh"
