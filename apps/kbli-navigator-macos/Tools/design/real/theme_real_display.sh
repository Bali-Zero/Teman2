#!/bin/zsh
# theme_real_display.sh APP [N=5] — the app never paints a mixed theme on a REAL display (M5, interactive session).
# The offscreen host (theme_flip_check.py) sees the runtime flip but NOT the launch order: a window that is built in the wrong mode and
# flipped by RootView's first-render sync paints correctly offscreen. So the launch is judged here, on a real launch:
#   launch: the saved override {light, system} (system appearance light: the global appearance is never changed), N launches each;
#   toggle: launch dark and click the toolbar toggle (night -> day), launch light and click it (day -> night).
# Pixel probe per shot: the sheet's title ink vs the sheet fill >= 4.5:1, the selected row's Bali chip against its mode, the sheet fill's mode.
# Prints the defect count per cell; exit 1 on any defect. Backs up and restores the app's preferences. Closes every instance it opens.
# Guilt/innocence: run it on 87e438b7b3 (fails) and on the fix (passes); the PR body carries both runs.
APP="$1"; N="${2:-5}"
HERE="${0:A:h}"; DOM=com.balizero.kbli-navigator.internal; T=$(mktemp -d)
BAK="$T/prefs.plist"; defaults export $DOM "$BAK" 2>/dev/null
restore() { defaults delete $DOM themeOverride 2>/dev/null; defaults delete $DOM AppleInterfaceStyle 2>/dev/null
  [[ -s "$BAK" ]] && defaults import $DOM "$BAK"; rm -rf "$T"; }
trap restore EXIT
swiftc -O "$HERE/winid.swift" -o "$T/winid" && swiftc -O "$HERE/clickwin.swift" -o "$T/clickwin" || exit 2
bin="$APP/Contents/MacOS/KBLINavigator"
probe() { python3 - "$1" "$2" <<'P'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB"); want = sys.argv[2]; W, H = im.size
def lum(p):
    f = lambda c: (c/255)/12.92 if c/255 <= 0.03928 else ((c/255+0.055)/1.055)**2.4
    return 0.2126*f(p[0])+0.7152*f(p[1])+0.0722*f(p[2])
def cr(a, b):
    hi, lo = max(lum(a), lum(b)), min(lum(a), lum(b)); return (hi+0.05)/(lo+0.05)
def box(x0, x1, y0, y1): return [im.getpixel((x, y)) for x in range(int(x0*W), int(x1*W), 2) for y in range(int(y0*H), int(y1*H), 2)]
t = box(.19, .35, .61, .655); fill = max(set(t), key=t.count); title = max(cr(fill, p) for p in t)
chip = im.getpixel((int(.775*W), int(.355*H)))
night = lum(fill) < 0.1
chipnight = chip[1] < 120
bad = []
if title < 4.5: bad.append("title %.1f:1" % title)
if (want == "night") != night: bad.append("sheet is %s" % ("night" if night else "day"))
if (want == "night") != chipnight: bad.append("chip is %s" % ("night" if chipnight else "day"))
print("DEFECT " + ", ".join(bad) if bad else "ok"); sys.exit(1 if bad else 0)
P
}
launch() { open -n "$APP"; sleep 1; PID=$(pgrep -n -f "$bin"); sleep 4; }
shot() { WID=$("$T/winid" $PID) && screencapture -x -o -l $WID "$1"; }
quit() { kill $PID 2>/dev/null; sleep 1; pgrep -f "$bin" >/dev/null && kill -9 $(pgrep -f "$bin"); sleep .5; }
defects=0
cell() { echo "$1: $2 of $N launches defective"; defects=$((defects + $2)); }
for ov in light system; do
  d=0; defaults delete $DOM AppleInterfaceStyle 2>/dev/null
  [[ $ov == system ]] && defaults delete $DOM themeOverride 2>/dev/null || defaults write $DOM themeOverride -string $ov
  for i in $(seq 1 $N); do launch; shot "$T/l.png"; quit; probe "$T/l.png" day >/dev/null || d=$((d+1)); done
  cell "launch override=$ov system=light" $d
done
for pair in "dark night day" "light day night"; do
  set -- ${=pair}; defaults write $DOM themeOverride -string $1; d=0
  for i in $(seq 1 $N); do launch; shot "$T/a.png"; probe "$T/a.png" $2 >/dev/null || d=$((d+1))
    "$T/clickwin" $PID 27 26 >/dev/null; sleep 2.5; shot "$T/b.png"; quit; probe "$T/b.png" $3 >/dev/null || d=$((d+1)); done
  cell "toggle $1: $2 -> $3 (before + after, $((2*N)) shots)" $d
done
echo "theme_real_display: $defects defective shot(s)"; exit $(( defects > 0 ))
