#!/bin/zsh
# head_mutants.sh: C26 on real renders (writes the mutants into Sources/Views/RegistryVerdictSheet.swift, so the tree must be committed: it is restored with git checkout), one mutant build with env switches (sources restored after the build).
cd "${0:A:h}/../.." || exit 2
# The mutants are written into Sources/ and the build reads them there: however this script ends (a hangup of the session, ^C, a failed step),
# Sources/ goes back to what is committed. It refuses to start on a tree with uncommitted Sources, so the restore can never throw a cure away.
git diff --quiet -- Sources && git diff --cached --quiet -- Sources || { echo "head_mutants: Sources/ has uncommitted or STAGED changes; commit them first"; exit 4; }
trap 'git checkout -q -- Sources' EXIT
trap 'exit 129' HUP INT TERM   # a signal ends the run (the EXIT trap restores): without it zsh would go on running the other mutants on a restored tree
# A closed pipe (`head_mutants.sh | head -n 1`) is SIGPIPE, which kills a script WITHOUT running its EXIT trap: it left ten M5_ switches in Sources (#8492 gate A3a).
[ -n "$HM_NO_PIPE_TRAP" ] || trap 'exit 141' PIPE   # HM_NO_PIPE_TRAP is the trap test's guilt: the same script without this line
# The mutant set only grows: Tools/design/head_mutants.names is its list, and a name that origin/main has and this tree does not FAILs the run.
NAMES=(${(f)"$(<Tools/design/head_mutants.names)"})
if git cat-file -e origin/main:./Tools/design/head_mutants.names 2>/dev/null; then
  for n in ${(f)"$(git show origin/main:./Tools/design/head_mutants.names)"}; do
    (( ${NAMES[(Ie)$n]} )) || { echo "head_mutants: mutant '$n' was dropped from head_mutants.names: the set only grows"; exit 6; }
  done
fi
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
edit(F, "if immersive && Theme.decorationsVisible && expanded {\n                GlyphStroke(", "if immersive && Theme.decorationsVisible && expanded && %s[\"M5_NOGLYPH\"] == nil {\n                GlyphStroke(" % E)
edit(F, "@State private var open = ProcessInfo.processInfo.environment[\"KBLI_SOURCE_OPEN\"] != nil", "@State private var open = ProcessInfo.processInfo.environment[\"KBLI_SOURCE_OPEN\"] != nil || %s[\"M5_SRCOPEN\"] != nil" % E)
edit(F, ".modifier(DrawnRule(p: arrival, from: 0.1, to: 0.5)).censusFrame(\"rule\")", ".modifier(DrawnRule(p: arrival, from: 0.1, to: 0.5)).opacity(%s[\"M5_NORULE\"] != nil ? 0 : 1).censusFrame(\"rule\")" % E)
edit(F, "WideOrStacked(side: 330, wideFrom: 780, spacing: 32) {\n                    identity()", "WideOrStacked(side: 330, wideFrom: %s[\"M5_STACK\"] != nil ? 100000 : 780, spacing: 32) {\n                    identity()" % E)
edit(F, "                verdictBand(v).background(SheetFit.reader)\n                nationalPlate(v)\n", "                if (%s[\"M5_PLATEFIRST\"] != nil || %s[\"M5_PLATE201\"] != nil) { nationalPlate(v); verdictBand(v).background(SheetFit.reader) } else { verdictBand(v).background(SheetFit.reader); nationalPlate(v) }\n" % (E, E))
edit(F, "        .padding(.horizontal, compact ? 14 : 20).padding(.vertical, compact ? 8 : 20)\n", "        .padding(.horizontal, compact ? 14 : 20).padding(.vertical, compact ? 8 : 20)\n        .frame(minHeight: %s[\"M5_PLATE201\"] != nil ? 201 : nil, alignment: .top)\n" % E)
edit(F, "                    identity()\n                    nationalPlate(v)", "                    identity().censusFrame(\"head.compact\", \"\", when: %s[\"M5_COMPACTEXP\"] != nil)\n                    nationalPlate(v)" % E)
edit(F, "        .modifier(Beat(p: immersive ? arrival : 1, from: 0.15, to: 0.5, dy: 6))\n        .censusFrame(\"band\")",
     "        .modifier(Beat(p: immersive ? arrival : 1, from: 0.15, to: 0.5, dy: 6))\n        .background(Color.clear.frame(width: 60, height: 30).offset(y: 30).censusFrame(\"band\", \"\", when: %s[\"M5_BANDMOVE\"] != nil), alignment: .topLeading)\n        .censusFrame(\"band\", \"\", when: %s[\"M5_BANDMOVE\"] == nil)" % (E, E))
edit("Sources/Snapshot.swift", "                UserDefaults.pinThemeOverride(Theme.mode)\n                content = AnyView(RootView()", "                UserDefaults.pinThemeOverride(%s[\"M5_NIGHTREVERT\"] != nil ? (Theme.mode == .dark ? .light : .dark) : Theme.mode)\n                content = AnyView(RootView()" % E)
print("mutants in")
P
if [ -n "$HM_TRAP_TEST" ]; then for i in {1..300}; do echo "mutated $i"; sleep 0.01; done; exit 0; fi   # head_mutants_trap_test.sh: the sources are mutated here
zsh build.sh --variant internal > $M/build.log 2>&1 || { echo "head_mutants: the mutants' build FAILED (see $M/build.log): stopping, no mutant can be judged on a stale binary"; tail -5 $M/build.log; exit 5; }
echo "MUTANT_BUILD_RC=0"
git checkout -q -- Sources/Views/RegistryVerdictSheet.swift Sources/Snapshot.swift 2>/dev/null
shot() { local out=$1; shift; mkdir -p ${out:h}; "$BIN" --snapshot-band "$@" --layout-json ${out%.png}.json $out 2>/dev/null || echo "RENDER FAIL $out"; }
WRONG=()
for MUT in none $NAMES; do
  D=$M/$MUT; unset M5_SQUASH M5_OVERLAP M5_NOCAP M5_GLYPH M5_HOSTOFF M5_NOGLYPH M5_SRCOPEN M5_NORULE M5_STACK M5_PLATEFIRST M5_COMPACTEXP M5_BANDMOVE M5_PLATE201 M5_NIGHTREVERT M5_NIGHTREVERT
  case $MUT in
    squash) export M5_SQUASH=1 ;; overlap) export M5_OVERLAP=1 ;; nocap) export M5_NOCAP=1 ;; glyph) export M5_GLYPH=1 ;; hostoff) export M5_HOSTOFF=1 ;; noglyph) export M5_NOGLYPH=1 ;; srcopen) export M5_SRCOPEN=1 ;; norule) export M5_NORULE=1 ;; stack) export M5_STACK=1 ;; platefirst) export M5_PLATEFIRST=1 ;; compactexp) export M5_COMPACTEXP=1 M5_NOGLYPH=1 ;; bandmove) export M5_BANDMOVE=1 ;; plate201) export M5_PLATE201=1 ;; nightrevert) export M5_NIGHTREVERT=1 ;;
    none) ;; *) echo "head_mutants: no mutation for '$MUT' in this script"; exit 7 ;;
  esac
  shot $D/imm/sheet-open-56101-day-en.png registry-sheet --imm --sheet-open --theme day --lang en --code 56101 --height 3200
  shot $D/imm/sheet-head-87202-day-id.png registry-sheet --imm --sheet-open --theme day --lang id --code 87202 --height 3600
  shot $D/live/min-collapsed-87202-day-id.png live-sheet --theme day --lang id --code 87202 --width 1040 --height 700
  shot $D/live/root-collapsed-56306-day-en-648.png root-sheet --theme day --lang en --code 56306 --width 1040 --height 648
  shot $D/live/root-collapsed-55203-night-en-648.png root-sheet --theme night --lang en --code 55203 --width 1040 --height 648   # N1: the harness pins the theme a user's toggle sets (nightrevert pins the other one)
  unset M5_SQUASH M5_OVERLAP M5_NOCAP M5_GLYPH M5_HOSTOFF M5_NOGLYPH M5_SRCOPEN M5_NORULE M5_STACK M5_PLATEFIRST M5_COMPACTEXP M5_BANDMOVE M5_PLATE201 M5_NIGHTREVERT M5_NIGHTREVERT
  python3 Tools/design/png_census.py $D --require C26,C27,N1 > $D.log 2>&1; rc=$?; echo "== mutant $MUT: census rc=$rc ($(tail -1 $D.log))"
  want=1; [ $MUT = none ] && want=0; [ $rc = $want ] || WRONG+=("$MUT(rc $rc, want $want)")
  grep -E "C26|C27|N1" $D.log | grep -v "self-test" | cut -c1-260 | head -2
done
echo mutdone > $M/done
[ ${#WRONG} = 0 ] || { echo "head_mutants: WRONG verdicts: ${WRONG[*]}"; exit 1; }
echo "head_mutants: the control passes and all ${#NAMES} mutants FAIL"
