#!/bin/zsh
# render_set.sh [band …] — the design loop's snapshot set (spec §7), from the app root, INTERNAL build.
# 6 bands × day/night × en/id at 1280 pt, plus narrow/ (948 pt, day-en), xxl/ (registry-table) and tall/
# (the ledger's risk chips below the fold: 56101's cellDetail, 71109's 29 scope rows; day and night), and the two
# bands spec D6/D14 add: search-results-multi (query 552, three results or more) and registry-table at 51101 (sector
# H, 2400 pt tall so its rows reach division 51), day-en/id. Each PNG gets its census frames beside it (<name>.json, `--layout-json`) for png_census's C-checks.
# CENSUS_IDENTITY=1 renders each band again without the collector and fails on any byte that differs.
# OUT may be overridden (the before-set used OUT=…-before and the first loop only). Exit 1 on any failed render.
cd "${0:A:h}/../.." || exit 2
BIN="build/KBLI Navigator - INTERNAL.app/Contents/MacOS/KBLINavigator"; OUT="${OUT:-docs/design/baseline-$(date +%F)}"
typeset -A CODE=(search-results 55203 registry-table 55203 detail-card 55203 dossier 51101 sheet-ledger 56101 chat 51101)
mkdir -p "$OUT/narrow" "$OUT/xxl" "$OUT/tall"; fails=0 same=0
shot() { "$BIN" --snapshot-band "${@[1,-2]}" --layout-json "${@[-1]%.png}.json" "${@[-1]}" 2>/dev/null \
  || { fails=$((fails+1)); echo "FAIL $*"; return; }
  [[ -n $CENSUS_IDENTITY ]] || return 0   # the same band without the collector: the marks must draw nothing
  "$BIN" --snapshot-band "${@[1,-2]}" "${@[-1]%.png}.plain.png" 2>/dev/null && cmp -s "${@[-1]}" "${@[-1]%.png}.plain.png" \
    && same=$((same+1)) || { fails=$((fails+1)); echo "DIFF with and without the census collector: ${@[-1]}"; }
  rm -f "${@[-1]%.png}.plain.png"; }
for b in ${=1:-search-results registry-table detail-card dossier sheet-ledger chat}; do
  for t in day night; do for l in en id; do
    shot $b --theme $t --lang $l --code ${CODE[$b]} "$OUT/$b-$t-$l.png"; done; done
  shot $b --theme day --lang en --code ${CODE[$b]} --width 948 "$OUT/narrow/$b-day-en.png"
done
shot registry-table --theme day --lang en --code 55203 --text-size xxxLarge "$OUT/xxl/registry-table-day-en.png"
for t in day night; do
  shot sheet-ledger --theme $t --lang en --code 56101 --height 2800 "$OUT/tall/sheet-ledger-56101-$t-en.png"
  shot sheet-ledger --theme $t --lang en --code 71109 --height 3600 "$OUT/tall/sheet-ledger-71109-$t-en.png"; done
# The expanded live sheet (RegistryVerdictSheet with its dossier open), what the user reads: a ring on the shown risk cell and the hint.
for c in 56101 55203 19201; do for t in day night; do for l in en id; do
  shot registry-sheet --sheet-open --theme $t --lang $l --code $c --height 2600 "$OUT/tall/registry-sheet-open-$c-$t-$l.png"; done; done; done
for l in en id; do
  shot search-results-multi --theme day --lang $l --code 552 "$OUT/search-results-multi-day-$l.png"
  shot registry-table --theme day --lang $l --code 51101 --height 2400 "$OUT/tall/registry-table-51101-day-$l.png"; done
# The immersive set (IMM): what the user sees, a first-class set beside the flat baseline. IMM=1 adds it under $OUT/imm/.
if [ -n "${IMM:-}" ]; then
  mkdir -p "$OUT/imm/narrow" "$OUT/live"
  typeset -A IMMCODE=(detail-card 55203 sheet-ledger 56101 chat 51101 registry-sheet 56101)
  for b in detail-card sheet-ledger chat registry-sheet; do
    for t in day night; do for l in en id; do
      shot $b --imm --theme $t --lang $l --code ${IMMCODE[$b]} "$OUT/imm/$b-$t-$l.png"; done; done
    shot $b --imm --theme day --lang en --code ${IMMCODE[$b]} --width 948 "$OUT/imm/narrow/$b-day-en.png"
  done
  # The expanded live sheet, immersive: what the user sees (scale path as the matrix, ring, hint). 71109 has 29 scopes.
  for c in 56101 55203 71109 19201; do for t in day night; do for l in en id; do
    shot registry-sheet --imm --sheet-open --theme $t --lang $l --code $c --height 3200 "$OUT/imm/sheet-open-$c-$t-$l.png"; done; done; done
  # The sheet as the app mounts it (SearchListView.sheetLayer): C25 reads it against the flat twin (tall/) and this set's immersive one.
  for c in 56101 55203; do for t in day night; do
    shot live-sheet --sheet-open --theme $t --lang en --code $c --height 2600 "$OUT/live/sheet-open-$c-$t-en.png"; done; done
  # The longest titles of the dataset (87202 in Indonesian, 199 characters, no scale rows; 77520 and 47192 in English, with a matrix): the head's
  # title wraps to 2-5 lines and never squashes the plate (C26). The two with a matrix are `sheet-open` renders, so C24 judges them too, on a canvas
  # tall enough for the detail (77520's reaches y 3618 pt in Indonesian: a 3600 pt canvas cut it, and C24 could not see it).
  for c in 77520 47192; do for t in day night; do for l in en id; do
    shot registry-sheet --imm --sheet-open --theme $t --lang $l --code $c --height 4200 "$OUT/imm/sheet-open-$c-$t-$l.png"; done; done; done
  for t in day night; do for l in en id; do
    shot registry-sheet --imm --sheet-open --theme $t --lang $l --code 87202 --height 3600 "$OUT/imm/sheet-head-87202-$t-$l.png"; done; done
  # Stacked cells open on the shown cell next to a neighbour chip: High at night, Medium-High by day (the ring must clear it).
  shot registry-sheet --imm --sheet-open --theme night --lang en --code 85510 --height 2600 "$OUT/imm/sheet-open-85510-night-en.png"
  shot registry-sheet --imm --sheet-open --theme day --lang en --code 20111 --height 4000 "$OUT/imm/sheet-open-20111-day-en.png"
  # Medium-Low at night, stacked (#8288 gate): the ring's census (C24) must see it clear of the chip beside it.
  # A row that spans several scales (43110's first row: Micro, Small, Medium) draws one chip per scale and rings each: C24 counts chips.
  shot registry-sheet --imm --sheet-open --theme night --lang en --code 43110 --scope 0 --scale-focus Mikro --height 4000 "$OUT/imm/sheet-open-43110-night-en.png"
  for c in 03300 32300; do shot registry-sheet --imm --sheet-open --theme night --lang en --code $c --height 4000 "$OUT/imm/sheet-open-$c-night-en.png"; done
fi
[[ -n $CENSUS_IDENTITY ]] && echo "census collector: $same PNGs byte-identical with and without it"
echo "render_set: $(find "$OUT" -name '*.png' | wc -l | tr -d ' ') PNGs in $OUT, $fails failed"
exit $(( fails > 0 ))
