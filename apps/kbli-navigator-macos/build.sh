#!/bin/zsh
# build.sh — compile KBLI Navigator with swiftc and assemble a .app bundle.
# No Xcode.app activation required (CLT is the active developer dir). SwiftUI's
# @State/@StateObject/etc. are EXTERNAL MACROS whose plugin (libSwiftUIMacros) ships only
# inside an Xcode bundle. We locate that plugin inside an installed Xcode(-beta).app and feed
# it to swiftc via -external-plugin-path — WITHOUT `sudo xcode-select`.
# Adapted from wr2-control-app/build.sh (internal Bali Zero repo).
set -euo pipefail

ROOT="${0:A:h}"
cd "$ROOT"

# ── variant selection (2026-08-09 app split) ───────────────────────────────────────────
# One codebase, two shipped .apps. INTERNAL (default, back-compat: plain `./build.sh` still
# produces it) is everything the app has today. BKPM excludes Resources/articles/ from the
# bundle (below) and strips balizero.com links at runtime (Sources/Variant.swift, read from
# the BZVariant Info.plist key this script writes) — Chat is unchanged in both. Pick ONE
# mechanism and keep it simple: a plist key, not a compile-time -D flag, so a single already-
# compiled binary + two resource trees could in principle serve both (not done today, but
# nothing about this design forecloses it).
VARIANT="internal"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant)
      VARIANT="${2:?--variant requires internal|bkpm}"
      shift 2
      ;;
    --variant=*)
      VARIANT="${1#--variant=}"
      shift
      ;;
    *)
      echo "✗ unknown argument: $1 (only --variant internal|bkpm is supported)" >&2
      exit 2
      ;;
  esac
done

case "$VARIANT" in
  internal) APP_NAME="KBLI Navigator - INTERNAL"; BUNDLE_ID="com.balizero.kbli-navigator.internal" ;;
  bkpm)     APP_NAME="KBLI Navigator - BKPM";      BUNDLE_ID="com.balizero.kbli-navigator.bkpm" ;;
  *)
    echo "✗ unknown --variant: $VARIANT (want internal|bkpm)" >&2
    exit 2
    ;;
esac
echo "▸ variant:  $VARIANT → \"$APP_NAME\" ($BUNDLE_ID)"

EXEC_NAME="KBLINavigator"
BUILD_DIR="$ROOT/build"
APP="$BUILD_DIR/$APP_NAME.app"

SDK="$(xcrun --sdk macosx --show-sdk-path 2>/dev/null || echo /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk)"
# Universal binary, min macOS 14 (Sonoma). The old arm64-apple-macosx26.0 target was an
# inherited hardcode (wr2-control-app), NOT an API requirement: typecheck 2026-07-13 proved
# 0 errors on BOTH arches at 14.0 (13.0 fails with 2). This is what lets the TEAM's Macs —
# Intel or Apple Silicon, Sonoma or later — run the same app as the M5/Pro/Mini fleet.
# Keep Info.plist LSMinimumSystemVersion in sync with MIN_OS.
MIN_OS="14.0"
TARGETS=("arm64-apple-macosx${MIN_OS}" "x86_64-apple-macosx${MIN_OS}")

echo "▸ SDK:     $SDK"
echo "▸ targets: ${TARGETS[*]} (universal, min macOS $MIN_OS)"

# --- locate SwiftUI macro plugin inside any installed Xcode bundle ---------------------
find_xcode() {
  local candidates=(
    "/Applications/Xcode.app"
    "/Applications/Xcode-beta.app"
    "$HOME/Downloads/Xcode-beta.app"
    "$HOME/Applications/Xcode.app"
  )
  for x in "${candidates[@]}"; do
    if [[ -d "$x/Contents/Developer/Platforms/MacOSX.platform/Developer/usr/lib/swift/host/plugins" ]]; then
      echo "$x"; return 0
    fi
  done
  mdfind "kMDItemCFBundleIdentifier == 'com.apple.dt.Xcode'" 2>/dev/null | head -1
}

PLUGIN_FLAGS=()
XCODE="$(find_xcode || true)"
if [[ -n "${XCODE:-}" && -d "$XCODE" ]]; then
  PLUGIN_DIR="$XCODE/Contents/Developer/Platforms/MacOSX.platform/Developer/usr/lib/swift/host/plugins"
  PLUGIN_SERVER="$XCODE/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swift-plugin-server"
  if [[ -f "$PLUGIN_DIR/libSwiftUIMacros.dylib" && -x "$PLUGIN_SERVER" ]]; then
    echo "▸ macro plugin: $XCODE"
    PLUGIN_FLAGS=(-external-plugin-path "${PLUGIN_DIR}#${PLUGIN_SERVER}")
  fi
fi
if [[ ${#PLUGIN_FLAGS[@]} -eq 0 ]]; then
  echo "⚠︎ No Xcode bundle with libSwiftUIMacros found."
  echo "  SwiftUI macros (@State/@StateObject) cannot expand under CLT-only."
  echo "  Install Xcode(-beta).app (no xcode-select needed) and rebuild."
  exit 3
fi

# ── book PDFs are bundle inputs that no longer live in this tree ──────────────────────
# The two Bali-Threshold-2026 book PDFs (~49 MB each) stayed out of the monorepo import.
# Fail LOUDLY before compiling rather than ship a bundle without the book.
KBLI_BOOK_PDF_DIR="${KBLI_BOOK_PDF_DIR:-$HOME/kbli-navigator-app/Resources}"
BOOK_PDFS=("Bali-Threshold-2026.pdf" "Bali-Threshold-2026-ID.pdf")
for pdf in "${BOOK_PDFS[@]}"; do
  # present, plausibly sized (> 1 MB) and really a PDF: a truncated or mislabelled file must not ship
  if [[ ! -f "$KBLI_BOOK_PDF_DIR/$pdf" ]]; then
    echo "✗ book PDF missing: $KBLI_BOOK_PDF_DIR/$pdf" >&2
    echo "  Set KBLI_BOOK_PDF_DIR to a directory holding ${BOOK_PDFS[*]}." >&2
    echo "  Archive: gdrive:M5-archive-2026-10-06/logo-tar/kbli-navigator-app.tar (Resources/)." >&2
    exit 5
  fi
  if [[ "$(wc -c < "$KBLI_BOOK_PDF_DIR/$pdf")" -lt 1000000 || "$(head -c 4 "$KBLI_BOOK_PDF_DIR/$pdf")" != "%PDF" ]]; then
    echo "✗ book PDF looks truncated or is not a PDF: $KBLI_BOOK_PDF_DIR/$pdf" >&2
    exit 5
  fi
done

# collect sources (app sources only — Tests/ excluded from the app binary)
SOURCES=($(find "$ROOT/Sources" -name "*.swift"))
echo "▸ sources: ${#SOURCES[@]} files"

# Scoped to THIS variant's .app, not the whole build/ dir: with two variants sharing one
# BUILD_DIR, `rm -rf "$BUILD_DIR"` would delete the other variant's already-built bundle —
# breaking the "build internal, then build bkpm, both exist for verification" workflow.
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

echo "▸ compiling (one slice per arch, then lipo)…"
SLICES=()
for T in "${TARGETS[@]}"; do
  SLICE="$BUILD_DIR/.slice-${T%%-*}"
  echo "  · $T"
  swiftc -parse-as-library -O \
    -sdk "$SDK" -target "$T" \
    "${PLUGIN_FLAGS[@]}" \
    -framework SwiftUI -framework AppKit -framework Combine -framework PDFKit \
    -o "$SLICE" \
    "${SOURCES[@]}"
  SLICES+=("$SLICE")
done
lipo -create "${SLICES[@]}" -output "$APP/Contents/MacOS/$EXEC_NAME"
rm -f "${SLICES[@]}"
echo "▸ universal: $(lipo -archs "$APP/Contents/MacOS/$EXEC_NAME")"

# ── refresh the KBLI dataset from the repo's single source-of-truth ───────────────────
# The canonical KBLI_2025_FINAL_CLEAN.json lives in the nuzantara repo
# (source_documents/KBLI_2025_FINAL_CLEAN.json) and is kept in sync there by
# scripts/sync_kbli_dataset.sh + the check-kbli-dataset-sync CI lint. This app's
# Resources/ copy is OUTSIDE that repo, so CI can't guard it. To stop it drifting
# (superscar #1 HOME-fork), we re-copy from canonical at every build — freshness
# becomes structural, not a thing to remember.
#
# Repo resolution is path-HOME-safe (cabling /Users/<x>/... would itself be a #1
# cicatrix): monorepo root → env override → sibling ../nuzantara → $HOME/nuzantara →
# fail loudly rather than ship a stale build. No probe under the Desktop folder: the
# fleet left it on 2026-07-16 (launchd lost its TCC grant there, superscar #2/W84).
#
# 2026-08-03: $HOME/nuzantara added, and it is not cosmetic. The fleet moved the
# repo out of the Desktop folder on 2026-07-16 (launchd lost its TCC grant to that
# folder — superscar #2/W84), so a probe there is a dead path that only resolved
# through a leftover symlink. It is dropped (2026-10-08): the day the symlink goes
# the loop must not fall through quietly to a stale build.
KBLI_REL="source_documents/KBLI_2025_FINAL_CLEAN.json"
CANON=""
# 2026-10-07: the app now lives in the monorepo (apps/kbli-navigator-macos), so the FIRST
# probe is the monorepo root this script sits in ($ROOT/../..). There source_documents/ is
# a tracked symlink to data/source_documents/, so each repo is tried under the real
# data/ path first, then the legacy path (older checkouts keep a real source_documents/).
MONOREPO_ROOT="$ROOT/../.."
for repo in "$MONOREPO_ROOT" "${NUZANTARA_REPO:-}" "$ROOT/../nuzantara" "$HOME/nuzantara"; do
  for rel in "data/$KBLI_REL" "$KBLI_REL"; do
    if [[ -n "$repo" && -f "$repo/$rel" && ! -L "$repo/$rel" ]]; then
      CANON_REPO="$(cd "$repo" && pwd)"
      CANON="$CANON_REPO/$rel"
      break 2
    fi
  done
done

# ── D2 LOCK: refuse to ship a dataset other than the anchored one ─────────────────────
# Resources/DATASET_MANIFEST.json pins the sha256 of the ONE dataset build this app is
# anchored to (see the data(dataset) re-anchor commit). If the resolved canonical has
# since moved, that is a decision for a fresh, deliberate re-anchor commit — never a
# silent swap into the build the next time build.sh happens to run.
KBLI_MANIFEST="$ROOT/Resources/DATASET_MANIFEST.json"
if [[ -n "$CANON" && -f "$KBLI_MANIFEST" ]]; then
  MANIFEST_SHA="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('sha256',''))" "$KBLI_MANIFEST" 2>/dev/null || true)"
  CANON_SHA="$(shasum -a 256 "$CANON" | cut -d' ' -f1)"
  if [[ -n "$MANIFEST_SHA" && "$MANIFEST_SHA" != "$CANON_SHA" ]]; then
    echo "✗ D2 LOCK: canonical moved — refusing to ship a dataset other than the anchored one."
    echo "  anchored (Resources/DATASET_MANIFEST.json): $MANIFEST_SHA"
    echo "  canonical ($CANON):                          $CANON_SHA"
    echo "  re-anchor deliberately (data(dataset) commit), never silently."
    exit 4
  fi
fi

if [[ -n "$CANON" ]]; then
  if cmp -s "$CANON" "$ROOT/Resources/KBLI_2025_FINAL_CLEAN.json" 2>/dev/null; then
    echo "▸ KBLI dataset: Resources/ already matches canonical ($CANON)"
  else
    cp -f "$CANON" "$ROOT/Resources/KBLI_2025_FINAL_CLEAN.json"
    echo "▸ KBLI dataset: refreshed Resources/ from canonical ($CANON)"
  fi
else
  echo "⚠︎ KBLI canonical not found (set NUZANTARA_REPO or place repo as ../nuzantara)."
  echo "  Building with the existing Resources/KBLI_2025_FINAL_CLEAN.json — it may be STALE."
fi

# ── refresh the EDITORIAL OVERLAY from the repo too ───────────────────────────────────
# 2026-08-03. The block above guarded the machine dataset and nothing else, while the
# three overlay files carry the sentences a human actually reads — and they had drifted
# badly: the app was telling the team that a PT PMA "cannot register a youth hostel, a
# villa rental or a massage parlour anywhere in Indonesia" (an inference withdrawn from
# the web the same day), that Umrah travel is "fully open, 100%" (the Perpres annex caps
# it at 0%), and that a GOVERNMENT hospital can be 100% foreign-owned. The guard covered
# the file that could not lie in prose and missed the three that do.
#
# The overlay now lives in the monorepo at data/kbli-app-overlay/ so CI can reach it
# (scripts/kbli_filiera/tests/test_withdrawn_umkm_inference_absent.py), and is copied in
# here at every build on the same ladder as the dataset. REPO_ROOT is derived from the
# dataset we just resolved, so the two can never disagree about which checkout is
# canonical.
if [[ -n "$CANON" ]]; then
  OVERLAY_DIR="$CANON_REPO/data/kbli-app-overlay"
  if [[ -d "$OVERLAY_DIR" ]]; then
    for f in kbli-overlay.json kbli-reason-i18n.json kbli-balicontext-i18n-id.json; do
      if [[ -f "$OVERLAY_DIR/$f" ]]; then
        cmp -s "$OVERLAY_DIR/$f" "$ROOT/Resources/$f" || cp -f "$OVERLAY_DIR/$f" "$ROOT/Resources/$f"
      else
        echo "⚠︎ overlay: $f missing from $OVERLAY_DIR — shipping the existing Resources/ copy."
      fi
    done
    echo "▸ editorial overlay: synced from $OVERLAY_DIR"
  else
    echo "⚠︎ editorial overlay dir not found at $OVERLAY_DIR — Resources/ copies may be STALE."
  fi
fi

# bundle resources (KBLI JSON, articles, chapters, PDFs, logo)
if [[ -d "$ROOT/Resources" ]]; then
  cp -R "$ROOT/Resources/." "$APP/Contents/Resources/" 2>/dev/null || true
  if [[ "$VARIANT" == "bkpm" ]]; then
    # BKPM Media keeps the book only (2 PDFs + 13 book-chapters). The 20 editorial articles
    # are EXCLUDED FROM THE BUNDLE here — not merely hidden in the UI — so they never ship.
    N_ARTICLES="$(ls -1 "$ROOT/Resources/articles" 2>/dev/null | wc -l | tr -d ' ')"
    rm -rf "$APP/Contents/Resources/articles"
    echo "▸ BKPM bundle: Resources/articles/ excluded ($N_ARTICLES files not shipped)"
  fi
fi

for pdf in "${BOOK_PDFS[@]}"; do
  cp -f "$KBLI_BOOK_PDF_DIR/$pdf" "$APP/Contents/Resources/$pdf"
done
echo "▸ book PDFs: copied from $KBLI_BOOK_PDF_DIR"

# ── bundle manifest ────────────────────────────────────────────────────────────────────
# Contents/Resources/MANIFEST.json records what this .app was actually built from: the
# source commit, which variant, the exact dataset shipped (full sha256, not truncated),
# the record count, and whether the working tree had tracked modifications at build time.
# This is what lets a later "open it" step prove which candidate answered a question,
# instead of trusting that the build directory matches whatever HEAD says now.
BUILD_COMMIT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
DATASET_SHA256="$(shasum -a 256 "$APP/Contents/Resources/KBLI_2025_FINAL_CLEAN.json" | cut -d' ' -f1)"
RECORDS="$(python3 -c "import json; print(len(json.load(open('$APP/Contents/Resources/KBLI_2025_FINAL_CLEAN.json'))['data']))")"
# "dirty" must cover every tracked input that reaches the bundle: this app's own tree AND
# the canonical dataset + overlay it was copied from (they may live in another checkout).
DIRTY="false"
if [[ -n "$(git -C "$ROOT" status --porcelain -- . 2>/dev/null | grep -v '^??')" ]]; then
  DIRTY="true"
fi
if [[ -n "${CANON:-}" && -n "$(git -C "$CANON_REPO" status --porcelain -- "$CANON" "$CANON_REPO/data/kbli-app-overlay" 2>/dev/null | grep -v '^??')" ]]; then
  DIRTY="true"
fi
python3 -c "
import json, sys
manifest = {
    'commit': sys.argv[1],
    'variant': sys.argv[2],
    'dataset_sha256': sys.argv[3],
    'records': int(sys.argv[4]),
    'dirty': sys.argv[5] == 'true',
}
json.dump(manifest, open(sys.argv[6], 'w'), indent=2)
" "$BUILD_COMMIT" "$VARIANT" "$DATASET_SHA256" "$RECORDS" "$DIRTY" "$APP/Contents/Resources/MANIFEST.json"
echo "▸ manifest: commit=$BUILD_COMMIT variant=$VARIANT records=$RECORDS dirty=$DIRTY"

cp "$ROOT/Info.plist" "$APP/Contents/Info.plist"
plutil -replace CFBundleName -string "$APP_NAME" "$APP/Contents/Info.plist"
plutil -replace CFBundleDisplayName -string "$APP_NAME" "$APP/Contents/Info.plist"
plutil -replace CFBundleIdentifier -string "$BUNDLE_ID" "$APP/Contents/Info.plist"
plutil -insert BZVariant -string "$VARIANT" "$APP/Contents/Info.plist"
plutil -lint "$APP/Contents/Info.plist" >/dev/null

echo "▸ ad-hoc codesign…"
codesign --force --deep --sign - "$APP" 2>/dev/null || echo "  (codesign skipped)"

echo "✅ built: $APP"
