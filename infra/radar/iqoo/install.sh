#!/data/data/com.termux/files/usr/bin/bash
# Install/update the iQOO RADAR receiver from a staged directory in Termux.

set -eu
umask 077

SOURCE_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
LIBEXEC_DIR="$HOME/.local/libexec"
BIN_DIR="$HOME/.local/bin"
BOOT_DIR="$HOME/.termux/boot"
STATE_DIR="$HOME/.local/state/nuzantara-radar/incidents"

mkdir -p "$LIBEXEC_DIR" "$BIN_DIR" "$BOOT_DIR" "$STATE_DIR"
chmod 700 "$HOME/.local" "$LIBEXEC_DIR" "$BIN_DIR" "$HOME/.local/state" \
    "$HOME/.local/state/nuzantara-radar" "$STATE_DIR" "$HOME/.termux" "$BOOT_DIR"

install -m 700 "$SOURCE_DIR/nuzantara-radar-receive" \
    "$LIBEXEC_DIR/nuzantara-radar-receive"
install -m 700 "$SOURCE_DIR/radar" "$BIN_DIR/radar"
install -m 700 "$SOURCE_DIR/10-nuzantara-radar" "$BOOT_DIR/10-nuzantara-radar"

case ":${PATH}:" in
    *":$BIN_DIR:"*) ;;
    *)
        PROFILE="$HOME/.profile"
        LINE="export PATH=\"\$HOME/.local/bin:\$PATH\""
        touch "$PROFILE"
        grep -Fqx "$LINE" "$PROFILE" || printf '%s\n' "$LINE" >> "$PROFILE"
        chmod 600 "$PROFILE"
        ;;
esac

printf 'RADAR_INSTALL_OK\n'
