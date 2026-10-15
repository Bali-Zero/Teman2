#!/bin/zsh
# title_whole_mutant.sh: the title-whole check bites (#8492 gate, binding 8). Builds Tests/titlewhole twice from a COMMITTED tree: as it is (the
# control passes), and with `.lineLimit(2)` on StepDownTitle's text (the guilt: long titles lose their last words, the check FAILs).
# Sources/ is restored however this ends, SIGPIPE included, and staged changes are refused, as head_mutants.sh does.
cd "${0:A:h}/../.." || exit 2
git diff --quiet -- Sources && git diff --cached --quiet -- Sources || { echo "title_whole_mutant: Sources/ has uncommitted or STAGED changes; commit them first"; exit 4; }
trap 'git checkout -q -- Sources' EXIT
trap 'exit 129' HUP INT TERM
trap 'exit 141' PIPE
APP=$PWD; XC=/Applications/Xcode.app
mkdir -p "$APP/build"; T=$(mktemp -d "$APP/build/title-whole-mutant.XXXXXX") || exit 2
trap 'git checkout -q -- Sources; rm -rf -- "$T"' EXIT
mkdir -p "$T/Contents"; ln -s "$APP/Resources" "$T/Contents/Resources"
export KBLI_JSON=$APP/Resources/KBLI_2025_FINAL_CLEAN.json KBLI_APP_ROOT=$APP
SRC=(${(f)"$(find Sources -name '*.swift' ! -name KBLINavigatorApp.swift | sort)"})
build() { swiftc -sdk "$(xcrun --sdk macosx --show-sdk-path)" -target arm64-apple-macosx14.0 \
  -external-plugin-path "$XC/Contents/Developer/Platforms/MacOSX.platform/Developer/usr/lib/swift/host/plugins#$XC/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swift-plugin-server" \
  -framework SwiftUI -framework AppKit -framework Combine -framework PDFKit "$SRC[@]" Tests/titlewhole/main.swift -o "$T/$1"; }
LONG=87202,16299,47779,47192,56101
run() { "$T/$1" "$T/$1-en.jsonl" --lang en --codes $LONG 2> /dev/null && "$T/$1" "$T/$1-id.jsonl" --lang id --codes $LONG 2> /dev/null && python3 Tools/design/title_whole.py "$T/$1-en.jsonl" "$T/$1-id.jsonl"; }
build control || { echo "title_whole_mutant: control build failed"; exit 5; }
run control > "$T/control.log" 2>&1; rc=$?; tail -1 "$T/control.log"
[ $rc = 0 ] || { echo "title_whole_mutant: FAIL, the control (as committed) does not pass"; exit 1; }
python3 - <<'P' || exit 3
import pathlib
p = pathlib.Path("Sources/Views/RegistryVerdictSheet.swift"); s = p.read_text()
old = "Text(text).font(Theme.display(size)).foregroundStyle(Theme.white).fixedSize(horizontal: false, vertical: true)"
assert s.count(old) == 1, s.count(old); p.write_text(s.replace(old, old + ".lineLimit(2)"))
P
build guilt || { echo "title_whole_mutant: guilt build failed"; exit 5; }
git checkout -q -- Sources
run guilt > "$T/guilt.log" 2>&1; rc=$?; tail -2 "$T/guilt.log"
[ $rc = 1 ] || { echo "title_whole_mutant: FAIL, a title cut by .lineLimit(2) was not caught (rc $rc)"; exit 1; }
echo "title_whole_mutant: ok, the control passes and .lineLimit(2) FAILs"
