#!/bin/bash
# setup-cockpit-pin.sh — interactive high-entropy passphrase initialization
# Creates ~/.config/zantara-cockpit/{pin.hash,hmac.key,session.key}
# v2 panel: file mode 0600

set -euo pipefail
umask 077

CONFIG_DIR="$HOME/.config/zantara-cockpit"
PIN_HASH_FILE="$CONFIG_DIR/pin.hash"
HMAC_KEY_FILE="$CONFIG_DIR/hmac.key"
SESSION_KEY_FILE="$CONFIG_DIR/session.key"

mkdir -p "$CONFIG_DIR"
chmod 0700 "$CONFIG_DIR"

if [ -f "$PIN_HASH_FILE" ]; then
    read -r -p "Passphrase already exists at $PIN_HASH_FILE. Overwrite? (y/N) " ans
    if [ "$ans" != "y" ]; then exit 0; fi
fi

echo "Enter a high-entropy cockpit passphrase (16-64 characters, max 72 UTF-8 bytes):"
read -rs -p "Passphrase: " PIN
echo
read -rs -p "Confirm passphrase: " PIN2
echo

if [ "$PIN" != "$PIN2" ]; then
    echo "ERROR: passphrases do not match" >&2
    exit 1
fi

# Validate with the same JavaScript character and UTF-8 byte bounds as the
# runtime verifier, then hash. Plaintext crosses the process boundary only on
# stdin — never argv, process listings, or environment variables.
HASH=$(
    printf '%s' "$PIN" | (
        cd "$(dirname "$0")/.."
        node -e '
const fs = require("node:fs");
const bcrypt = require("bcryptjs");
const passphrase = fs.readFileSync(0, "utf8");
const utf8Bytes = Buffer.byteLength(passphrase, "utf8");
if (passphrase.length < 16 || passphrase.length > 64 || utf8Bytes > 72) {
  console.error("ERROR: passphrase must be 16-64 characters and at most 72 UTF-8 bytes");
  process.exit(1);
}
process.stdout.write(bcrypt.hashSync(passphrase, 12));
'
    )
) || exit 1

echo "$HASH" > "$PIN_HASH_FILE"
chmod 0600 "$PIN_HASH_FILE"

# Generate HMAC key if missing (32 random bytes hex)
if [ ! -f "$HMAC_KEY_FILE" ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$HMAC_KEY_FILE"
    echo "Generated new HMAC key at $HMAC_KEY_FILE"
fi
chmod 0600 "$HMAC_KEY_FILE"

# Session signing is deliberately separate from audit-chain signing. Rotate
# this key after every successful passphrase setup so changing the passphrase
# invalidates every token issued under the previous setup.
head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$SESSION_KEY_FILE"
chmod 0600 "$SESSION_KEY_FILE"

echo "OK: passphrase hash saved to $PIN_HASH_FILE (mode 0600)"
echo "    Audit HMAC key at $HMAC_KEY_FILE"
echo "    Rotated session key at $SESSION_KEY_FILE (mode 0600)"
echo "Now run: bash scripts/start-cockpit.sh"
