#!/bin/zsh
# render_set.sh [band …] — the design loop's snapshot set (spec §7), from the app root, INTERNAL build.
# 6 bands × day/night × en/id at 1280 pt, plus narrow/ (948 pt, day-en) and xxl/ (registry-table).
# OUT may be overridden (the before-set used OUT=…-before and the first loop only). Exit 1 on any failed render.
cd "${0:A:h}/../.." || exit 2
BIN="build/KBLI Navigator - INTERNAL.app/Contents/MacOS/KBLINavigator"; OUT="${OUT:-docs/design/baseline-$(date +%F)}"
typeset -A CODE=(search-results 55203 registry-table 55203 detail-card 55203 dossier 51101 sheet-ledger 56101 chat 51101)
mkdir -p "$OUT/narrow" "$OUT/xxl"; fails=0
shot() { "$BIN" --snapshot-band "$@" 2>/dev/null || { fails=$((fails+1)); echo "FAIL $*"; } }
for b in ${=1:-search-results registry-table detail-card dossier sheet-ledger chat}; do
  for t in day night; do for l in en id; do
    shot $b --theme $t --lang $l --code ${CODE[$b]} "$OUT/$b-$t-$l.png"; done; done
  shot $b --theme day --lang en --code ${CODE[$b]} --width 948 "$OUT/narrow/$b-day-en.png"
done
shot registry-table --theme day --lang en --code 55203 --text-size xxxLarge "$OUT/xxl/registry-table-day-en.png"
echo "render_set: $(find "$OUT" -name '*.png' | wc -l | tr -d ' ') PNGs in $OUT, $fails failed"
exit $(( fails > 0 ))
