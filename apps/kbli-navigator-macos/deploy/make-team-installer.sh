#!/bin/zsh
# make-team-installer.sh — package KBLI Navigator for the office team's own Macs.
#
# The 3-Mac fleet (M5/Pro/Mini) is ssh-reachable and served by install-3mac.sh; the team's
# Macs are NOT (no keys, and handing out ssh to our machines would widen the trust boundary
# — scar family #4). So the team path is a zip: the .app + a double-clickable installer
# that does ON THE DESTINATION what install-3mac.sh does over ssh (strip quarantine +
# ad-hoc re-sign — the Gatekeeper F2 trick; an ad-hoc bundle copied between Macs is
# "damaged" until re-signed locally).
#
# Data parity: build.sh refreshes the dataset from the repo canonical at build time, so the
# team app ships EXACTLY what balizero.com/kbli serves. Re-run this after every canonical
# change (the same moment you re-run install-3mac.sh) and re-share the zip.
#
# Known limit (v1): the Zantara chat tab reaches the brain via `ssh mini` — on team Macs it
# degrades to a clean "unreachable" error. Search/detail/book/articles are fully offline.
set -euo pipefail

ROOT="${0:A:h:h}"
cd "$ROOT"
# The team installer always ships INTERNAL (2026-08-09 app split); BKPM is a separate,
# on-demand build zipped to build/ only — see build.sh --variant.
APP_NAME="KBLI Navigator - INTERNAL"
APP="$ROOT/build/$APP_NAME.app"
DATASET_REL="Contents/Resources/KBLI_2025_FINAL_CLEAN.json"

echo "▸ building on $(hostname)…"
./build.sh --variant internal

# commit the dataset refresh if build.sh pulled a new canonical (same rule as install-3mac.sh)
if ! git diff --quiet -- Resources/KBLI_2025_FINAL_CLEAN.json 2>/dev/null; then
  DHASH="$(shasum -a 256 Resources/KBLI_2025_FINAL_CLEAN.json | cut -c1-12)"
  git add Resources/KBLI_2025_FINAL_CLEAN.json
  git commit -m "chore(data): refresh dataset from canonical ($DHASH)" -- Resources/KBLI_2025_FINAL_CLEAN.json
  echo "▸ dataset refresh committed ($DHASH)"
fi

# fail-visible secret scan: nothing key-shaped may leave on a team machine (scar family #4)
if grep -rIlE '(sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key["'\'' ]*[:=]|Bearer [A-Za-z0-9._-]{20,})' \
     "$APP/Contents/Resources" 2>/dev/null; then
  echo "✗ secret-shaped content found in the bundle (files above) — NOT packaging."; exit 1
fi

SRC_HASH="$(shasum -a 256 "$APP/$DATASET_REL" | cut -c1-12)"
STAGE_PARENT="$(mktemp -d)"
STAGE="$STAGE_PARENT/KBLI-Navigator-Team"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/$APP_NAME.app"

cat > "$STAGE/Install KBLI Navigator.command" <<'INSTALLER'
#!/bin/zsh
# Install KBLI Navigator — double-click (first time: right-click → Open).
set -euo pipefail
HERE="${0:A:h}"
APP="KBLI Navigator - INTERNAL.app"
SRC="$HERE/$APP"
if [[ ! -d "$SRC" ]]; then
  echo "✗ '$APP' not found next to this installer. Unzip the whole folder first."; exit 1
fi
DEST="${KBLI_INSTALL_DEST:-/Applications}"
if [[ ! -w "$DEST" ]]; then DEST="$HOME/Applications"; fi
mkdir -p "$DEST"
echo "▸ installing to $DEST…"
rsync -a --delete "$SRC" "$DEST/"
# Gatekeeper: strip quarantine + ad-hoc re-sign ON this Mac, or the app opens as "damaged".
xattr -cr "$DEST/$APP" 2>/dev/null || true
codesign --force --deep --sign - "$DEST/$APP"
echo "✓ installed. Opening…"
open "$DEST/$APP"
INSTALLER
chmod +x "$STAGE/Install KBLI Navigator.command"

cat > "$STAGE/README-INSTALL.txt" <<README
KBLI Navigator — install on your Mac / instal di Mac Anda
==========================================================
(macOS 15 Sequoia / 26 Tahoe removed the old right-click->Open bypass for
unsigned software — the ONE-TIME unlock now goes through System Settings.)

EN — first time only
1. Unzip this folder (double-click the zip).
2. Double-click "Install KBLI Navigator.command". macOS blocks it -> click OK
   (do NOT click "Move to Trash").
3. Open System Settings -> Privacy & Security, scroll to the bottom:
   '"Install KBLI Navigator.command" was blocked...' -> click "Open Anyway",
   confirm with your password / Touch ID.
4. Terminal opens, installs the app into Applications and launches it.
   From now on: open it from Launchpad / Applications like any app.
(On macOS 14 Sonoma the old way also works: right-click the .command -> Open -> Open.)

ID — hanya pertama kali
1. Ekstrak folder ini (klik dua kali file zip).
2. Klik dua kali "Install KBLI Navigator.command". macOS memblokir -> klik OK
   (JANGAN klik "Move to Trash").
3. Buka System Settings -> Privacy & Security, scroll ke paling bawah:
   '"Install KBLI Navigator.command" was blocked...' -> klik "Open Anyway",
   konfirmasi dengan password / Touch ID.
4. Terminal terbuka, aplikasi terpasang di Applications dan langsung jalan.
   Selanjutnya buka dari Launchpad / Applications seperti biasa.
(Di macOS 14 Sonoma cara lama juga bisa: klik kanan file .command -> Open -> Open.)

If "Open Anyway" does not appear / Kalau "Open Anyway" tidak muncul:
open Terminal and paste (adjust the folder if not in Downloads):
  xattr -cr ~/Downloads/KBLI-Navigator-Team && "\$HOME/Downloads/KBLI-Navigator-Team/Install KBLI Navigator.command"

Notes / Catatan
- Requires macOS 14 Sonoma or later (Intel and Apple Silicon both fine).
  If it says "requires macOS 14": the Mac is too old -> use https://balizero.com/kbli.
  Butuh macOS 14 Sonoma atau lebih baru (Intel & Apple Silicon dua-duanya bisa).
- Works fully offline: 1,559 KBLI 2025 codes, Bali PMA status, book + articles.
  Berfungsi offline: 1.559 kode KBLI 2025, status PMA Bali, buku + artikel.
- The "Chat" tab only works on the office admin Macs for now. For questions use
  https://balizero.com/kbli or ask on WhatsApp.
  Tab "Chat" untuk saat ini hanya berfungsi di Mac admin kantor. Untuk pertanyaan gunakan
  https://balizero.com/kbli atau WhatsApp.
- Dataset build: $SRC_HASH ($(date +%Y-%m-%d))
README

OUT="$HOME/Desktop/KBLI-Navigator-Team-$(date +%Y%m%d).zip"
rm -f "$OUT"
ditto -c -k --keepParent "$STAGE" "$OUT"
rm -rf "$STAGE_PARENT"
echo "✅ team installer: $OUT (dataset $SRC_HASH — matches balizero.com/kbli canonical)"
echo "   Share it via Drive/AirDrop; team installs with right-click → Open."
