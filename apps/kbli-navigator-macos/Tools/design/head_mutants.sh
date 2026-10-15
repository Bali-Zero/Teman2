#!/bin/zsh
# head_mutants.sh: C26 on real renders (writes the mutants into Sources/Views/RegistryVerdictSheet.swift, so the tree must be committed: it is restored with git checkout), one mutant build with env switches (sources restored after the build).
cd "${0:A:h}/../.." || exit 2
# The mutants are written into Sources/ and the build reads them there: however this script ends (a hangup of the session, ^C, a failed step),
# Sources/ goes back to what is committed. It refuses to start on a tree with uncommitted Sources, so the restore can never throw a cure away.
git diff --quiet -- Sources || { echo "head_mutants: Sources/ has uncommitted changes; commit them first"; exit 4; }
trap 'git checkout -q -- Sources' EXIT
trap 'exit 129' HUP INT TERM   # a signal ends the run (the EXIT trap restores): without it zsh would go on running the other mutants on a restored tree
export KBLI_BOOK_PDF_DIR=~/.local/share/nuzantara/kbli-navigator/book-pdfs
BIN="build/KBLI Navigator - INTERNAL.app/Contents/MacOS/KBLINavigator"
M=build/h1-mut; rm -rf $M; mkdir -p $M
python3 - <<'P' || exit 3
import pathlib
E = 'ProcessInfo.processInfo.environment'
def edit(f, old, new, n=1):
    p = pathlib.Path(f); s = p.read_text(); assert s.count(old) == n, (f, old[:50], s.count(old)); p.write_text(s.replace(old, new))
F = "Sources/Views/RegistryVerdictSheet.swift"
edit(F, '''        .modifier(Beat(p: immersive ? arrival : 1, from: 0.1, to: 0.45, dy: 6))
        .censusFrame("plate")''', '''        .modifier(Beat(p: immersive ? arrival : 1, from: 0.1, to: 0.45, dy: 6))
        .frame(height: %s["M5_SQUASH"] != nil ? 70 : nil)
        .censusFrame("plate")''' % E)
edit(F, '''.censusFrame("cap")''', '''.censusFrame("cap", "", when: %s["M5_NOCAP"] == nil)''' % E)
edit(F, '''                    .modifier(Beat(p: arrival, from: 0, to: 0.6, dx: 16, fade: false))
                    .censusFrame("glyph")''', '''                    .modifier(Beat(p: arrival, from: 0, to: 0.6, dx: 16, fade: false))
                    .offset(x: %s["M5_GLYPH"] != nil ? -200 : 0)
                    .censusFrame("glyph")''' % E)
edit(F, '''        .modifier(Beat(p: immersive ? arrival : 1, from: 0, to: 0.35, dy: 6))
    }''', '''        .modifier(Beat(p: immersive ? arrival : 1, from: 0, to: 0.35, dy: 6))
        .offset(y: %s["M5_HOSTOFF"] != nil ? 4 : 0)
    }''' % E)
edit(F, "let aw = bounds.width - side - spacing\n", "let aw = %s[\"M5_OVERLAP\"] != nil ? bounds.width : bounds.width - side - spacing\n" % E)
edit(F, "if immersive && Theme.decorationsVisible && expanded {\n                GlyphStroke(", "if immersive && Theme.decorationsVisible && (expanded || %s[\"M5_PLATE201\"] != nil) && %s[\"M5_NOGLYPH\"] == nil {\n                GlyphStroke(" % (E, E))
edit(F, "@State private var open = ProcessInfo.processInfo.environment[\"KBLI_SOURCE_OPEN\"] != nil", "@State private var open = ProcessInfo.processInfo.environment[\"KBLI_SOURCE_OPEN\"] != nil || %s[\"M5_SRCOPEN\"] != nil" % E)
edit(F, ".modifier(DrawnRule(p: arrival, from: 0.1, to: 0.5)).censusFrame(\"rule\")", ".modifier(DrawnRule(p: arrival, from: 0.1, to: 0.5)).opacity(%s[\"M5_NORULE\"] != nil ? 0 : 1).censusFrame(\"rule\")" % E)
edit(F, "WideOrStacked(side: 330, wideFrom: 780, spacing: 32) {\n                identity", "WideOrStacked(side: 330, wideFrom: %s[\"M5_STACK\"] != nil ? 100000 : 780, spacing: 32) {\n                identity" % E)
edit(F, "        .padding(compact ? 14 : 20)\n", "        .padding(compact ? 14 : 20)\n        .frame(minHeight: %s[\"M5_PLATE201\"] != nil ? 201 : nil, alignment: .top)\n" % E)
print("mutants in")
P
zsh build.sh --variant internal > $M/build.log 2>&1; echo "MUTANT_BUILD_RC=$?"
git checkout -q -- Sources/Views/RegistryVerdictSheet.swift 2>/dev/null
shot() { local out=$1; shift; mkdir -p ${out:h}; "$BIN" --snapshot-band "$@" --layout-json ${out%.png}.json $out 2>/dev/null || echo "RENDER FAIL $out"; }
for MUT in none squash overlap nocap glyph hostoff noglyph srcopen norule stack plate201; do
  D=$M/$MUT; unset M5_SQUASH M5_OVERLAP M5_NOCAP M5_GLYPH M5_HOSTOFF M5_NOGLYPH M5_SRCOPEN M5_NORULE M5_STACK M5_PLATE201
  case $MUT in
    squash) export M5_SQUASH=1 ;; overlap) export M5_OVERLAP=1 ;; nocap) export M5_NOCAP=1 ;; glyph) export M5_GLYPH=1 ;; hostoff) export M5_HOSTOFF=1 ;; noglyph) export M5_NOGLYPH=1 ;; srcopen) export M5_SRCOPEN=1 ;; norule) export M5_NORULE=1 ;; stack) export M5_STACK=1 ;; plate201) export M5_PLATE201=1 ;;
  esac
  shot $D/imm/sheet-open-56101-day-en.png registry-sheet --imm --sheet-open --theme day --lang en --code 56101 --height 3200
  shot $D/imm/sheet-head-87202-day-id.png registry-sheet --imm --sheet-open --theme day --lang id --code 87202 --height 3600
  shot $D/live/min-collapsed-87202-day-id.png live-sheet --theme day --lang id --code 87202 --width 1040 --height 700
  unset M5_SQUASH M5_OVERLAP M5_NOCAP M5_GLYPH M5_HOSTOFF M5_NOGLYPH M5_SRCOPEN M5_NORULE M5_STACK M5_PLATE201
  python3 Tools/design/png_census.py $D > $D.log 2>&1; echo "== mutant $MUT: census rc=$? ($(tail -1 $D.log))"
  grep -E "C26|C27" $D.log | grep -v "self-test" | cut -c1-260 | head -2
done
echo mutdone > $M/done
