#!/bin/bash
# ===========================================================================
# WA Meta Inbox — installer (Section 5 of 2026-06-03-wa-meta-inbox-design)
# ---------------------------------------------------------------------------
# Idempotent. Generates "WA Meta Inbox.app" (clone of WA Dashboard.app pattern)
# and installs the com.balizero.wa-meta-inbox LaunchAgent (KeepAlive, :7791).
# Re-running is safe: existing artifacts are overwritten; the LaunchAgent is
# bootout'd then bootstrap'd (no duplicate registration).
#
# Usage:  bash install_app.sh
# Prereq: API key in Keychain  ->  see README.md
# ===========================================================================
set -euo pipefail

LABEL="com.balizero.wa-meta-inbox"
PORT="7791"
NODE_BIN="/opt/homebrew/bin/node"

# --- Resolve absolute paths (this script lives in apps/wa-meta-inbox) --------
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_CJS="${APP_DIR}/server.cjs"
TEMPLATE="${APP_DIR}/${LABEL}.plist.example"
LA_DIR="${HOME}/Library/LaunchAgents"
PLIST="${LA_DIR}/${LABEL}.plist"
APP_BUNDLE="${HOME}/Desktop/WA Meta Inbox.app"
LOG_DIR="${HOME}/logs"
LOG_OUT="${LOG_DIR}/wa-meta-inbox.out.log"
LOG_ERR="${LOG_DIR}/wa-meta-inbox.err.log"

echo "[install] app dir:      ${APP_DIR}"

# --- Preflight --------------------------------------------------------------
[ -f "${SERVER_CJS}" ] || { echo "[install] FATAL: server.cjs not found at ${SERVER_CJS}"; exit 1; }
[ -f "${TEMPLATE}" ]   || { echo "[install] FATAL: plist template not found at ${TEMPLATE}"; exit 1; }
[ -x "${NODE_BIN}" ]   || { echo "[install] FATAL: node not executable at ${NODE_BIN}"; exit 1; }

mkdir -p "${LA_DIR}" "${LOG_DIR}"

# --- 1) Generate the .app bundle (idempotent overwrite) ---------------------
echo "[install] generating ${APP_BUNDLE}"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"

cat > "${APP_BUNDLE}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>WA Meta Inbox</string>
  <key>CFBundleDisplayName</key><string>WA Meta Inbox</string>
  <key>CFBundleIdentifier</key><string>${LABEL}.launcher</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

cat > "${APP_BUNDLE}/Contents/MacOS/launch" <<LAUNCH
#!/bin/bash
URL="http://127.0.0.1:${PORT}/"
# Best-effort: if the daemon is down, bootstrap it.
if ! /usr/bin/nc -z 127.0.0.1 ${PORT} 2>/dev/null; then
  /bin/launchctl bootstrap gui/\$(/usr/bin/id -u) "\${HOME}/Library/LaunchAgents/${LABEL}.plist" 2>/dev/null || true
  for i in 1 2 3 4 5; do
    /usr/bin/nc -z 127.0.0.1 ${PORT} 2>/dev/null && break
    /bin/sleep 1
  done
fi
/usr/bin/open "\${URL}"
LAUNCH
chmod +x "${APP_BUNDLE}/Contents/MacOS/launch"

# --- 2) Materialize the LaunchAgent plist from the template -----------------
echo "[install] materializing ${PLIST}"
TMP_PLIST="$(mktemp)"
sed \
  -e "s|__NODE_BIN__|${NODE_BIN}|g" \
  -e "s|__SERVER_CJS__|${SERVER_CJS}|g" \
  -e "s|__WORKING_DIR__|${APP_DIR}|g" \
  -e "s|__LOG_OUT__|${LOG_OUT}|g" \
  -e "s|__LOG_ERR__|${LOG_ERR}|g" \
  "${TEMPLATE}" > "${TMP_PLIST}"

# Validate BEFORE installing (a bad plist must never be bootstrapped).
if ! /usr/bin/plutil -lint "${TMP_PLIST}" >/dev/null; then
  echo "[install] FATAL: generated plist failed plutil -lint"; rm -f "${TMP_PLIST}"; exit 1
fi
# If the live plist is hardened read-only (cicatrix 2026-04-29), make writable first.
[ -f "${PLIST}" ] && chmod u+w "${PLIST}" 2>/dev/null || true
mv "${TMP_PLIST}" "${PLIST}"
/usr/bin/plutil -lint "${PLIST}" >/dev/null && echo "[install] plist lint OK"

# --- 3) Idempotent (re)load via bootout + bootstrap -------------------------
UID_NUM="$(/usr/bin/id -u)"
echo "[install] reloading LaunchAgent (bootout + bootstrap)"
/bin/launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
/bin/launchctl bootstrap "gui/${UID_NUM}" "${PLIST}"
/bin/launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
/bin/launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

echo "[install] done."
echo "[install] verify:  launchctl print gui/${UID_NUM}/${LABEL} | head -20"
echo "[install] verify:  lsof -nP -iTCP@127.0.0.1:${PORT} -sTCP:LISTEN"
echo "[install] logs:    tail -f ${LOG_OUT} ${LOG_ERR}"
echo "[install] open UI: open '${APP_BUNDLE}'   (or http://127.0.0.1:${PORT}/)"
