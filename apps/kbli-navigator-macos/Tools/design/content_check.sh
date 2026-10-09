#!/bin/zsh
# Compile contenttest + headsuptest against Sources/ and run the content gate (spec §7).
# Run from anywhere; operates on the app root. Leaves $T in /tmp (never deletes).
cd "$(dirname "$0")/../.." || exit 2
APP=$PWD; XC=/Applications/Xcode.app
export KBLI_JSON=$APP/Resources/KBLI_2025_FINAL_CLEAN.json KBLI_APP_ROOT=$APP
T=$(mktemp -d); mkdir -p "$T/Contents"; ln -s "$APP/Resources" "$T/Contents/Resources"
SRC=(${(f)"$(find Sources -name '*.swift' ! -name KBLINavigatorApp.swift | sort)"})
build() { swiftc -sdk "$(xcrun --sdk macosx --show-sdk-path)" -target arm64-apple-macosx14.0 \
  -external-plugin-path "$XC/Contents/Developer/Platforms/MacOSX.platform/Developer/usr/lib/swift/host/plugins#$XC/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swift-plugin-server" \
  -framework SwiftUI -framework AppKit -framework Combine -framework PDFKit "$SRC[@]" "Tests/$1/main.swift" -o "$T/$1"; }
build contenttest || { echo "build contenttest failed"; exit 1; }
build headsuptest || { echo "build headsuptest failed"; exit 1; }
rc=0
"$T/contenttest" > "$T/out.json" && python3 Tools/design/content_check.py < "$T/out.json"
if [ $? -eq 0 ]; then echo "step 1 ok: contenttest | content_check"; else echo "step 1 FAILED"; rc=1; fi
python3 - "$T/pack-guilt.json" <<'P'
import json, sys
p = json.load(open("docs/design/content-pack-2026-10-09.json"))
p["codes"]["55203"]["verdict"] = "TERTUTUP"
json.dump(p, open(sys.argv[1], "w"), ensure_ascii=False)
P
if python3 Tools/design/content_check.py --pack "$T/pack-guilt.json" < "$T/out.json" > /dev/null; then
  echo "step 2 FAILED: guilt control: edited pack accepted"; rc=1
else echo "guilt control: edited pack rejected"; fi
if "$T/headsuptest"; then echo "step 3 ok: headsuptest"; else echo "step 3 FAILED"; rc=1; fi
exit $rc
