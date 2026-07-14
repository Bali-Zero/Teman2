#!/bin/zsh
# build.sh — compile WR2 Control with swiftc and assemble a .app bundle.
# No Xcode.app activation required (this machine has Command Line Tools as the active
# developer dir). SwiftUI's @State/@StateObject/etc. are EXTERNAL MACROS whose plugin
# (libSwiftUIMacros) ships only inside an Xcode bundle, not in CLT. We locate that plugin
# inside an installed Xcode(-beta).app and feed it to swiftc via -external-plugin-path —
# WITHOUT running `sudo xcode-select` (no privilege change, just a compile-time flag
# pointing at a dylib already on disk).
set -euo pipefail

ROOT="${0:A:h}"
cd "$ROOT"

APP_NAME="WR2 Control"
EXEC_NAME="WR2Control"
BUILD_DIR="$ROOT/build"
APP="$BUILD_DIR/$APP_NAME.app"

SDK="$(xcrun --show-sdk-path 2>/dev/null || echo /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk)"
TARGET="arm64-apple-macosx26.0"

echo "▸ SDK:    $SDK"
echo "▸ target: $TARGET"

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
  # last resort: spotlight
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

# collect sources (app sources only — Tests/ excluded from the app binary).
# zsh-native recursive glob, NOT `$(find ...)`: the latter word-splits on IFS when
# populating an array, which silently truncates any path containing a space — and
# this app's own directory name ("WR2 Control...") has one.
SOURCES=("$ROOT"/Sources/**/*.swift(.N))
echo "▸ sources: ${#SOURCES[@]} files"

rm -rf "$BUILD_DIR"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

echo "▸ compiling…"
swiftc -parse-as-library -O \
  -sdk "$SDK" -target "$TARGET" \
  "${PLUGIN_FLAGS[@]}" \
  -framework SwiftUI -framework AppKit -framework Combine \
  -o "$APP/Contents/MacOS/$EXEC_NAME" \
  "${SOURCES[@]}"

# bundle resources (Bali Zero logo, etc.)
if [[ -d "$ROOT/Resources" ]]; then
  cp -R "$ROOT/Resources/." "$APP/Contents/Resources/" 2>/dev/null || true
fi

# --- app icon: generate from the WR2+BZ concept, build .icns, embed ---------------------
echo "▸ icon…"
ICON_PNG="$BUILD_DIR/icon-1024.png"
"$APP/Contents/MacOS/$EXEC_NAME" --makeicon "$ICON_PNG" >/dev/null 2>&1 || true
if [[ -f "$ICON_PNG" ]]; then
  ICONSET="$BUILD_DIR/WR2.iconset"
  mkdir -p "$ICONSET"
  for s in 16 32 64 128 256 512; do
    sips -z $s $s "$ICON_PNG" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
    d=$((s*2)); sips -z $d $d "$ICON_PNG" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  cp "$ICON_PNG" "$ICONSET/icon_512x512@2x.png"
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns" 2>/dev/null \
    && echo "  ✅ AppIcon.icns embedded" || echo "  ⚠︎ iconutil failed"
fi

cp "$ROOT/Info.plist" "$APP/Contents/Info.plist"
plutil -lint "$APP/Contents/Info.plist" >/dev/null

echo "▸ ad-hoc codesign…"
codesign --force --deep --sign - "$APP" 2>/dev/null || echo "  (codesign skipped)"

echo "✅ built: $APP"
