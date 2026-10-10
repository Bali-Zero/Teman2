#!/bin/zsh
# Compile contenttest + headsuptest + encensus against Sources/ and run the content gate (spec §7) and the
# en-purity gate (Q12): the text census of the drawn Views (fast sample; EN_CENSUS=full for all 1,559 codes) and
# the never-drawn static check. Run from anywhere; operates on the app root. Its binaries and outputs live in a
# fresh directory under THIS app's ignored build/ (never deleted), so a concurrent run in another worktree or
# session can neither be picked up nor overwrite them: every path below is $T's, by construction.
cd "$(dirname "$0")/../.." || exit 2
APP=$PWD; XC=/Applications/Xcode.app
export KBLI_JSON=$APP/Resources/KBLI_2025_FINAL_CLEAN.json KBLI_APP_ROOT=$APP
mkdir -p "$APP/build" && T=$(mktemp -d "$APP/build/content-check.XXXXXX") || exit 2
mkdir -p "$T/Contents"; ln -s "$APP/Resources" "$T/Contents/Resources"; echo "content_check: work dir $T"
SRC=(${(f)"$(find Sources -name '*.swift' ! -name KBLINavigatorApp.swift | sort)"})
build() { swiftc -sdk "$(xcrun --sdk macosx --show-sdk-path)" -target arm64-apple-macosx14.0 \
  -external-plugin-path "$XC/Contents/Developer/Platforms/MacOSX.platform/Developer/usr/lib/swift/host/plugins#$XC/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swift-plugin-server" \
  -framework SwiftUI -framework AppKit -framework Combine -framework PDFKit "$SRC[@]" "Tests/$1/main.swift" -o "$T/$1"; }
build contenttest || { echo "build contenttest failed"; exit 1; }
build headsuptest || { echo "build headsuptest failed"; exit 1; }
build encensus || { echo "build encensus failed"; exit 1; }
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
if "$T/encensus" "$T/en-census.jsonl" --lang en --mode "${EN_CENSUS:-fast}" 2> "$T/encensus.err" \
   && "$T/encensus" "$T/id-surfaces.jsonl" --lang id --codes none 2>> "$T/encensus.err" \
   && python3 Tools/design/en_purity.py census "$T/en-census.jsonl" --id "$T/id-surfaces.jsonl"; then
  echo "step 4 ok: en-purity census (${EN_CENSUS:-fast})"
else echo "step 4 FAILED: en-purity census ($T/encensus.err)"; rc=1; fi
if python3 Tools/design/en_purity.py static; then echo "step 5 ok: never-drawn"; else echo "step 5 FAILED"; rc=1; fi
exit $rc
