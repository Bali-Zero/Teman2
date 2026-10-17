#!/bin/zsh
# no_focus_check.sh [app-bundle]: a harness run never shows a Dock icon and never takes focus (owner, 2026-10-17: the census stole the focus once per band).
# Runs the built binary in each harness mode (one --snapshot-band, one --snapshot-band root-sheet, a --fold-census on 2 codes collapsed and --open) and, every
# ~50 ms while it runs, asks Launch Services (lsappinfo) for the frontmost application and for the harness' own application type.
# FAIL if the harness is ever frontmost, or its type is Foreground (a Dock app: the activation policy is .regular) other than in the opening polls before
# KBLINavigatorApp.init sets the policy (a run that never leaves Foreground FAILs). PASS otherwise.
# A locked screen leaves loginwindow frontmost, so "never frontmost" alone proves nothing there: the type check is the one that holds on a locked Pro.
# Guilt: the binary of a head before the fix FAILs. Run it on a machine you may disturb: a guilty binary DOES take the focus, once, for the run.
cd "${0:A:h}/../.." || exit 2
APP=${1:-"build/KBLI Navigator - INTERNAL.app"}; BIN="$APP/Contents/MacOS/KBLINavigator"
[ -x "$BIN" ] || { echo "no_focus_check: no binary at $BIN"; exit 2; }
export KBLI_BOOK_PDF_DIR=${KBLI_BOOK_PDF_DIR:-~/.local/share/nuzantara/kbli-navigator/book-pdfs}
T=$(mktemp -d "${TMPDIR:-/tmp}/no-focus.XXXXXX"); trap 'rm -rf -- "$T"' EXIT
bad=0 ran=0
watch_run() { # <label> <command...>: runs it in the background and polls until it ends
  local label=$1; shift
  "$@" > $T/out.log 2>&1 &
  local pid=$! polls=0 front=0 fg=0 seen=0 lead=0 settled=0 t="" asn fpid
  while kill -0 $pid 2>/dev/null; do
    polls=$((polls+1))
    asn=$(lsappinfo find pid=$pid 2>/dev/null)
    if [ -n "$asn" ]; then
      seen=$((seen+1))
      t=$(lsappinfo info "$asn" 2>/dev/null | sed -n 's/.* type="\([^"]*\)".*/\1/p' | head -1)
      # Launch Services lists a process as Foreground until KBLINavigatorApp.init runs (Info.plist cannot say "harness"): that opening prefix is
      # tolerated and counted apart. Foreground AFTER the type has once been something else, or still Foreground when the run ends, is a FAIL.
      if [ "$t" = Foreground ]; then if [ $settled -eq 0 ]; then lead=$((lead+1)); else fg=$((fg+1)); fi; else settled=1; fi
    fi
    fpid=$(lsappinfo info "$(lsappinfo front 2>/dev/null)" 2>/dev/null | sed -n 's/.*pid = \([0-9]*\).*/\1/p' | head -1)
    [ "$fpid" = "$pid" ] && front=$((front+1))
    sleep 0.05
  done
  wait $pid; local rc=$?
  [ $settled -eq 0 ] && [ $lead -gt 0 ] && fg=$((fg+lead))   # never left Foreground
  ran=$((ran+1))
  local verdict=ok; { [ $front -gt 0 ] || [ $fg -gt 0 ]; } && { verdict=FAIL; bad=$((bad+1)); }
  echo "$verdict $label: rc=$rc polls=$polls seen-by-LaunchServices=$seen frontmost=$front type-Foreground=$fg (opening prefix $lead)"
  [ $rc -eq 0 ] || { verdict=FAIL; bad=$((bad+1)); echo "FAIL $label: the harness exited $rc"; tail -3 $T/out.log; }
}
watch_run "snapshot-band sheet-ledger" "$BIN" --snapshot-band sheet-ledger --theme day --lang en --code 56101 $T/a.png
watch_run "snapshot-band root-sheet (the NSWindow host)" "$BIN" --snapshot-band root-sheet --theme day --lang en --code 56101 --width 1040 --height 700 $T/b.png
watch_run "fold-census collapsed" "$BIN" --fold-census $T/c.jsonl --codes 56101,56306 --sizes 1040x700 --lang en
watch_run "fold-census --open" "$BIN" --fold-census $T/o.jsonl --open --codes 56101,56306 --sizes 1040x700 --lang en
n=$(cat $T/c.jsonl $T/o.jsonl 2>/dev/null | wc -l | tr -d ' ')
[ "$n" = 4 ] || { bad=$((bad+1)); echo "FAIL fold-census wrote $n rows, not 4"; }
if [ $bad -eq 0 ]; then echo "no_focus_check: PASS ($ran harness runs, never frontmost, never a Dock app)"; exit 0; fi
echo "no_focus_check: FAIL ($bad)"; exit 1
